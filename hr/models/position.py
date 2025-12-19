from django.db import models
from django.core.exceptions import ValidationError
from hr.models.base import DateTrackedModel, StatusChoices, CodeGenerationMixin
from hr.models.structure import BusinessGroup, Location
from hr.models.department import Department
from hr.managers import PositionManager, GradeManager

class Grade(CodeGenerationMixin, DateTrackedModel):
    """Job level definition. Requirements: C.8"""
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=128)
    business_group = models.ForeignKey(BusinessGroup, on_delete=models.PROTECT)
    
    objects = GradeManager()  # Implements scoped filtering
    
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
    
    class Meta:
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class GradeRate(models.Model):
    """Salary/benefit ranges for grades. Requirements: C.8"""
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='rates')
    rate_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='EGP')
    effective_start_date = models.DateField()
    effective_end_date = models.DateField(null=True, blank=True)
    
    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Amount must be positive")


class Position(CodeGenerationMixin, DateTrackedModel):
    """
    Job position independent of employees.
    Requirements: C.6, C.7
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
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )
    objects = PositionManager()  # Implements scoped filtering

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
    
    class Meta:
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'
        ordering = ['code', '-effective_start_date']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
