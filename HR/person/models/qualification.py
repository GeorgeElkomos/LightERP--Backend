from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import SoftDeleteMixin, AuditMixin
from core.base.managers import SoftDeleteManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from .competency import Competency


class Qualification(SoftDeleteMixin, AuditMixin, models.Model):
    """
    Tracks person's educational qualifications and certifications.

    Supports both completed and in-progress qualifications with status-based validation.

    Mixins:
    - SoftDeleteMixin: Soft delete with status field (ACTIVE/INACTIVE)
    - AuditMixin: Tracks creation/updates

    Fields:
    - person: FK to Person
    - qualification_type: FK to LookupValue (QUALIFICATION_TYPE - e.g., Bachelor, Master, Certification)
    - qualification_title: FK to LookupValue (QUALIFICATION_TITLE - specific degree/cert)
    - title_if_others: Text field if qualification_title is "Others"
    - qualification_status: FK to LookupValue (QUALIFICATION_STATUS - Completed, In Progress)
    - grade: Grade or GPA achieved (for completed)
    - awarding_entity: FK to LookupValue (AWARDING_ENTITY - university/institution)
    - awarded_date: Date qualification was awarded (required for Completed)
    - projected_completion_date: Expected completion date (required for In Progress)
    - completed_percentage: Progress percentage (for In Progress, 0-100)
    - study_start_date: When study began
    - study_end_date: When study ended (for Completed)
    - competency_achieved: M2M to Competency (skills gained from qualification)
    - tuition_method: FK to LookupValue (TUITION_METHOD - Self-funded, Company-sponsored)
    - tuition_fees: Amount paid
    - tuition_fees_currency: FK to LookupValue (CURRENCY)
    - remarks: Additional notes
    - effective_start_date: When this qualification record becomes effective
    - effective_end_date: When this qualification record ends
    """
    person = models.ForeignKey(
        'person.Person',
        on_delete=models.PROTECT,
        related_name='qualifications',
        help_text="Person who has this qualification"
    )

    qualification_type = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='qualifications_by_type',
        limit_choices_to={'lookup_type__name': CoreLookups.QUALIFICATION_TYPE, 'is_active': True},
        help_text="Type of qualification (e.g., Bachelor, Master, Certification)"
    )

    qualification_title = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='qualifications_by_title',
        limit_choices_to={'lookup_type__name': CoreLookups.QUALIFICATION_TITLE, 'is_active': True},
        help_text="Specific qualification title (e.g., Computer Science, MBA)"
    )

    title_if_others = models.CharField(
        max_length=255,
        blank=True,
        help_text="Specify qualification title if 'Others' selected"
    )

    qualification_status = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='qualifications_by_status',
        limit_choices_to={'lookup_type__name': CoreLookups.QUALIFICATION_STATUS, 'is_active': True},
        help_text="Status (e.g., Completed, In Progress)"
    )

    grade = models.CharField(
        max_length=50,
        blank=True,
        help_text="Grade or GPA achieved (required for Completed status)"
    )

    awarding_entity = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='qualifications_by_entity',
        limit_choices_to={'lookup_type__name': CoreLookups.AWARDING_ENTITY, 'is_active': True},
        help_text="University or institution that awarded the qualification"
    )

    awarded_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date qualification was awarded (required for Completed)"
    )

    projected_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected completion date (required for In Progress)"
    )

    completed_percentage = models.IntegerField(
        null=True,
        blank=True,
        help_text="Progress percentage for In Progress qualifications (0-100)"
    )

    study_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="When study began"
    )

    study_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="When study ended (for Completed)"
    )

    competency_achieved = models.ManyToManyField(
        Competency,
        related_name='qualifications',
        blank=True,
        help_text="Competencies gained from this qualification"
    )

    tuition_method = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='qualifications_by_tuition_method',
        limit_choices_to={'lookup_type__name': CoreLookups.TUITION_METHOD, 'is_active': True},
        null=True,
        blank=True,
        help_text="How tuition was funded (e.g., Self-funded, Company-sponsored)"
    )

    tuition_fees = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount paid for tuition"
    )

    tuition_fees_currency = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='qualifications_by_currency',
        limit_choices_to={'lookup_type__name': CoreLookups.CURRENCY, 'is_active': True},
        null=True,
        blank=True,
        help_text="Currency for tuition fees"
    )

    remarks = models.TextField(
        blank=True,
        help_text="Additional notes about the qualification"
    )

    effective_start_date = models.DateField(
        default=date.today,
        help_text="When this qualification record becomes effective"
    )

    effective_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="When this qualification record ends"
    )

    objects = SoftDeleteManager()

    class Meta:
        db_table = 'hr_qualification'
        verbose_name = 'Qualification'
        verbose_name_plural = 'Qualifications'
        ordering = ['person', '-effective_start_date']
        indexes = [
            models.Index(fields=['status', 'person']),
            models.Index(fields=['person', 'qualification_status']),
            models.Index(fields=['qualification_type', 'qualification_status']),
            models.Index(fields=['effective_start_date', 'effective_end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(completed_percentage__isnull=True) |
                      models.Q(completed_percentage__gte=0, completed_percentage__lte=100),
                name='qualification_percentage_valid_range'
            ),
            models.CheckConstraint(
                condition=models.Q(effective_end_date__isnull=True) |
                      models.Q(effective_end_date__gte=models.F('effective_start_date')),
                name='qualification_effective_end_after_start'
            ),
            models.CheckConstraint(
                condition=models.Q(study_end_date__isnull=True) |
                      models.Q(study_start_date__isnull=True) |
                      models.Q(study_end_date__gte=models.F('study_start_date')),
                name='qualification_study_end_after_start'
            ),
            models.CheckConstraint(
                condition=models.Q(tuition_fees__isnull=True) |
                      models.Q(tuition_fees_currency__isnull=False),
                name='qualification_fees_requires_currency'
            ),
        ]

    def __str__(self):
        title = self.title_if_others or self.qualification_title.name
        return f"{self.person.full_name} - {title} ({self.qualification_status.name})"

    def clean(self):
        """Validate qualification data with status-based rules"""
        super().clean()

        # Validation 1: Qualification type lookup
        if self.qualification_type_id:
            if self.qualification_type.lookup_type.name != CoreLookups.QUALIFICATION_TYPE:
                raise ValidationError({
                    'qualification_type': 'Must be a QUALIFICATION_TYPE lookup value'
                })
            if not self.qualification_type.is_active:
                raise ValidationError({
                    'qualification_type': f'Qualification type "{self.qualification_type.name}" is inactive'
                })

        # Validation 2: Qualification title lookup
        if self.qualification_title_id:
            if self.qualification_title.lookup_type.name != CoreLookups.QUALIFICATION_TITLE:
                raise ValidationError({
                    'qualification_title': 'Must be a QUALIFICATION_TITLE lookup value'
                })
            if not self.qualification_title.is_active:
                raise ValidationError({
                    'qualification_title': f'Qualification title "{self.qualification_title.name}" is inactive'
                })

            # If "Others" is selected, title_if_others is required
            if self.qualification_title.name == 'Others' and not self.title_if_others:
                raise ValidationError({
                    'title_if_others': 'Please specify the qualification title when "Others" is selected'
                })

        # Validation 3: Qualification status lookup
        if self.qualification_status_id:
            if self.qualification_status.lookup_type.name != CoreLookups.QUALIFICATION_STATUS:
                raise ValidationError({
                    'qualification_status': 'Must be a QUALIFICATION_STATUS lookup value'
                })
            if not self.qualification_status.is_active:
                raise ValidationError({
                    'qualification_status': f'Status "{self.qualification_status.name}" is inactive'
                })

        # Validation 4: Awarding entity lookup
        if self.awarding_entity_id:
            if self.awarding_entity.lookup_type.name != CoreLookups.AWARDING_ENTITY:
                raise ValidationError({
                    'awarding_entity': 'Must be an AWARDING_ENTITY lookup value'
                })
            if not self.awarding_entity.is_active:
                raise ValidationError({
                    'awarding_entity': f'Awarding entity "{self.awarding_entity.name}" is inactive'
                })

        # Validation 5: Status-based validation rules
        if self.qualification_status_id:
            status_name = self.qualification_status.name

            # For "Completed" status
            if status_name == 'Completed':
                if not self.awarded_date:
                    raise ValidationError({
                        'awarded_date': 'Awarded date is required for completed qualifications'
                    })
                if not self.grade:
                    raise ValidationError({
                        'grade': 'Grade is required for completed qualifications'
                    })
                if not self.study_end_date:
                    raise ValidationError({
                        'study_end_date': 'Study end date is required for completed qualifications'
                    })

            # For "In Progress" status
            elif status_name == 'In Progress':
                if not self.projected_completion_date:
                    raise ValidationError({
                        'projected_completion_date': 'Projected completion date is required for in-progress qualifications'
                    })
                if self.completed_percentage is None:
                    raise ValidationError({
                        'completed_percentage': 'Completed percentage is required for in-progress qualifications'
                    })

        # Validation 6: Percentage range (0-100)
        if self.completed_percentage is not None:
            if self.completed_percentage < 0 or self.completed_percentage > 100:
                raise ValidationError({
                    'completed_percentage': 'Percentage must be between 0 and 100'
                })

        # Validation 7: Date validations
        if self.study_start_date and self.study_end_date:
            if self.study_end_date < self.study_start_date:
                raise ValidationError({
                    'study_end_date': 'Study end date must be on or after study start date'
                })

        if self.effective_start_date and self.effective_end_date:
            if self.effective_end_date < self.effective_start_date:
                raise ValidationError({
                    'effective_end_date': 'Effective end date must be on or after effective start date'
                })

        # Validation 8: Tuition fees validation
        if self.tuition_fees and not self.tuition_fees_currency_id:
            raise ValidationError({
                'tuition_fees_currency': 'Currency is required when tuition fees are specified'
            })

        if self.tuition_fees and self.tuition_fees < 0:
            raise ValidationError({
                'tuition_fees': 'Tuition fees cannot be negative'
            })

        # Validation 9: Tuition method lookup if provided
        if self.tuition_method_id:
            if self.tuition_method.lookup_type.name != CoreLookups.TUITION_METHOD:
                raise ValidationError({
                    'tuition_method': 'Must be a TUITION_METHOD lookup value'
                })
            if not self.tuition_method.is_active:
                raise ValidationError({
                    'tuition_method': f'Tuition method "{self.tuition_method.name}" is inactive'
                })

        # Validation 10: Currency lookup if provided
        if self.tuition_fees_currency_id:
            if self.tuition_fees_currency.lookup_type.name != CoreLookups.CURRENCY:
                raise ValidationError({
                    'tuition_fees_currency': 'Must be a CURRENCY lookup value'
                })
            if not self.tuition_fees_currency.is_active:
                raise ValidationError({
                    'tuition_fees_currency': f'Currency "{self.tuition_fees_currency.name}" is inactive'
                })

