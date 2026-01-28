from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from core.base.models import (
    VersionedMixin,
    SoftDeleteMixin,
    AuditMixin)
from core.base.managers import VersionedManager, SoftDeleteManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from .organization import Organization
from .location import Location


class Grade(SoftDeleteMixin, AuditMixin, models.Model):
    """
    Job level definition (e.g., Grade 1-8).

    Each business group has its own set of grades with unique sequences.

    Mixins:
    - SoftDeleteMixin: Soft delete with status field (ACTIVE/INACTIVE)
    - AuditMixin: Tracks creation/updates

    Fields:
    - organization: FK to root Organization (Business Group)
    - sequence: Numeric order within business group (must be unique per BG)
    - grade_name: FK to LookupValue (GRADE_NAME)

    Validation:
    - Organization must be root (business_group is None)
    - Sequence must be > 0
    - Grade name must be valid GRADE_NAME lookup and active
    - Organization must be active
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='grades',
        limit_choices_to={'business_group__isnull': True},
        help_text="Root organization (Business Group) that owns this grade"
    )

    sequence = models.IntegerField(
        help_text="Numeric order of grade within business group (lower = more junior)"
    )

    grade_name = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='grades_by_name',
        limit_choices_to={'lookup_type__name': CoreLookups.GRADE_NAME, 'is_active': True},
        help_text="Grade name from lookup (e.g., Grade 1, Grade 2, Manager Level)"
    )

    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Effective from date"
    )

    objects = SoftDeleteManager()

    class Meta:
        db_table = 'hr_grade'
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
        ordering = ['organization', 'sequence']
        indexes = [
            models.Index(fields=['status', 'organization', 'sequence']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'sequence'],
                name='unique_grade_sequence_per_org'
            ),
            models.UniqueConstraint(
                fields=['organization', 'grade_name'],
                name='unique_grade_name_per_org'
            ),
            models.CheckConstraint(
                check=models.Q(sequence__gt=0),
                name='grade_sequence_positive'
            ),
        ]

    def __str__(self):
        return f"{self.grade_name.name} (Seq: {self.sequence})"

    def clean(self):
        """Validate grade data"""
        super().clean()

        # Validation 1: Organization must be root (business group)
        if self.organization_id:
            if not self.organization.is_business_group:
                raise ValidationError({
                    'organization': 'Grade must belong to a root organization (Business Group), not a child organization'
                })

            # Check if organization is active (for versioned models, check if active today)
            from datetime import date
            if hasattr(self.organization, 'effective_end_date'):
                if not self.organization.active_on(date.today()):
                    raise ValidationError({
                        'organization': f'Organization "{self.organization.organization_name}" is not currently active'
                    })

        # Validation 2: Sequence must be positive
        if self.sequence is not None and self.sequence <= 0:
            raise ValidationError({
                'sequence': 'Sequence must be greater than 0'
            })

        # Validation 3: Grade name lookup validation
        if self.grade_name_id:
            if self.grade_name.lookup_type.name != CoreLookups.GRADE_NAME:
                raise ValidationError({
                    'grade_name': 'Must be a GRADE_NAME lookup value'
                })
            if not self.grade_name.is_active:
                raise ValidationError({
                    'grade_name': f'Grade name "{self.grade_name.name}" is inactive'
                })


class GradeRateType(AuditMixin, models.Model):
    """
    Types of compensation (Basic Salary, Transportation Allowance, Housing Allowance, etc.).
    
    Mixins:
    - AuditMixin: Tracks creation/updates
    """
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'hr_grade_rate_type'
        verbose_name = 'Grade Rate Type'
        verbose_name_plural = 'Grade Rate Types'
        ordering = ['code']
    
    def __str__(self):
        return self.code


class GradeRate(VersionedMixin, AuditMixin, models.Model):
    """
    Rate definition for a grade and rate type combination.
    Supports both range-based (min/max) and fixed-value compensation.
    
    Mixins:
    - VersionedMixin: Temporal versioning
    - AuditMixin: Tracks creation/updates
    
    Examples:
    - Grade 1, Basic Salary: min=5000, max=10000
    - Grade 1, Transportation: fixed=250
    """
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='rate_levels')
    rate_type = models.ForeignKey(GradeRateType, on_delete=models.PROTECT, related_name='levels')
    
    # For range-based rates (e.g., Basic Salary)
    min_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Minimum amount for range-based rates"
    )
    max_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Maximum amount for range-based rates"
    )
    
    # For fixed-value rates (e.g., Transportation Allowance)
    fixed_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Fixed amount for non-range rates"
    )
    
    currency = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='grade_rates',
        limit_choices_to={'lookup_type__name': CoreLookups.CURRENCY, 'is_active': True},
        null=True,
        blank=True,
        help_text="Currency lookup value"
    )
    
    objects = VersionedManager()  # Implements temporal/versioned
    
    class Meta:
        db_table = 'hr_grade_rate'
        verbose_name = 'Grade Rate Level'
        verbose_name_plural = 'Grade Rate Levels'
        ordering = ['grade', 'rate_type', '-effective_start_date']
        constraints = [
            models.UniqueConstraint(
                fields=['grade', 'rate_type', 'effective_start_date'],
                name='unique_grade_rate_effective_start'
            )
        ]
    
    def get_version_group_field(self):
        """Use grade as the primary grouping field"""
        return 'grade'
    
    def get_version_scope_filters(self):
        """Versions are scoped to same grade and rate_type"""
        return {
            'rate_type': self.rate_type
        }
    
    def clean(self):
        """Validate rate data"""
        super().clean()
        
        has_range_values = self.min_amount is not None or self.max_amount is not None
        has_fixed_value = self.fixed_amount is not None
        
        if has_range_values and has_fixed_value:
             raise ValidationError("Cannot set both fixed amount and range amounts")
        
        if has_range_values:
            if self.min_amount is None or self.max_amount is None:
                raise ValidationError("Both min_amount and max_amount are required for range-based rates")
            if self.min_amount < 0 or self.max_amount < 0:
                raise ValidationError("Amounts must be non-negative")
            if self.min_amount > self.max_amount:
                raise ValidationError("min_amount cannot exceed max_amount")
                
        if has_fixed_value:
            if self.fixed_amount < 0:
                raise ValidationError("fixed_amount must be non-negative")
                
        if not has_range_values and not has_fixed_value:
             raise ValidationError("Must specify either fixed_amount or min/max amounts")
    
    def __str__(self):
        grade_str = self.grade.grade_name.name if self.grade.grade_name else str(self.grade.sequence)
        
        if self.fixed_amount is not None:
            return f"{grade_str} - {self.rate_type.code}: {self.fixed_amount} {self.currency}"
        elif self.min_amount is not None:
            return f"{grade_str} - {self.rate_type.code}: {self.min_amount}-{self.max_amount} {self.currency}"
        else:
            return f"{grade_str} - {self.rate_type.code}: Undefined"


class Position(VersionedMixin, AuditMixin, models.Model):
    """
    Job position with versioning support.

    Positions are specific instances of jobs within an organization structure.
    Uses VersionedMixin for temporal versioning.

    Mixins:
    - VersionedMixin: Temporal versioning with effective_start_date/effective_end_date
    - AuditMixin: Tracks creation/updates

    Fields:
    - code: Position code (unique within version group)
    - business_group: FK to root Organization
    - position_family/category/title/type: FKs to LookupValues
    - position_sync: synchronization flag
    - organization: FK to Organization (department/unit where position exists)
    - job: FK to Job (job definition this position is based on)
    - status: FK to LookupValue (POSITION_STATUS)
    - location: FK to Location
    - full_time_equivalent: Decimal (0.1-1.5, where 1.0 = full time)
    - head_count: Integer (number of people for this position, default 1)
    - payroll: FK to LookupValue (PAYROLL_TYPE)
    - grade: FK to Grade
    - salary_basis: FK to LookupValue (SALARY_BASIS)
    - reports_to: Self-referential FK (reporting hierarchy)
    - effective_start_date, effective_end_date: From VersionedMixin
    """
    code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Position code (unique within version group)"
    )

    # no need to store business_group separately if we can get it via organization->business_group
    @property
    def business_group(self):
        """Returns the root organization (Business Group) of the managed organization"""
        return self.organization.get_root_business_group()

    position_title = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='positions_by_title',
        limit_choices_to={'lookup_type__name': CoreLookups.POSITION_TITLE, 'is_active': True},
        help_text="Position title"
    )

    position_type = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='positions_by_type',
        limit_choices_to={'lookup_type__name': CoreLookups.POSITION_TYPE, 'is_active': True},
        help_text="Position type (e.g., Regular, Temporary)"
    )

    position_sync = models.BooleanField(
        default=False,
        help_text="Synchronization flag"
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='positions',
        help_text="Organization (department/unit) where this position exists"
    )

    job = models.ForeignKey(
        'Job',
        on_delete=models.PROTECT,
        related_name='positions',
        help_text="Job definition this position is based on"
    )

    position_status = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='positions_by_status',
        limit_choices_to={'lookup_type__name': CoreLookups.POSITION_STATUS, 'is_active': True},
        help_text="Position status (e.g., Active, Frozen, Eliminated)"
    )

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='positions',
        null=True,
        blank=True,
        help_text="Physical location of position"
    )

    full_time_equivalent = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.00,
        help_text="FTE: 1.0 = full time, 0.5 = half time (range: 0.1-1.5)"
    )

    head_count = models.IntegerField(
        default=1,
        help_text="Number of people for this position (headcount)"
    )

    payroll = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='positions_by_payroll',
        limit_choices_to={'lookup_type__name': CoreLookups.PAYROLL, 'is_active': True},
        null=True,
        blank=True,
        help_text="Payroll type"
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        related_name='positions',
        null=True,
        blank=True,
        help_text="Grade/level for this position"
    )

    salary_basis = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='positions_by_salary_basis',
        limit_choices_to={'lookup_type__name': CoreLookups.SALARY_BASIS, 'is_active': True},
        null=True,
        blank=True,
        help_text="Salary basis (e.g., Monthly, Hourly)"
    )

    reports_to = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='direct_reports',
        help_text="Reporting position (supervisory hierarchy)"
    )
    
    # M2M relationships for position requirements
    # Competencies with proficiency levels (through model)
    competencies = models.ManyToManyField(
        'person.Competency',
        through='person.PositionCompetencyRequirement',
        related_name='required_for_positions',
        blank=True,
        help_text="Required competencies with proficiency levels"
    )
    
    # Qualifications (through model for type/title requirements)
    # Note: through_fields specifies (position, qualification_type) - we use type as the main link
    qualifications = models.ManyToManyField(
        LookupValue,
        through='PositionQualificationRequirement',
        through_fields=('position', 'qualification_type'),
        related_name='required_for_positions',
        blank=True,
        help_text="Required qualification types/titles"
    )

    objects = VersionedManager()

    class Meta:
        db_table = 'hr_position'
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'
        ordering = ['organization', 'code']
        indexes = [
            models.Index(fields=['organization', 'effective_start_date', 'effective_end_date']),
            models.Index(fields=['code']),
            models.Index(fields=['organization', 'job']),
            models.Index(fields=['position_status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'organization', 'effective_start_date'],
                name='unique_position_code_org_start_date'
            ),
            models.CheckConstraint(
                check=models.Q(full_time_equivalent__gte=0.1) & models.Q(full_time_equivalent__lte=1.5),
                name='position_fte_valid_range'
            ),
            models.CheckConstraint(
                check=models.Q(head_count__gt=0),
                name='position_headcount_positive'
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.position_title.name} ({self.organization.organization_name})"

    def get_version_group_field(self):
        """Group versions by code"""
        return 'code'

    def get_version_scope_filters(self):
        """Scope versions by organization"""
        return {'organization': self.organization}

    def clean(self):
        """Validate position data"""
        super().clean()

        from datetime import date
        today = date.today()

        # Validation 1: Business group validation via organization
        bg = self.business_group if self.organization_id else None
        if bg:
            if not bg.is_business_group:
                raise ValidationError({
                    'organization': 'Position must belong to an organization that has a valid root (Business Group)'
                })

            # Check if business group is active
            if hasattr(bg, 'effective_end_date'):
                if not bg.active_on(today):
                    raise ValidationError({
                        'organization': f'Business group "{bg.organization_name}" for this organization is not currently active'
                    })

        # Validation 2: Organization must belong to same business group
        # (This is implicitly handled by Validation 1 and the property logic, 
        # but we can keep additional checks if needed)

        # Validation 3: Job must belong to same business group
        if self.job_id and bg:
            if self.job.business_group_id != bg.id:
                raise ValidationError({
                    'job': f'Job must belong to business group "{bg.organization_name}"'
                })

        # Validation 4: Grade must belong to same business group (if provided)
        if self.grade_id and bg:
            if self.grade.organization_id != bg.id:
                raise ValidationError({
                    'grade': f'Grade must belong to business group "{bg.organization_name}"'
                })

        # Validation 5: Location must belong to same business group (if provided)
        if self.location_id and bg:
            if self.location.business_group_id != bg.id:
                raise ValidationError({
                    'location': f'Location must belong to business group "{bg.organization_name}"'
                })

        # Validation 6: FTE range validation
        if self.full_time_equivalent is not None:
            from decimal import Decimal
            fte = Decimal(str(self.full_time_equivalent))
            if fte < Decimal('0.1') or fte > Decimal('1.5'):
                raise ValidationError({
                    'full_time_equivalent': 'FTE must be between 0.1 and 1.5'
                })

        # Validation 7: Head count validation
        if self.head_count is not None and self.head_count <= 0:
            raise ValidationError({
                'head_count': 'Head count must be greater than 0'
            })

        # Validation 8: All lookup validations
        lookup_validations = [
            ('position_title', CoreLookups.POSITION_TITLE),
            ('position_type', CoreLookups.POSITION_TYPE),
            ('position_status', CoreLookups.POSITION_STATUS),
            ('payroll', CoreLookups.PAYROLL),
            ('salary_basis', CoreLookups.SALARY_BASIS),
        ]

        for field_name, lookup_type_name in lookup_validations:
            field_id = f'{field_name}_id'
            if hasattr(self, field_id) and getattr(self, field_id):
                lookup_obj = getattr(self, field_name)
                if lookup_obj.lookup_type.name != lookup_type_name:
                    raise ValidationError({
                        field_name: f'Must be a {lookup_type_name} lookup value'
                    })
                if not lookup_obj.is_active:
                    raise ValidationError({
                        field_name: f'{lookup_obj.name} is inactive'
                    })


class Job(VersionedMixin, AuditMixin, models.Model):
    """
    Job definition with versioning support.

    Jobs are owned by business groups (root organizations) and define:
    - Required qualifications, competencies, and grades
    - Job responsibilities (stored as JSON list)

    Uses VersionedMixin for temporal versioning - changes create new versions
    rather than updating in place.

    Mixins:
    - VersionedMixin: Temporal versioning with effective_start_date/effective_end_date
    - AuditMixin: Tracks creation/updates

    Fields:
    - code: Unique job identifier
    - business_group: FK to root Organization
    - job_category: FK to LookupValue (JOB_CATEGORY)
    - job_title: FK to LookupValue (JOB_TITLE)
    - job_description: Detailed description
    - responsibilities: JSON list of responsibility strings
    - qualifications: M2M to Qualification (required qualifications)
    - competencies: M2M to Competency (required competencies)
    - grades: M2M to Grade (valid grades for this job)
    """
    code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Job code (unique within version group)"
    )

    business_group = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='jobs',
        limit_choices_to={'business_group__isnull': True},
        help_text="Root organization (Business Group) that owns this job"
    )

    job_category = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='jobs_by_category',
        limit_choices_to={'lookup_type__name': CoreLookups.JOB_CATEGORY, 'is_active': True},
        help_text="Job category (e.g., Management, Technical, Administrative)"
    )

    job_title = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='jobs_by_title',
        limit_choices_to={'lookup_type__name': CoreLookups.JOB_TITLE, 'is_active': True},
        help_text="Job title (e.g., Software Engineer, Manager)"
    )


    job_description = models.TextField(
        help_text="Detailed job description"
    )

    responsibilities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of job responsibilities (stored as JSON array)"
    )


    # M2M relationships for job requirements
    # Competencies with proficiency levels (through model)
    competencies = models.ManyToManyField(
        'person.Competency',
        through='person.JobCompetencyRequirement',
        related_name='required_for_jobs',
        blank=True,
        help_text="Required competencies with proficiency levels"
    )

    # Qualifications (through model for type/title requirements)
    # Note: through_fields specifies (job, qualification_type) - we use type as the main link
    qualifications = models.ManyToManyField(
        LookupValue,
        through='JobQualificationRequirement',
        through_fields=('job', 'qualification_type'),
        related_name='required_for_jobs',
        blank=True,
        help_text="Required qualification types/titles"
    )

    # Valid grades for this job (simple M2M, no through model needed)
    grades = models.ManyToManyField(
        Grade,
        related_name='jobs',
        blank=True,
        help_text="Valid grades for this job"
    )

    objects = VersionedManager()

    class Meta:
        db_table = 'hr_job'
        verbose_name = 'Job'
        verbose_name_plural = 'Jobs'
        ordering = ['business_group', 'code']
        indexes = [
            models.Index(fields=['business_group', 'effective_start_date', 'effective_end_date']),
            models.Index(fields=['code']),
            models.Index(fields=['job_category']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'business_group', 'effective_start_date'],
                name='unique_job_code_bg_start_date'
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.job_title.name} ({self.business_group.organization_name})"

    def get_version_group_field(self):
        """Group versions by code"""
        return 'code'

    def get_version_scope_filters(self):
        """Scope versions by business group"""
        return {'business_group': self.business_group}

    def clean(self):
        """Validate job data"""
        super().clean()

        # Validation 1: Business group must be root organization
        if self.business_group_id:
            if not self.business_group.is_business_group:
                raise ValidationError({
                    'business_group': 'Job must belong to a root organization (Business Group)'
                })

            # Check if business group is active
            today = date.today()
            if hasattr(self.business_group, 'effective_end_date'):
                if not self.business_group.active_on(today):
                    raise ValidationError({
                        'business_group': f'Business group "{self.business_group.organization_name}" is not currently active'
                    })

        # Validation 2: Job category lookup
        if self.job_category_id:
            if self.job_category.lookup_type.name != CoreLookups.JOB_CATEGORY:
                raise ValidationError({
                    'job_category': 'Must be a JOB_CATEGORY lookup value'
                })
            if not self.job_category.is_active:
                raise ValidationError({
                    'job_category': f'Job category "{self.job_category.name}" is inactive'
                })

        # Validation 3: Job title lookup
        if self.job_title_id:
            if self.job_title.lookup_type.name != CoreLookups.JOB_TITLE:
                raise ValidationError({
                    'job_title': 'Must be a JOB_TITLE lookup value'
                })
            if not self.job_title.is_active:
                raise ValidationError({
                    'job_title': f'Job title "{self.job_title.name}" is inactive'
                })

        # Validation 4: Responsibilities must be a list of strings
        if self.responsibilities is not None:
            if not isinstance(self.responsibilities, list):
                raise ValidationError({
                    'responsibilities': 'Responsibilities must be a list'
                })

            for idx, item in enumerate(self.responsibilities):
                if not isinstance(item, str):
                    raise ValidationError({
                        'responsibilities': f'Responsibility at index {idx} must be a string, got {type(item).__name__}'
                    })

        # Validation 5: Job description cannot be empty
        if not self.job_description or not self.job_description.strip():
            raise ValidationError({
                'job_description': 'Job description cannot be empty'
            })
