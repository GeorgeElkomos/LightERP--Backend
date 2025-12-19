from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from hr.dtos import GradeCreateDTO, GradeRateCreateDTO
from hr.models import Grade, GradeRate
from hr.security import validate_data_scope_on_create


class GradeService:
    
    @staticmethod
    @transaction.atomic
    def create_grade(user, dto: GradeCreateDTO):
        """
        Create grade with validation.
        Requirements: C.8
        """
        
        # Validate data scope
        validate_data_scope_on_create(user, dto.business_group_id)
        
        # Create grade
        grade = Grade(
            code=dto.code,
            name=dto.name,
            business_group_id=dto.business_group_id,
            effective_start_date=dto.effective_start_date or timezone.now().date()
        )
        
        grade.full_clean()
        grade.save()
        
        return grade
    
    @staticmethod
    @transaction.atomic
    def create_grade_rate(user, dto: GradeRateCreateDTO):
        """
        Create grade rate with validation.
        Requirements: C.8
        """
        
        # Get grade and validate scope
        grade = Grade.objects.get(pk=dto.grade_id)
        validate_data_scope_on_create(user, grade.business_group_id)
        
        # Create grade rate
        rate = GradeRate(
            grade_id=dto.grade_id,
            rate_type=dto.rate_type,
            amount=dto.amount,
            currency=dto.currency,
            effective_start_date=dto.effective_start_date or timezone.now().date(),
            effective_end_date=dto.effective_end_date
        )
        
        rate.full_clean()
        rate.save()
        
        return rate
