from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from HR.work_structures.dtos import GradeCreateDTO, GradeUpdateDTO, GradeRateCreateDTO
from HR.work_structures.models import Grade, GradeRate
from HR.work_structures.security import validate_data_scope_on_create
from datetime import timedelta
from HR.work_structures.models.position import Position

class GradeService:
    
    @staticmethod
    @transaction.atomic
    def create_grade(user, dto: GradeCreateDTO):
        """
        Create grade with validation.
        """
        
        # Validate data scope
        validate_data_scope_on_create(user, dto.business_group_id)
        
        # Create grade
        grade = Grade(
            code=dto.code,
            name=dto.name,
            business_group_id=dto.business_group_id,
            effective_start_date=dto.effective_start_date or timezone.now().date(),
            effective_end_date=dto.effective_end_date
        )
        
        grade.full_clean()
        grade.save()
        
        return grade

    @staticmethod
    @transaction.atomic
    def update_grade(user, dto: GradeUpdateDTO):
        """
        Update grade.
        - If new_start_date == current.effective_start_date: Correct current record.
        - Otherwise: End-date current record and create new version.
        """
        current = Grade.objects.active().filter(code=dto.code).first()
        if not current:
            raise ValidationError("No active grade found")
            
        validate_data_scope_on_create(user, current.business_group_id)
        
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
            if is_provided('effective_end_date'):
                current.effective_end_date = dto.effective_end_date
            
            current.full_clean()
            current.save()
            return current
        
        # Different day = New Version
        # Capture original end date before modifying current
        original_end_date = current.effective_end_date
        
        # End-date the current version
        current.effective_end_date = new_start_date - timedelta(days=1)
        current.save()
        
        # Create new version
        new_version = Grade(
            code=current.code,
            business_group=current.business_group,
            name=dto.name if is_provided('name') else current.name,
            effective_start_date=new_start_date,
            effective_end_date=dto.effective_end_date if is_provided('effective_end_date') else original_end_date
        )
        
        new_version.full_clean()
        new_version.save()
        
        return new_version
    
    @staticmethod
    @transaction.atomic
    def create_grade_rate(user, dto: GradeRateCreateDTO):
        """
        Create grade rate level with validation.
        """
        
        # Get grade and validate scope
        grade = Grade.objects.get(pk=dto.grade_id)
        validate_data_scope_on_create(user, grade.business_group_id)
        
        # Create grade rate level
        rate = GradeRate(
            grade_id=dto.grade_id,
            rate_type_id=dto.rate_type_id,
            min_amount=dto.min_amount,
            max_amount=dto.max_amount,
            fixed_amount=dto.fixed_amount,
            currency=dto.currency,
            effective_start_date=dto.effective_start_date or timezone.now().date(),
            effective_end_date=dto.effective_end_date
        )
        
        rate.full_clean()
        rate.save()
        
        return rate
    
    @staticmethod
    @transaction.atomic
    def update_grade_rate(user, rate_id, updates):
        """
        Update grade rate level.
        - If effective_start_date == old_rate.effective_start_date: Correct current record.
        - Otherwise: End-date old record and create new version.
        """
        from datetime import timedelta, date
        from django.utils.dateparse import parse_date
        
        # Get existing rate and validate scope
        old_rate = GradeRate.objects.select_related('grade').get(pk=rate_id)
        validate_data_scope_on_create(user, old_rate.grade.business_group_id)
        
        # Determine effective date for new version
        # If effective_start_date is not provided, keep the original date (correction mode)
        effective_start_date_raw = updates.get('effective_start_date')
        if effective_start_date_raw is not None:
            if isinstance(effective_start_date_raw, str):
                effective_start_date = parse_date(effective_start_date_raw)
            else:
                effective_start_date = effective_start_date_raw
            
            if not effective_start_date:
                effective_start_date = timezone.now().date()
        else:
            # No effective_start_date provided = correction mode (keep original date)
            effective_start_date = old_rate.effective_start_date

        # Same-day update = Correction
        # Correction mode: effective_start_date not provided OR equals current date
        if effective_start_date == old_rate.effective_start_date:
            # Match serializer field names to model fields
            field_map = {
                'rate_type': 'rate_type_id',
                'min_amount': 'min_amount',
                'max_amount': 'max_amount',
                'fixed_amount': 'fixed_amount',
                'currency': 'currency',
                'effective_end_date': 'effective_end_date'
            }
            for api_field, model_field in field_map.items():
                if api_field in updates:
                    setattr(old_rate, model_field, updates[api_field])
                elif model_field in updates:
                    setattr(old_rate, model_field, updates[model_field])
            
            old_rate.full_clean()
            old_rate.save()
            return old_rate
        
        # Different day = New Version
        # Capture original end date
        original_end_date = old_rate.effective_end_date
        
        # End-date the old version (only update the end date field)
        old_rate.effective_end_date = effective_start_date - timedelta(days=1)
        old_rate.save(update_fields=['effective_end_date'])
        
        # Create new version with updates
        new_rate = GradeRate(
            grade=old_rate.grade,
            rate_type_id=updates.get('rate_type', updates.get('rate_type_id', old_rate.rate_type_id)),
            min_amount=updates.get('min_amount', old_rate.min_amount),
            max_amount=updates.get('max_amount', old_rate.max_amount),
            fixed_amount=updates.get('fixed_amount', old_rate.fixed_amount),
            currency=updates.get('currency', old_rate.currency),
            effective_start_date=effective_start_date,
            effective_end_date=updates.get('effective_end_date', original_end_date)
        )
        
        new_rate.full_clean()
        new_rate.save()
        
        return new_rate

    @staticmethod
    @transaction.atomic
    def deactivate_grade(user, grade_id, effective_end_date=None):
        grade = Grade.objects.select_related('business_group').get(pk=grade_id)
        validate_data_scope_on_create(user, grade.business_group_id)
        if grade.effective_end_date is not None:
            raise ValidationError("Grade is already inactive")
        active_positions = Position.objects.filter(
            grade=grade,
            effective_end_date__isnull=True
        ).count()
        if active_positions > 0:
            raise ValidationError(
                f"Cannot deactivate grade. {active_positions} active position(s) use this grade."
            )
        grade.deactivate(end_date=effective_end_date)
        return grade
