"""
Hard delete views for HR entities.

These views provide permanent deletion endpoints that bypass the soft delete pattern.
All hard delete operations require super admin privileges.

⚠️ WARNING: Hard deletes permanently remove records from the database and cannot be undone.
Use only for:
- Removing test/dummy data
- Data cleanup after migration errors
- Compliance with data deletion requests (GDPR/data privacy)
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from HR.work_structures.permissions import require_super_admin
from HR.work_structures.models import Enterprise, BusinessGroup, Department, DepartmentManager, Position, Grade, GradeRate, Location


@api_view(['DELETE'])
@require_super_admin
def enterprise_hard_delete(request, pk):
    """
    HARD DELETE: Permanently remove an enterprise from the database.
    
    ⚠️ WARNING: This bypasses soft delete and permanently removes the record.
    
    Requires: Super admin privileges
    
    DELETE /hr/enterprises/{id}/hard-delete/
    """
    try:
        enterprise = Enterprise.objects.get(pk=pk)
    except Enterprise.DoesNotExist:
        return Response(
            {'error': 'Enterprise not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check for related business groups
    active_bgs = BusinessGroup.objects.filter(enterprise=enterprise).active()
    if active_bgs.exists():
        return Response(
            {
                'error': 'Cannot hard delete enterprise with active business groups',
                'detail': f'Found {active_bgs.count()} active business group(s)',
                'active_business_groups': [
                    {'id': bg.id, 'code': bg.code, 'name': bg.name}
                    for bg in active_bgs[:5]
                ]
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Store details for response
    ent_data = {
        'id': enterprise.id,
        'code': enterprise.code,
        'name': enterprise.name,
        'effective_start_date': enterprise.effective_start_date,
        'effective_end_date': enterprise.effective_end_date
    }
    
    enterprise.delete()
    
    return Response(
        {
            'message': 'Enterprise permanently deleted',
            'deleted_enterprise': ent_data,
            'warning': 'This operation cannot be undone'
        },
        status=status.HTTP_200_OK
    )


@api_view(['DELETE'])
@require_super_admin
def business_group_hard_delete(request, pk):
    """
    HARD DELETE: Permanently remove a business group from the database.
    
    ⚠️ WARNING: This bypasses soft delete and permanently removes the record.
    
    Requires: Super admin privileges
    
    DELETE /hr/business-groups/{id}/hard-delete/
    """
    try:
        bg = BusinessGroup.objects.select_related('enterprise').get(pk=pk)
    except BusinessGroup.DoesNotExist:
        return Response(
            {'error': 'Business group not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check for related departments
    from HR.work_structures.models import Department
    active_depts = Department.objects.filter(business_group=bg).active()
    if active_depts.exists():
        return Response(
            {
                'error': 'Cannot hard delete business group with active departments',
                'detail': f'Found {active_depts.count()} active department(s)',
                'active_departments': [
                    {'id': dept.id, 'code': dept.code, 'name': dept.name}
                    for dept in active_depts[:5]
                ]
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Store details for response
    bg_data = {
        'id': bg.id,
        'code': bg.code,
        'name': bg.name,
        'enterprise': bg.enterprise.code,
        'effective_start_date': bg.effective_start_date,
        'effective_end_date': bg.effective_end_date
    }
    
    bg.delete()
    
    return Response(
        {
            'message': 'Business group permanently deleted',
            'deleted_business_group': bg_data,
            'warning': 'This operation cannot be undone'
        },
        status=status.HTTP_200_OK
    )

@api_view(['DELETE'])
@require_super_admin
def department_hard_delete(request, pk):
    """
    HARD DELETE: Permanently remove a department from the database.
    
    ⚠️ WARNING: This bypasses soft delete and permanently removes the record.
    Use with extreme caution. This operation cannot be undone.
    
    Requires: Super admin privileges
    
    DELETE /hr/departments/{id}/hard-delete/
    - Permanently deletes the department record from the database
    - Returns: Success message with deleted department details
    
    Use cases:
    - Removing test/dummy data
    - Data cleanup after migration errors
    - Compliance with data deletion requests (GDPR)
    
    Restrictions:
    - Only super admins can perform hard deletes
    - Cannot delete departments with active positions
    - Cannot delete departments with active child departments
    """
    try:
        # Don't scope this query - super admin should be able to delete any department
        department = Department.objects.select_related(
            'business_group', 'location', 'parent'
        ).get(pk=pk)
    except Department.DoesNotExist:
        return Response(
            {'error': 'Department not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check for active child departments
    active_children = Department.objects.filter(parent=department).active()
    if active_children.exists():
        return Response(
            {
                'error': 'Cannot hard delete department with active child departments',
                'detail': f'Found {active_children.count()} active child department(s)',
                'active_children': [
                    {'id': child.id, 'code': child.code, 'name': child.name}
                    for child in active_children[:5]  # Show first 5
                ]
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check for positions in this department
    active_positions = Position.objects.filter(department=department).active()
    if active_positions.exists():
        return Response(
            {
                'error': 'Cannot hard delete department with active positions',
                'detail': f'Found {active_positions.count()} active position(s)',
                'active_positions': [
                    {'id': pos.id, 'code': pos.code, 'name': pos.name}
                    for pos in active_positions[:5]  # Show first 5
                ]
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Store details for response before deletion
    dept_data = {
        'id': department.id,
        'code': department.code,
        'name': department.name,
        'business_group': department.business_group.code,
        'effective_start_date': department.effective_start_date,
        'effective_end_date': department.effective_end_date
    }
    
    # Perform hard delete
    department.delete()
    
    return Response(
        {
            'message': 'Department permanently deleted',
            'deleted_department': dept_data,
            'warning': 'This operation cannot be undone'
        },
        status=status.HTTP_200_OK
    )

def department_manager_hard_delete(request, pk):
    """
    HARD DELETE: Permanently remove a department manager assignment from the database.
    
    ⚠️ WARNING: This bypasses soft delete and permanently removes the record.
    
    Requires: Super admin privileges
    
    DELETE /hr/department-managers/{id}/hard-delete/
    """
    try:
        dept_manager = DepartmentManager.objects.select_related(
            'department', 'manager'
        ).get(pk=pk)
    except DepartmentManager.DoesNotExist:
        return Response(
            {'error': 'Department manager assignment not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Store details for response
    dm_data = {
        'id': dept_manager.id,
        'department': dept_manager.department.code,
        'manager': dept_manager.manager.username,
        'effective_start_date': dept_manager.effective_start_date,
        'effective_end_date': dept_manager.effective_end_date
    }
    
    dept_manager.delete()
    
    return Response(
        {
            'message': 'Department manager assignment permanently deleted',
            'deleted_department_manager': dm_data,
            'warning': 'This operation cannot be undone'
        },
        status=status.HTTP_200_OK
    )

@api_view(['DELETE'])
@require_super_admin
def position_hard_delete(request, pk):
    """
    HARD DELETE: Permanently remove a position from the database.
    
    ⚠️ WARNING: This bypasses soft delete and permanently removes the record.
    
    Requires: Super admin privileges
    
    DELETE /hr/positions/{id}/hard-delete/
    """
    try:
        position = Position.objects.select_related(
            'department', 'location', 'grade'
        ).get(pk=pk)
    except Position.DoesNotExist:
        return Response(
            {'error': 'Position not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check for positions that report to this one
    active_reports = Position.objects.filter(reports_to=position).active()
    if active_reports.exists():
        return Response(
            {
                'error': 'Cannot hard delete position with active direct reports',
                'detail': f'Found {active_reports.count()} position(s) reporting to this position',
                'active_reports': [
                    {'id': pos.id, 'code': pos.code, 'name': pos.name}
                    for pos in active_reports[:5]
                ]
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Store details for response
    pos_data = {
        'id': position.id,
        'code': position.code,
        'name': position.name,
        'department': position.department.code,
        'effective_start_date': position.effective_start_date,
        'effective_end_date': position.effective_end_date
    }
    
    position.delete()
    
    return Response(
        {
            'message': 'Position permanently deleted',
            'deleted_position': pos_data,
            'warning': 'This operation cannot be undone'
        },
        status=status.HTTP_200_OK
    )


@api_view(['DELETE'])
@require_super_admin
def grade_hard_delete(request, pk):
    """
    HARD DELETE: Permanently remove a grade from the database.
    
    ⚠️ WARNING: This bypasses soft delete and permanently removes the record.
    
    Requires: Super admin privileges
    
    DELETE /hr/grades/{id}/hard-delete/
    """
    try:
        grade = Grade.objects.select_related('business_group').get(pk=pk)
    except Grade.DoesNotExist:
        return Response(
            {'error': 'Grade not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check for positions using this grade
    active_positions = Position.objects.filter(grade=grade).active()
    if active_positions.exists():
        return Response(
            {
                'error': 'Cannot hard delete grade with active positions',
                'detail': f'Found {active_positions.count()} active position(s) using this grade',
                'active_positions': [
                    {'id': pos.id, 'code': pos.code, 'name': pos.name}
                    for pos in active_positions[:5]
                ]
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Store details for response
    grade_data = {
        'id': grade.id,
        'code': grade.code,
        'name': grade.name,
        'business_group': grade.business_group.code,
        'effective_start_date': grade.effective_start_date,
        'effective_end_date': grade.effective_end_date
    }
    
    # Note: Related GradeRate records will be cascade deleted
    rate_count = GradeRate.objects.filter(grade=grade).count()
    
    grade.delete()
    
    return Response(
        {
            'message': 'Grade permanently deleted',
            'deleted_grade': grade_data,
            'cascade_deleted_rates': rate_count,
            'warning': 'This operation cannot be undone'
        },
        status=status.HTTP_200_OK
    )


@api_view(['DELETE'])
@require_super_admin
def location_hard_delete(request, pk):
    """
    HARD DELETE: Permanently remove a location from the database.
    
    ⚠️ WARNING: This bypasses soft delete and permanently removes the record.
    
    Requires: Super admin privileges
    
    DELETE /hr/locations/{id}/hard-delete/
    
    Note: Location does not use date tracking (no effective dates).
    """
    try:
        location = Location.objects.select_related('enterprise', 'business_group').get(pk=pk)
    except Location.DoesNotExist:
        return Response(
            {'error': 'Location not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Validate location is not linked to active enterprise
    if location.enterprise and location.enterprise.is_active:
        return Response(
            {
                'error': 'Cannot hard delete location linked to active enterprise',
                'detail': 'Location belongs to an active enterprise',
                'enterprise': {
                    'id': location.enterprise.id,
                    'code': location.enterprise.code,
                    'name': location.enterprise.name
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate location is not linked to active business group
    if location.business_group:
        active_bg = BusinessGroup.objects.filter(id=location.business_group.id).active()
        if active_bg.exists():
            bg = location.business_group
            return Response(
                {
                    'error': 'Cannot hard delete location linked to active business group',
                    'detail': 'Location belongs to an active business group',
                    'business_group': {
                        'id': bg.id,
                        'code': bg.code,
                        'name': bg.name
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Store details for response
    loc_data = {
        'id': location.id,
        'code': location.code,
        'name': location.name,
        'country': location.country
    }
    
    location.delete()
    
    return Response(
        {
            'message': 'Location permanently deleted',
            'deleted_location': loc_data,
            'warning': 'This operation cannot be undone'
        },
        status=status.HTTP_200_OK
    )
