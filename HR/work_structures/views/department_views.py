"""
API Views for Department models.
Provides REST API endpoints for managing departments with date tracking.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from HR.work_structures.models import Department, BusinessGroup

from HR.work_structures.services.department_service import DepartmentService
from HR.work_structures.serializers import (
    DepartmentSerializer,
    DepartmentCreateSerializer,
    DepartmentUpdateSerializer
)


@api_view(['GET', 'POST'])
@require_page_action('hr_department')
@auto_paginate
def department_list(request):
    """
    List all active departments or create a new department.
    
    GET /hr/departments/
    - Returns list of currently active departments (scoped by user's business groups)
    - Query params:
        - status: Filter by status (active/inactive)
        - business_group: Filter by business group code or name
        - location: Filter by location code or name
        - code: Filter by department code
        - name: Filter by department name
        - search: Search across code and name
    
    POST /hr/departments/
    - Create a new department
    - Request body: DepartmentCreateSerializer fields
    """
    if request.method == 'GET':
        departments = Department.objects.scoped(request.user).active()
        departments = departments.select_related('business_group', 'location', 'parent')
        
        # Apply filters
        # Note: Status is computed from dates, so filtering handled by .active() above
        # If user wants all records (active + inactive), they should use include_inactive param
        status_param = request.query_params.get('status')
        if status_param and status_param.lower() == 'inactive':
            # Get all records, then filter out active ones (return inactive only)
            from django.utils import timezone
            today = timezone.now().date()
            departments = Department.objects.scoped(request.user).exclude(
                Q(effective_start_date__lte=today) &
                (Q(effective_end_date__gte=today) | Q(effective_end_date__isnull=True))
            )
        
        # Filter by business group (name or code)
        business_group_filter = request.query_params.get('business_group')
        if business_group_filter:
            departments = departments.filter(
                Q(business_group__name__icontains=business_group_filter) |
                Q(business_group__code__icontains=business_group_filter)
            )
        
        # Filter by location (name or code)
        location_filter = request.query_params.get('location')
        if location_filter:
            departments = departments.filter(
                Q(location__name__icontains=location_filter) |
                Q(location__code__icontains=location_filter)
            )
            
        # Apply standard code/name/search filters
        departments = departments.filter_by_search_params(request.query_params)
        
        serializer = DepartmentSerializer(departments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = DepartmentCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            dto = serializer.to_dto()
            try:
                dept = DepartmentService.create_department(request.user, dto)
                return Response(
                    DepartmentSerializer(dept).data,
                    status=status.HTTP_201_CREATED
                )
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to create department: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_department')
def department_detail(request, pk):
    """
    Retrieve, update, or delete a specific department.
    
    GET /hr/departments/{id}/
    - Returns detailed information about a department
    
    PUT/PATCH /hr/departments/{id}/
    - Update a department (creates new version with date tracking)
    - Request body: DepartmentUpdateSerializer fields
    
    DELETE /hr/departments/{id}/
    - Deactivate a department (end-dates it and sets status to inactive)
    - Optional body: {"effective_end_date": "YYYY-MM-DD"} (defaults to today)
    """
    try:
        department = Department.objects.scoped(request.user).select_related(
            'business_group', 'location', 'parent'
        ).get(pk=pk)
    except Department.DoesNotExist:
        # Check if department exists at all
        if Department.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this department. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Department not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = DepartmentSerializer(department)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = DepartmentUpdateSerializer(data=request.data)
        if serializer.is_valid():
            dto = serializer.to_dto(code=department.code)
            try:
                updated_dept = DepartmentService.update_department(request.user, dto)
                return Response(
                    DepartmentSerializer(updated_dept).data,
                    status=status.HTTP_200_OK
                )
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to update department: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            effective_end_date = request.data.get('effective_end_date') if request.data else None
            if effective_end_date:
                from django.utils.dateparse import parse_date
                effective_end_date = parse_date(effective_end_date)
            
            deactivated_dept = DepartmentService.deactivate_department(request.user, pk, effective_end_date)
            return Response(
                {
                    'message': 'Department deactivated successfully',
                    'department': DepartmentSerializer(deactivated_dept).data
                },
                status=status.HTTP_200_OK
            )
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@require_page_action('hr_department', 'view')
def department_history(request, pk):
    """
    Get all historical versions of a department.
    
    GET /hr/departments/{id}/history/
    - Returns all versions of a department (date tracked)
    """
    try:
        department = Department.objects.scoped(request.user).get(pk=pk)
    except Department.DoesNotExist:
        # Check if department exists at all
        if Department.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this department. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Department not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all versions with the same code within the same scope (business_group)
    versions = Department.objects.filter(
        code=department.code,
        **department.get_version_scope_filters()
    ).order_by('-effective_start_date')
    
    serializer = DepartmentSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@require_page_action('hr_department', 'view')
def department_tree(request):
    """
    Get department hierarchy tree for a business group.
    
    GET /hr/departments/tree/?bg={id_or_code}
    - Returns nested department hierarchy
    - Required query param: bg (business group ID or code)
    """
    bg_param = request.query_params.get('bg')
    
    if not bg_param:
        return Response(
            {'error': 'bg parameter (ID or code) required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Try numeric ID first
        if bg_param.isdigit():
            bg = BusinessGroup.objects.get(id=int(bg_param))
        else:
            # Try code (case insensitive)
            bg = BusinessGroup.objects.active().filter(code__iexact=bg_param).first()
            if not bg:
                raise BusinessGroup.DoesNotExist
        
        tree = DepartmentService.get_department_tree(request.user, bg.id)
        return Response(tree, status=status.HTTP_200_OK)
    except BusinessGroup.DoesNotExist:
        return Response(
            {'error': f"Business Group '{bg_param}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except PermissionDenied as e:
        return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f"Failed to retrieve department tree: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@require_page_action('hr_department', 'view')
def department_children(request, pk):
    """
    Get all direct children of a department.
    
    GET /hr/departments/{id}/children/
    - Returns list of departments that have this department as parent
    - Only returns active children by default
    """
    try:
        department = Department.objects.scoped(request.user).get(pk=pk)
    except Department.DoesNotExist:
        # Check if department exists at all
        if Department.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this department. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Department not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get direct children
    children = Department.objects.filter(
        parent=department,
        business_group=department.business_group
    ).order_by('name')
    
    serializer = DepartmentSerializer(children, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@require_page_action('hr_department', 'view')
def department_parent(request, pk):
    """
    Get the parent department of a department.
    
    GET /hr/departments/{id}/parent/
    - Returns parent department if it exists
    - Returns 404 if department has no parent (top-level department)
    """
    try:
        department = Department.objects.scoped(request.user).get(pk=pk)
    except Department.DoesNotExist:
        # Check if department exists at all
        if Department.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this department. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Department not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not department.parent:
        return Response(
            {'error': 'This department has no parent (it is a top-level department)'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    serializer = DepartmentSerializer(department.parent)
    return Response(serializer.data, status=status.HTTP_200_OK)
