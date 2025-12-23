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
    - Request body: { "page_id": 1 }
    - Returns: JobRolePage details
    """
    job_role = get_object_or_404(JobRole, pk=pk)
    page_id = request.data.get('page_id')
    
    if not page_id:
        return Response(
            {'error': 'page_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        page = Page.objects.get(id=page_id)
    except Page.DoesNotExist:
        return Response(
            {'error': f'Page with id {page_id} does not exist'},
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
    Remove a page from a job role.
    
    POST /job-roles/{id}/remove-page/
    - Request body: { "page_id": 1 }
    - Returns: Success message
    """
    job_role = get_object_or_404(JobRole, pk=pk)
    page_id = request.data.get('page_id')
    
    if not page_id:
        return Response(
            {'error': 'page_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        job_role_page = JobRolePage.objects.get(
            job_role=job_role,
            page_id=page_id
        )
        job_role_page.delete()
        return Response(
            {'message': 'Page removed successfully'},
            status=status.HTTP_200_OK
        )
    except JobRolePage.DoesNotExist:
        return Response(
            {'error': 'Page assignment not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
def job_role_assign_user(request, pk):
    """
    Assign a user to a job role.

    POST /job-roles/{id}/assign-user/
    - Request body: { "user_id": <int> }
    - Only users with admin privileges can assign roles
    """
    job_role = get_object_or_404(JobRole, pk=pk)

    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    # Import user model dynamically to avoid circular imports
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Permission: only admin users can assign roles
    requesting_user = request.user
    if not getattr(requesting_user, 'is_admin', lambda: False)():
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': f'User with id {user_id} does not exist'}, status=status.HTTP_404_NOT_FOUND)

    # Assign and save
    user.job_role = job_role
    user.save()

    # Minimal user info response
    return Response({
        'message': 'User assigned to job role successfully',
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
    - Request body: {
        "name": "Manager",
        "description": "Manager role with specific page access",
        "page_ids": [1, 2, 3]
      }
    - page_ids is optional - if omitted, creates job role with no pages
    - All page_ids must exist or the entire operation fails (atomic)
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
    - Request body: { "action_id": 1 }
    - Returns: PageAction details
    """
    page = get_object_or_404(Page, pk=pk)
    action_id = request.data.get('action_id')
    
    if not action_id:
        return Response(
            {'error': 'action_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        action = Action.objects.get(id=action_id)
    except Action.DoesNotExist:
        return Response(
            {'error': f'Action with id {action_id} does not exist'},
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
    - Request body: { "action_id": 1 }
    - Returns: Success message
    """
    page = get_object_or_404(Page, pk=pk)
    action_id = request.data.get('action_id')
    
    if not action_id:
        return Response(
            {'error': 'action_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
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
        return Response(
            {'error': 'Action assignment not found'},
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
    - Request body: { "page": 1, "action_id": 2 }
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
    - Request body: { "user": 1, "page_action": 2 }
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
