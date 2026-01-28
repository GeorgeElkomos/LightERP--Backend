from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.dff import DFFMixin
from Finance.core.base_models import ChildModelMixin, ChildModelManagerMixin
from .person import Person
from .person_type import PersonType


class ContingentWorkerManager(ChildModelManagerMixin, VersionedManager):
    """Manager for ContingentWorker with automatic Person field handling"""
    parent_model = Person


class ContingentWorker(DFFMixin, VersionedMixin, ChildModelMixin, AuditMixin, models.Model):
    """
    Contingent Worker periods (versioned).

    Covers non-employee workers:
    - Consultants
    - Contractors
    - Freelancers
    - Agency workers
    - Temporary staff

    Each version = one placement/assignment period.

    Examples:
    - External consultant on 6-month assignment = ContingentWorker v1
    - Same consultant renewed for another 6 months = ContingentWorker v2
    """

    # Configuration for ChildModelMixin
    parent_model = Person
    parent_field_name = 'person'

    # Link to Person
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='contingent_worker_periods'
    )

    # Worker type (subtype within base_type='CWK')
    worker_type = models.ForeignKey(
        PersonType,
        on_delete=models.PROTECT,
        limit_choices_to={'base_type': 'CWK', 'is_active': True},
        help_text="Worker subtype (Consultant, Contractor, etc.)"
    )

    # VersionedMixin provides:
    # - effective_start_date
    # - effective_end_date
    # - status (computed property)

    # Worker-specific fields
    worker_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique worker identifier"
    )
    placement_date = models.DateField(
        help_text="Date placement started"
    )

    # Vendor/Agency information
    vendor_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Staffing agency or contracting company"
    )
    po_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Purchase order number for services"
    )

    # Assignment details
    current_assignment = models.ForeignKey(
        'work_structures.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Current organization/department/team assignment"
    )
    assignment_role = models.ForeignKey(
        'work_structures.Position',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Role/position for this assignment"
    )

    objects = ContingentWorkerManager()

    class Meta:
        db_table = 'contingent_worker'
        indexes = [
            models.Index(fields=['person', 'effective_start_date']),
            models.Index(fields=['worker_number']),
            models.Index(fields=['vendor_name']),
            models.Index(fields=['effective_start_date', 'effective_end_date']),
        ]

    def __str__(self):
        return f"{self.worker_number} - {self.person.full_name}"

    def get_version_group_field(self):
        """Versions grouped by worker_number"""
        return 'worker_number'

    def clean(self):
        super().clean()  # Validates date order

        # Validate worker type has correct base_type
        if self.worker_type.base_type != 'CWK':
            raise ValidationError(
                f"ContingentWorker must use PersonType with base_type='CWK', "
                f"not '{self.worker_type.base_type}'"
            )

        # Validate dates
        if self.effective_start_date and self.placement_date:
            if self.placement_date < self.effective_start_date:
                raise ValidationError(
                    "Placement date cannot be before effective start date"
                )

        # Check for overlapping periods for same person
        overlapping = ContingentWorker.objects.active_between(
            self.effective_start_date,
            self.effective_end_date or date.max
        ).filter(person=self.person).exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError(
                "Contingent worker periods cannot overlap for the same person"
            )


    def save(self, force_new_version=False, *args, **kwargs):
        """
        Override VersionedMixin:
        - New record: Use versioning
        - Update: Don't version (update in place)
        - force_new_version=True: Create new version
        """
        if self.pk and not force_new_version:
            # Updating existing - don't create new version
            super(VersionedMixin, self).save(*args, **kwargs)
        else:
            # New period or forced versioning
            super().save(*args, **kwargs)

