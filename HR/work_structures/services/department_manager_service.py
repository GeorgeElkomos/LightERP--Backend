from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from HR.work_structures.models import Department, DepartmentManager
from HR.work_structures.security import validate_data_scope_on_create


class DepartmentManagerService:
    """
    Service for managing department manager assignments.
    Handles automatic end-dating of existing managers when assigning new ones.
    """
    
    @staticmethod
    @transaction.atomic
    def assign_manager(user, department_id: int, manager_id: int, effective_start_date=None, effective_end_date=None):
        """
        Assign a manager to a department.
        Automatically end-dates any existing active manager.
        
        Args:
            user: User performing the action
            department_id: ID of the department
            manager_id: ID of the user to assign as manager
            effective_start_date: Date when assignment becomes effective (defaults to today)
                                  Can be a date object or string in 'YYYY-MM-DD' format
            effective_end_date: Optional end date for the assignment
                                Can be a date object or string in 'YYYY-MM-DD' format
        
        Returns:
            The created DepartmentManager instance
        """
        # Get department and validate scope
        department = Department.objects.select_related('business_group').get(pk=department_id)
        
        # Validate scope - user must have access to this department
        validate_data_scope_on_create(
            user, 
            department.business_group_id,
            department_id=department.id
        )
        
        # Parse and determine effective start date
        if effective_start_date:
            if isinstance(effective_start_date, str):
                from datetime import datetime
                start_date = datetime.strptime(effective_start_date, '%Y-%m-%d').date()
            else:
                start_date = effective_start_date
        else:
            start_date = timezone.now().date()
        
        # Parse effective end date if provided
        if effective_end_date:
            if isinstance(effective_end_date, str):
                from datetime import datetime
                end_date = datetime.strptime(effective_end_date, '%Y-%m-%d').date()
            else:
                end_date = effective_end_date
        else:
            end_date = None
        
        # BEFORE creating new assignment, end-date any existing active manager
        # Only ONE manager can be active per department at any time
        existing_manager = DepartmentManager.objects.filter(
            department=department
        ).active().first()
        
        if existing_manager:
            # End-date one day before the new manager starts
            existing_manager.effective_end_date = start_date - timedelta(days=1)
            existing_manager.save(update_fields=['effective_end_date'])
        
        # Now create the new assignment (no overlap validation will trigger)
        manager_assignment = DepartmentManager(
            department_id=department_id,
            manager_id=manager_id,
            effective_start_date=start_date,
            effective_end_date=end_date
        )
        
        # Validate the assignment (checks for Employee record, etc.)
        manager_assignment.full_clean()
        manager_assignment.save()
        
        return manager_assignment
    
    @staticmethod
    @transaction.atomic
    def update_manager_assignment(user, assignment_id: int, effective_end_date=None):
        """
        Update a manager assignment (typically to end-date it).
        
        Args:
            user: User performing the action
            assignment_id: ID of the DepartmentManager assignment
            effective_end_date: New end date for the assignment
                                Can be a date object or string in 'YYYY-MM-DD' format
        
        Returns:
            The updated DepartmentManager instance
        """
        # Get the assignment
        assignment = DepartmentManager.objects.select_related(
            'department__business_group'
        ).get(pk=assignment_id)
        
        # Validate scope
        validate_data_scope_on_create(
            user,
            assignment.department.business_group_id,
            department_id=assignment.department_id
        )
        
        # Parse and update the end date
        if effective_end_date is not None:
            if isinstance(effective_end_date, str):
                from datetime import datetime
                end_date = datetime.strptime(effective_end_date, '%Y-%m-%d').date()
            else:
                end_date = effective_end_date
            assignment.effective_end_date = end_date
        
        assignment.full_clean()
        assignment.save()
        
        return assignment
    
    @staticmethod
    @transaction.atomic
    def end_manager_assignment(user, assignment_id: int, end_date=None):
        """
        End a manager assignment by setting effective_end_date.
        
        Args:
            user: User performing the action
            assignment_id: ID of the DepartmentManager assignment
            end_date: Date to end the assignment (defaults to today)
        
        Returns:
            The ended DepartmentManager instance
        """
        # Get the assignment
        assignment = DepartmentManager.objects.select_related(
            'department__business_group'
        ).get(pk=assignment_id)
        
        # Validate scope
        validate_data_scope_on_create(
            user,
            assignment.department.business_group_id,
            department_id=assignment.department_id
        )
        
        # End-date the assignment
        assignment.effective_end_date = end_date or timezone.now().date()
        assignment.save(update_fields=['effective_end_date'])
        
        return assignment
    
    @staticmethod
    def get_department_managers(user, department_id: int, active_only=False):
        """
        Get all manager assignments for a department.
        
        Args:
            user: User requesting the data
            department_id: ID of the department
            active_only: If True, return only currently active managers
        
        Returns:
            QuerySet of DepartmentManager instances
        """
        # Get department and validate scope
        department = Department.objects.select_related('business_group').get(pk=department_id)
        
        # Validate scope
        validate_data_scope_on_create(
            user,
            department.business_group_id,
            department_id=department.id
        )
        
        # Get managers
        managers = DepartmentManager.objects.filter(
            department=department
        ).select_related('manager', 'department')
        
        if active_only:
            managers = managers.active()
        else:
            managers = managers.order_by('-effective_start_date')
        
        return managers
