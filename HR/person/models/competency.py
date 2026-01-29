from django.db import models
from django.core.exceptions import ValidationError
from core.base.models import SoftDeleteMixin, AuditMixin
from core.base.managers import SoftDeleteManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups

class Competency(SoftDeleteMixin, AuditMixin, models.Model):
    """
    Competency definition (skills, knowledge, abilities).

    System-wide competencies that can be used across all business groups.
    Examples: Python Programming, Project Management, Customer Service

    Mixins:
    - SoftDeleteMixin: Soft delete with status field (ACTIVE/INACTIVE)
    - AuditMixin: Tracks creation/updates

    Fields:
    - code: Unique identifier
    - name: Competency name
    - description: Detailed description
    - category: FK to LookupValue (COMPETENCY_CATEGORY)
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique competency code"
    )

    name = models.CharField(
        max_length=255,
        help_text="Competency name (e.g., Python Programming, Leadership)"
    )

    description = models.TextField(
        blank=True,
        help_text="Detailed description of the competency"
    )

    category = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='competencies_by_category',
        limit_choices_to={'lookup_type__name': CoreLookups.COMPETENCY_CATEGORY, 'is_active': True},
        help_text="Competency category from lookup (e.g., Technical, Behavioral)"
    )

    objects = SoftDeleteManager()

    class Meta:
        db_table = 'hr_competency'
        verbose_name = 'Competency'
        verbose_name_plural = 'Competencies'
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['code']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """Validate competency data"""
        super().clean()

        # Validation 1: Name and code required
        if not self.name or not self.name.strip():
            raise ValidationError({'name': 'Competency name cannot be empty'})

        if not self.code or not self.code.strip():
            raise ValidationError({'code': 'Competency code cannot be empty'})

        # Validation 2: Category lookup validation
        if self.category_id:
            if self.category.lookup_type.name != CoreLookups.COMPETENCY_CATEGORY:
                raise ValidationError({
                    'category': 'Must be a COMPETENCY_CATEGORY lookup value'
                })
            if not self.category.is_active:
                raise ValidationError({
                    'category': f'Category "{self.category.name}" is inactive'
                })

