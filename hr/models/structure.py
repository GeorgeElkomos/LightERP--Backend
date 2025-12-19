from django.db import models
from hr.models.base import StatusChoices, CodeGenerationMixin
from hr.managers import LocationManager

class Enterprise(CodeGenerationMixin, models.Model):
    """
    Highest organizational boundary for HR data.
    Requirements: C.1
    """
    code = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=128)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Enterprise'
        verbose_name_plural = 'Enterprises'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_code_generation_config(self):
        """Customize code generation for Enterprise"""
        return {
            'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to', 'group', 'company'},
            'scope_filter': {},  # Globally unique
            'min_length': 2,
            'use_acronym': True
        }

    def deactivate(self):
        """Requirement C.1.4: Deactivate instead of delete"""
        self.status = StatusChoices.INACTIVE
        # Call parent's save directly to avoid code generation logic
        super().save(update_fields=['status', 'updated_at'])


class BusinessGroup(CodeGenerationMixin, models.Model):
    """
    Organizational unit within an Enterprise.
    Requirements: C.1
    Security: Basis for Data Scope filtering
    """
    enterprise = models.ForeignKey(
        Enterprise,
        on_delete=models.PROTECT,
        related_name='business_groups'
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=128)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Business Group'
        verbose_name_plural = 'Business Groups'
        ordering = ['enterprise', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['enterprise', 'code'],
                name='unique_bg_code_per_enterprise'
            )
        ]
        indexes = [
            models.Index(fields=['enterprise', 'code']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.enterprise.code}.{self.code} - {self.name}"
    
    def get_code_generation_config(self):
        """Customize code generation for BusinessGroup - scoped to enterprise"""
        return {
            'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to', 'operations', 'division'},
            'scope_filter': {'enterprise': self.enterprise},  # Unique within enterprise
            'min_length': 2,
            'use_acronym': True
        }
    
    def deactivate(self):
        """Deactivate business group instead of delete"""
        self.status = StatusChoices.INACTIVE
        # Call parent's save directly to avoid code generation logic
        super().save(update_fields=['status', 'updated_at'])


class Location(CodeGenerationMixin,models.Model):
    """
    Physical or logical workplace.
    Requirements: C.2
    """
    enterprise = models.ForeignKey(
        Enterprise,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='locations'
    )
    business_group = models.ForeignKey(
        BusinessGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='locations'
    )
    
    code = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=128)
    
    # Address details (optional - C.2.5)
    address_line1 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100)
    
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = LocationManager()  # Implements scoped filtering
    
    def save(self, *args, **kwargs):
        """Generate code from name if not provided"""
        if not self.code and self.name:
            self.code = self._generate_unique_code()
        super().save(*args, **kwargs)
    
    def get_code_generation_config(self):
        """Customize code generation for Location"""
        return {
            'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to', 'group', 'company'},
            'scope_filter': {},  # Globally unique
            'min_length': 2,
            'use_acronym': True
        }    
    