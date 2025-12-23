"""
API Views for Job Roles and Permissions models.
Provides REST API endpoints for managing role-based access control.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q

from erp_project.pagination import auto_paginate

from .models import (
    JobRole,
    Page,
    Action,
    PageAction,
    JobRolePage,
    UserActionDenial,
)
from .serializers import (
    JobRoleSerializer,
    JobRoleListSerializer,
    JobRoleWithPagesSerializer,
    PageSerializer,
    PageListSerializer,
    ActionSerializer,
    PageActionSerializer,
    JobRolePageSerializer,
    UserActionDenialSerializer,
    UserActionDenialCreateSerializer,
)
from core.user_accounts.models import CustomUser


# ============================================================================
# JobRole API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def job_role_list(request):
    """
    List all job roles or create a new job role.
    
    GET /job-roles/
    - Returns list of all job roles
    - Query params:
        - name: Filter by name (case-insensitive contains)
        - search: Search across name and description
    
    POST /job-roles/
    - Create a new job role
    - Request body: JobRoleSerializer fields
    """
    if request.method == 'GET':
        job_roles = JobRole.objects.prefetch_related('job_role_pages__page').all()
        
        # Apply filters
        name = request.query_params.get('name')
        if name:
            job_roles = job_roles.filter(name__icontains=name)
        
        search = request.query_params.get('search')
        if search:
            job_roles = job_roles.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        serializer = JobRoleListSerializer(job_roles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # Support both single-object and bulk (list) creates
        data = request.data
        is_list = isinstance(data, list)
        serializer = JobRoleSerializer(data=data, many=is_list)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def job_role_detail(request, pk):
    """
    Retrieve, update, or delete a specific job role.
    
    GET /job-roles/{id}/
    - Returns detailed information about a job role including pages
    
    PUT/PATCH /job-roles/{id}/
    - Update a job role
    - Request body: JobRoleSerializer fields
    
    DELETE /job-roles/{id}/
    - Delete a job role (if not assigned to users)
    """
    job_role = get_object_or_404(
        JobRole.objects.prefetch_related('job_role_pages__page'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = JobRoleSerializer(job_role)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = JobRoleSerializer(job_role, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            job_role.delete()
            return Response(
                {'message': 'Job role deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def job_role_assign_page(request, pk):
    """
    Assign a page to a job role.
    
    POST /job-roles/{id}/assign-page/
    - Request body: { "page_id": 1 } or { "page_name": "invoice_page" }
    - Returns: JobRolePage details
    """
    job_role = get_object_or_404(JobRole, pk=pk)
    page_id = request.data.get('page_id')
    page_name = request.data.get('page_name')
    
    if not page_id and not page_name:
        return Response(
            {'error': 'Either page_id or page_name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if page_name:
            page = Page.objects.get(name=page_name)
        else:
            page = Page.objects.get(id=page_id)
    except Page.DoesNotExist:
        identifier = page_name if page_name else f'id {page_id}'
        return Response(
            {'error': f'Page with {identifier} does not exist'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Create or get the job role page assignment
    job_role_page, created = JobRolePage.objects.get_or_create(
        job_role=job_role,
        page=page
    )
    
    serializer = JobRolePageSerializer(job_role_page)
    return Response(
        {
            'message': 'Page assigned successfully' if created else 'Page already assigned',
            'data': serializer.data
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['POST'])
def job_role_remove_page(request, pk):
    """
    Remove one or more pages from a job role.
    
    POST /job-roles/{id}/remove-page/
    - Request body: { "page_ids": [1, 2, 3] } or { "page_names": ["invoice_page", "hr_page"] } for bulk removal
    - OR: { "page_id": 1 } or { "page_name": "invoice_page" } for single removal
    - Returns: Summary of removed pages and any not found
    """
    job_role = get_object_or_404(JobRole, pk=pk)
    
    # Support both IDs and names for backward compatibility
    page_ids = request.data.get('page_ids')
    page_id = request.data.get('page_id')
    page_names = request.data.get('page_names')
    page_name = request.data.get('page_name')
    
    if not any([page_ids, page_id, page_names, page_name]):
        return Response(
            {'error': 'Either page_ids, page_id, page_names, or page_name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Normalize to list of IDs
    ids_to_remove = []
    provided_names = []
    
    if page_names is not None:
        if not isinstance(page_names, list):
            return Response(
                {'error': 'page_names must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Convert names to IDs
        provided_names = page_names
        pages = Page.objects.filter(name__in=page_names)
        ids_to_remove = list(pages.values_list('id', flat=True))
        
        # Check if all names were found
        found_names = set(pages.values_list('name', flat=True))
        missing_names = set(page_names) - found_names
        if missing_names:
            return Response(
                {'error': f'Pages with names {list(missing_names)} do not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
    elif page_name:
        try:
            page = Page.objects.get(name=page_name)
            ids_to_remove = [page.id]
        except Page.DoesNotExist:
            return Response(
                {'error': f'Page with name {page_name} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
    elif page_ids is not None:
        if not isinstance(page_ids, list):
            return Response(
                {'error': 'page_ids must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        ids_to_remove = page_ids
    else:
        ids_to_remove = [page_id]
    
    if not ids_to_remove:
        return Response(
            {'error': 'No valid pages found to remove'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find and delete all matching JobRolePage entries
    job_role_pages = JobRolePage.objects.filter(
        job_role=job_role,
        page_id__in=ids_to_remove
    )
    
    found_page_ids = set(job_role_pages.values_list('page_id', flat=True))
    not_found_page_ids = [pid for pid in ids_to_remove if pid not in found_page_ids]
    
    deleted_count = job_role_pages.count()
    job_role_pages.delete()
    
    # Build response message
    if deleted_count == 0:
        return Response(
            {
                'error': 'No page assignments found',
                'not_found_page_ids': not_found_page_ids
            },
            status=status.HTTP_404_NOT_FOUND
        )
    
    response_data = {
        'message': f'{deleted_count} page(s) removed successfully',
        'removed_count': deleted_count,
        'removed_page_ids': list(found_page_ids)
    }
    
    if not_found_page_ids:
        response_data['not_found_page_ids'] = not_found_page_ids
        response_data['message'] += f' ({len(not_found_page_ids)} not found)'
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_job_role(request):
    """
    Assign a job role to a user.
    
    POST /job-roles/assign/
    - Request body (by user_id and job_role_id): 
        {"user_id": 1, "job_role_id": 2}
    - Request body (by email and job_role_name): 
        {"user_email": "user@example.com", "job_role_name": "Accountant"}
    - Returns: User details with assigned role
    - Permission: Only admins can assign roles
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Check admin permission
    try:
        is_authorized = request.user.is_admin()
    except (AttributeError, TypeError):
        is_authorized = False
    
    if not is_authorized:
        return Response(
            {'error': 'Permission denied. Only admins can assign job roles.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get job role (support both ID and name)
    job_role_id = request.data.get('job_role_id') or request.data.get('role_id')
    job_role_name = request.data.get('job_role_name') or request.data.get('role_name')
    
    if not job_role_id and not job_role_name:
        return Response(
            {'error': 'Either job_role_id or job_role_name is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find job role
    try:
        if job_role_name:
            job_role = JobRole.objects.get(name=job_role_name)
        else:
            job_role = JobRole.objects.get(pk=job_role_id)
    except JobRole.DoesNotExist:
        identifier = job_role_name if job_role_name else f'id {job_role_id}'
        return Response(
            {'error': f'Job role with {identifier} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Handle both email and user_id
    email = request.data.get('user_email') or request.data.get('email')
    user_id = request.data.get('user_id')
    
    if not email and not user_id:
        return Response(
            {'error': 'Either user_id or user_email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find user
    try:
        if email:
            user = User.objects.get(email=email)
        else:
            user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        identifier = email if email else f'id {user_id}'
        return Response(
            {'error': f'User with {identifier} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Assign and save
    user.job_role = job_role
    user.save()
    
    return Response({
        'message': 'Job role assigned successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'job_role': {
                'id': job_role.id,
                'name': job_role.name
            }
        }
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def job_role_create_with_pages(request):
    """
    Create a job role and assign pages to it in one atomic operation.
    
    POST /job-roles/with-pages/
    - Request body (using page IDs): {
        "name": "Manager",
        "description": "Manager role with specific page access",
        "page_ids": [1, 2, 3]
      }
    - Request body (using page names): {
        "name": "Manager",
        "description": "Manager role with specific page access",
        "page_names": ["invoice_page", "reports_page"]
      }
    - page_ids/page_names are optional - if omitted, creates job role with no pages
    - All page_ids/page_names must exist or the entire operation fails (atomic)
    - Returns: Created job role with assigned pages
    """
    serializer = JobRoleWithPagesSerializer(data=request.data)
    if serializer.is_valid():
        try:
            job_role = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Page API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def page_list(request):
    """
    List all pages or create a new page.
    
    GET /pages/
    - Returns list of all pages
    - Query params:
        - name: Filter by name (case-insensitive contains)
        - search: Search across name, display_name, and description
    
    POST /pages/
    - Create a new page
    - Request body: PageSerializer fields
    """
    if request.method == 'GET':
        pages = Page.objects.prefetch_related('page_actions__action').all()
        
        # Apply filters
        name = request.query_params.get('name')
        if name:
            pages = pages.filter(name__icontains=name)
        
        search = request.query_params.get('search')
        if search:
            pages = pages.filter(
                Q(name__icontains=search) |
                Q(display_name__icontains=search) |
                Q(description__icontains=search)
            )
        
        serializer = PageListSerializer(pages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = PageSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def page_detail(request, pk):
    """
    Retrieve, update, or delete a specific page.
    
    GET /pages/{id}/
    - Returns detailed information about a page including available actions
    
    PUT/PATCH /pages/{id}/
    - Update a page
    - Request body: PageSerializer fields
    
    DELETE /pages/{id}/
    - Delete a page (if not linked to job roles)
    """
    page = get_object_or_404(
        Page.objects.prefetch_related('page_actions__action'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = PageSerializer(page)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = PageSerializer(page, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            page.delete()
            return Response(
                {'message': 'Page deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def page_assign_action(request, pk):
    """
    Assign an action to a page.
    
    POST /pages/{id}/assign-action/
    - Request body: { "action_id": 1 } or { "action_name": "view" }
    - Returns: PageAction details
    """
    page = get_object_or_404(Page, pk=pk)
    action_id = request.data.get('action_id')
    action_name = request.data.get('action_name')
    
    if not action_id and not action_name:
        return Response(
            {'error': 'Either action_id or action_name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if action_name:
            action = Action.objects.get(name=action_name)
        else:
            action = Action.objects.get(id=action_id)
    except Action.DoesNotExist:
        identifier = action_name if action_name else f'id {action_id}'
        return Response(
            {'error': f'Action with {identifier} does not exist'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Create or get the page action
    page_action, created = PageAction.objects.get_or_create(
        page=page,
        action=action
    )
    
    serializer = PageActionSerializer(page_action)
    return Response(
        {
            'message': 'Action assigned successfully' if created else 'Action already assigned',
            'data': serializer.data
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['POST'])
def page_remove_action(request, pk):
    """
    Remove an action from a page.
    
    POST /pages/{id}/remove-action/
    - Request body: { "action_id": 1 } or { "action_name": "view" }
    - Returns: Success message
    """
    page = get_object_or_404(Page, pk=pk)
    action_id = request.data.get('action_id')
    action_name = request.data.get('action_name')
    
    if not action_id and not action_name:
        return Response(
            {'error': 'Either action_id or action_name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if action_name:
            page_action = PageAction.objects.get(
                page=page,
                action__name=action_name
            )
        else:
            page_action = PageAction.objects.get(
                page=page,
                action_id=action_id
            )
        page_action.delete()
        return Response(
            {'message': 'Action removed successfully'},
            status=status.HTTP_200_OK
        )
    except PageAction.DoesNotExist:
        identifier = action_name if action_name else f'id {action_id}'
        return Response(
            {'error': f'Action assignment with {identifier} not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# ============================================================================
# Action API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def action_list(request):
    """
    List all actions or create a new action.
    
    GET /actions/
    - Returns list of all actions
    - Query params:
        - name: Filter by name (case-insensitive contains)
        - search: Search across name, display_name, and description
    
    POST /actions/
    - Create a new action
    - Request body: ActionSerializer fields
    """
    if request.method == 'GET':
        actions = Action.objects.all()
        
        # Apply filters
        name = request.query_params.get('name')
        if name:
            actions = actions.filter(name__icontains=name)
        
        search = request.query_params.get('search')
        if search:
            actions = actions.filter(
                Q(name__icontains=search) |
                Q(display_name__icontains=search) |
                Q(description__icontains=search)
            )
        
        serializer = ActionSerializer(actions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = ActionSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def action_detail(request, pk):
    """
    Retrieve, update, or delete a specific action.
    
    GET /actions/{id}/
    - Returns detailed information about an action
    
    PUT/PATCH /actions/{id}/
    - Update an action
    - Request body: ActionSerializer fields
    
    DELETE /actions/{id}/
    - Delete an action (if not linked to pages)
    """
    action = get_object_or_404(Action, pk=pk)
    
    if request.method == 'GET':
        serializer = ActionSerializer(action)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = ActionSerializer(action, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            action.delete()
            return Response(
                {'message': 'Action deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# PageAction API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def page_action_list(request):
    """
    List all page-action relationships or create a new one.
    
    GET /page-actions/
    - Returns list of all page-action relationships
    - Query params:
        - page_id: Filter by page ID (use this instead of `page` to avoid colliding with pagination)
        - action_id: Filter by action ID (use this instead of `action` to avoid ambiguity)
    
    POST /page-actions/
    - Create a new page-action relationship
    - Request body (using IDs): { "page": 1, "action_id": 2 }
    - Request body (using names): { "page": 1, "action_name": "view" }
    """
    if request.method == 'GET':
        page_actions = PageAction.objects.select_related('page', 'action').all()
        
        # Apply filters. Use `page_id` and `action_id` query params so they don't
        # conflict with the pagination query param `page` which is reserved for
        # page numbers (and will raise "Invalid page." if out of range).
        page_id = request.query_params.get('page_id') or request.query_params.get('page')
        if page_id:
            page_actions = page_actions.filter(page_id=page_id)

        action_id = request.query_params.get('action_id')
        if action_id:
            page_actions = page_actions.filter(action_id=action_id)
        
        serializer = PageActionSerializer(page_actions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = PageActionSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def page_action_detail(request, pk):
    """
    Retrieve, update, or delete a specific page-action relationship.
    
    GET /page-actions/{id}/
    - Returns detailed information about a page-action relationship
    
    PUT/PATCH /page-actions/{id}/
    - Update a page-action relationship
    - Request body: PageActionSerializer fields
    
    DELETE /page-actions/{id}/
    - Delete a page-action relationship (if no user denials)
    """
    page_action = get_object_or_404(
        PageAction.objects.select_related('page', 'action'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = PageActionSerializer(page_action)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = PageActionSerializer(page_action, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            page_action.delete()
            return Response(
                {'message': 'Page action deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# UserActionDenial API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def user_action_denial_list(request):
    """
    List all user action denials or create a new one.
    
    GET /user-action-denials/
    - Returns list of all user action denials
    - Query params:
        - user: Filter by user ID
        - page: Filter by page ID
        - action: Filter by action ID
    
    POST /user-action-denials/
    - Create a new user action denial
    - Request body (using IDs): { "user": 1, "page_action": 2 }
    - Request body (using names/email): { 
        "user_email": "user@example.com", 
        "page_name": "invoice_page", 
        "action_name": "delete" 
      }
    """
    if request.method == 'GET':
        denials = UserActionDenial.objects.select_related(
            'user', 'page_action__page', 'page_action__action'
        ).all()
        
        # Apply filters
        user_id = request.query_params.get('user')
        if user_id:
            denials = denials.filter(user_id=user_id)
        
        page_id = request.query_params.get('page')
        if page_id:
            denials = denials.filter(page_action__page_id=page_id)
        
        action_id = request.query_params.get('action')
        if action_id:
            denials = denials.filter(page_action__action_id=action_id)
        
        serializer = UserActionDenialSerializer(denials, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = UserActionDenialCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                denial = serializer.save()
                result_serializer = UserActionDenialSerializer(denial)
                return Response(result_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'DELETE'])
def user_action_denial_detail(request, pk):
    """
    Retrieve or delete a specific user action denial.
    
    GET /user-action-denials/{id}/
    - Returns detailed information about a user action denial
    
    DELETE /user-action-denials/{id}/
    - Delete a user action denial (restore permission)
    """
    denial = get_object_or_404(
        UserActionDenial.objects.select_related(
            'user', 'page_action__page', 'page_action__action'
        ),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = UserActionDenialSerializer(denial)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'DELETE':
        denial.delete()
        return Response(
            {'message': 'User action denial removed successfully'},
            status=status.HTTP_204_NO_CONTENT
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_actions(request, pk):
    """
    GET /users/{id}/actions/ - Return the allowed actions (page_actions)
    for a specific user based on their job role minus any explicit denials.

    Permission: user themselves or super_admin.
    """
    # Fetch target user
    target_user = get_object_or_404(CustomUser, pk=pk)

    # Authorization: allow if requesting user is super_admin or the user themselves
    if not (request.user.is_authenticated and (request.user.is_super_admin() or request.user.pk == target_user.pk)):
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    # If user has no job role, they have no inherited actions
    if not target_user.job_role:
        return Response([], status=status.HTTP_200_OK)

    # Actions available to the user's job role
    # Use an explicit JobRolePage -> PageAction lookup to avoid
    # ambiguous ORM coercion when values aren't strictly model instances.
    page_ids = JobRolePage.objects.filter(job_role=target_user.job_role).values_list('page_id', flat=True)
    available = PageAction.objects.filter(page_id__in=page_ids).select_related('page', 'action').distinct()

    # Exclude any explicit denials for this user
    denied_ids = UserActionDenial.objects.filter(user=target_user).values_list('page_action_id', flat=True)
    if denied_ids:
        available = available.exclude(id__in=denied_ids)

    serializer = PageActionSerializer(available, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

