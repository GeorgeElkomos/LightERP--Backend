from django.db import models
from django.core.exceptions import ValidationError
from .base import DateTrackedModel, StatusChoices, CodeGenerationMixin
from .structure import BusinessGroup, Location
from .department import Department
from HR.work_structures.managers import DateTrackedModelManager

class Grade(CodeGenerationMixin, DateTrackedModel):
    """Job level definition (e.g., Grade 1-8)."""
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=128)
    business_group = models.ForeignKey(BusinessGroup, on_delete=models.PROTECT)
    
    objects = DateTrackedModelManager()  # Implements scoped filtering
    
    def get_code_generation_config(self):
        """Customize code generation for Grade - use shorter codes"""
        return {
            'skip_words': set(),  # Don't skip any words for grades
            'scope_filter': {},  # Globally unique
            'min_length': 2,
            'use_acronym': True
        }
    
    def get_version_group_field(self):
        return 'code'
    
    def get_version_scope_filters(self):
        """Return scope filters for version history - scoped to business_group"""
        return {'business_group': self.business_group}
    
    class Meta:
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class GradeRateType(models.Model):
    """
    Types of compensation (Basic Salary, Transportation Allowance, Housing Allowance, etc.).
    Defines whether a rate type uses a range (min/max) or a fixed value.
    """
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    has_range = models.BooleanField(
        default=True,
        help_text="True for min/max range (e.g., Basic Salary), False for fixed value (e.g., Transportation)"
    )
    description = models.TextField(blank=True, null=True)


    
    class Meta:
        db_table = 'hr_grade_rate_type'
        verbose_name = 'Grade Rate Type'
        verbose_name_plural = 'Grade Rate Types'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({'Range' if self.has_range else 'Fixed'})"


class GradeRate(DateTrackedModel):
    """
    Rate definition for a grade and rate type combination.
    Supports both range-based (min/max) and fixed-value compensation.
    
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
    
    currency = models.CharField(max_length=3, default='EGP')
    
    objects = DateTrackedModelManager()
    
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
        """Validate rate data based on rate type"""
        super().clean()
        
        if self.rate_type.has_range:
            # Range-based rates require min and max
            if self.min_amount is None or self.max_amount is None:
                raise ValidationError(
                    f"Rate type '{self.rate_type.name}' requires both min_amount and max_amount"
                )
            if self.min_amount < 0 or self.max_amount < 0:
                raise ValidationError("Amounts must be non-negative")
            if self.min_amount > self.max_amount:
                raise ValidationError("min_amount cannot exceed max_amount")
            # Fixed amount should be null for range-based
            if self.fixed_amount is not None:
                raise ValidationError("Range-based rates should not have fixed_amount set")
        else:
            # Fixed-value rates require fixed_amount
            if self.fixed_amount is None:
                raise ValidationError(
                    f"Rate type '{self.rate_type.name}' requires fixed_amount"
                )
            if self.fixed_amount < 0:
                raise ValidationError("fixed_amount must be non-negative")
            # Min/max should be null for fixed-value
            if self.min_amount is not None or self.max_amount is not None:
                raise ValidationError("Fixed-value rates should not have min_amount or max_amount set")
    
    def __str__(self):
        if self.rate_type.has_range:
            return f"{self.grade.code} - {self.rate_type.name}: {self.min_amount}-{self.max_amount} {self.currency}"
        else:
            return f"{self.grade.code} - {self.rate_type.name}: {self.fixed_amount} {self.currency}"


class Position(CodeGenerationMixin, DateTrackedModel):
    """
    Job position independent of employees.
    """
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=128)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT)
    reports_to = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='direct_reports'
    )
    
    objects = DateTrackedModelManager()  # Implements scoped filtering

    def get_code_generation_config(self):
        """Customize code generation for Position"""
        return {
            'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to'},
            'scope_filter': {},  # Globally unique
            'min_length': 2,
            'use_acronym': True
        }

    def get_version_group_field(self):
        return 'code'
    
    def get_version_scope_filters(self):
        """Return scope filters for version history - scoped to business_group via department"""
        return {'department__business_group': self.department.business_group}
    
    class Meta:
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'
        ordering = ['code', '-effective_start_date']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
