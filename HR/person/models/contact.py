from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.dff import DFFMixin
from Finance.core.base_models import ChildModelMixin, ChildModelManagerMixin
from .person import Person
from .person_type import PersonType


class ContactManager(ChildModelManagerMixin, VersionedManager):
    """Manager for Contact with automatic Person field handling"""
    parent_model = Person


class Contact(DFFMixin, VersionedMixin, ChildModelMixin, AuditMixin, models.Model):
    """
    Contact periods (versioned).

    Covers individuals tracked in the system who are NOT:
    - Employees
    - Applicants
    - Contingent Workers

    Examples:
    - Vendor contacts
    - Emergency contacts for employees
    - Customer contacts
    - Partner organization contacts
    - Reference contacts

    Each version = one contact relationship period.
    """

    # Configuration for ChildModelMixin
    parent_model = Person
    parent_field_name = 'person'

    # Link to Person
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='contact_periods'
    )

    # Contact type (subtype within base_type='CON')
    contact_type = models.ForeignKey(
        PersonType,
        on_delete=models.PROTECT,
        limit_choices_to={'base_type': 'CON', 'is_active': True},
        help_text="Contact subtype (Vendor, Emergency, Customer, etc.)"
    )

    # VersionedMixin provides:
    # - effective_start_date
    # - effective_end_date
    # - status (computed property)

    # Contact-specific fields
    contact_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique contact identifier"
    )

    # Organization/Relationship
    organization_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Organization this contact represents"
    )
    job_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Contact's job title"
    )
    relationship_to_company = models.CharField(
        max_length=100,
        blank=True,
        help_text="How this contact relates to the company"
    )

    # Emergency contact specific (if applicable)
    emergency_for_employee = models.ForeignKey(
        'Employee',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='emergency_contacts',
        help_text="Employee this is an emergency contact for (if applicable)"
    )
    emergency_relationship = models.CharField(
        max_length=50,
        blank=True,
        help_text="Relationship to employee (spouse, parent, sibling, etc.)"
    )
    is_primary_contact = models.BooleanField(
        default=False,
        help_text="Is this the primary emergency contact?"
    )

    # Contact preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('sms', 'SMS'),
            ('mail', 'Mail')
        ],
        help_text="Preferred way to contact this person"
    )

    objects = ContactManager()

    class Meta:
        db_table = 'contact'
        indexes = [
            models.Index(fields=['person', 'effective_start_date']),
            models.Index(fields=['contact_number']),
            models.Index(fields=['organization_name']),
            models.Index(fields=['emergency_for_employee']),
            models.Index(fields=['effective_start_date', 'effective_end_date']),
        ]

    def __str__(self):
        return f"{self.contact_number} - {self.person.full_name}"

    def get_version_group_field(self):
        """Versions grouped by contact_number"""
        return 'contact_number'

    def clean(self):
        super().clean()  # Validates date order

        # Validate contact type has correct base_type
        if self.contact_type.base_type != 'CON':
            raise ValidationError(
                f"Contact must use PersonType with base_type='CON', "
                f"not '{self.contact_type.base_type}'"
            )

        # Check for overlapping periods for same person
        overlapping = Contact.objects.active_between(
            self.effective_start_date,
            self.effective_end_date or date.max
        ).filter(person=self.person).exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError(
                "Contact periods cannot overlap for the same person"
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

