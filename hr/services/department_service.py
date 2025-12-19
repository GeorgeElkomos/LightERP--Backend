from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from hr.dtos import DepartmentCreateDTO, DepartmentUpdateDTO
from hr.models import Department, BusinessGroup, Location
from hr.security import validate_data_scope_on_create

class DepartmentService:
    
    @staticmethod
    @transaction.atomic
    def create_department(user, dto: DepartmentCreateDTO):
        """
        Create department with hierarchy validation.
        Requirements: C.3, C.4
        """
        # Validate data scope
        validate_data_scope_on_create(user, dto.business_group_id)
        
        # Validate parent if provided (C.4 Hierarchy)
        if dto.parent_id:
            parent = Department.objects.filter(
                pk=dto.parent_id,
                effective_end_date__isnull=True
            ).first()
            
            if not parent:
                raise ValidationError("Parent department not found or not active")
            
            # C.4.5: Validate no circular reference
            DepartmentService._validate_no_circular_reference(parent, None)
        
        # Create department
        dept = Department(
            code=dto.code,
            business_group_id=dto.business_group_id,
            name=dto.name,
            location_id=dto.location_id,
            parent_id=dto.parent_id,
            effective_start_date=dto.effective_start_date or timezone.now().date()
        )
        dept.full_clean()
        dept.save()
        
        return dept
    
    @staticmethod
    @transaction.atomic
    def update_department(user, dto: DepartmentUpdateDTO):
        """
        Update by creating new version (date tracking).
        Requirements: C.3.4
        """
        
        # Get currently active version
        current = Department.objects.filter(
            code=dto.code,
            effective_end_date__isnull=True
        ).first()
        
        if not current:
            raise ValidationError("No active department found")
        
        validate_data_scope_on_create(user, current.business_group_id)
        
        effective_date = dto.effective_date or timezone.now().date()
        
        # C.4.5: Validate no circular reference before updating
        if dto.parent_id:
            parent = Department.objects.filter(
                pk=dto.parent_id,
                effective_end_date__isnull=True
            ).first()
            if not parent:
                raise ValidationError("Parent department not found or not active")
            
            # Check if current department is an ancestor of the new parent
            DepartmentService._validate_no_circular_reference(parent, current.code)
        
        # End-date current version
        current.effective_end_date = effective_date - timedelta(days=1)
        current.save()
        
        # Create new version
        new_version = Department(
            code=current.code,
            business_group=current.business_group,
            name=dto.name or current.name,
            location_id=dto.location_id or current.location_id,
            parent_id=dto.parent_id if dto.parent_id is not None else current.parent_id,
            effective_start_date=effective_date
        )
        
        new_version.full_clean()
        new_version.save()
        
        return new_version
    
    @staticmethod
    def _validate_no_circular_reference(parent, child_code):
        """
        Requirement C.4.5: Circular references not allowed
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
        Requirements: C.4.4
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
