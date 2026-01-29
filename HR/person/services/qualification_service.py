from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date
from typing import List, Optional
from decimal import Decimal
from HR.person.dtos import QualificationCreateDTO, QualificationUpdateDTO
from HR.person.models import Qualification, Person, Competency
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class QualificationService:
    """Service for Qualification business logic"""

    @staticmethod
    @transaction.atomic
    def create(user, dto: QualificationCreateDTO) -> Qualification:
        """
        Create new qualification with status-based validation.

        Validates:
        - Person exists
        - All lookup values are valid and active
        - Status-specific requirements (Completed vs In Progress)
        - Date relationships
        - Tuition fees with currency
        """
        # Validate person exists
        try:
            person = Person.objects.get(pk=dto.person_id)
        except Person.DoesNotExist:
            raise ValidationError({'person_id': 'Person not found'})

        # Validate qualification type
        try:
            qual_type = LookupValue.objects.get(pk=dto.qualification_type_id)
            if qual_type.lookup_type.name != CoreLookups.QUALIFICATION_TYPE:
                raise ValidationError({'qualification_type_id': 'Must be a QUALIFICATION_TYPE lookup value'})
            if not qual_type.is_active:
                raise ValidationError({'qualification_type_id': f'Qualification type "{qual_type.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'qualification_type_id': 'Qualification type not found'})

        # Validate qualification title
        try:
            qual_title = LookupValue.objects.get(pk=dto.qualification_title_id)
            if qual_title.lookup_type.name != CoreLookups.QUALIFICATION_TITLE:
                raise ValidationError({'qualification_title_id': 'Must be a QUALIFICATION_TITLE lookup value'})
            if not qual_title.is_active:
                raise ValidationError({'qualification_title_id': f'Qualification title "{qual_title.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'qualification_title_id': 'Qualification title not found'})

        # Validate qualification status
        try:
            qual_status = LookupValue.objects.get(pk=dto.qualification_status_id)
            if qual_status.lookup_type.name != CoreLookups.QUALIFICATION_STATUS:
                raise ValidationError({'qualification_status_id': 'Must be a QUALIFICATION_STATUS lookup value'})
            if not qual_status.is_active:
                raise ValidationError({'qualification_status_id': f'Status "{qual_status.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'qualification_status_id': 'Qualification status not found'})

        # Validate awarding entity
        try:
            awarding_entity = LookupValue.objects.get(pk=dto.awarding_entity_id)
            if awarding_entity.lookup_type.name != CoreLookups.AWARDING_ENTITY:
                raise ValidationError({'awarding_entity_id': 'Must be an AWARDING_ENTITY lookup value'})
            if not awarding_entity.is_active:
                raise ValidationError({'awarding_entity_id': f'Awarding entity "{awarding_entity.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'awarding_entity_id': 'Awarding entity not found'})

        # Validate tuition method if provided
        tuition_method = None
        if dto.tuition_method_id:
            try:
                tuition_method = LookupValue.objects.get(pk=dto.tuition_method_id)
                if tuition_method.lookup_type.name != CoreLookups.TUITION_METHOD:
                    raise ValidationError({'tuition_method_id': 'Must be a TUITION_METHOD lookup value'})
                if not tuition_method.is_active:
                    raise ValidationError({'tuition_method_id': f'Tuition method "{tuition_method.name}" is inactive'})
            except LookupValue.DoesNotExist:
                raise ValidationError({'tuition_method_id': 'Tuition method not found'})

        # Validate currency if provided
        currency = None
        if dto.tuition_fees_currency_id:
            try:
                currency = LookupValue.objects.get(pk=dto.tuition_fees_currency_id)
                if currency.lookup_type.name != CoreLookups.CURRENCY:
                    raise ValidationError({'tuition_fees_currency_id': 'Must be a CURRENCY lookup value'})
                if not currency.is_active:
                    raise ValidationError({'tuition_fees_currency_id': f'Currency "{currency.name}" is inactive'})
            except LookupValue.DoesNotExist:
                raise ValidationError({'tuition_fees_currency_id': 'Currency not found'})

        # Validate competencies if provided
        competencies = []
        if dto.competency_achieved_ids:
            for comp_id in dto.competency_achieved_ids:
                try:
                    comp = Competency.objects.active().get(pk=comp_id)
                    competencies.append(comp)
                except Competency.DoesNotExist:
                    raise ValidationError({'competency_achieved_ids': f'Competency with ID {comp_id} not found or inactive'})

        # Create qualification
        qualification = Qualification(
            person=person,
            qualification_type=qual_type,
            qualification_title=qual_title,
            title_if_others=dto.title_if_others or '',
            qualification_status=qual_status,
            grade=dto.grade or '',
            awarding_entity=awarding_entity,
            awarded_date=dto.awarded_date,
            projected_completion_date=dto.projected_completion_date,
            completed_percentage=dto.completed_percentage,
            study_start_date=dto.study_start_date,
            study_end_date=dto.study_end_date,
            tuition_method=tuition_method,
            tuition_fees=Decimal(str(dto.tuition_fees)) if dto.tuition_fees else None,
            tuition_fees_currency=currency,
            remarks=dto.remarks or '',
            effective_start_date=dto.effective_start_date or date.today(),
            created_by=user,
            updated_by=user
        )
        qualification.full_clean()
        qualification.save()

        # Set M2M competencies
        if competencies:
            qualification.competency_achieved.set(competencies)

        return qualification

    @staticmethod
    @transaction.atomic
    def update(user, dto: QualificationUpdateDTO) -> Qualification:
        """
        Update existing qualification.

        Uses SoftDeleteMixin.update_fields() for consistency.
        """
        try:
            qualification = Qualification.objects.active().get(pk=dto.qualification_id)
        except Qualification.DoesNotExist:
            raise ValidationError(f"Qualification with ID {dto.qualification_id} not found")

        # Build field updates dictionary
        field_updates = {}

        # Validate and prepare qualification type update
        if dto.qualification_type_id is not None:
            try:
                qual_type = LookupValue.objects.get(pk=dto.qualification_type_id)
                if qual_type.lookup_type.name != CoreLookups.QUALIFICATION_TYPE:
                    raise ValidationError({'qualification_type_id': 'Must be a QUALIFICATION_TYPE lookup value'})
                if not qual_type.is_active:
                    raise ValidationError({'qualification_type_id': f'Qualification type "{qual_type.name}" is inactive'})
                field_updates['qualification_type'] = qual_type
            except LookupValue.DoesNotExist:
                raise ValidationError({'qualification_type_id': 'Qualification type not found'})

        # Validate and prepare qualification title update
        if dto.qualification_title_id is not None:
            try:
                qual_title = LookupValue.objects.get(pk=dto.qualification_title_id)
                if qual_title.lookup_type.name != CoreLookups.QUALIFICATION_TITLE:
                    raise ValidationError({'qualification_title_id': 'Must be a QUALIFICATION_TITLE lookup value'})
                if not qual_title.is_active:
                    raise ValidationError({'qualification_title_id': f'Qualification title "{qual_title.name}" is inactive'})
                field_updates['qualification_title'] = qual_title
            except LookupValue.DoesNotExist:
                raise ValidationError({'qualification_title_id': 'Qualification title not found'})

        # Validate and prepare status update
        if dto.qualification_status_id is not None:
            try:
                qual_status = LookupValue.objects.get(pk=dto.qualification_status_id)
                if qual_status.lookup_type.name != CoreLookups.QUALIFICATION_STATUS:
                    raise ValidationError({'qualification_status_id': 'Must be a QUALIFICATION_STATUS lookup value'})
                if not qual_status.is_active:
                    raise ValidationError({'qualification_status_id': f'Status "{qual_status.name}" is inactive'})
                field_updates['qualification_status'] = qual_status
            except LookupValue.DoesNotExist:
                raise ValidationError({'qualification_status_id': 'Qualification status not found'})

        # Validate and prepare awarding entity update
        if dto.awarding_entity_id is not None:
            try:
                awarding_entity = LookupValue.objects.get(pk=dto.awarding_entity_id)
                if awarding_entity.lookup_type.name != CoreLookups.AWARDING_ENTITY:
                    raise ValidationError({'awarding_entity_id': 'Must be an AWARDING_ENTITY lookup value'})
                if not awarding_entity.is_active:
                    raise ValidationError({'awarding_entity_id': f'Awarding entity "{awarding_entity.name}" is inactive'})
                field_updates['awarding_entity'] = awarding_entity
            except LookupValue.DoesNotExist:
                raise ValidationError({'awarding_entity_id': 'Awarding entity not found'})

        # Simple field updates
        if dto.title_if_others is not None:
            field_updates['title_if_others'] = dto.title_if_others
        if dto.grade is not None:
            field_updates['grade'] = dto.grade
        if dto.awarded_date is not None:
            field_updates['awarded_date'] = dto.awarded_date
        if dto.projected_completion_date is not None:
            field_updates['projected_completion_date'] = dto.projected_completion_date
        if dto.completed_percentage is not None:
            field_updates['completed_percentage'] = dto.completed_percentage
        if dto.study_start_date is not None:
            field_updates['study_start_date'] = dto.study_start_date
        if dto.study_end_date is not None:
            field_updates['study_end_date'] = dto.study_end_date
        if dto.tuition_fees is not None:
            field_updates['tuition_fees'] = Decimal(str(dto.tuition_fees))
        if dto.remarks is not None:
            field_updates['remarks'] = dto.remarks
        if dto.effective_end_date is not None:
            field_updates['effective_end_date'] = dto.effective_end_date

        # Validate and prepare tuition method update
        if dto.tuition_method_id is not None:
            try:
                tuition_method = LookupValue.objects.get(pk=dto.tuition_method_id)
                if tuition_method.lookup_type.name != CoreLookups.TUITION_METHOD:
                    raise ValidationError({'tuition_method_id': 'Must be a TUITION_METHOD lookup value'})
                if not tuition_method.is_active:
                    raise ValidationError({'tuition_method_id': f'Tuition method "{tuition_method.name}" is inactive'})
                field_updates['tuition_method'] = tuition_method
            except LookupValue.DoesNotExist:
                raise ValidationError({'tuition_method_id': 'Tuition method not found'})

        # Validate and prepare currency update
        if dto.tuition_fees_currency_id is not None:
            try:
                currency = LookupValue.objects.get(pk=dto.tuition_fees_currency_id)
                if currency.lookup_type.name != CoreLookups.CURRENCY:
                    raise ValidationError({'tuition_fees_currency_id': 'Must be a CURRENCY lookup value'})
                if not currency.is_active:
                    raise ValidationError({'tuition_fees_currency_id': f'Currency "{currency.name}" is inactive'})
                field_updates['tuition_fees_currency'] = currency
            except LookupValue.DoesNotExist:
                raise ValidationError({'tuition_fees_currency_id': 'Currency not found'})

        # Use SoftDeleteMixin.update_fields() method
        if field_updates:
            qualification.update_fields(field_updates)

        # Handle M2M competencies separately
        if dto.competency_achieved_ids is not None:
            competencies = []
            for comp_id in dto.competency_achieved_ids:
                try:
                    comp = Competency.objects.active().get(pk=comp_id)
                    competencies.append(comp)
                except Competency.DoesNotExist:
                    raise ValidationError({'competency_achieved_ids': f'Competency with ID {comp_id} not found or inactive'})
            qualification.competency_achieved.set(competencies)

        qualification.updated_by = user
        qualification.save(update_fields=['updated_by'])
        return qualification

    @staticmethod
    @transaction.atomic
    def deactivate(user, qualification_id: int) -> Qualification:
        """
        Deactivate (soft delete) a qualification.

        Uses SoftDeleteMixin.deactivate() method.
        """
        try:
            qualification = Qualification.objects.active().get(pk=qualification_id)
        except Qualification.DoesNotExist:
            raise ValidationError(f"Qualification with ID {qualification_id} not found")

        # Use SoftDeleteMixin.deactivate() method
        qualification.deactivate()
        qualification.updated_by = user
        qualification.save(update_fields=['updated_by'])
        return qualification

    @staticmethod
    def get_qualifications_by_person(person_id: int) -> List[Qualification]:
        """
        Get all active qualifications for a person.

        Args:
            person_id: ID of the person

        Returns:
            QuerySet of Qualification instances ordered by effective_start_date (newest first)
        """
        return Qualification.objects.active().filter(
            person_id=person_id
        ).select_related(
            'qualification_type',
            'qualification_title',
            'qualification_status',
            'awarding_entity',
            'tuition_method',
            'tuition_fees_currency'
        ).prefetch_related('competency_achieved').order_by('-effective_start_date')

    @staticmethod
    def get_completed_qualifications(person_id: int) -> List[Qualification]:
        """
        Get all completed qualifications for a person.

        Args:
            person_id: ID of the person

        Returns:
            QuerySet of completed Qualification instances
        """
        return Qualification.objects.active().filter(
            person_id=person_id,
            qualification_status__name='Completed'
        ).select_related(
            'qualification_type',
            'qualification_title',
            'qualification_status',
            'awarding_entity'
        ).prefetch_related('competency_achieved').order_by('-awarded_date')

    @staticmethod
    def get_in_progress_qualifications(person_id: int) -> List[Qualification]:
        """
        Get all in-progress qualifications for a person.

        Args:
            person_id: ID of the person

        Returns:
            QuerySet of in-progress Qualification instances
        """
        return Qualification.objects.active().filter(
            person_id=person_id,
            qualification_status__name='In Progress'
        ).select_related(
            'qualification_type',
            'qualification_title',
            'qualification_status',
            'awarding_entity'
        ).prefetch_related('competency_achieved').order_by('-projected_completion_date')

    @staticmethod
    def get_qualifications_by_type(qualification_type_name: str) -> List[Qualification]:
        """
        Get all active qualifications of a specific type.

        Args:
            qualification_type_name: Name of the QUALIFICATION_TYPE lookup

        Returns:
            QuerySet of Qualification instances
        """
        return Qualification.objects.active().filter(
            qualification_type__name=qualification_type_name
        ).select_related(
            'person',
            'qualification_type',
            'qualification_title',
            'qualification_status',
            'awarding_entity'
        ).order_by('person__last_name', 'person__first_name')

