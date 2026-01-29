"""
Core Base Managers Module

Provides custom managers and querysets for base models.

**Architecture:**
- BaseQuerySet: Generic filtering (code/name/search)
- SoftDeleteQuerySet: For models with status field
- VersionedQuerySet: For models with effective_start_date/end_date

Exports:
    QuerySets:
        - BaseQuerySet: filter_by_search_params
        - SoftDeleteQuerySet: active(), inactive()
        - VersionedQuerySet: active_on(), active_between(), all_versions(), latest_version()

    Managers:
        - SoftDeleteManager: For SoftDeleteMixin models
        - VersionedManager: For VersionedMixin models

Usage:
    # For soft-delete models
    from core.base import SoftDeleteMixin, StatusChoices
    from core.base.managers import SoftDeleteManager

    class Employee(SoftDeleteMixin, models.Model):
        objects = SoftDeleteManager()

    # For versioned models
    from core.base import VersionedMixin, StatusChoices
    from core.base.managers import VersionedManager

    class Department(VersionedMixin, models.Model):
        objects = VersionedManager()
"""

from django.db import models
from django.db.models import Q
from core.base.models import StatusChoices


class BaseQuerySet(models.QuerySet):
    """
    Base QuerySet with common filtering methods.

    Methods:
        - filter_by_search_params: Filter by code/name/search
    """

    def filter_by_search_params(self, query_params):
        """
        Apply standard code/name/search filters from query parameters.

        Args:
            query_params: QueryDict or dict with optional keys:
                - code: Exact match (case-insensitive)
                - name: Contains match (case-insensitive)
                - search: Contains match across code and name

        Returns:
            Filtered QuerySet
        """
        queryset = self

        code = query_params.get('code')
        if code:
            queryset = queryset.filter(code__iexact=code)

        name = query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name)

        search = query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )

        return queryset


class SoftDeleteQuerySet(BaseQuerySet):
    """
    QuerySet for SoftDeleteMixin models (models with status field).

    Methods:
        - active(): Return status=ACTIVE records
        - inactive(): Return status=INACTIVE records
    """

    def active(self):
        """Return only active records (status=ACTIVE)."""
        return self.filter(status=StatusChoices.ACTIVE)

    def inactive(self):
        """Return only inactive records (status=INACTIVE)."""
        return self.filter(status=StatusChoices.INACTIVE)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """
    Manager for SoftDeleteMixin models.

    Usage:
        class Employee(SoftDeleteMixin, models.Model):
            objects = SoftDeleteManager()

        Employee.objects.active()
        Employee.objects.inactive()
    """
    pass


class VersionedQuerySet(BaseQuerySet):
    """
    QuerySet for VersionedMixin models (models with effective_start_date/end_date).

    Versioned models do NOT have is_active field - status is computed from dates.

    Methods:
        - active_on(date): Records active on specific date
        - active_between(start, end): Records active in date range
        - all_versions(): All versions including inactive
        - latest_version(group_field, group_value): Most recent version

    Usage:
        class Department(VersionedMixin, models.Model):
            objects = VersionedManager()

        # Get currently active (today)
        Department.objects.active_on(date.today())

        # Get active on specific date
        Department.objects.active_on(date(2024, 1, 1))

        # Get active in date range
        Department.objects.active_between(date(2024, 1, 1), date(2024, 12, 31))

        # Get all versions
        Department.objects.all_versions()

        # Get latest version
        Department.objects.latest_version('code', 'IT')
    """

    def active_on(self, reference_date):
        """
        Return records active on a specific date.

        Args:
            reference_date: Date to check

        Returns:
            QuerySet: Records active on that date
        """
        return self.filter(
            effective_start_date__lte=reference_date
        ).filter(
            Q(effective_end_date__isnull=True) |
            Q(effective_end_date__gt=reference_date)
        )

    def active_between(self, start_date, end_date):
        """
        Return records active at any point in date range.

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            QuerySet: Records active in that range
        """
        return self.filter(
            effective_start_date__lte=end_date
        ).filter(
            Q(effective_end_date__isnull=True) |
            Q(effective_end_date__gt=start_date)
        )

    def all_versions(self):
        """
        Return all versions including inactive/expired.

        Returns:
            QuerySet: All records
        """
        return self.all()

    def latest_version(self, group_field, group_value):
        """
        Get the most recent version of an entity.

        Args:
            group_field: Field that groups versions (e.g., 'code')
            group_value: Value to filter by (e.g., 'IT')

        Returns:
            Model instance or None

        Example:
            # Get latest version of IT department
            latest = Department.objects.latest_version('code', 'IT')
        """
        return self.filter(
            **{group_field: group_value}
        ).order_by('-effective_start_date').first()


class VersionedManager(models.Manager.from_queryset(VersionedQuerySet)):
    """
    Manager for VersionedMixin models.

    Usage:
        class Department(VersionedMixin, models.Model):
            objects = VersionedManager()

        Department.objects.active_on(date.today())
        Department.objects.active_between(start, end)
        Department.objects.all_versions()
        Department.objects.latest_version('code', 'IT')
    """
    pass
