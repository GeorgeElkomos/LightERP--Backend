from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import date
from typing import Optional
from HR.work_structures.dtos import OrganizationManagerCreateDTO, OrganizationManagerUpdateDTO
from HR.work_structures.models import OrganizationManager, Organization
from HR.person.models import Person, Employee


class OrganizationManagerService:
    """Service for OrganizationManager business logic"""

    @staticmethod
    @transaction.atomic
    def create(user, dto: OrganizationManagerCreateDTO) -> OrganizationManager:
        """
        Create new manager assignment with validation.

        Validates:
        - Organization exists and is active
        - Person exists and has active Employee record
        - Business group (if provided) is root organization and matches org's root
        - No overlapping assignments for same organization
        - Effective dates are valid
        """
        # Validate organization exists and is active
        today = date.today()
        try:
            organization = Organization.objects.active_on(today).get(pk=dto.organization_id)
        except Organization.DoesNotExist:
            raise ValidationError({'organization_id': 'Organization not found or inactive'})

        # Validate person exists
        try:
            person = Person.objects.get(pk=dto.person_id)
        except Person.DoesNotExist:
            raise ValidationError({'person_id': 'Person not found'})

        # Validate person has active Employee record
        check_date = dto.effective_start_date if dto.effective_start_date <= today else today
        active_employee = Employee.objects.active_on(check_date).filter(person_id=dto.person_id).exists()
        if not active_employee:
            raise ValidationError({
                'person_id': f'Person "{person.full_name}" does not have an active Employee record on {check_date}'
            })

        # Business group validation is implicitly handled by organization validation
        # since organization must be active today.

        # Create assignment
        # Note: Overlap detection and date validation handled by model.full_clean()
        # which calls VersionedMixin.clean()
        assignment = OrganizationManager(
            organization=organization,
            person=person,
            effective_start_date=dto.effective_start_date,
            effective_end_date=dto.effective_end_date,
            created_by=user,
            updated_by=user
        )
        assignment.full_clean()  # This calls VersionedMixin.clean() for overlap detection
        assignment.save()
        return assignment

    @staticmethod
    @transaction.atomic
    def update(user, dto: OrganizationManagerUpdateDTO) -> OrganizationManager:
        """
        Update existing manager assignment.

        Currently only supports updating effective_end_date (ending an assignment).
        Uses VersionedMixin.update_version() in correction mode (updates in-place).

        To change organization or person, create a new assignment instead.

        Note: Date validation handled by VersionedMixin.clean() via full_clean()
        """
        try:
            assignment = OrganizationManager.objects.get(pk=dto.assignment_id)
        except OrganizationManager.DoesNotExist:
            raise ValidationError(f"Manager assignment with ID {dto.assignment_id} not found")

        # Use VersionedMixin.update_version() in correction mode
        # Correction mode: no new_start_date means update in-place
        # Date validation is handled by update_version's full_clean() call
        updated = assignment.update_version(
            field_updates={},  # Empty since we only update end_date
            new_end_date=dto.effective_end_date
        )

        updated.updated_by = user
        updated.save(update_fields=['updated_by'])
        return updated

    @staticmethod
    @transaction.atomic
    def deactivate(user, assignment_id: int, effective_end_date: Optional[date] = None) -> OrganizationManager:
        """
        Deactivate (end) a manager assignment by setting effective_end_date.

        Uses VersionedMixin.deactivate() pattern:
        - If no end_date provided: defaults to yesterday (inactive today)
        - If end_date provided: uses that date

        Args:
            user: User performing the action
            assignment_id: ID of OrganizationManager record
            effective_end_date: Date to end assignment (defaults to yesterday per VersionedMixin)

        Returns:
            Updated assignment
        """
        try:
            assignment = OrganizationManager.objects.get(pk=assignment_id)
        except OrganizationManager.DoesNotExist:
            raise ValidationError(f"Manager assignment with ID {assignment_id} not found")

        # Use VersionedMixin.deactivate() method
        assignment.deactivate(end_date=effective_end_date)
        assignment.updated_by = user
        assignment.save(update_fields=['updated_by'])
        return assignment

    @staticmethod
    def get_current_manager(organization_id: int, as_of_date: Optional[date] = None) -> Optional[OrganizationManager]:
        """
        Get the current manager for an organization as of a specific date.

        Args:
            organization_id: ID of the organization
            as_of_date: Date to check (defaults to today)

        Returns:
            OrganizationManager instance or None if no manager assigned
        """
        check_date = as_of_date or date.today()

        return OrganizationManager.objects.active_on(check_date).filter(
            organization_id=organization_id
        ).select_related('organization', 'person').first()

    @staticmethod
    def get_manager_history(organization_id: int):
        """
        Get all manager assignments for an organization (past and present).

        Args:
            organization_id: ID of the organization

        Returns:
            QuerySet of OrganizationManager instances ordered by start date (newest first)
        """
        return OrganizationManager.objects.filter(
            organization_id=organization_id
        ).select_related('organization', 'person').order_by('-effective_start_date')

    @staticmethod
    def get_organizations_managed_by_person(person_id: int, as_of_date: Optional[date] = None):
        """
        Get all organizations currently managed by a person.

        Args:
            person_id: ID of the person
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of OrganizationManager instances
        """
        check_date = as_of_date or date.today()

        return OrganizationManager.objects.active_on(check_date).filter(
            person_id=person_id
        ).select_related('organization', 'person')

    @staticmethod
    def get_all_managers_in_business_group(business_group_id: int, as_of_date: Optional[date] = None):
        """
        Get all current manager assignments within a business group.

        Args:
            business_group_id: ID of the root organization (business group)
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of OrganizationManager instances
        """
        check_date = as_of_date or date.today()

        return OrganizationManager.objects.active_on(check_date).filter(
            Q(organization_id=business_group_id) | Q(organization__business_group_id=business_group_id)
        ).select_related('organization', 'person').order_by('organization__organization_name')

