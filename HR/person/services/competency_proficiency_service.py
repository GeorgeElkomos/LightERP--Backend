from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from datetime import date, timedelta
from typing import List, Optional
from HR.person.dtos import CompetencyProficiencyCreateDTO, CompetencyProficiencyUpdateDTO
from HR.person.models import CompetencyProficiency, Competency, Person
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class CompetencyProficiencyService:
    """Service for CompetencyProficiency business logic"""

    @staticmethod
    @transaction.atomic
    def create(user, dto: CompetencyProficiencyCreateDTO) -> CompetencyProficiency:
        """
        Create new competency proficiency record with validation.

        Validates:
        - Person exists
        - Competency exists and is active
        - Proficiency level and source lookups are valid and active
        - No future start date
        - effective_end_date >= effective_start_date if provided
        - No overlapping date ranges for same person/competency
        """
        # Validate person exists
        try:
            person = Person.objects.get(pk=dto.person_id)
        except Person.DoesNotExist:
            raise ValidationError({'person_id': 'Person not found'})

        # Validate competency exists and is active
        try:
            competency = Competency.objects.active().get(pk=dto.competency_id)
        except Competency.DoesNotExist:
            raise ValidationError({'competency_id': 'Competency not found or inactive'})

        # Validate proficiency level lookup
        try:
            proficiency_level = LookupValue.objects.get(pk=dto.proficiency_level_id)
            if proficiency_level.lookup_type.name != CoreLookups.PROFICIENCY_LEVEL:
                raise ValidationError({'proficiency_level_id': 'Must be a PROFICIENCY_LEVEL lookup value'})
            if not proficiency_level.is_active:
                raise ValidationError({'proficiency_level_id': f'Proficiency level "{proficiency_level.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'proficiency_level_id': 'Proficiency level lookup not found'})

        # Validate proficiency source lookup
        try:
            proficiency_source = LookupValue.objects.get(pk=dto.proficiency_source_id)
            if proficiency_source.lookup_type.name != CoreLookups.PROFICIENCY_SOURCE:
                raise ValidationError({'proficiency_source_id': 'Must be a PROFICIENCY_SOURCE lookup value'})
            if not proficiency_source.is_active:
                raise ValidationError({'proficiency_source_id': f'Proficiency source "{proficiency_source.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'proficiency_source_id': 'Proficiency source lookup not found'})

        # Determine effective dates
        start_date = dto.effective_start_date
        end_date = dto.effective_end_date

        # Validate no future start date
        if start_date > date.today():
            raise ValidationError({'effective_start_date': 'Start date cannot be in the future'})

        # Validate date range
        if end_date and end_date < start_date:
            raise ValidationError({'effective_end_date': 'End date must be on or after start date'})

        # Check for overlapping records - this is also in model.clean() but we check early
        overlapping = CompetencyProficiency.objects.filter(
            person_id=dto.person_id,
            competency_id=dto.competency_id,
            effective_start_date__lte=(end_date or date.max),
        )

        overlapping = overlapping.filter(
            Q(effective_end_date__isnull=True) |
            Q(effective_end_date__gte=start_date)
        )

        if overlapping.exists():
            existing = overlapping.first()
            raise ValidationError({
                'effective_start_date': (
                    f'Date range overlaps with existing proficiency record '
                    f'from {existing.effective_start_date} to {existing.effective_end_date or "present"}'
                )
            })

        # Create proficiency record
        proficiency = CompetencyProficiency(
            person=person,
            competency=competency,
            proficiency_level=proficiency_level,
            proficiency_source=proficiency_source,
            effective_start_date=start_date,
            effective_end_date=end_date,
            created_by=user,
            updated_by=user
        )
        proficiency.full_clean()
        proficiency.save()
        return proficiency

    @staticmethod
    @transaction.atomic
    def update(user, dto: CompetencyProficiencyUpdateDTO) -> CompetencyProficiency:
        """
        Update existing competency proficiency record.

        Typically used to update proficiency level, source, or end date.
        Uses VersionedMixin.update_version() for consistency.
        """
        try:
            proficiency = CompetencyProficiency.objects.get(pk=dto.proficiency_id)
        except CompetencyProficiency.DoesNotExist:
            raise ValidationError(f"Competency proficiency record with ID {dto.proficiency_id} not found")

        # Build field updates dictionary
        field_updates = {}

        # Validate and prepare proficiency level update
        if dto.proficiency_level_id is not None:
            try:
                proficiency_level = LookupValue.objects.get(pk=dto.proficiency_level_id)
                if proficiency_level.lookup_type.name != CoreLookups.PROFICIENCY_LEVEL:
                    raise ValidationError({'proficiency_level_id': 'Must be a PROFICIENCY_LEVEL lookup value'})
                if not proficiency_level.is_active:
                    raise ValidationError({'proficiency_level_id': f'Proficiency level "{proficiency_level.name}" is inactive'})
                field_updates['proficiency_level'] = proficiency_level
            except LookupValue.DoesNotExist:
                raise ValidationError({'proficiency_level_id': 'Proficiency level lookup not found'})

        # Validate and prepare proficiency source update
        if dto.proficiency_source_id is not None:
            try:
                proficiency_source = LookupValue.objects.get(pk=dto.proficiency_source_id)
                if proficiency_source.lookup_type.name != CoreLookups.PROFICIENCY_SOURCE:
                    raise ValidationError({'proficiency_source_id': 'Must be a PROFICIENCY_SOURCE lookup value'})
                if not proficiency_source.is_active:
                    raise ValidationError({'proficiency_source_id': f'Proficiency source "{proficiency_source.name}" is inactive'})
                field_updates['proficiency_source'] = proficiency_source
            except LookupValue.DoesNotExist:
                raise ValidationError({'proficiency_source_id': 'Proficiency source lookup not found'})

        # Validate and prepare effective dates update
        new_start_date = dto.effective_start_date
        new_end_date = dto.effective_end_date

        if new_start_date is not None:
            if new_start_date > date.today():
                raise ValidationError({'effective_start_date': 'Start date cannot be in the future'})
            
        # Use VersionedMixin.update_version() method
        proficiency.update_version(
            field_updates=field_updates,
            new_start_date=new_start_date,
            new_end_date=new_end_date
        )

        proficiency.updated_by = user
        proficiency.save(update_fields=['updated_by'])
        return proficiency

    @staticmethod
    @transaction.atomic
    def deactivate(user, proficiency_id: int) -> CompetencyProficiency:
        """
        Deactivate (end-date) a competency proficiency record.

        Uses VersionedMixin.deactivate() method.
        """
        try:
            proficiency = CompetencyProficiency.objects.get(pk=proficiency_id)
        except CompetencyProficiency.DoesNotExist:
            raise ValidationError(f"Competency proficiency record with ID {proficiency_id} not found")

        # Use VersionedMixin.deactivate() method
        # End date is exclusive in VersionedMixin, so we use tomorrow to keep it active today
        proficiency.deactivate(end_date=date.today() + timedelta(days=1))
        proficiency.updated_by = user
        proficiency.save(update_fields=['updated_by'])
        return proficiency

    @staticmethod
    def get_proficiencies_by_person(person_id: int) -> List[CompetencyProficiency]:
        """
        Get all competency proficiency records for a person.

        Args:
            person_id: ID of the person

        Returns:
            QuerySet of CompetencyProficiency instances ordered by competency name
        """
        return CompetencyProficiency.objects.filter(
            person_id=person_id
        ).select_related(
            'competency',
            'competency__category',
            'proficiency_level',
            'proficiency_source'
        ).order_by('competency__name', '-effective_start_date')

    @staticmethod
    def get_current_proficiency(person_id: int, competency_id: int, as_of_date: Optional[date] = None) -> Optional[CompetencyProficiency]:
        """
        Get current proficiency for a person/competency as of a specific date.

        Args:
            person_id: ID of the person
            competency_id: ID of the competency
            as_of_date: Date to check (defaults to today)

        Returns:
            CompetencyProficiency instance or None if not found
        """
        check_date = as_of_date or date.today()

        return CompetencyProficiency.objects.active_on(check_date).filter(
            person_id=person_id,
            competency_id=competency_id
        ).select_related(
            'competency',
            'proficiency_level',
            'proficiency_source'
        ).first()

    @staticmethod
    def get_proficiency_history(person_id: int, competency_id: int) -> List[CompetencyProficiency]:
        """
        Get all proficiency records (past and present) for a person/competency.

        Args:
            person_id: ID of the person
            competency_id: ID of the competency

        Returns:
            QuerySet of CompetencyProficiency instances ordered by effective_start_date (newest first)
        """
        return CompetencyProficiency.objects.filter(
            person_id=person_id,
            competency_id=competency_id
        ).select_related(
            'competency',
            'proficiency_level',
            'proficiency_source'
        ).order_by('-effective_start_date')

    @staticmethod
    def get_proficiencies_by_competency(competency_id: int, as_of_date: Optional[date] = None) -> List[CompetencyProficiency]:
        """
        Get all people who have a specific competency as of a date.

        Args:
            competency_id: ID of the competency
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of CompetencyProficiency instances
        """
        check_date = as_of_date or date.today()

        return CompetencyProficiency.objects.active_on(check_date).filter(
            competency_id=competency_id
        ).select_related(
            'person',
            'proficiency_level',
            'proficiency_source'
        ).order_by('person__last_name', 'person__first_name')
