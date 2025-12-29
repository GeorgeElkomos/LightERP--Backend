from django.db import models
from .base import DateTrackedModel, StatusChoices, CodeGenerationMixin
from .structure import BusinessGroup, Location
from HR.work_structures.managers import DateTrackedModelManager

class Department(CodeGenerationMixin, DateTrackedModel):
    """
    Organizational unit with date tracking.
    Pattern: Updates create new records, preserving history
    """
    code = models.CharField(max_length=50, blank=True)
    business_group = models.ForeignKey(
        BusinessGroup,
        on_delete=models.PROTECT,
        related_name='departments'
    )
    name = models.CharField(max_length=128)
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='departments'
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='children'
    )
    
    objects = DateTrackedModelManager()  # Implements scoped filtering

    def get_code_generation_config(self):
        """Customize code generation for Department - scoped to business group"""
        return {
            'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to', 'department', 'dept'},
            'scope_filter': {'business_group': self.business_group},  # Unique within business group
            'min_length': 2,
            'use_acronym': True
        }

    def get_version_group_field(self):
        return 'code'
    
    def get_version_scope_filters(self):
        """Department codes are scoped to business_group"""
        return {'business_group': self.business_group}
    
    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        constraints = [
            models.UniqueConstraint(
                fields=['business_group', 'code', 'effective_start_date'],
                name='unique_dept_version'
            )
        ]
        indexes = [
            models.Index(fields=['code', 'effective_start_date']),
            models.Index(fields=['business_group']),
        ]
    
    def __str__(self):
        return f"{self.business_group.code}.{self.code} - {self.name}"


class DepartmentManager(DateTrackedModel):
    """
    Assigns managers to departments with date tracking.
    Only ONE manager can be active per department at any time.
    """
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='managers'
    )
    manager = models.ForeignKey(
        'user_accounts.UserAccount',
        on_delete=models.PROTECT,
        related_name='managed_departments'
    )
    
    objects = DateTrackedModelManager()  # Implements scoped filtering
    
    def get_version_group_field(self):
        # Group by department - only one manager per department at a time
        return 'department_id'
    
    def get_version_scope_filters(self):
        """Only one active manager per department"""
        return {'department': self.department}
    
    class Meta:
        verbose_name = 'Department Manager'
        verbose_name_plural = 'Department Managers'
        constraints = [
            models.UniqueConstraint(
                fields=['department', 'manager', 'effective_start_date'],
                name='unique_dept_manager_assignment'
            )
        ]
        indexes = [
            models.Index(fields=['department', 'effective_start_date', 'effective_end_date']),
        ]

    def clean(self):
        """
        Validate:
        1. Assigned manager corresponds to an active Employee (if Employee model exists)
        2. Only one active manager per department
        """
        from django.apps import apps
        from django.core.exceptions import ValidationError
        from datetime import date
        
        super().clean()
        
        # Validation 1: Manager must have Employee record (if Employee model exists)
        try:
            Employee = apps.get_model('hr', 'Employee')
        except LookupError:
            pass  # Employee model doesn't exist yet
        else:
            employees = Employee.objects.filter(user=self.manager)
            if not employees.exists():
                raise ValidationError('Assigned manager must have an Employee record')

            emp = employees.order_by('-pk').first()

            if hasattr(emp, 'is_active') and not getattr(emp, 'is_active'):
                raise ValidationError("Assigned manager's Employee record is not active")

            if hasattr(emp, 'status'):
                status_val = getattr(emp, 'status')
                if isinstance(status_val, str) and str(status_val).lower() != 'active':
                    raise ValidationError("Assigned manager's Employee record is not active")

            if hasattr(emp, 'effective_end_date') and emp.effective_end_date is not None and self.effective_start_date:
                try:
                    from datetime import date as _date
                    if isinstance(emp.effective_end_date, _date) and emp.effective_end_date < self.effective_start_date:
                        raise ValidationError("Assigned manager is not active on the assignment start date")
                except TypeError:
                    pass
        
        # Validation 2: Only one active manager per department
        if self.department:
            # Check for overlapping assignments to the SAME department
            overlapping = DepartmentManager.objects.filter(
                department=self.department,
                effective_start_date__lt=(self.effective_end_date or date.max),
            ).exclude(pk=self.pk)
            
            overlapping = overlapping.filter(
                models.Q(effective_end_date__isnull=True) | 
                models.Q(effective_end_date__gt=self.effective_start_date)
            )
            
            if overlapping.exists():
                existing = overlapping.first()
                raise ValidationError(
                    f"Department '{self.department.name}' already has an active manager "
                    f"({existing.manager.get_full_name()}) from {existing.effective_start_date}. "
                    f"End-date the existing assignment before creating a new one."
                )
