from django.db import models
from core.base.models import AuditMixin
from django.db.models import Q


class PersonType(AuditMixin, models.Model):
    """
    Lookup table for person types (subtypes within base types).

    Base Types (system-defined, map to child models):
    - APL: Applicant
    - EMP: Employee
    - CWK: Contingent Worker
    - CON: Contact

    User Types (business-defined, unlimited):
    - PERM_EMP: Permanent Employee (base_type='EMP')
    - TEMP_EMP: Temporary Employee (base_type='EMP')
    - CONTRACT_EMP: Contract Employee (base_type='EMP')
    - INTERNAL_APL: Internal Applicant (base_type='APL')
    - EXTERNAL_APL: External Applicant (base_type='APL')
    - ... unlimited more

    Note: Business rules are configured via DFF, not stored here.
    """
    BASE_TYPE_CHOICES = [
        ('APL', 'Applicant'),
        ('EMP', 'Employee'),
        ('CWK', 'Contingent Worker'),
        ('CON', 'Contact'),
    ]

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique code (e.g., 'PERM_EMP', 'TEMP_EMP')"
    )
    name = models.CharField(
        max_length=128,
        help_text="Display name (e.g., 'Permanent Employee')"
    )
    description = models.TextField(blank=True)

    base_type = models.CharField(
        max_length=20,
        choices=BASE_TYPE_CHOICES,
        null=False,
        blank=False,
        help_text="Which child model this maps to (APL/EMP/CWK/CON)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive types hidden from dropdowns"
    )


    class Meta:
        db_table = 'person_type'
        ordering = ['base_type', 'name']
        indexes = [
            models.Index(fields=['base_type', 'is_active']),
        ]
        # Add database-level check constraint
        constraints = [
            # Ensure base_type is not empty at database level
            models.CheckConstraint(
                condition=Q(base_type__in=['APL', 'EMP', 'CWK', 'CON']),
                name='valid_base_type'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.base_type})"

    def clean(self):
        """Validate PersonType data"""
        super().clean()

    @classmethod
    def get_active_for_base(cls, base_type):
        """Get all active person types for a base type"""
        return cls.objects.filter(
            base_type=base_type,
            is_active=True
        ).order_by('name')
