from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import CheckConstraint, Q, F
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups

class Contract(VersionedMixin, AuditMixin, models.Model):
    """
    Contract model for employee contract management.
    Uses VersionedMixin for temporal versioning.
    """
    PERIOD_CHOICES = [
        ('Days', 'Days'),
        ('Weeks', 'Weeks'),
        ('Months', 'Months'),
        ('Years', 'Years'),
    ]

    contract_reference = models.CharField(
        max_length=100,
        help_text="Unique contract reference number"
    )
    person = models.ForeignKey(
        'person.Person', 
        on_delete=models.CASCADE, 
        related_name='contracts',
        help_text="Person associated with this contract"
    )
    
    contract_status = models.ForeignKey(
        LookupValue, 
        on_delete=models.PROTECT, 
        related_name='contract_status_records',
        limit_choices_to={'lookup_type__name': CoreLookups.CONTRACT_STATUS, 'is_active': True},
        help_text="Current status of the contract (e.g., Active, Ended)"
    )
    contract_end_reason = models.ForeignKey(
        LookupValue, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name='contract_end_reason_records',
        limit_choices_to={'lookup_type__name': CoreLookups.CONTRACT_END_REASON, 'is_active': True},
        help_text="Reason for contract ending (optional)"
    )
    
    description = models.TextField(
        null=True, 
        blank=True,
        help_text="Optional description of the contract"
    )
    contract_duration = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Duration value"
    )
    contract_period = models.CharField(
        max_length=20, 
        choices=PERIOD_CHOICES,
        help_text="Period unit for duration (Days/Weeks/Months/Years)"
    )
    contract_start_date = models.DateField(help_text="Start date of the contract")
    contract_end_date = models.DateField(help_text="End date of the contract")
    
    contractual_job_position = models.TextField(
        help_text="Job position as stated in the contract"
    )
    
    extension_duration = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Duration of contract extension (optional)"
    )
    extension_period = models.CharField(
        max_length=20, 
        choices=PERIOD_CHOICES, 
        null=True, 
        blank=True,
        help_text="Period unit for extension duration (optional)"
    )
    extension_start_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Start date of the contract extension (optional)"
    )
    extension_end_date = models.DateField(
        null=True, 
        blank=True,
        help_text="End date of the contract extension (optional)"
    )
    
    basic_salary = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        help_text="Basic salary amount"
    )

    objects = VersionedManager()

    class Meta:
        db_table = 'hr_contract'
        verbose_name = 'Contract'
        verbose_name_plural = 'Contracts'
        ordering = ['contract_reference', '-effective_start_date']
        indexes = [
            models.Index(fields=['contract_reference']),
            models.Index(fields=['person']),
            models.Index(fields=['contract_status']),
        ]
        unique_together = [('contract_reference', 'effective_start_date')]
        constraints = [
            CheckConstraint(
                check=Q(contract_end_date__gte=F('contract_start_date')),
                name='contract_end_date_gte_start'
            ),
            CheckConstraint(
                check=Q(basic_salary__gte=0),
                name='contract_basic_salary_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.contract_reference} - {self.person}"

    def get_version_group_field(self):
        return 'contract_reference'

    def clean(self):
        super().clean()
        
        # 1. Validate contract dates
        if self.contract_start_date and self.contract_end_date:
            if self.contract_end_date < self.contract_start_date:
                raise ValidationError({'contract_end_date': 'Contract end date must be after or equal to start date'})
            
        # 2. Validate extension logic
        extension_fields = {'extension_start_date': self.extension_start_date, 
                            'extension_end_date': self.extension_end_date, 
                            'extension_duration': self.extension_duration, 
                            'extension_period': self.extension_period}
        
        provided_extension_fields = [k for k, v in extension_fields.items() if v is not None]
        
        if provided_extension_fields:
            if len(provided_extension_fields) < len(extension_fields):
                 raise ValidationError("All extension fields (start date, end date, duration, period) must be provided if any extension data is present.")
            
            if self.extension_end_date < self.extension_start_date:
                raise ValidationError({'extension_end_date': 'Extension end date must be after or equal to start date'})
            
            if self.contract_end_date and self.extension_start_date < self.contract_end_date:
                raise ValidationError({'extension_start_date': 'Extension start date must be after or equal to contract end date'})

        # 3. Validate lookups
        if self.contract_status_id:
            if self.contract_status.lookup_type.name != CoreLookups.CONTRACT_STATUS:
                 raise ValidationError({'contract_status': 'Invalid lookup type for contract status. Expected CONTRACT_STATUS.'})
             
        if self.contract_end_reason_id:
            if self.contract_end_reason.lookup_type.name != CoreLookups.CONTRACT_END_REASON:
                 raise ValidationError({'contract_end_reason': 'Invalid lookup type for contract end reason. Expected CONTRACT_END_REASON.'})
