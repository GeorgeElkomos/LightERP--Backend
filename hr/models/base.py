import re
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from datetime import date
from hr.managers import DateTrackedModelManager

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
    
    Requirements: C.3.2, C.6.2, C.8.3
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
    
    def get_version_group_field(self):
        """
        Override in child models to specify which field groups versions.
        Example: Department returns 'department_code', Position returns 'code'
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_version_group_field()"
        )
    
    def clean(self):
        """Prevent overlapping date ranges within same entity"""
        if self.effective_end_date and self.effective_start_date > self.effective_end_date:
            raise ValidationError("Start date must be before end date")
        
        # Get the grouping field that identifies this entity
        group_field = self.get_version_group_field()
        group_value = getattr(self, group_field)
        
        # Check for overlapping records (same entity only, excluding self)
        overlapping = self.__class__.objects.filter(
            **{group_field: group_value},  # Critical: same entity only
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
            