"""
API Views for Department models.
Provides REST API endpoints for managing departments with date tracking.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from hr.models import Department
from hr.services.department_service import DepartmentService
from hr.serializers import (
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
        - business_group: Filter by business group ID
        - location: Filter by location ID
        - search: Search across code and name
    
    POST /hr/departments/
    - Create a new department
    - Request body: DepartmentCreateSerializer fields
    """
    if request.method == 'GET':
        departments = Department.objects.scoped(request.user).currently_active()
        departments = departments.select_related('business_group', 'location', 'parent')
        
        # Apply filters
        status_param = request.query_params.get('status')
        if status_param:
            departments = departments.filter(status=status_param)
        
        business_group_id = request.query_params.get('business_group')
        if business_group_id:
            departments = departments.filter(business_group_id=business_group_id)
        
        location_id = request.query_params.get('location')
        if location_id:
            departments = departments.filter(location_id=location_id)
        
        search = request.query_params.get('search')
        if search:
            departments = departments.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
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
            except (ValidationError, PermissionDenied) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to create department: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH'])
@require_page_action('hr_department')
def department_detail(request, pk):
    """
    Retrieve or update a specific department.
    
    GET /hr/departments/{id}/
    - Returns detailed information about a department
    
    PUT/PATCH /hr/departments/{id}/
    - Update a department (creates new version with date tracking)
    - Request body: DepartmentUpdateSerializer fields
    """
    department = get_object_or_404(
        Department.objects.scoped(request.user).select_related(
            'business_group', 'location', 'parent'
        ),
        pk=pk
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
            except (ValidationError, PermissionDenied) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to update department: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_department', 'view')
def department_history(request, pk):
    """
    Get all historical versions of a department.
    
    GET /hr/departments/{id}/history/
    - Returns all versions of a department (date tracked)
    """
    department = get_object_or_404(Department, pk=pk)
    
    # Get all versions with the same department_code
    versions = Department.objects.filter(
        code=department.code
    ).order_by('-effective_start_date')
    
    serializer = DepartmentSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@require_page_action('hr_department', 'view')
def department_tree(request):
    """
    Get department hierarchy tree for a business group.
    
    GET /hr/departments/tree/?bg={id}
    - Returns nested department hierarchy
    - Required query param: bg (business group ID)
    """
    bg_id = request.query_params.get('bg')
    
    if not bg_id:
        return Response(
            {'error': 'bg parameter required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        tree = DepartmentService.get_department_tree(request.user, int(bg_id))
        return Response(tree, status=status.HTTP_200_OK)
    except (ValidationError, PermissionDenied) as e:
        return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response(
            {'error': f"Failed to retrieve department tree: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )
