from django.db import models
from django.core.exceptions import ValidationError
from core.base.models import AuditMixin
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from .competency import Competency

class JobCompetencyRequirement(AuditMixin, models.Model):
    """
    Through model for Job-Competency M2M relationship with proficiency level.

    Tracks which competencies are required for a job and at what proficiency level.

    Fields:
    - job: FK to Job
    - competency: FK to Competency
    - proficiency_level: FK to LookupValue (PROFICIENCY_LEVEL)
    """
    job = models.ForeignKey(
        'work_structures.Job',
        on_delete=models.CASCADE,
        related_name='competency_requirements'
    )

    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name='job_requirements'
    )

    proficiency_level = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'lookup_type__name': CoreLookups.PROFICIENCY_LEVEL, 'is_active': True},
        help_text="Required proficiency level for this competency"
    )

    class Meta:
        db_table = 'hr_job_competency_requirement'
        verbose_name = 'Job Competency Requirement'
        verbose_name_plural = 'Job Competency Requirements'
        unique_together = ['job', 'competency']
        indexes = [
            models.Index(fields=['job', 'competency']),
        ]

    def __str__(self):
        return f"{self.job.code} requires {self.competency.name} at {self.proficiency_level.name}"

    def clean(self):
        """Validate competency requirement"""
        super().clean()

        # Validate proficiency level lookup
        if self.proficiency_level_id:
            if self.proficiency_level.lookup_type.name != CoreLookups.PROFICIENCY_LEVEL:
                raise ValidationError({
                    'proficiency_level': 'Must be a PROFICIENCY_LEVEL lookup value'
                })
            if not self.proficiency_level.is_active:
                raise ValidationError({
                    'proficiency_level': f'Proficiency level "{self.proficiency_level.name}" is inactive'
                })

        # Validate competency is active
        if self.competency_id:
            if self.competency.status != 'ACTIVE':
                raise ValidationError({
                    'competency': f'Competency "{self.competency.name}" is inactive'
                })


class PositionCompetencyRequirement(AuditMixin, models.Model):
    """
    Through model for Position-Competency M2M relationship with proficiency level.

    Tracks which competencies are required for a position and at what proficiency level.

    Fields:
    - position: FK to Position
    - competency: FK to Competency
    - proficiency_level: FK to LookupValue (PROFICIENCY_LEVEL)
    """
    position = models.ForeignKey(
        'work_structures.Position',
        on_delete=models.CASCADE,
        related_name='competency_requirements'
    )

    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name='position_requirements'
    )

    proficiency_level = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'lookup_type__name': CoreLookups.PROFICIENCY_LEVEL, 'is_active': True},
        help_text="Required proficiency level for this competency"
    )

    class Meta:
        db_table = 'hr_position_competency_requirement'
        verbose_name = 'Position Competency Requirement'
        verbose_name_plural = 'Position Competency Requirements'
        unique_together = ['position', 'competency']
        indexes = [
            models.Index(fields=['position', 'competency']),
        ]

    def __str__(self):
        return f"{self.position.code} requires {self.competency.name} at {self.proficiency_level.name}"

    def clean(self):
        """Validate competency requirement"""
        super().clean()

        # Validate proficiency level lookup
        if self.proficiency_level_id:
            if self.proficiency_level.lookup_type.name != CoreLookups.PROFICIENCY_LEVEL:
                raise ValidationError({
                    'proficiency_level': 'Must be a PROFICIENCY_LEVEL lookup value'
                })
            if not self.proficiency_level.is_active:
                raise ValidationError({
                    'proficiency_level': f'Proficiency level "{self.proficiency_level.name}" is inactive'
                })

        # Validate competency is active
        if self.competency_id:
            if self.competency.status != 'ACTIVE':
                raise ValidationError({
                    'competency': f'Competency "{self.competency.name}" is inactive'
                })
