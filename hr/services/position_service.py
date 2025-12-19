from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from hr.dtos import PositionCreateDTO, PositionUpdateDTO
from hr.models import Position, Department
from hr.security import validate_data_scope_on_create

class PositionService:
    
    @staticmethod
    @transaction.atomic
    def create_position(user, dto: PositionCreateDTO):
        """
        Create position with validation.
        Requirements: C.6, C.7
        """
        
        # Validate department and scope
        department = Department.objects.get(pk=dto.department_id)
        validate_data_scope_on_create(user, department.business_group_id)
        
        # Validate reporting line (C.7)
        if dto.reports_to_id:
            reports_to = Position.objects.filter(
                pk=dto.reports_to_id,
                effective_end_date__isnull=True
            ).first()
            
            if not reports_to:
                raise ValidationError("Reporting position not found or not active")
            
            # C.7.5: Validate no circular reference
            PositionService._validate_no_circular_reporting_line(reports_to, None)
        
        # Create position
        position = Position(
            code=dto.code,
            name=dto.name,
            department_id=dto.department_id,
            location_id=dto.location_id,
            grade_id=dto.grade_id,
            reports_to_id=dto.reports_to_id,
            effective_start_date=dto.effective_start_date or timezone.now().date()
        )
        
        position.full_clean()
        position.save()
        
        return position
    
    @staticmethod
    @transaction.atomic
    def update_position(user, dto: PositionUpdateDTO):
        """
        Update by creating new version (date tracking).
        Requirements: C.6.4
        """
        
        # Get currently active version
        current = Position.objects.filter(
            code=dto.code,
            effective_end_date__isnull=True
        ).first()
        
        if not current:
            raise ValidationError("No active position found")
        
        # Validate scope through department
        department_id = dto.department_id or current.department_id
        department = Department.objects.get(pk=department_id)
        validate_data_scope_on_create(user, department.business_group_id)
        
        effective_date = dto.effective_date or timezone.now().date()
        
        # C.7.5: Validate no circular reporting line before updating
        if dto.reports_to_id:
            reports_to = Position.objects.filter(
                pk=dto.reports_to_id,
                effective_end_date__isnull=True
            ).first()
            if not reports_to:
                raise ValidationError("Reporting position not found or not active")
            
            # Check if current position is an ancestor of the new manager
            PositionService._validate_no_circular_reporting_line(reports_to, current.code)
        
        # End-date current version
        current.effective_end_date = effective_date - timedelta(days=1)
        current.save()
        
        # Create new version
        new_version = Position(
            code=current.code,
            name=dto.name or current.name,
            department_id=dto.department_id or current.department_id,
            location_id=dto.location_id or current.location_id,
            grade_id=dto.grade_id or current.grade_id,
            reports_to_id=dto.reports_to_id if dto.reports_to_id is not None else current.reports_to_id,
            effective_start_date=effective_date
        )
        
        new_version.full_clean()
        new_version.save()
        
        return new_version
    
    @staticmethod
    def get_position_hierarchy(user, business_group_id: int):
        """
        Get reporting hierarchy as tree structure.
        Requirements: C.7.3
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
        """Requirement C.7.5: No circular references"""
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
