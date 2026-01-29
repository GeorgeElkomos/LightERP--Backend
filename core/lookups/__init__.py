"""
Generic Lookup Tables Module

Provides configurable dropdown values (lookups) for the application.
"""

# Don't import models here - causes circular import during Django initialization
# Import them where needed instead: from core.lookups.models import LookupType

__all__ = ['LookupType', 'LookupValue']
