from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.dff import DFFMixin
from Finance.core.base_models import ChildModelMixin, ChildModelManagerMixin
from .person import Person
from .person_type import PersonType


class ApplicantManager(ChildModelManagerMixin, VersionedManager):
    """Manager for Applicant with automatic Person field handling and versioned queryset methods"""
    parent_model = Person


class Applicant(DFFMixin, VersionedMixin, ChildModelMixin, AuditMixin, models.Model):
    """
    Applicant periods (versioned).

    Each version = one application period.
    Tracks job applications and candidate lifecycle.

    Examples:
    - External candidate applies for role = Applicant v1 (active)
    - Hired → Applicant period ends, Employee period starts
    - Employee applies for different role = Applicant v2 (internal applicant)
    """

    # Configuration for ChildModelMixin
    parent_model = Person
    parent_field_name = 'person'

    # Link to Person
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='applicant_periods'
    )

    # Applicant type (subtype within base_type='APL')
    applicant_type = models.ForeignKey(
        PersonType,
        on_delete=models.PROTECT,
        limit_choices_to={'base_type': 'APL', 'is_active': True},
        help_text="Applicant subtype (Internal, External, etc.)"
    )

    # VersionedMixin provides:
    # - effective_start_date
    # - effective_end_date
    # - status (computed property)

    # Applicant-specific fields
    application_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique application identifier"
    )
    application_source = models.CharField(
        max_length=50,
        blank=True,
        help_text="How applicant found position (LinkedIn, referral, etc.)"
    )
    application_status = models.CharField(
        max_length=50,
        default='applied',
        help_text="Current status (applied, screening, interview, offer, hired, rejected)"
    )

    # Applied position
    applied_position = models.ForeignKey(
        'work_structures.Position',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Position applied for"
    )

    objects = ApplicantManager()

    class Meta:
        db_table = 'applicant'
        indexes = [
            models.Index(fields=['person', 'effective_start_date']),
            models.Index(fields=['application_number']),
            models.Index(fields=['application_status']),
            models.Index(fields=['effective_start_date', 'effective_end_date']),
        ]

    def __str__(self):
        return f"{self.application_number} - {self.person.full_name}"

    def get_version_group_field(self):
        """Versions grouped by application_number"""
        return 'application_number'

    def clean(self):
        super().clean()  # Validates date order

        # Validate applicant type has correct base_type
        if self.applicant_type.base_type != 'APL':
            raise ValidationError(
                f"Applicant must use PersonType with base_type='APL', "
                f"not '{self.applicant_type.base_type}'"
            )

        # Check for overlapping periods for same person
        overlapping = Applicant.objects.active_between(
            self.effective_start_date,
            self.effective_end_date or date.max
        ).filter(person=self.person).exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError(
                "Applicant periods cannot overlap for the same person"
            )


    def save(self, force_new_version=False, *args, **kwargs):
        """
        Override VersionedMixin:
        - New record: Use versioning
        - Update: Don't version (update in place)
        - force_new_version=True: Create new version
        """
        # Always run validation before saving
        self.full_clean()

        if self.pk and not force_new_version:
            # Updating existing - don't create new version
            super(VersionedMixin, self).save(*args, **kwargs)
        else:
            # New period or forced versioning
            super().save(*args, **kwargs)

