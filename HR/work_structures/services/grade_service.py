from django.db import transaction, models
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import date
from typing import Optional
from HR.work_structures.dtos import (
    GradeCreateDTO, GradeUpdateDTO, 
    GradeRateCreateDTO, GradeRateUpdateDTO,
    GradeRateTypeCreateDTO, GradeRateTypeUpdateDTO
)
from HR.work_structures.models import Grade, Organization, GradeRate, GradeRateType
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class GradeService:
    """Service for Grade business logic"""

    @staticmethod
    def list_grades(filters: dict = None) -> models.QuerySet:
        """
        List grades with flexible filtering.

        Args:
            filters: Dictionary of filters
                - business_group: ID
                - search: Search query string
                - status: 'ALL' (default), 'ACTIVE', or 'INACTIVE'

        Returns:
            QuerySet of Grade objects
        """
        filters = filters or {}
        status_filter = filters.get('status', 'ALL')

        if status_filter == 'ALL':
            queryset = Grade.objects.all()
        elif status_filter == 'INACTIVE':
            queryset = Grade.objects.inactive()
        else:
            queryset = Grade.objects.active()

        queryset = queryset.select_related('organization', 'grade_name').order_by('organization', 'sequence')

        org_filter = filters.get('business_group')
        if org_filter:
            queryset = queryset.filter(organization_id=org_filter)

        search_query = filters.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(grade_name__name__icontains=search_query)
            )

        return queryset

    @staticmethod
    def list_grade_rates(filters: dict = None) -> models.QuerySet:
        """
        List grade rates with flexible filtering.

        Args:
            filters: Dictionary of filters
                - grade_id: ID
                - rate_type_id: ID
                - as_of_date: Date (default today)

        Returns:
            QuerySet of GradeRate objects
        """
        filters = filters or {}
        
        queryset = GradeRate.objects.all().select_related('grade', 'rate_type').order_by('grade__organization_id', 'grade__sequence', 'rate_type__code')
        
        # Date filter (default to ALL if not specified or 'ALL')
        as_of_date = filters.get('as_of_date')
        if as_of_date and as_of_date != 'ALL':
             queryset = queryset.active_on(as_of_date)

        grade_id = filters.get('grade_id')
        if grade_id:
            queryset = queryset.filter(grade_id=grade_id)

        rate_type_id = filters.get('rate_type_id')
        if rate_type_id:
            queryset = queryset.filter(rate_type_id=rate_type_id)

        return queryset

    @staticmethod
    def list_grade_rate_types() -> models.QuerySet:
        """List all grade rate types"""
        return GradeRateType.objects.all().order_by('code')

    @staticmethod
    @transaction.atomic
    def create_grade_rate_type(user, dto: GradeRateTypeCreateDTO) -> GradeRateType:
        """Create new grade rate type"""
        if GradeRateType.objects.filter(code=dto.code).exists():
             raise ValidationError({'code': f'Grade Rate Type with code "{dto.code}" already exists'})
        
        rate_type = GradeRateType(
            code=dto.code,
            description=dto.description,
            created_by=user,
            updated_by=user
        )
        rate_type.full_clean()
        rate_type.save()
        return rate_type

    @staticmethod
    @transaction.atomic
    def update_grade_rate_type(user, dto: GradeRateTypeUpdateDTO) -> GradeRateType:
        """Update existing grade rate type"""
        try:
            rate_type = GradeRateType.objects.get(pk=dto.rate_type_id)
        except GradeRateType.DoesNotExist:
            raise ValidationError(f"Grade Rate Type with ID {dto.rate_type_id} not found")

        if dto.code and dto.code != rate_type.code:
             if GradeRateType.objects.filter(code=dto.code).exclude(pk=dto.rate_type_id).exists():
                 raise ValidationError({'code': f'Grade Rate Type with code "{dto.code}" already exists'})
             rate_type.code = dto.code
        
        if dto.description is not None:
            rate_type.description = dto.description

        rate_type.updated_by = user
        rate_type.save()
        return rate_type

    @staticmethod
    @transaction.atomic
    def delete_grade_rate_type(user, rate_type_id: int):
        """Delete grade rate type"""
        try:
            rate_type = GradeRateType.objects.get(pk=rate_type_id)
        except GradeRateType.DoesNotExist:
            raise ValidationError(f"Grade Rate Type with ID {rate_type_id} not found")
            
        # Check usage in GradeRate
        if rate_type.levels.exists():
             raise ValidationError("Cannot delete Grade Rate Type because it is used in Grade Rates")
             
        rate_type.delete()

    @staticmethod
    def get_next_sequence(organization_id: int) -> int:
        """
        Get the next available sequence number for a business group.

        Args:
            organization_id: ID of the root organization (business group)

        Returns:
            Next available sequence number (starts at 1)
        """
        max_sequence = Grade.objects.active().filter(
            organization_id=organization_id
        ).aggregate(
            models.Max('sequence')
        )['sequence__max']

        return (max_sequence or 0) + 1

    @staticmethod
    @transaction.atomic
    def create(user, dto: GradeCreateDTO) -> Grade:
        """
        Create new grade with validation.

        Validates:
        - Organization exists and is root (business group)
        - Grade name lookup is valid and active
        - Sequence is unique within business group
        - Sequence is positive
        """
        # Validate organization exists and is root
        today = date.today()
        try:
            organization = Organization.objects.active_on(today).get(pk=dto.business_group_id)
            if not organization.is_business_group:
                raise ValidationError({
                    'business_group_id': 'Grade must belong to a root organization (Business Group)'
                })
        except Organization.DoesNotExist:
            raise ValidationError({'business_group_id': 'Organization not found or inactive'})

        # Validate grade name lookup
        try:
            grade_name = LookupValue.objects.get(pk=dto.grade_name_id)
            if grade_name.lookup_type.name != CoreLookups.GRADE_NAME:
                raise ValidationError({'grade_name_id': 'Must be a GRADE_NAME lookup value'})
            if not grade_name.is_active:
                raise ValidationError({'grade_name_id': f'Grade name "{grade_name.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'grade_name_id': 'Grade name lookup not found'})

        # Validate sequence
        if dto.sequence <= 0:
            raise ValidationError({'sequence': 'Sequence must be greater than 0'})

        # Check for duplicate sequence within business group
        if Grade.objects.active().filter(
            organization_id=dto.business_group_id,
            sequence=dto.sequence
        ).exists():
            raise ValidationError({
                'sequence': f'Sequence {dto.sequence} already exists for this business group'
            })

        # Create grade
        grade = Grade(
            organization=organization,
            sequence=dto.sequence,
            grade_name=grade_name,
            effective_from=dto.effective_from,
            created_by=user,
            updated_by=user
        )
        grade.full_clean()
        grade.save()
        return grade

    @staticmethod
    @transaction.atomic
    def update(user, dto: GradeUpdateDTO) -> Grade:
        """
        Update existing grade.

        Uses SoftDeleteMixin.update_fields() for consistent update pattern.

        Validates:
        - Grade exists and is active
        - If grade name updated, validates lookup
        - If sequence updated, validates uniqueness and positive value
        """
        try:
            grade = Grade.objects.active().get(pk=dto.grade_id)
        except Grade.DoesNotExist:
            raise ValidationError(f"No active grade found with ID '{dto.grade_id}'")

        # Build field updates dictionary
        field_updates = {}

        # Validate and prepare grade name update
        if dto.grade_name_id is not None:
            try:
                grade_name = LookupValue.objects.get(pk=dto.grade_name_id)
                if grade_name.lookup_type.name != CoreLookups.GRADE_NAME:
                    raise ValidationError({'grade_name_id': 'Must be a GRADE_NAME lookup value'})
                if not grade_name.is_active:
                    raise ValidationError({'grade_name_id': f'Grade name "{grade_name.name}" is inactive'})
                field_updates['grade_name'] = grade_name
            except LookupValue.DoesNotExist:
                raise ValidationError({'grade_name_id': 'Grade name lookup not found'})

        # Validate and prepare sequence update
        if dto.sequence is not None:
            if dto.sequence <= 0:
                raise ValidationError({'sequence': 'Sequence must be greater than 0'})

            # Check for duplicate sequence (excluding current grade)
            if Grade.objects.active().filter(
                organization_id=grade.organization_id,
                sequence=dto.sequence
            ).exclude(pk=grade.pk).exists():
                raise ValidationError({
                    'sequence': f'Sequence {dto.sequence} already exists for this business group'
                })

            field_updates['sequence'] = dto.sequence

        # Use SoftDeleteMixin.update_fields() method
        if field_updates:
            grade.update_fields(field_updates)

        grade.updated_by = user
        grade.save(update_fields=['updated_by'])
        return grade

    @staticmethod
    @transaction.atomic
    def deactivate(user, grade_id: int) -> Grade:
        """
        Deactivate (soft delete) a grade.

        Uses SoftDeleteMixin.deactivate() method.

        Args:
            user: User performing deactivation
            grade_id: Grade ID

        Returns:
            Deactivated grade
        """
        try:
            grade = Grade.objects.active().get(pk=grade_id)
        except Grade.DoesNotExist:
            raise ValidationError(f"No active grade found with ID '{grade_id}'")

        # Dependency Checks
        today = date.today()

        # 1. Check active Positions
        from HR.work_structures.models import Position
        # Position is versioned, so use active_on(today)
        pos_count = Position.objects.active_on(today).filter(
            grade_id=grade.id
        ).count()
        if pos_count > 0:
            raise ValidationError(
                f"Cannot deactivate Grade '{str(grade)}' because it is used by {pos_count} active positions."
            )

        # 2. Check active Jobs (M2M)
        # Job is versioned
        from HR.work_structures.models import Job
        job_count = Job.objects.active_on(today).filter(
            grades=grade
        ).count()
        if job_count > 0:
            raise ValidationError(
                f"Cannot deactivate Grade '{str(grade)}' because it is used by {job_count} active jobs."
            )

        # 3. Check active Assignments
        from HR.person.models import Assignment
        # Assignment is versioned
        assign_count = Assignment.objects.active_on(today).filter(
            grade_id=grade.id
        ).count()
        if assign_count > 0:
            raise ValidationError(
                f"Cannot deactivate Grade '{str(grade)}' because it is used by {assign_count} active employee assignments."
            )

        # Use SoftDeleteMixin.deactivate() method
        grade.deactivate()
        grade.updated_by = user
        grade.save(update_fields=['updated_by'])
        return grade

    @staticmethod
    def get_grades_by_organization(organization_id: int):
        """
        Get all active grades for a business group, ordered by sequence.

        Args:
            organization_id: ID of the root organization (business group)

        Returns:
            QuerySet of Grade instances ordered by sequence
        """
        return Grade.objects.active().filter(
            organization_id=organization_id
        ).select_related('organization', 'grade_name').order_by('sequence')

    @staticmethod
    def get_grade_by_sequence(organization_id: int, sequence: int) -> Optional[Grade]:
        """
        Get a grade by organization and sequence.

        Args:
            organization_id: ID of the root organization
            sequence: Sequence number

        Returns:
            Grade instance or None if not found
        """
        return Grade.objects.active().filter(
            organization_id=organization_id,
            sequence=sequence
        ).select_related('organization', 'grade_name').first()

    # ===== GradeRate Service Methods =====

    @staticmethod
    @transaction.atomic
    def create_grade_rate(user, dto: GradeRateCreateDTO) -> GradeRate:
        """
        Create new grade rate with validation.

        Validates:
        - Grade exists and is active
        - Rate type exists
        - Amount values match rate type configuration (range vs fixed)
        - No duplicate active rate for same grade+rate_type combination
        """
        today = date.today()

        # Validate grade exists and is active
        try:
            grade = Grade.objects.active().get(pk=dto.grade_id)
        except Grade.DoesNotExist:
            raise ValidationError({'grade_id': 'Grade not found or inactive'})

        # Validate rate type exists
        try:
            rate_type = GradeRateType.objects.get(pk=dto.rate_type_id)
        except GradeRateType.DoesNotExist:
            raise ValidationError({'rate_type_id': 'Rate type not found'})

        # Check for duplicate active rate (same grade + rate type)
        effective_start = dto.effective_start_date or today
        existing = GradeRate.objects.active_on(effective_start).filter(
            grade_id=dto.grade_id,
            rate_type_id=dto.rate_type_id
        ).exists()

        if existing:
            raise ValidationError({
                'grade_id': f'An active rate already exists for {grade.grade_name.name} - {rate_type.code} on {effective_start}'
            })

        # Create grade rate
        grade_rate = GradeRate(
            grade=grade,
            rate_type=rate_type,
            min_amount=dto.min_amount,
            max_amount=dto.max_amount,
            fixed_amount=dto.fixed_amount,
            currency_id=dto.currency_id,
            effective_start_date=effective_start,
            effective_end_date=dto.effective_end_date,
            created_by=user,
            updated_by=user
        )

        # Model's clean() method will validate range vs fixed logic
        grade_rate.full_clean()
        grade_rate.save()
        return grade_rate

    @staticmethod
    @transaction.atomic
    def update_grade_rate(user, dto: GradeRateUpdateDTO) -> GradeRate:
        """
        Update existing grade rate (creates new version).

        Uses VersionedMixin.update_version() for temporal versioning.

        Validates:
        - Current grade rate exists and is active
        - If provided, amount values match rate type configuration
        """
        today = date.today()

        # Find current active version for this grade + rate_type combination
        try:
            current = GradeRate.objects.active_on(today).get(
                grade_id=dto.grade_id,
                rate_type_id=dto.rate_type_id
            )
        except GradeRate.DoesNotExist:
            raise ValidationError(
                f"No active grade rate found for grade_id={dto.grade_id} and rate_type_id={dto.rate_type_id}"
            )

        # Build field updates dictionary
        field_updates = {}

        if dto.min_amount is not None:
            field_updates['min_amount'] = dto.min_amount
        if dto.max_amount is not None:
            field_updates['max_amount'] = dto.max_amount
        if dto.fixed_amount is not None:
            field_updates['fixed_amount'] = dto.fixed_amount
        if dto.currency_id is not None:
            field_updates['currency_id'] = dto.currency_id

        # Handle switching between fixed amount and range amounts
        # If switching to fixed amount, clear min/max if not provided
        if dto.fixed_amount is not None:
            if dto.min_amount is None:
                field_updates['min_amount'] = None
            if dto.max_amount is None:
                field_updates['max_amount'] = None
        
        # If switching to range amounts, clear fixed if not provided
        if dto.min_amount is not None or dto.max_amount is not None:
            if dto.fixed_amount is None:
                field_updates['fixed_amount'] = None

        # Use VersionedMixin.update_version()
        # If new_start_date provided, creates new version; otherwise correction mode
        updated = current.update_version(
            field_updates=field_updates,
            new_start_date=dto.new_start_date,
            new_end_date=dto.effective_end_date
        )

        updated.updated_by = user
        updated.save(update_fields=['updated_by'])
        return updated

    @staticmethod
    @transaction.atomic
    def delete_grade_rate(user, grade_rate_id: int):
        """
        Delete a specific grade rate version (row).
        Note: Since it's versioned, this deletes the specific version.
        """
        try:
            rate = GradeRate.objects.get(pk=grade_rate_id)
        except GradeRate.DoesNotExist:
            raise ValidationError(f"Grade Rate with ID {grade_rate_id} not found")
            
        rate.delete()

    @staticmethod
    def get_grade_rates(grade_id: int, active_only: bool = True):
        """
        Get all rates for a specific grade.

        Args:
            grade_id: ID of the grade
            active_only: If True, return only currently active rates

        Returns:
            QuerySet of GradeRate instances
        """
        queryset = GradeRate.objects.filter(grade_id=grade_id)
        if active_only:
            queryset = queryset.active()
        return queryset.select_related('grade', 'rate_type').order_by('rate_type__name')

    @staticmethod
    def get_grade_rate_by_type(grade_id: int, rate_type_id: int, as_of_date: Optional[date] = None) -> Optional[GradeRate]:
        """
        Get a specific grade rate by grade and rate type.

        Args:
            grade_id: ID of the grade
            rate_type_id: ID of the rate type
            as_of_date: Date to check for active version (defaults to today)

        Returns:
            GradeRate instance or None if not found
        """
        as_of = as_of_date or date.today()
        return GradeRate.objects.active_on(as_of).filter(
            grade_id=grade_id,
            rate_type_id=rate_type_id
        ).select_related('grade', 'rate_type').first()

    @staticmethod
    def get_all_rates_for_grade(grade_id: int, as_of_date: Optional[date] = None):
        """
        Get all active rate types with their amounts for a specific grade.

        Args:
            grade_id: ID of the grade
            as_of_date: Date to check for active versions (defaults to today)

        Returns:
            QuerySet of GradeRate instances for all rate types
        """
        as_of = as_of_date or date.today()
        return GradeRate.objects.active_on(as_of).filter(
            grade_id=grade_id
        ).select_related('grade', 'rate_type').order_by('rate_type__code')

