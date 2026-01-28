from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import CheckConstraint, Q, F
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from datetime import datetime, date

class Assignment(VersionedMixin, AuditMixin, models.Model):
    """
    Assignment model for employee job assignments.
    Uses VersionedMixin for temporal versioning.
    """
    HOURLY_SALARIED_CHOICES = [
        ('Hourly', 'Hourly'),
        ('Salaried', 'Salaried'),
    ]
    
    FREQUENCY_CHOICES = [
        ('Day', 'Day'),
        ('Hourly', 'Hourly'),
        ('Month', 'Month'),
        ('Week', 'Week'),
    ]

    person = models.ForeignKey(
        'person.Person', 
        on_delete=models.CASCADE, 
        related_name='assignments',
        help_text="Person associated with this assignment"
    )
    
    business_group = models.ForeignKey(
        'work_structures.Organization',
        on_delete=models.PROTECT,
        related_name='bg_assignments',
        limit_choices_to={'business_group__isnull': True},
        help_text="Root organization (Business Group)"
    )
    
    assignment_no = models.CharField(
        max_length=50,
        help_text="Assignment number"
    )
    
    department = models.ForeignKey(
        'work_structures.Organization',
        on_delete=models.PROTECT,
        related_name='dept_assignments',
        help_text="Department (Organization where name='department')"
    )
    
    job = models.ForeignKey(
        'work_structures.Job',
        on_delete=models.PROTECT,
        related_name='assignments',
        help_text="Job assigned to the person"
    )
    
    position = models.ForeignKey(
        'work_structures.Position',
        on_delete=models.PROTECT,
        related_name='assignments',
        help_text="Position assigned to the person"
    )
    
    grade = models.ForeignKey(
        'work_structures.Grade',
        on_delete=models.PROTECT,
        related_name='assignments',
        help_text="Grade level of the assignment"
    )
    
    payroll = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assignments_by_payroll',
        limit_choices_to={'lookup_type__name': CoreLookups.PAYROLL, 'is_active': True},
        help_text="Payroll associated with the assignment"
    )
    
    salary_basis = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assignments_by_salary_basis',
        limit_choices_to={'lookup_type__name': CoreLookups.SALARY_BASIS, 'is_active': True},
        help_text="Salary basis for the assignment"
    )
    
    line_manager = models.ForeignKey(
        'person.Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_assignments',
        help_text="Line manager for this assignment"
    )
    
    assignment_action_reason = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='assignments_by_action_reason',
        limit_choices_to={'lookup_type__name': CoreLookups.ASSIGNMENT_ACTION_REASON, 'is_active': True},
        help_text="Reason for assignment action (e.g., Hire, Promotion)"
    )
    
    primary_assignment = models.BooleanField(
        default=True,
        help_text="Whether this is the person's primary assignment"
    )
    
    contract = models.ForeignKey(
        'person.Contract',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assignments',
        help_text="Contract associated with this assignment"
    )
    
    assignment_status = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='assignments_by_status',
        limit_choices_to={'lookup_type__name': CoreLookups.ASSIGNMENT_STATUS, 'is_active': True},
        help_text="Status of the assignment (e.g., Active, Suspended)"
    )
    
    project_manager = models.ForeignKey(
        'person.Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_managed_assignments',
        help_text="Project manager for this assignment (optional)"
    )
    
    probation_period_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of the probation period"
    )
    
    probation_period = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assignments_by_probation_period',
        limit_choices_to={'lookup_type__name': CoreLookups.PROBATION_PERIOD, 'is_active': True},
        help_text="Probation period duration (e.g., 3 months)"
    )
    
    probation_period_end = models.DateField(
        null=True,
        blank=True,
        help_text="End date of the probation period (auto-calculated)"
    )
    
    termination_notice_period = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='assignments_by_notice_period',
        limit_choices_to={'lookup_type__name': CoreLookups.TERMINATION_NOTICE_PERIOD, 'is_active': True},
        help_text="Notice period required for termination"
    )
    
    hourly_salaried = models.CharField(
        max_length=20,
        choices=HOURLY_SALARIED_CHOICES,
        default='Salaried'
    )
    
    working_frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='Month'
    )
    
    work_start_time = models.TimeField(null=True, blank=True)
    work_end_time = models.TimeField(null=True, blank=True)
    
    work_from_home = models.BooleanField(default=False)
    is_manager = models.BooleanField(default=False)
    title = models.CharField(max_length=255, null=True, blank=True)
    employment_confirmation_date = models.DateField(null=True, blank=True)

    objects = VersionedManager()

    @property
    def working_hours(self) -> float:
        """Calculate working hours per day based on start/end time"""
        if not self.work_start_time or not self.work_end_time:
            return 0.0
        
        start = datetime.combine(date.today(), self.work_start_time)
        end = datetime.combine(date.today(), self.work_end_time)
        
        if end <= start:
             return 0.0
             
        duration = end - start
        return duration.total_seconds() / 3600.0

    class Meta:
        db_table = 'hr_assignment'
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'
        ordering = ['person', '-effective_start_date']
        indexes = [
            models.Index(fields=['person']),
            models.Index(fields=['business_group']),
            models.Index(fields=['assignment_no']),
            models.Index(fields=['department']),
            models.Index(fields=['job']),
            models.Index(fields=['position']),
        ]
        unique_together = [('assignment_no', 'effective_start_date')]
        constraints = [
            CheckConstraint(
                check=Q(work_end_time__gt=F('work_start_time')) | Q(work_start_time__isnull=True) | Q(work_end_time__isnull=True),
                name='assignment_work_end_after_start'
            ),
        ]

    def get_version_group_field(self):
        return 'assignment_no'

    def clean(self):
        super().clean()
        
        # 1. Validate lookups
        lookup_fields = [
            ('payroll', CoreLookups.PAYROLL),
            ('salary_basis', CoreLookups.SALARY_BASIS),
            ('assignment_action_reason', CoreLookups.ASSIGNMENT_ACTION_REASON),
            ('assignment_status', CoreLookups.ASSIGNMENT_STATUS),
            ('probation_period', CoreLookups.PROBATION_PERIOD),
            ('termination_notice_period', CoreLookups.TERMINATION_NOTICE_PERIOD),
        ]
        
        for field_name, lookup_type_obj in lookup_fields:
            val = getattr(self, field_name)
            if val and val.lookup_type.name != lookup_type_obj:
                raise ValidationError({field_name: f'Invalid lookup type. Expected {lookup_type_obj}.'})

        # 3. Validate FKs belong to same Business Group
        if self.business_group_id:
            if self.department_id:
                if self.department.get_root_business_group().id != self.business_group_id:
                     raise ValidationError({'department': 'Department must belong to the selected Business Group.'})
            
            if self.job_id:
                if self.job.business_group_id != self.business_group_id:
                     raise ValidationError({'job': 'Job must belong to the selected Business Group.'})
            
            if self.position_id:
                if self.position.organization.get_root_business_group().id != self.business_group_id:
                     raise ValidationError({'position': 'Position must belong to the selected Business Group.'})
            
            if self.grade_id:
                if self.grade.organization_id != self.business_group_id:
                     raise ValidationError({'grade': 'Grade must belong to the selected Business Group.'})

        # 4. Work time validation
        if self.work_start_time and self.work_end_time:
            if self.work_end_time <= self.work_start_time:
                raise ValidationError({'work_end_time': 'Work end time must be after start time.'})
