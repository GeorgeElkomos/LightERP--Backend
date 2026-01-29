from django.db import models
from django.core.exceptions import ValidationError
from core.base.models import AuditMixin
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups

class JobQualificationRequirement(AuditMixin, models.Model):
    """
    Through model for Job-Qualification M2M relationship.

    Tracks which qualification types/titles are required for a job.

    Note: This links to qualification TYPE/TITLE lookups, not actual Qualification records.

    Fields:
    - job: FK to Job
    - qualification_type: FK to LookupValue (QUALIFICATION_TYPE)
    - qualification_title: FK to LookupValue (QUALIFICATION_TITLE)
    """
    job = models.ForeignKey(
        'Job',
        on_delete=models.CASCADE,
        related_name='qualification_requirements'
    )

    qualification_type = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'lookup_type__name': CoreLookups.QUALIFICATION_TYPE, 'is_active': True},
        help_text="Required qualification type (e.g., Bachelor's, Master's)"
    )

    qualification_title = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'lookup_type__name': CoreLookups.QUALIFICATION_TITLE, 'is_active': True},
        help_text="Required qualification title (e.g., Computer Science, Business Administration)"
    )

    class Meta:
        db_table = 'hr_job_qualification_requirement'
        verbose_name = 'Job Qualification Requirement'
        verbose_name_plural = 'Job Qualification Requirements'
        unique_together = ['job', 'qualification_type', 'qualification_title']
        indexes = [
            models.Index(fields=['job']),
        ]

    def __str__(self):
        return f"{self.job.code}: {self.qualification_type.name} in {self.qualification_title.name}"

    def clean(self):
        """Validate qualification requirement"""
        super().clean()

        # Validate qualification type lookup
        if self.qualification_type_id:
            if self.qualification_type.lookup_type.name != CoreLookups.QUALIFICATION_TYPE:
                raise ValidationError({
                    'qualification_type': 'Must be a QUALIFICATION_TYPE lookup value'
                })
            if not self.qualification_type.is_active:
                raise ValidationError({
                    'qualification_type': f'Qualification type "{self.qualification_type.name}" is inactive'
                })

        # Validate qualification title lookup
        if self.qualification_title_id:
            if self.qualification_title.lookup_type.name != CoreLookups.QUALIFICATION_TITLE:
                raise ValidationError({
                    'qualification_title': 'Must be a QUALIFICATION_TITLE lookup value'
                })
            if not self.qualification_title.is_active:
                raise ValidationError({
                    'qualification_title': f'Qualification title "{self.qualification_title.name}" is inactive'
                })


class PositionQualificationRequirement(AuditMixin, models.Model):
    """
    Through model for Position-Qualification M2M relationship.

    Tracks which qualification types/titles are required for a position.

    Note: This links to qualification TYPE/TITLE lookups, not actual Qualification records.

    Fields:
    - position: FK to Position
    - qualification_type: FK to LookupValue (QUALIFICATION_TYPE)
    - qualification_title: FK to LookupValue (QUALIFICATION_TITLE)
    """
    position = models.ForeignKey(
        'Position',
        on_delete=models.CASCADE,
        related_name='qualification_requirements'
    )

    qualification_type = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'lookup_type__name': CoreLookups.QUALIFICATION_TYPE, 'is_active': True},
        help_text="Required qualification type (e.g., Bachelor's, Master's)"
    )

    qualification_title = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'lookup_type__name': CoreLookups.QUALIFICATION_TITLE, 'is_active': True},
        help_text="Required qualification title (e.g., Computer Science, Business Administration)"
    )

    class Meta:
        db_table = 'hr_position_qualification_requirement'
        verbose_name = 'Position Qualification Requirement'
        verbose_name_plural = 'Position Qualification Requirements'
        unique_together = ['position', 'qualification_type', 'qualification_title']
        indexes = [
            models.Index(fields=['position']),
        ]

    def __str__(self):
        return f"{self.position.code}: {self.qualification_type.name} in {self.qualification_title.name}"

    def clean(self):
        """Validate qualification requirement"""
        super().clean()

        # Validate qualification type lookup
        if self.qualification_type_id:
            if self.qualification_type.lookup_type.name != CoreLookups.QUALIFICATION_TYPE:
                raise ValidationError({
                    'qualification_type': 'Must be a QUALIFICATION_TYPE lookup value'
                })
            if not self.qualification_type.is_active:
                raise ValidationError({
                    'qualification_type': f'Qualification type "{self.qualification_type.name}" is inactive'
                })

        # Validate qualification title lookup
        if self.qualification_title_id:
            if self.qualification_title.lookup_type.name != CoreLookups.QUALIFICATION_TITLE:
                raise ValidationError({
                    'qualification_title': 'Must be a QUALIFICATION_TITLE lookup value'
                })
            if not self.qualification_title.is_active:
                raise ValidationError({
                    'qualification_title': f'Qualification title "{self.qualification_title.name}" is inactive'
                })
