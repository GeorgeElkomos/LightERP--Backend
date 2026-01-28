from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from .organization import Organization


class OrganizationManager(VersionedMixin, AuditMixin, models.Model):
    """
    Assigns managers to organizations with date tracking.

    Key Rules:
    - Only ONE manager can be active per organization at any time
    - Manager must be an active Employee (Person with Employee record)
    - If business_group is specified, organization must belong to that business_group
    - Uses VersionedMixin for temporal tracking (effective_start_date/effective_end_date)

    Mixins:
    - VersionedMixin: Temporal versioning with date ranges
    - AuditMixin: Tracks creation/updates (created_by, updated_by, created_at, updated_at)

    Fields:
    - organization: Organization being managed
    - business_group: Optional root organization (for validation/filtering)
    - person: Person who is the manager (must have Employee record)
    - effective_start_date/effective_end_date: From VersionedMixin

    Validation:
    - No overlapping active assignments for same organization
    - Business group must be root organization if provided
    - Organization must belong to specified business_group
    - Person must have an active Employee record
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='managers',
        help_text="Organization being managed"
    )


    person = models.ForeignKey(
        'person.Person',
        on_delete=models.PROTECT,
        related_name='managed_organizations',
        help_text="Person who is the manager (must be an Employee)"
    )

    @property
    def business_group(self):
        """Returns the root organization (Business Group) of the managed organization"""
        return self.organization.get_root_business_group()

    objects = VersionedManager()

    class Meta:
        db_table = 'hr_organization_manager'
        verbose_name = 'Organization Manager'
        verbose_name_plural = 'Organization Managers'
        ordering = ['-effective_start_date']
        indexes = [
            models.Index(fields=['organization', 'effective_start_date', 'effective_end_date']),
            models.Index(fields=['person', 'effective_start_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'person', 'effective_start_date'],
                name='unique_org_manager_assignment'
            ),
            models.CheckConstraint(
                check=models.Q(effective_end_date__isnull=True) |
                      models.Q(effective_end_date__gte=models.F('effective_start_date')),
                name='org_manager_end_after_start'
            ),
        ]

    def __str__(self):
        return f"{self.organization.organization_name} - Manager: {self.person.full_name} ({self.effective_start_date})"

    def get_version_group_field(self):
        """Group by organization - only one manager per organization at a time"""
        return 'organization_id'

    def get_version_scope_filters(self):
        """Only one active manager per organization"""
        return {'organization': self.organization}

    def clean(self):
        """
        Validate manager assignment.

        Validates:
        1. Person must have an active Employee record

        Note: Overlap detection and date validation handled by VersionedMixin.clean()
        via get_version_group_field() and get_version_scope_filters()
        """
        super().clean()  # Calls VersionedMixin.clean() which handles overlap detection

        # Validation 1: Person must have an active Employee record
        if self.person_id:
            from HR.person.models import Employee

            # Check if person has any employee records
            employee_periods = Employee.objects.filter(person_id=self.person_id)
            if not employee_periods.exists():
                raise ValidationError({
                    'person': f'Person "{self.person.full_name}" must have an Employee record to be a manager'
                })

            # Check if person has an active employee record during the assignment period
            if self.effective_start_date:
                today = date.today()
                check_date = self.effective_start_date if self.effective_start_date <= today else today

                active_employee = Employee.objects.active_on(check_date).filter(
                    person_id=self.person_id
                ).exists()

                if not active_employee:
                    raise ValidationError({
                        'person': f'Person "{self.person.full_name}" does not have an active Employee record on {check_date}'
                    })


