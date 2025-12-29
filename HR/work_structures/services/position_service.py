from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from HR.work_structures.dtos import PositionCreateDTO, PositionUpdateDTO
from HR.work_structures.models import Position, Department, Location
from HR.work_structures.security import validate_data_scope_on_create

class PositionService:
    
    @staticmethod
    @transaction.atomic
    def create_position(user, dto: PositionCreateDTO):
        """
        Create position with validation.
        """
        
        # Validate department and scope
        department = Department.objects.get(pk=dto.department_id)
        
        # Validate scope - user must have access to this department
        validate_data_scope_on_create(
            user, 
            department.business_group_id,
            department_id=department.id
        )
        
        # Validate location belongs to the same business group or is enterprise-level
        location = Location.objects.get(id=dto.location_id)
        business_group = department.business_group
        
        if location.enterprise and not location.business_group:
            # Enterprise-level location - check it belongs to the same enterprise
            if location.enterprise != business_group.enterprise:
                raise ValidationError(
                    f"Location '{location.name}' belongs to enterprise '{location.enterprise.name}', "
                    f"but position's business group (via department) belongs to '{business_group.enterprise.name}'."
                )
        elif location.business_group:
            # Location is BG-specific - must match exactly
            if location.business_group != business_group:
                raise ValidationError(
                    f"Location '{location.name}' belongs to business group '{location.business_group.name}', "
                    f"but position's department is in '{business_group.name}'."
                )
        
        # Validate reporting line
        if dto.reports_to_id:
            reports_to = Position.objects.filter(
                pk=dto.reports_to_id,
                effective_end_date__isnull=True
            ).first()
            
            if not reports_to:
                raise ValidationError("Reporting position not found or not active")
            
            # Validate no circular reference
            PositionService._validate_no_circular_reporting_line(reports_to, None)
        
        # Create position
        position = Position(
            code=dto.code,
            name=dto.name,
            department_id=dto.department_id,
            location_id=dto.location_id,
            grade_id=dto.grade_id,
            reports_to_id=dto.reports_to_id,
            effective_start_date=dto.effective_start_date or timezone.now().date(),
            effective_end_date=dto.effective_end_date
        )
        
        position.full_clean()
        position.save()
        
        return position
    
    @staticmethod
    @transaction.atomic
    def update_position(user, dto: PositionUpdateDTO):
        """
        Update position.
        - If new_start_date == current.effective_start_date: Correct current record.
        - Otherwise: End-date current record and create new version.
        """
        
        # Get currently active version
        current = Position.objects.active().filter(
            code=dto.code
        ).first()
        
        if not current:
            raise ValidationError("No active position found")
        
        # Validate scope through department
        department_id = dto.department_id or current.department_id
        department = Department.objects.get(pk=department_id)
        
        # Validate scope
        validate_data_scope_on_create(
            user, 
            department.business_group_id,
            department_id=department.id
        )
        
        # Validate location if provided
        if dto.location_id:
            location = Location.objects.get(id=dto.location_id)
            business_group = department.business_group
            
            if location.enterprise and not location.business_group:
                if location.enterprise != business_group.enterprise:
                    raise ValidationError(
                        f"Location '{location.name}' belongs to enterprise '{location.enterprise.name}', "
                        f"but position's business group (via department) belongs to '{business_group.enterprise.name}'."
                    )
            elif location.business_group:
                if location.business_group != business_group:
                    raise ValidationError(
                        f"Location '{location.name}' belongs to business group '{location.business_group.name}', "
                        f"but position's department is in '{business_group.name}'."
                    )
        
        # Validate reporting line if provided
        if dto.reports_to_id:
            reports_to = Position.objects.filter(
                pk=dto.reports_to_id,
                effective_end_date__isnull=True
            ).first()
            if not reports_to:
                raise ValidationError("Reporting position not found or not active")
            
            # Check for circular reporting line
            PositionService._validate_no_circular_reporting_line(reports_to, current.code)
        
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
            if is_provided('department_id'):
                current.department_id = dto.department_id
            if is_provided('location_id'):
                current.location_id = dto.location_id
            if is_provided('grade_id'):
                current.grade_id = dto.grade_id
            if is_provided('reports_to_id'):
                current.reports_to_id = dto.reports_to_id
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
        new_version = Position(
            code=current.code,
            name=dto.name if is_provided('name') else current.name,
            department_id=dto.department_id if is_provided('department_id') else current.department_id,
            location_id=dto.location_id if is_provided('location_id') else current.location_id,
            grade_id=dto.grade_id if is_provided('grade_id') else current.grade_id,
            reports_to_id=dto.reports_to_id if is_provided('reports_to_id') else current.reports_to_id,
            effective_start_date=new_start_date,
            effective_end_date=dto.effective_end_date if is_provided('effective_end_date') else original_end_date
        )
        
        new_version.full_clean()
        new_version.save()
        
        return new_version
    
    @staticmethod
    @transaction.atomic
    def deactivate_position(user, position_id, effective_end_date=None):
        """
        Deactivate a position by end-dating it and setting status to inactive.
        
        Args:
            user: User performing the action
            position_id: ID of the position to deactivate
            effective_end_date: Date when deactivation takes effect (defaults to today)
        
        Returns:
            The deactivated position instance
        """
        # Get the position and validate scope
        position = Position.objects.select_related('department__business_group').get(pk=position_id)
        
        # Validate scope - user must have access to position's department
        validate_data_scope_on_create(
            user, 
            position.department.business_group_id,
            department_id=position.department_id
        )
        
        # Check if already inactive
        if position.effective_end_date is not None:
            raise ValidationError("Position is already inactive")
        
        # Check if any active positions report to this one
        active_reports = Position.objects.filter(
            reports_to=position,
            effective_end_date__isnull=True
        ).count()
        
        if active_reports > 0:
            raise ValidationError(
                f"Cannot deactivate position. {active_reports} active position(s) still report to it. "
                "Please reassign or deactivate them first."
            )
        
        # Deactivate using model method (handles date safety)
        position.deactivate(end_date=effective_end_date)
        return position
    
    @staticmethod
    def get_position_hierarchy(user, business_group_id: int):
        """
        Get reporting hierarchy as tree structure.
        """
        
        validate_data_scope_on_create(user, business_group_id)
        
        positions = Position.objects.filter(
            department__business_group_id=business_group_id,
            effective_end_date__isnull=True
        ).select_related('reports_to', 'department')
        
        pos_dict = {p.pk: p for p in positions}
        tree = []
        
        for pos in positions:
            if not pos.reports_to:
                tree.append(PositionService._build_hierarchy_node(pos, pos_dict))
        
        return tree
    
    @staticmethod
    def _build_hierarchy_node(position, pos_dict):
        node = {
            'id': position.pk,
            'code': position.code,
            'name': position.name,
            'department': position.department.name,
            'direct_reports': []
        }
        
        reports = [p for p in pos_dict.values() if p.reports_to_id == position.pk]
        node['direct_reports'] = [
            PositionService._build_hierarchy_node(report, pos_dict)
            for report in reports
        ]
        
        return node
    
    @staticmethod
    def _validate_no_circular_reporting_line(reports_to, position_code):
        """No circular references"""
        if not reports_to:
            return
        
        visited = set()
        current = reports_to
        
        while current:
            if current.code == position_code:
                raise ValidationError(
                    f"Circular reference: {position_code} cannot report to {reports_to.code}"
                )
            
            if current.code in visited:
                raise ValidationError("Circular reference in existing reporting line")
            
            visited.add(current.code)
            current = current.reports_to
