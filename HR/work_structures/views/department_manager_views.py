"""
API Views for Department Manager assignments.
Allows assigning/removing managers to/from departments with date tracking.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError, PermissionDenied

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from HR.work_structures.models import Department, DepartmentManager as DepartmentManagerModel
from HR.work_structures.serializers import DepartmentManagerSerializer
from HR.work_structures.services.department_manager_service import DepartmentManagerService


@api_view(['GET', 'POST'])
@require_page_action('hr_department')
@auto_paginate
def department_manager_list(request, department_pk):
    """
    List all manager assignments for a department or create a new assignment.
    
    GET /hr/departments/{department_id}/managers/
    - Returns all manager assignments for the department (past and current)
    - Query params:
        - active_only: If 'true', returns only currently active manager (default: false)
    
    POST /hr/departments/{department_id}/managers/
    - Assign a manager to the department
    - Automatically end-dates any existing active manager
    - Only ONE manager can be active per department at any time
    - Request body: DepartmentManagerSerializer fields
    """
    # Verify department exists and user has access
    try:
        department = Department.objects.scoped(request.user).get(pk=department_pk)
    except Department.DoesNotExist:
        if Department.objects.filter(pk=department_pk).exists():
            return Response(
                {'error': 'You do not have access to this department. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Department not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        # Use service to get managers (handles scope validation)
        try:
            managers = DepartmentManagerService.get_department_managers(
                request.user,
                department_pk,
                active_only=request.query_params.get('active_only', 'false').lower() == 'true'
            )
        except Department.DoesNotExist:
            return Response(
                {'error': 'Department not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DepartmentManagerSerializer(managers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # Extract data from request
        manager_id = request.data.get('manager')
        effective_start_date = request.data.get('effective_start_date')
        effective_end_date = request.data.get('effective_end_date')
        
        # Validate required fields
        if not manager_id:
            return Response(
                {'error': 'manager field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use service to handle assignment (automatically end-dates existing manager)
            manager_assignment = DepartmentManagerService.assign_manager(
                user=request.user,
                department_id=department_pk,
                manager_id=manager_id,
                effective_start_date=effective_start_date,
                effective_end_date=effective_end_date
            )
            
            return Response(
                DepartmentManagerSerializer(manager_assignment).data,
                status=status.HTTP_201_CREATED
            )
        except Department.DoesNotExist:
            return Response(
                {'error': 'Department not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f"Failed to assign manager: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET', 'PATCH', 'DELETE'])
@require_page_action('hr_department')
def department_manager_detail(request, department_pk, manager_pk):
    """
    Retrieve, update, or remove a department manager assignment.
    
    GET /hr/departments/{department_id}/managers/{manager_id}/
    - Returns detailed information about a manager assignment
    
    PATCH /hr/departments/{department_id}/managers/{manager_id}/
    - Update the assignment (typically to end-date it)
    
    DELETE /hr/departments/{department_id}/managers/{manager_id}/
    - End-date the assignment (sets effective_end_date to today)
    """
    # Verify department exists and user has access
    try:
        department = Department.objects.scoped(request.user).get(pk=department_pk)
    except Department.DoesNotExist:
        if Department.objects.filter(pk=department_pk).exists():
            return Response(
                {'error': 'You do not have access to this department.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Department not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get the manager assignment
    try:
        manager_assignment = DepartmentManagerModel.objects.select_related(
            'department', 'manager'
        ).get(pk=manager_pk, department=department)
    except DepartmentManagerModel.DoesNotExist:
        return Response(
            {'error': 'Manager assignment not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = DepartmentManagerSerializer(manager_assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'PATCH':
        try:
            # Use service to update the assignment
            effective_end_date = request.data.get('effective_end_date')
            
            updated_assignment = DepartmentManagerService.update_manager_assignment(
                user=request.user,
                assignment_id=manager_pk,
                effective_end_date=effective_end_date
            )
            
            return Response(
                DepartmentManagerSerializer(updated_assignment).data,
                status=status.HTTP_200_OK
            )
        except DepartmentManagerModel.DoesNotExist:
            return Response(
                {'error': 'Manager assignment not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            # Use service to end the assignment
            ended_assignment = DepartmentManagerService.end_manager_assignment(
                user=request.user,
                assignment_id=manager_pk
            )
            
            return Response(
                {
                    'message': 'Manager assignment ended successfully',
                    'assignment': DepartmentManagerSerializer(ended_assignment).data
                },
                status=status.HTTP_200_OK
            )
        except DepartmentManagerModel.DoesNotExist:
            return Response(
                {'error': 'Manager assignment not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response(
                {'error': f"Failed to end manager assignment: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
