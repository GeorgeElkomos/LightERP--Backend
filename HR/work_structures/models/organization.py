from django.db import models
from django.core.exceptions import ValidationError
from datetime import time, datetime
from core.base.models import VersionedMixin, AuditMixin
from core.base.managers import VersionedManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from .location import Location


class Organization(VersionedMixin, AuditMixin, models.Model):
    """
    Unified organization model - replaces BusinessGroup + Department.

    Supports hierarchical structure:
    - Root organizations (business_group=None) = Business Groups
    - Child organizations (business_group=FK) = Departments/Units

    Mixins:
    - VersionedMixin: Temporal versioning with effective_start_date/effective_end_date
    - AuditMixin: Tracks created_by, updated_by, created_at, updated_at

    Fields:
    - organization_name: Unique identifier
    - business_group: Self-FK to root organization (null for business groups)
    - organization_type: FK to LookupValue (Organization Type)
    - location: FK to Location
    - work_start_time/work_end_time: Working hours
    - effective_start_date/effective_end_date: From VersionedMixin

    Computed Properties:
    - is_business_group: True if business_group is None
    - working_hours: Calculated from work times
    - hierarchy_level: Depth in hierarchy (0 for business groups)
    """

    organization_name = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique organization name"
    )

    business_group = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='child_organizations',
        limit_choices_to={'business_group__isnull': True},
        help_text="Root organization (null for business groups)"
    )

    organization_type = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='organizations_by_type',
        limit_choices_to={'lookup_type__name': CoreLookups.ORGANIZATION_TYPE, 'is_active': True},
        help_text="Organization type from lookup"
    )

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='organizations',
        null=True,
        blank=True,
        help_text="Primary location of organization"
    )


    work_start_time = models.TimeField(
        default=time(9, 0),
        help_text="Work start time (e.g., 09:00)"
    )

    work_end_time = models.TimeField(
        default=time(17, 0),
        help_text="Work end time (e.g., 17:00)"
    )

    objects = VersionedManager()

    def save(self, *args, **kwargs):
        """
        Save organization.
        
        Custom logic:
        - If this is a Business Group (root organization) and has a location,
          automatically assign this Business Group to the location if it doesn't have one.
        """
        super().save(*args, **kwargs)

        # Automatic Location linking for Business Groups
        if self.is_business_group and self.location:
            # Check if location needs to be updated (avoid unnecessary DB writes)
            # We refresh from DB to ensure we have latest state, although self.location might be cached
            if self.location.business_group_id is None:
                self.location.business_group = self
                # Update only the business_group field to minimize side effects
                self.location.save(update_fields=['business_group'])

    class Meta:
        db_table = 'hr_organization'
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        ordering = ['organization_name']  # Removed business_group from ordering to avoid infinite loop
        indexes = [
            models.Index(fields=['business_group', 'effective_start_date', 'effective_end_date']),
            models.Index(fields=['organization_name']),
            models.Index(fields=['location']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(work_end_time__gt=models.F('work_start_time')),
                name='work_end_after_start'
            ),
        ]

    def __str__(self):
        if self.is_business_group:
            return f"{self.organization_name} - {self.organization_type.name} (BG)"
        return f"{self.business_group.organization_name}.{self.organization_name} - {self.organization_type.name}"

    @property
    def is_business_group(self) -> bool:
        """Check if this is a root business group"""
        return self.business_group_id is None

    @property
    def working_hours(self) -> float:
        """Calculate working hours per day"""
        if not self.work_start_time or not self.work_end_time:
            return 0.0

        # Convert to datetime for calculation
        start = datetime.combine(datetime.today(), self.work_start_time)
        end = datetime.combine(datetime.today(), self.work_end_time)

        duration = end - start
        return duration.total_seconds() / 3600.0  # Convert to hours

    @property
    def hierarchy_level(self) -> int:
        """
        Calculate hierarchy depth (0 = business group, 1 = first level child, etc.)
        Uses iterative approach to avoid recursion depth issues
        """
        if self.is_business_group:
            return 0

        level = 0
        current = self
        max_depth = 10  # Prevent infinite loops

        while current.business_group_id and level < max_depth:
            level += 1
            current = current.business_group

        return level

    def get_version_group_field(self):
        """Version grouping by organization_name - each organization can have multiple versions"""
        return 'organization_name'

    def get_version_scope_filters(self):
        """Scope for version overlap detection"""
        return {'organization_name': self.organization_name}

    def clean(self):
        """Validate organization data"""
        super().clean()

        # Validate organization type lookup
        if self.organization_type:
            if self.organization_type.lookup_type.name != CoreLookups.ORGANIZATION_TYPE:
                raise ValidationError({'organization_type': 'Must be an Organization Type lookup value'})
            if not self.organization_type.is_active:
                raise ValidationError({'organization_type': 'Selected organization type is inactive'})

        # Validate location exists and belongs to business group
        if self.location_id:
            if not Location.objects.filter(pk=self.location_id).exists():
                raise ValidationError({'location': 'Location not found'})

            # If this is a child organization, validate location belongs to business group
            if self.business_group_id:
                location = Location.objects.get(pk=self.location_id)
                # Get the root business group
                root_bg = self.business_group if self.business_group.is_business_group else self.business_group.business_group

                # Check if location's business_group matches root BG
                # Note: Location model has business_group FK, need to check structure
                if hasattr(location, 'business_group') and location.business_group_id != root_bg.id:
                    raise ValidationError({
                        'location': f'Location must belong to business group "{root_bg.organization_type.name}"'
                    })

        # Validate work times
        if self.work_start_time and self.work_end_time:
            if self.work_end_time <= self.work_start_time:
                raise ValidationError({
                    'work_end_time': 'Work end time must be after work start time'
                })

        # Validate business group (if not a root BG)
        if self.business_group_id:
            try:
                bg = Organization.objects.get(pk=self.business_group_id)

                # Business group must be a root organization
                if not bg.is_business_group:
                    raise ValidationError({
                        'business_group': 'Business group must be a root organization (business_group=null)'
                    })

                # Check for circular reference
                if self.pk and self.business_group_id == self.pk:
                    raise ValidationError({
                        'business_group': 'Organization cannot be its own business group (circular reference)'
                    })

                # Check if business group is active (has valid date range)
                # For VersionedMixin, check if it has an active version
                from datetime import date
                today = date.today()
                active_bg = Organization.objects.active_on(today).filter(pk=self.business_group_id).exists()
                if not active_bg:
                    raise ValidationError({
                        'business_group': 'Selected business group is not active'
                    })

            except Organization.DoesNotExist:
                raise ValidationError({'business_group': 'Business group not found'})

        # Validate effective dates
        if self.effective_start_date and self.effective_end_date:
            if self.effective_end_date <= self.effective_start_date:
                raise ValidationError({
                    'effective_end_date': 'Effective end date must be after effective start date'
                })

    def get_ancestors(self):
        """Get all ancestors up to root business group (iterative to avoid recursion)"""
        ancestors = []
        current = self.business_group
        max_depth = 10  # Safety limit

        while current and len(ancestors) < max_depth:
            ancestors.append(current)
            current = current.business_group

        return ancestors

    def get_root_business_group(self):
        """Get the root business group for this organization"""
        if self.is_business_group:
            return self

        current = self
        max_depth = 10
        depth = 0

        while current.business_group and depth < max_depth:
            current = current.business_group
            depth += 1

        return current

