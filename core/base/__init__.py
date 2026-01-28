"""
Core Base Module

Provides shared base classes, mixins, and utilities for all LightERP modules.

**Architecture:**
Each feature is a separate mixin that can be composed together.

Exports:
    Basic Utilities:
        - StatusChoices: Standard ACTIVE/INACTIVE status choices

    Individual Feature Mixins:
        - AuditMixin: Adds created_at, updated_at, created_by, updated_by
        - SoftDeleteMixin: Adds is_active + soft delete behavior
        - VersionedMixin: Adds effective_start_date, effective_end_date (status is computed)
        - CodeGenerationMixin: Auto-generates codes from names

    Managers & QuerySets:
        - BaseQuerySet: Base queryset with filter_by_search_params
        - SoftDeleteQuerySet: QuerySet with active()/inactive() filters
        - SoftDeleteManager: Manager for SoftDeleteMixin models
        - VersionedQuerySet: QuerySet with versioned query methods
        - VersionedManager: Manager for VersionedMixin models

Usage Examples:

    # Soft delete only
    from core.base import SoftDeleteMixin
    from core.base.managers import SoftDeleteManager

    class Employee(SoftDeleteMixin, models.Model):
        name = models.CharField(max_length=128)
        objects = SoftDeleteManager()

    # Versioned models (status computed from dates)
    from core.base import VersionedMixin, CodeGenerationMixin
    from core.base.managers import VersionedManager

    class Department(CodeGenerationMixin, VersionedMixin, models.Model):
        code = models.CharField(max_length=50, blank=True)
        name = models.CharField(max_length=128)
        objects = VersionedManager()

        def get_version_group_field(self):
            return 'code'
"""

# Import from local modules
from core.base.models import (
    StatusChoices,
    AuditMixin,
    # CodeGenerationMixin,  # Commented out in models.py
    SoftDeleteMixin,
    VersionedMixin,
)

from core.base.managers import (
    BaseQuerySet,
    VersionedQuerySet,
    VersionedManager,
    SoftDeleteQuerySet,
    SoftDeleteManager,
)

__all__ = [
    # Basic Utilities
    'StatusChoices',

    # Individual Feature Mixins
    'AuditMixin',
    'SoftDeleteMixin',
    'VersionedMixin',
    # 'CodeGenerationMixin',  # Commented out in models.py

    # Managers & QuerySets
    'BaseQuerySet',
    'VersionedQuerySet',
    'VersionedManager',
    'SoftDeleteQuerySet',
    'SoftDeleteManager',
]

