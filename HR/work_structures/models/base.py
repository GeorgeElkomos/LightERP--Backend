import re
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from datetime import date
from HR.work_structures.managers import DateTrackedModelManager

class StatusChoices(models.TextChoices):
    """Standard status choices for HR entities"""
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'


class CodeGenerationMixin:
    """
    Centralized code generation logic for all HR models with code fields.
    
    Usage:
        1. Inherit this mixin in your model
        2. Override get_code_generation_config() to customize behavior
        3. Call super().save() in your model's save() method
    
    Configuration Options:
        - skip_words: Words to ignore when generating acronyms
        - scope_filter: Dict for scoped uniqueness (e.g., {'enterprise': self.enterprise})
        - min_length: Minimum code length (default: 2)
        - use_acronym: Whether to use initials vs truncation (default: True)
    """
    
    def get_code_generation_config(self):
        """
        Override this method to customize code generation behavior.
        
        Returns:
            dict with keys:
                - skip_words: list of words to ignore (default: common connectors)
                - scope_filter: dict for uniqueness check (default: {} = globally unique)
                - min_length: minimum code length (default: 2)
                - use_acronym: use initials vs truncation (default: True)
        """
        return {
            'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to'},
            'scope_filter': {},  # Empty = globally unique
            'min_length': 2,
            'use_acronym': True
        }
    
    def _generate_unique_code(self):
        """Generate readable acronym-based code from name"""
        config = self.get_code_generation_config()
        
        # Remove special chars and split into words
        clean_name = re.sub(r'[^\w\s]', '', self.name)
        words = clean_name.split()
        
        # Filter out skip words
        skip_words = config.get('skip_words', set())
        significant_words = [w for w in words if w.lower() not in skip_words]
        
        # Generate base code
        if config.get('use_acronym', True) and len(significant_words) >= 2:
            # Use initials: "Backend Development" -> "BD"
            base_code = ''.join(w[0].upper() for w in significant_words[:4])
        else:
            # Single word or truncation: use first 4-6 chars
            base_code = clean_name[:6].upper().replace(' ', '')
        
        # Ensure minimum length
        min_length = config.get('min_length', 2)
        if len(base_code) < min_length:
            base_code = clean_name[:max(min_length, 4)].upper().replace(' ', '')
        
        return self._ensure_unique_code(base_code, config.get('scope_filter', {}))
    
    def _ensure_unique_code(self, base_code, scope_filter):
        """Add numeric suffix if code exists"""
        code = base_code
        suffix = 1
        
        # Build filter query
        filter_kwargs = {'code': code}
        filter_kwargs.update(scope_filter)
        
        # Check uniqueness and add suffix if needed
        while self.__class__.objects.filter(**filter_kwargs).exclude(pk=self.pk).exists():
            code = f"{base_code}{suffix}"
            filter_kwargs['code'] = code
            suffix += 1
        
        return code
    
    def save(self, *args, **kwargs):
        """Auto-generate code from name if not provided"""
        if not self.code and hasattr(self, 'name') and self.name:
            self.code = self._generate_unique_code()
        super().save(*args, **kwargs)


class DateTrackedModel(models.Model):
    """
    Abstract base for entities that track changes over time.
    
    Pattern: When updating, END-DATE the current record and CREATE a new one.
    Do NOT modify existing records (preserve history).
    
    Status is computed from effective dates:
    - ACTIVE: effective_start_date <= today AND (effective_end_date is NULL OR effective_end_date >= today)
    - INACTIVE: otherwise (future start date or past end date)
    """
    effective_start_date = models.DateField(
        help_text="Date this version becomes active"
    )
    effective_end_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date this version ends. NULL = currently active"
    )
    
    objects = DateTrackedModelManager()
    
    class Meta:
        abstract = True
        ordering = ['-effective_start_date']
    
    @property
    def status(self):
        """
        Computed status based on effective dates.
        Returns 'ACTIVE' if currently active, 'INACTIVE' otherwise.
        
        Logic:
        - ACTIVE: effective_start_date <= today AND (effective_end_date is NULL OR >= today)
        - INACTIVE: effective_start_date > today OR effective_end_date < today
        """
        return self._compute_status()
    
    @property
    def is_active(self):
        """
        Convenience boolean property for checking if record is currently active.
        Returns True if status is ACTIVE, False otherwise.
        """
        return self.status == StatusChoices.ACTIVE
    
    def _compute_status(self, reference_date=None):
        """
        Internal method to compute status based on effective dates.
        
        Args:
            reference_date: Date to check against. Defaults to today.
        
        Returns:
            StatusChoices.ACTIVE or StatusChoices.INACTIVE
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Not yet started (future record)
        if self.effective_start_date > reference_date:
            return StatusChoices.INACTIVE
        
        # Already ended (past record)
        if self.effective_end_date and self.effective_end_date < reference_date:
            return StatusChoices.INACTIVE
        
        # Currently active
        return StatusChoices.ACTIVE
    
    def deactivate(self, end_date=None):
        """
        Deactivate instead of delete by setting effective_end_date.
        Safely end-dates the record without violating start <= end constraint.
        
        Args:
            end_date: Date to end this record.
        """
        if end_date is None:
            # Default: set end date to yesterday so it's inactive today
            from datetime import timedelta
            end_date = date.today() - timedelta(days=1)
        
        # Prevent start > end error if it started today
        if end_date < self.effective_start_date:
            end_date = self.effective_start_date
            
        self.effective_end_date = end_date
        # Status is now computed property, so just save the end date
        self.save(update_fields=['effective_end_date'])
    
    def get_version_group_field(self):
        """
        Override in child models to specify which field groups versions.
        Example: Department returns 'department_code', Position returns 'code'
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_version_group_field()"
        )
    
    def get_version_scope_filters(self):
        """
        Override to define additional scope filters for version uniqueness.
        Used when codes are scoped (e.g., department codes are unique per business_group).
        Returns: dict of field_name: field_value
        """
        return {}
    
    def clean(self):
        """Prevent overlapping date ranges within same entity"""
        if self.effective_end_date and self.effective_start_date > self.effective_end_date:
            raise ValidationError("Start date must be before end date")
        
        # Get the grouping field that identifies this entity
        group_field = self.get_version_group_field()
        group_value = getattr(self, group_field)
        
        # Build filter with group field and any additional scope filters
        filter_kwargs = {group_field: group_value}
        filter_kwargs.update(self.get_version_scope_filters())
        
        # Check for overlapping records (same entity only, excluding self)
        overlapping = self.__class__.objects.filter(
            **filter_kwargs,
            effective_start_date__lt=(self.effective_end_date or date.max),
        ).exclude(pk=self.pk)
        
        overlapping = overlapping.filter(
            Q(effective_end_date__isnull=True) | 
            Q(effective_end_date__gt=self.effective_start_date)
        )
        
        if overlapping.exists():
            raise ValidationError(
                f"Date range overlaps with existing {group_field}={group_value}"
            )
            