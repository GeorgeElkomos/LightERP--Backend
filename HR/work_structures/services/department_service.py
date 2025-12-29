from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from HR.work_structures.dtos import DepartmentCreateDTO, DepartmentUpdateDTO
from HR.work_structures.models import Department, BusinessGroup, Location, Position
from HR.work_structures.security import validate_data_scope_on_create

class DepartmentService:
    
    @staticmethod
    @transaction.atomic
    def create_department(user, dto: DepartmentCreateDTO):
        """
        Create department with hierarchy validation.
        """
        # Validate data scope (including parent department if creating under one)
        validate_data_scope_on_create(
            user, 
            dto.business_group_id,
            parent_department_id=dto.parent_id
        )
        
        # Validate location belongs to the business group or is enterprise-level
        business_group = BusinessGroup.objects.get(id=dto.business_group_id)
        location = Location.objects.get(id=dto.location_id)
        
        if location.enterprise and not location.business_group:
            # Enterprise-level location - check it belongs to the same enterprise
            if location.enterprise != business_group.enterprise:
                raise ValidationError(
                    f"Location '{location.name}' belongs to enterprise '{location.enterprise.name}', "
                    f"but department's business group belongs to '{business_group.enterprise.name}'."
                )
        elif location.business_group:
            # Location is BG-specific - must match exactly
            if location.business_group_id != dto.business_group_id:
                raise ValidationError(
                    f"Location '{location.name}' belongs to business group '{location.business_group.name}', "
                    f"but department is in '{business_group.name}'."
                )
        
        # Validate parent if provided (Hierarchy)
        if dto.parent_id:
            parent = Department.objects.filter(
                pk=dto.parent_id,
                effective_end_date__isnull=True
            ).first()
            
            if not parent:
                raise ValidationError("Parent department not found or not active")
            
            # Validate no circular reference
            DepartmentService._validate_no_circular_reference(parent, None)
        
        # Create department
        dept = Department(
            code=dto.code,
            business_group_id=dto.business_group_id,
            name=dto.name,
            location_id=dto.location_id,
            parent_id=dto.parent_id,
            effective_start_date=dto.effective_start_date or timezone.now().date(),
            effective_end_date=dto.effective_end_date
        )
        dept.full_clean()
        dept.save()
        
        return dept
    
    @staticmethod
    @transaction.atomic
    def update_department(user, dto: DepartmentUpdateDTO):
        """
        Update department.
        - If new_start_date == current.effective_start_date: Correct current record.
        - Otherwise: End-date current record and create new version.
        """
        
        # Get currently active version
        current = Department.objects.active().filter(
            code=dto.code
        ).first()
        
        if not current:
            raise ValidationError("No active department found")
        
        # Validate scope
        validate_data_scope_on_create(
            user, 
            current.business_group_id,
            department_id=current.id
        )
        
        # Validate location if provided
        location_id = dto.location_id
        if location_id:
            location = Location.objects.get(id=location_id)
            business_group = current.business_group
            
            if location.enterprise and not location.business_group:
                # Enterprise-level location - check it belongs to the same enterprise
                if location.enterprise != business_group.enterprise:
                    raise ValidationError(
                        f"Location '{location.name}' belongs to enterprise '{location.enterprise.name}', "
                        f"but department's business group belongs to '{business_group.enterprise.name}'."
                    )
            elif location.business_group:
                # Location is BG-specific - must match exactly
                if location.business_group != business_group:
                    raise ValidationError(
                        f"Location '{location.name}' belongs to business group '{location.business_group.name}', "
                        f"but department is in '{business_group.name}'."
                    )
        
        # Validate parent if provided
        if dto.parent_id:
            parent = Department.objects.filter(
                pk=dto.parent_id,
                effective_end_date__isnull=True
            ).first()
            if not parent:
                raise ValidationError("Parent department not found or not active")
            
            # Check for circular reference
            DepartmentService._validate_no_circular_reference(parent, current.code)
        
        # Determine effective dates
        # If effective_start_date not provided, keep original date (correction mode)
        if dto.effective_start_date is not None:
            new_start_date = dto.effective_start_date
        else:
            new_start_date = current.effective_start_date
        
        provided = getattr(dto, '_provided_fields', None)
        
        def is_provided(field_name):
            if provided is not None:
                return field_name in provided
            return getattr(dto, field_name) is not None

        # Same-day update = Correction
        # Correction mode: effective_start_date not provided OR equals current date
        if new_start_date == current.effective_start_date:
            if is_provided('name'):
                current.name = dto.name
            if is_provided('location_id'):
                current.location_id = dto.location_id
            if is_provided('parent_id'):
                current.parent_id = dto.parent_id
            if is_provided('effective_end_date'):
                current.effective_end_date = dto.effective_end_date
            
            current.full_clean()
            current.save()
            return current
        
        # Different day = New Version
        # Capture original end date before modifying current
        original_end_date = current.effective_end_date
        
        # End current version
        current.effective_end_date = new_start_date - timedelta(days=1)
        current.save()
        
        # Create new version
        new_version = Department(
            code=current.code,
            business_group=current.business_group,
            name=dto.name if is_provided('name') else current.name,
            location_id=dto.location_id if is_provided('location_id') else current.location_id,
            parent_id=dto.parent_id if is_provided('parent_id') else current.parent_id,
            effective_start_date=new_start_date,
            effective_end_date=dto.effective_end_date if is_provided('effective_end_date') else original_end_date
        )
        
        new_version.full_clean()
        new_version.save()
        
        return new_version
    
    @staticmethod
    @transaction.atomic
    def deactivate_department(user, department_id, effective_end_date=None):
        """
        Deactivate a department by end-dating it and setting status to inactive.
        
        Args:
            user: User performing the action
            department_id: ID of the department to deactivate
            effective_end_date: Date when deactivation takes effect (defaults to today)
        
        Returns:
            The deactivated department instance
        """
        # Get the department and validate scope
        department = Department.objects.select_related('business_group').get(pk=department_id)
        
        # Validate scope - user must have access to this specific department
        validate_data_scope_on_create(
            user, 
            department.business_group_id,
            department_id=department.id
        )
        
        # Check if already inactive
        if department.effective_end_date is not None:
            raise ValidationError("Department is already inactive")
        
        # Check if any active child departments exist
        active_children = Department.objects.filter(
            parent=department,
            effective_end_date__isnull=True
        ).count()
        
        if active_children > 0:
            raise ValidationError(
                f"Cannot deactivate department. {active_children} active child department(s) exist. "
                "Please deactivate or reassign them first."
            )
        
        # Check if any active positions are assigned to this department
        active_positions = Position.objects.filter(
            department=department,
            effective_end_date__isnull=True
        ).count()
        
        if active_positions > 0:
            raise ValidationError(
                f"Cannot deactivate department. {active_positions} active position(s) are assigned to it. "
                "Please reassign or deactivate them first."
            )
        
        # Deactivate using model method (handles date safety)
        department.deactivate(end_date=effective_end_date)
        return department
    
    @staticmethod
    def _validate_no_circular_reference(parent, child_code):
        """
        Circular references not allowed
        """
        if not parent:
            return
        
        visited = set()
        current = parent
        
        while current:
            if current.code == child_code:
                raise ValidationError(
                    f"Circular reference: Cannot make {child_code} "
                    f"a child of {parent.code}"
                )
            
            if current.code in visited:
                raise ValidationError("Circular reference in existing hierarchy")
            
            visited.add(current.code)
            current = current.parent
    
    @staticmethod
    def get_department_tree(user, business_group_id: int):
        """
        Get hierarchy as tree structure.
        """
        
        validate_data_scope_on_create(user, business_group_id)
        
        departments = Department.objects.filter(
            business_group_id=business_group_id,
            effective_end_date__isnull=True
        ).select_related('parent')
        
        dept_dict = {d.pk: d for d in departments}
        tree = []
        
        for dept in departments:
            if not dept.parent:
                tree.append(DepartmentService._build_tree_node(dept, dept_dict))
        
        return tree
    
    @staticmethod
    def _build_tree_node(dept, dept_dict):
        node = {
            'id': dept.pk,
            'code': dept.code,
            'name': dept.name,
            'children': []
        }
        
        children = [d for d in dept_dict.values() if d.parent_id == dept.pk]
        node['children'] = [
            DepartmentService._build_tree_node(child, dept_dict)
            for child in children
        ]
        
        return node
