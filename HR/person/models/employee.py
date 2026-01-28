from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.dff import DFFMixin
from Finance.core.base_models import ChildModelMixin, ChildModelManagerMixin
from .person import Person
from .person_type import PersonType

class EmployeeManager(ChildModelManagerMixin, VersionedManager):
    """Manager for Employee with automatic Person field handling and versioned queryset methods"""
    parent_model = Person

class Employee(DFFMixin, VersionedMixin, ChildModelMixin, AuditMixin, models.Model):
    """
    Employment periods (versioned).

    Each version = one employment period or subtype change.
    New version created ONLY for:
    - New employment period (hire/rehire)
    - Employee subtype change (temp → permanent)

    Field updates within period: Update in-place (no new version)

    Examples:
    - Person #123 hired 2020-2024 (quit) = Employee v1 (ended)
    - Person #123 rehired 2026 = Employee v2 (active)
    - Temp employee converted to permanent = new version
    """

    # Configuration for ChildModelMixin
    parent_model = Person
    parent_field_name = 'person'

    # Link to Person (many versions per person possible)
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='employee_periods'
    )

    # Employee type (subtype within base_type='EMP')
    employee_type = models.ForeignKey(
        PersonType,
        on_delete=models.PROTECT,
        limit_choices_to={'base_type': 'EMP', 'is_active': True},
        help_text="Employee subtype (Permanent, Temporary, etc.)"
    )

    # VersionedMixin provides:
    # - effective_start_date
    # - effective_end_date
    # - status (computed property)

    # Employee-specific fields
    employee_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Globally unique employee identifier (auto-generated: EMP-000001)"
    )
    hire_date = models.DateField(
        help_text="First day of employment (this period)"
    )

    objects = EmployeeManager()

    class Meta:
        db_table = 'employee'
        indexes = [
            models.Index(fields=['person', 'effective_start_date']),
            models.Index(fields=['employee_number']),
            models.Index(fields=['effective_start_date', 'effective_end_date']),
        ]

    def __str__(self):
        return f"{self.employee_number} - {self.person.full_name}"

    def get_version_group_field(self):
        """
        Versions grouped by employee_number.

        Note: In practice, each employment period gets a NEW employee_number,
        so this is rarely used for actual versioning. The overlap check is
        done manually in clean() by person instead.
        """
        return 'employee_number'

    def clean(self):
        super().clean()  # Validates date order

        # Validate employee type has correct base_type
        if self.employee_type.base_type != 'EMP':
            raise ValidationError(
                f"Employee must use PersonType with base_type='EMP', "
                f"not '{self.employee_type.base_type}'"
            )

        # Validate dates
        if self.effective_start_date and self.hire_date:
            if self.hire_date < self.effective_start_date:
                raise ValidationError(
                    "Hire date cannot be before effective start date"
                )

        # Check for overlapping periods for same person (manual check needed)
        # Can't use VersionedMixin's overlap check because each period has different employee_number
        overlapping = Employee.objects.active_between(
            self.effective_start_date,
            self.effective_end_date or date.max
        ).filter(person=self.person).exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError(
                "Employment periods cannot overlap for the same person"
            )


    def save(self, force_new_version=False, *args, **kwargs):
        """
        Override VersionedMixin:
        - New record: Use versioning (create v1, v2, etc.)
        - Update: Don't version (just update in place)
        - force_new_version=True: Create new version
        - Auto-generate employee_number if not provided
        """
        # Always run validation before saving
        self.full_clean()

        # Auto-generate employee_number for new records
        if not self.pk and not self.employee_number:
            # Find the highest existing employee number starting with EMP-
            last_emp = Employee.objects.filter(employee_number__startswith='EMP-').order_by('-employee_number').first()
            
            if last_emp:
                try:
                    # Extract numeric part (EMP-XXXXXX)
                    last_num = int(last_emp.employee_number.split('-')[1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    # Fallback if parsing fails
                    next_num = Employee.objects.count() + 1
            else:
                next_num = 1
                
            # Format: EMP-000001 (6 digits)
            self.employee_number = f"EMP-{next_num:06d}"

        if self.pk and not force_new_version:
            # Updating existing - don't create new version
            super(VersionedMixin, self).save(*args, **kwargs)
        else:
            # New period or forced versioning
            super().save(*args, **kwargs)

