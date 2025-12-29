from django.db import models
from .base import StatusChoices, CodeGenerationMixin, DateTrackedModel
from HR.work_structures.managers import DateTrackedModelManager, ScopedModelManager

class Enterprise(CodeGenerationMixin, DateTrackedModel):
    """
    Highest organizational boundary for HR data.
    """
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=128)
    
    objects = DateTrackedModelManager()  # Implements scoped filtering
    
    def get_version_group_field(self):
        return 'code'

    class Meta:
        verbose_name = 'Enterprise'
        verbose_name_plural = 'Enterprises'
        ordering = ['-effective_start_date', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'effective_start_date'],
                name='unique_enterprise_version'
            )
        ]
        indexes = [
            models.Index(fields=['code', 'effective_start_date']),
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



class BusinessGroup(CodeGenerationMixin, DateTrackedModel):
    """
    Organizational unit within an Enterprise.
    Security: Basis for Data Scope filtering
    """
    enterprise = models.ForeignKey(
        Enterprise,
        on_delete=models.PROTECT,
        related_name='business_groups'
    )
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=128)
    objects = DateTrackedModelManager()  # Implements scoped filtering
    
    def get_version_group_field(self):
        return 'code'
    
    def get_version_scope_filters(self):
        return {'enterprise': self.enterprise}

    class Meta:
        verbose_name = 'Business Group'
        verbose_name_plural = 'Business Groups'
        ordering = ['-effective_start_date', 'enterprise', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['enterprise', 'code', 'effective_start_date'],
                name='unique_bg_version_per_enterprise'
            )
        ]
        indexes = [
            models.Index(fields=['enterprise', 'code', 'effective_start_date']),
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
    


class Location(CodeGenerationMixin, models.Model):
    """
    Physical or logical workplace.
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
    
    # Address details (optional)
    address_details = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100)
    
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )
    
    objects = ScopedModelManager()  # Implements scoped filtering
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_code_generation_config(self):
        """Customize code generation for Location"""
        return {
            'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to', 'group', 'company'},
            'scope_filter': {},  # Globally unique
            'min_length': 2,
            'use_acronym': True
        }