from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from .competency import Competency


class CompetencyProficiency(VersionedMixin, AuditMixin, models.Model):
    """
    Tracks a person's proficiency level in a competency over time.

    Links Person to Competency with a proficiency level and date range.
    No overlapping date ranges allowed for same person/competency combination.

    Mixins:
    - VersionedMixin: Handles effective dates (effective_start_date, effective_end_date)
    - AuditMixin: Tracks creation/updates

    Fields:
    - person: FK to Person
    - competency: FK to Competency
    - proficiency_level: FK to LookupValue (PROFICIENCY_LEVEL - e.g., Beginner, Expert)
    - proficiency_source: FK to LookupValue (PROFICIENCY_SOURCE - e.g., Self-Assessment, Manager)
    """
    person = models.ForeignKey(
        'person.Person',
        on_delete=models.PROTECT,
        related_name='competency_proficiencies',
        help_text="Person who has this competency"
    )

    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name='proficiencies',
        help_text="Competency being assessed"
    )

    proficiency_level = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='proficiencies_by_level',
        limit_choices_to={'lookup_type__name': CoreLookups.PROFICIENCY_LEVEL, 'is_active': True},
        help_text="Proficiency level (e.g., Beginner, Intermediate, Expert)"
    )

    proficiency_source = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='proficiencies_by_source',
        limit_choices_to={'lookup_type__name': CoreLookups.PROFICIENCY_SOURCE, 'is_active': True},
        help_text="How proficiency was assessed (e.g., Self-Assessment, Manager Assessment)"
    )

    objects = VersionedManager()

    class Meta:
        db_table = 'hr_competency_proficiency'
        verbose_name = 'Competency Proficiency'
        verbose_name_plural = 'Competency Proficiencies'
        ordering = ['person', 'competency', '-effective_start_date']
        indexes = [
            models.Index(fields=['person', 'effective_start_date', 'effective_end_date']),
            models.Index(fields=['competency', 'proficiency_level']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['person', 'competency', 'effective_start_date'],
                name='unique_person_competency_date'
            ),
            models.CheckConstraint(
                check=models.Q(effective_end_date__isnull=True) | models.Q(effective_end_date__gte=models.F('effective_start_date')),
                name='proficiency_end_after_start'
            ),
        ]

    def __str__(self):
        return f"{self.person.full_name} - {self.competency.name} ({self.proficiency_level.name})"

    def clean(self):
        """Validate competency proficiency data"""
        super().clean()
        
        # Validation: No overlapping date ranges for same person/competency
        if self.effective_start_date:
            # Base query excluding self
            queryset = CompetencyProficiency.objects.filter(
                person=self.person,
                competency=self.competency
            ).exclude(pk=self.pk)

            # Check overlap logic
            # Existing overlaps if:
            # (StartA <= EndB) and (EndA >= StartB)
            # Where B is existing record, A is new record
            
            # StartB <= EndA (if EndA is null, treated as infinity)
            query = models.Q(effective_start_date__lte=(self.effective_end_date or date.max))
            
            # EndB >= StartA (if EndB is null, treated as infinity)
            query &= (models.Q(effective_end_date__gte=self.effective_start_date) | models.Q(effective_end_date__isnull=True))

            if queryset.filter(query).exists():
                 raise ValidationError({
                    'effective_start_date': 'Date range overlaps with an existing proficiency record for this person and competency.'
                })
