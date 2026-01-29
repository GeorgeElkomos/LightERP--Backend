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
from .decorators import require_page_action, require_self_or_admin
from .core_config import CorePages

from .models import (
    JobRole,
    Page,
    JobRolePage,
    UserJobRole,
    UserPermissionOverride,
)
from .serializers import (
    JobRoleSerializer,
    PageSerializer,
    UserJobRoleSerializer,
    UserJobRoleCreateSerializer,
    UserPermissionOverrideSerializer,
    UserPermissionOverrideCreateSerializer,
)
from core.user_accounts.models import UserAccount


# ============================================================================
# JobRole API Views
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
@auto_paginate
def job_role_list(request):
    """
    List all job roles or create new job role(s).

    GET /job-roles/
    - Returns list of all job roles
    - Query params:
        - name: Filter by name (case-insensitive contains)
        - search: Search across name and description

    POST /job-roles/
    - Create job role(s) - supports single object or array for bulk creation
    - Request body: JobRoleSerializer fields (single) or array of objects (bulk)
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

        serializer = JobRoleSerializer(job_roles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        # Normalize to list for consistent handling
        data = request.data
        is_list = isinstance(data, list)
        if not is_list:
            data = [data]

        serializer = JobRoleSerializer(data=data, many=True)
        if serializer.is_valid():
            try:
                serializer.save()
                response_data = serializer.data if is_list else serializer.data[0]
                return Response(response_data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
def job_role_detail(request, pk):
    """
    Retrieve, update, or delete a specific job role.

    GET /job-roles/{pk}/
    - Returns detailed information about a job role including pages

    PUT/PATCH /job-roles/{pk}/
    - Update a job role
    - Request body: JobRoleSerializer fields

    DELETE /job-roles/{pk}/
    - Delete a job role
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
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT, 'edit')
def job_role_assign_page(request, pk):
    """
    Assign one or more pages to a job role.

    POST /job-roles/{id}/assign-page/
    - Request body: { "page_code": "hr_employee" } for single
    - OR: { "page_codes": ["hr_employee", "hr_department"] } for bulk
    - Returns: JobRolePage details (requires admin role)
    """
    job_role = get_object_or_404(JobRole, pk=pk)

    # Normalize to list for consistent handling
    page_codes = request.data.get('page_codes')
    page_code = request.data.get('page_code')

    if not page_codes and not page_code:
        return Response(
            {'error': 'Either page_code or page_codes is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Normalize to list
    if page_codes is not None:
        if not isinstance(page_codes, list):
            return Response(
                {'error': 'page_codes must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        codes_to_assign = page_codes
    else:
        codes_to_assign = [page_code]

    # Validate all pages exist
    pages = Page.objects.filter(code__in=codes_to_assign)
    found_codes = set(pages.values_list('code', flat=True))
    missing_codes = set(codes_to_assign) - found_codes

    if missing_codes:
        return Response(
            {'error': f'Pages with codes {list(missing_codes)} do not exist'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Create assignments
    created = []
    already_assigned = []

    for page in pages:
        job_role_page, was_created = JobRolePage.objects.get_or_create(
            job_role=job_role,
            page=page
        )
        if was_created:
            created.append(page.code)
        else:
            already_assigned.append(page.code)

    return Response({
        'message': f'{len(created)} page(s) assigned successfully',
        'created': created,
        'already_assigned': already_assigned
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT, 'edit')
def job_role_remove_page(request, pk):
    """
    Remove one or more pages from a job role.

    POST /job-roles/{id}/remove-page/
    - Request body: { "page_codes": ["hr_employee", "hr_department"] } for bulk removal
    - OR: { "page_code": "hr_employee" } for single removal
    - Returns: Summary of removed pages (requires admin role)
    """
    job_role = get_object_or_404(JobRole, pk=pk)

    page_codes = request.data.get('page_codes')
    page_code = request.data.get('page_code')

    if not any([page_codes, page_code]):
        return Response(
            {'error': 'Either page_codes or page_code is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Normalize to list
    if page_codes is not None:
        if not isinstance(page_codes, list):
            return Response(
                {'error': 'page_codes must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        codes_to_remove = page_codes
    else:
        codes_to_remove = [page_code]

    # Find pages by codes
    pages = Page.objects.filter(code__in=codes_to_remove)
    found_codes = set(pages.values_list('code', flat=True))
    missing_codes = set(codes_to_remove) - found_codes

    if missing_codes:
        return Response(
            {'error': f'Pages with codes {list(missing_codes)} do not exist'},
            status=status.HTTP_404_NOT_FOUND
        )

    page_ids = list(pages.values_list('id', flat=True))

    # Find and delete all matching JobRolePage entries
    job_role_pages = JobRolePage.objects.filter(
        job_role=job_role,
        page_id__in=page_ids
    )

    deleted_count = job_role_pages.count()

    if deleted_count == 0:
        return Response(
            {'error': 'No page assignments found'},
            status=status.HTTP_404_NOT_FOUND
        )

    job_role_pages.delete()

    return Response({
        'message': f'{deleted_count} page(s) removed successfully',
        'removed_count': deleted_count,
        'removed_page_codes': list(found_codes)
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
def job_role_create_with_pages(request):
    """
    Create a job role and assign pages to it in one atomic operation.

    POST /job-roles/with-pages/
    - Request body: {
        "name": "Manager",
        "description": "Manager role with specific page access",
        "page_codes": ["hr_employee", "hr_department"]
      }
    - page_codes is optional - if omitted, creates job role with no pages
    - All page_codes must exist or the entire operation fails (atomic)
    - Returns: Created job role with assigned pages (requires admin role)
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
# Page API Views (READ-ONLY)
# ============================================================================

@api_view(['GET'])
@auto_paginate
def page_list(request):
    """
    List all pages (READ-ONLY).

    GET /pages/
    - Returns list of all pages
    - Query params:
        - code: Filter by code (case-insensitive contains)
        - name: Filter by name (case-insensitive contains)
        - search: Search across code, name, and description
    """
    pages = Page.objects.prefetch_related('page_actions__action').all()

    # Apply filters
    code = request.query_params.get('code')
    if code:
        pages = pages.filter(code__icontains=code)

    name = request.query_params.get('name')
    if name:
        pages = pages.filter(name__icontains=name)

    search = request.query_params.get('search')
    if search:
        pages = pages.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )

    serializer = PageSerializer(pages, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def page_detail(request, pk):
    """
    Retrieve details of a specific page (READ-ONLY).

    GET /pages/{id}/
    - Returns detailed page information including available actions
    """
    page = get_object_or_404(
        Page.objects.prefetch_related('page_actions__action'),
        pk=pk
    )

    serializer = PageSerializer(page)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# UserJobRole API Views (Multiple Roles per User)
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
@auto_paginate
def user_job_role_list(request):
    """
    List all user-role assignments or create new one(s).

    GET /user-job-roles/
    - Returns list of user-role assignments
    - Query params:
        - user: Filter by user ID
        - job_role: Filter by job role ID

    POST /user-job-roles/
    - Create user-role assignment(s) - supports single object or array for bulk
    - Request body (single): {
        "user_email": "user@example.com",
        "job_role_code": "accountant",
        "effective_start_date": "2024-01-01",
        "effective_end_date": "2024-12-31"  // optional
      }
    - Request body (bulk): array of objects
    """
    if request.method == 'GET':
        assignments = UserJobRole.objects.select_related(
            'user', 'job_role', 'created_by'
        )

        # Apply filters
        user_id = request.query_params.get('user')
        if user_id:
            assignments = assignments.filter(user_id=user_id)

        job_role_id = request.query_params.get('job_role')
        if job_role_id:
            assignments = assignments.filter(job_role_id=job_role_id)

        serializer = UserJobRoleSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        # Normalize to list for consistent handling
        data = request.data
        is_list = isinstance(data, list)
        if not is_list:
            data = [data]

        created = []
        errors = []

        for idx, item in enumerate(data):
            serializer = UserJobRoleCreateSerializer(
                data=item,
                context={'request': request}
            )
            if serializer.is_valid():
                try:
                    assignment = serializer.save()
                    created.append(UserJobRoleSerializer(assignment).data)
                except Exception as e:
                    errors.append({'index': idx, 'error': str(e)})
            else:
                errors.append({'index': idx, 'errors': serializer.errors})

        if not created and errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        response_data = created if is_list else (created[0] if created else None)
        return Response({
            'data': response_data,
            'errors': errors if errors else None,
            'message': f'{len(created)} assignment(s) created successfully'
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
def user_job_role_detail(request, pk):
    """
    Retrieve, update, or delete a specific user-role assignment.

    GET /user-job-roles/{pk}/
    - Returns detailed assignment information

    PUT/PATCH /user-job-roles/{pk}/
    - Update assignment (effective dates)

    DELETE /user-job-roles/{pk}/
    - Delete the assignment
    """
    assignment = get_object_or_404(
        UserJobRole.objects.select_related('user', 'job_role', 'created_by'),
        pk=pk
    )

    if request.method == 'GET':
        serializer = UserJobRoleSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UserJobRoleSerializer(
            assignment,
            data=request.data,
            partial=partial
        )
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        assignment.delete()
        return Response(
            {'message': 'User role assignment deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_self_or_admin('pk')
def user_roles(request, pk):
    """
    Get all roles assigned to a specific user.

    GET /users/{pk}/roles/
    - Returns list of all roles for the user
    - Includes effective dates
    - Users can view their own roles, admins can view any user's roles
    """
    target_user = get_object_or_404(UserAccount, pk=pk)

    assignments = UserJobRole.objects.filter(user=target_user).select_related(
        'job_role', 'created_by'
    ).order_by('-effective_start_date', 'job_role__name')

    serializer = UserJobRoleSerializer(assignments, many=True)

    return Response({
        'user_id': target_user.pk,
        'user_email': target_user.email,
        'assignments': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
def user_assign_roles(request, pk):
    """
    Assign one or more roles to a user.

    POST /users/{pk}/assign-roles/
    - Request body (single): { "job_role_code": "accountant" }
    - Request body (bulk): { "roles": [{"job_role_code": "accountant"}, ...] }
    """
    target_user = get_object_or_404(UserAccount, pk=pk)

    # Normalize to list - accept either 'roles' array or single object
    roles_data = request.data.get('roles')
    if roles_data is None:
        # Single role in request body
        roles_data = [request.data]
    elif not isinstance(roles_data, list):
        return Response(
            {'error': 'roles must be a list'},
            status=status.HTTP_400_BAD_REQUEST
        )

    created = []
    errors = []

    for idx, role_data in enumerate(roles_data):
        role_data = role_data.copy()
        role_data['user'] = target_user.pk

        # Handle job_role_code lookup
        if 'job_role_code' in role_data and 'job_role' not in role_data:
            try:
                job_role = JobRole.objects.get(code=role_data['job_role_code'])
                role_data['job_role'] = job_role.id
            except JobRole.DoesNotExist:
                errors.append({'index': idx, 'error': f"JobRole with code '{role_data['job_role_code']}' not found"})
                continue

        serializer = UserJobRoleCreateSerializer(
            data=role_data,
            context={'request': request}
        )
        if serializer.is_valid():
            try:
                assignment = serializer.save()
                created.append(UserJobRoleSerializer(assignment).data)
            except Exception as e:
                errors.append({'index': idx, 'error': str(e)})
        else:
            errors.append({'index': idx, 'errors': serializer.errors})

    if not created and errors:
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'data': created,
        'errors': errors if errors else None,
        'message': f'{len(created)} role(s) assigned successfully'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
def user_remove_roles(request, pk):
    """
    Remove one or more roles from a user.

    POST /users/{pk}/remove-roles/
    - Request body (single): { "role_code": "accountant" }
    - Request body (bulk): { "role_codes": ["accountant", "manager"] }
    """
    target_user = get_object_or_404(UserAccount, pk=pk)

    # Normalize to list
    role_codes = request.data.get('role_codes')
    role_code = request.data.get('role_code')

    if role_codes is not None:
        if not isinstance(role_codes, list):
            return Response(
                {'error': 'role_codes must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        codes_to_remove = role_codes
    elif role_code is not None:
        codes_to_remove = [role_code]
    else:
        return Response(
            {'error': 'Provide role_codes or role_code'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Find and delete assignments by role codes
    assignments_to_delete = UserJobRole.objects.filter(
        user=target_user,
        job_role__code__in=codes_to_remove
    )

    count = assignments_to_delete.count()

    if count == 0:
        return Response(
            {'error': f'No assignments found for role codes: {codes_to_remove}'},
            status=status.HTTP_404_NOT_FOUND
        )

    assignments_to_delete.delete()

    return Response({
        'message': f'{count} role assignment(s) removed successfully',
        'removed_role_codes': codes_to_remove
    }, status=status.HTTP_200_OK)


# ============================================================================
# UserPermissionOverride API Views (Grants AND Denials)
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
@auto_paginate
def user_permission_override_list(request):
    """
    List all permission overrides or create a new one.

    GET /user-permission-overrides/
    - Returns list of all permission overrides
    - Query params:
        - user: Filter by user ID
        - permission_type: Filter by 'grant' or 'deny'
        - page: Filter by page ID
        - action: Filter by action ID

    POST /user-permission-overrides/
    - Create a new permission override
    - Request body: {
        "user_email": "user@example.com",
        "page_code": "hr_employee",
        "action_code": "delete",
        "permission_type": "deny",
        "reason": "Temporary restriction",
        "effective_start_date": "2024-01-01",
        "effective_end_date": "2024-03-31"  // optional
      }
    """
    if request.method == 'GET':
        overrides = UserPermissionOverride.objects.select_related(
            'user', 'page_action__page', 'page_action__action', 'created_by'
        ).all()

        # Apply filters
        user_id = request.query_params.get('user')
        if user_id:
            overrides = overrides.filter(user_id=user_id)

        permission_type = request.query_params.get('permission_type')
        if permission_type:
            overrides = overrides.filter(permission_type=permission_type)

        page_id = request.query_params.get('page')
        if page_id:
            overrides = overrides.filter(page_action__page_id=page_id)

        action_id = request.query_params.get('action')
        if action_id:
            overrides = overrides.filter(page_action__action_id=action_id)

        serializer = UserPermissionOverrideSerializer(overrides, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        serializer = UserPermissionOverrideCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            try:
                override = serializer.save()
                result_serializer = UserPermissionOverrideSerializer(override)
                return Response(result_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
@require_page_action(CorePages.JOB_ROLE_MANAGEMENT)
def user_permission_override_detail(request, pk):
    """
    Retrieve, update, or delete a specific permission override.

    GET /user-permission-overrides/{id}/
    - Returns detailed override information

    PUT/PATCH /user-permission-overrides/{id}/
    - Update override (reason, effective dates)

    DELETE /user-permission-overrides/{id}/
    - Delete the override (restores default role-based permission)
    """
    override = get_object_or_404(
        UserPermissionOverride.objects.select_related(
            'user', 'page_action__page', 'page_action__action', 'created_by'
        ),
        pk=pk
    )

    if request.method == 'GET':
        serializer = UserPermissionOverrideSerializer(override)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UserPermissionOverrideSerializer(
            override,
            data=request.data,
            partial=partial
        )
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        override.delete()
        return Response(
            {'message': 'Permission override deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_self_or_admin('pk')
def user_permissions(request, pk):
    """
    Get complete permission summary for a user.

    GET /users/{pk}/permissions/
    - Returns all pages and actions the user can access
    - Includes source of each permission (role, grant, denial)
    - Users can view their own permissions, admins can view any user's

    Uses the enhanced permission service that handles:
    - Multiple roles via M2M
    - Role hierarchy inheritance
    - Page hierarchy inheritance
    - Effective dates on roles and overrides
    - Both grants and denials
    """
    from .services import get_user_all_permissions

    target_user = get_object_or_404(UserAccount, pk=pk)

    permissions = get_user_all_permissions(target_user)

    return Response({
        'user_id': target_user.pk,
        'user_email': target_user.email,
        'permissions': permissions,
        'total_pages': len(permissions)
    }, status=status.HTTP_200_OK)