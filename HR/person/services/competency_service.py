from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from datetime import date
from typing import List, Optional
from HR.person.dtos import CompetencyCreateDTO, CompetencyUpdateDTO
from HR.person.models import Competency
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class CompetencyService:
    """Service for Competency business logic"""

    @staticmethod
    @transaction.atomic
    def create(user, dto: CompetencyCreateDTO) -> Competency:
        """
        Create new competency with validation.

        Validates:
        - Code is unique
        - Name is not empty
        - Category lookup is valid and active
        """
        # Validate code uniqueness
        if Competency.objects.filter(code=dto.code).exists():
            raise ValidationError({'code': f'Competency with code "{dto.code}" already exists'})

        # Validate category lookup
        try:
            category = LookupValue.objects.get(pk=dto.competency_category_id)
            if category.lookup_type.name != CoreLookups.COMPETENCY_CATEGORY:
                raise ValidationError({'competency_category_id': 'Must be a COMPETENCY_CATEGORY lookup value'})
            if not category.is_active:
                raise ValidationError({'competency_category_id': f'Category "{category.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'competency_category_id': 'Category lookup not found'})

        # Create competency
        competency = Competency(
            code=dto.code,
            name=dto.name,
            description=dto.description or '',
            category=category,
            created_by=user,
            updated_by=user
        )
        competency.full_clean()
        competency.save()
        return competency

    @staticmethod
    @transaction.atomic
    def update(user, dto: CompetencyUpdateDTO) -> Competency:
        """
        Update existing competency.

        Uses SoftDeleteMixin.update_fields() for consistent update pattern.
        """
        try:
            competency = Competency.objects.active().get(code=dto.code)
        except Competency.DoesNotExist:
            raise ValidationError(f"No active competency found with code '{dto.code}'")

        # Build field updates dictionary
        field_updates = {}

        if dto.name is not None:
            field_updates['name'] = dto.name

        if dto.description is not None:
            field_updates['description'] = dto.description

        # Validate and prepare category update
        if dto.competency_category_id is not None:
            try:
                category = LookupValue.objects.get(pk=dto.competency_category_id)
                if category.lookup_type.name != CoreLookups.COMPETENCY_CATEGORY:
                    raise ValidationError({'competency_category_id': 'Must be a COMPETENCY_CATEGORY lookup value'})
                if not category.is_active:
                    raise ValidationError({'competency_category_id': f'Category "{category.name}" is inactive'})
                field_updates['category'] = category
            except LookupValue.DoesNotExist:
                raise ValidationError({'competency_category_id': 'Category lookup not found'})

        # Use SoftDeleteMixin.update_fields() method
        if field_updates:
            competency.update_fields(field_updates)

        competency.updated_by = user
        competency.save(update_fields=['updated_by'])
        return competency

    @staticmethod
    @transaction.atomic
    def deactivate(user, code: str) -> Competency:
        """
        Deactivate (soft delete) a competency.

        Uses SoftDeleteMixin.deactivate() method.

        Checks dependencies:
        - Job requirements
        - Position requirements
        - Active competency proficiency records
        - Linked qualifications
        """
        try:
            competency = Competency.objects.active().get(code=code)
        except Competency.DoesNotExist:
            raise ValidationError(f"No active competency found with code '{code}'")

        # Check Job Requirements
        if competency.job_requirements.exists():
            raise ValidationError(f"Cannot deactivate competency '{code}': It is required by one or more Jobs.")

        # Check Position Requirements
        if competency.position_requirements.exists():
            raise ValidationError(f"Cannot deactivate competency '{code}': It is required by one or more Positions.")

        # Check Active Competency Proficiencies
        if competency.proficiencies.all().active_on(date.today()).exists():
            raise ValidationError(f"Cannot deactivate competency '{code}': It is assigned to one or more Persons (active proficiency records).")

        # Check Active Qualifications
        if competency.qualifications.all().active().exists():
            raise ValidationError(f"Cannot deactivate competency '{code}': It is linked to one or more active Qualifications.")

        # Use SoftDeleteMixin.deactivate() method
        competency.deactivate()
        competency.updated_by = user
        competency.save(update_fields=['updated_by'])
        return competency

    @staticmethod
    def get_competencies_by_category(category_name: str) -> List[Competency]:
        """
        Get all active competencies in a specific category.

        Args:
            category_name: Name of the COMPETENCY_CATEGORY lookup value

        Returns:
            QuerySet of Competency instances
        """
        return Competency.objects.active().filter(
            category__name=category_name
        ).select_related('category').order_by('name')

    @staticmethod
    def search_competencies(search_term: str) -> List[Competency]:
        """
        Search competencies by code, name, or description.

        Args:
            search_term: Search string (case-insensitive)

        Returns:
            QuerySet of Competency instances matching search
        """
        if not search_term:
            return Competency.objects.active().select_related('category').order_by('name')

        return Competency.objects.active().filter(
            Q(code__icontains=search_term) |
            Q(name__icontains=search_term) |
            Q(description__icontains=search_term)
        ).select_related('category').order_by('name')

    @staticmethod
    def get_competency_by_code(code: str) -> Optional[Competency]:
        """
        Get a competency by code.

        Args:
            code: Competency code

        Returns:
            Competency instance or None if not found
        """
        return Competency.objects.active().filter(code=code).select_related('category').first()

    @staticmethod
    def get_all_competencies() -> List[Competency]:
        """
        Get all active competencies.

        Returns:
            QuerySet of all active Competency instances ordered by category and name
        """
        return Competency.objects.active().select_related('category').order_by('category__name', 'name')

