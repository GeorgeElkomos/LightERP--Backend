from core.lookups.models import LookupValue
from core.base.models import SoftDeleteMixin, AuditMixin
from core.base.managers import SoftDeleteManager
from HR.lookup_config import CoreLookups
from django.db import models
from django.core.exceptions import ValidationError


class Location(SoftDeleteMixin, AuditMixin, models.Model):
    """
    Physical or logical workplace.

    Mixins:
    - SoftDeleteMixin: Soft delete with status field (ACTIVE/INACTIVE)
    - AuditMixin: Tracks created_by, updated_by, created_at, updated_at

    Fields:
    - location_name: Unique identifier
    - business_group: FK to Organization (root business group)
    - description: Optional description
    - country: FK to LookupValue (Country)
    - city: FK to LookupValue (City, child of country)
    - zone: Street zone/district
    - street: Street name
    - building: Building number/name
    - floor: Floor number
    - office: Office number
    - po_box: PO Box number
    """
    location_name = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="Unique location name"
    )

    business_group = models.ForeignKey(
        'Organization',
        on_delete=models.PROTECT,
        related_name='locations',
        limit_choices_to={'business_group__isnull': True},  # Only root organizations (business groups)
        help_text="Root organization (Business Group) that owns this location",
        null=True,
        blank=True
    )
    description = models.TextField(blank=True)

    # Address details using lookups
    country = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='locations_by_country',
        limit_choices_to={'lookup_type__name': CoreLookups.COUNTRY, 'is_active': True},
        help_text="Country lookup",
        null=True,
        blank=True
    )
    city = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='locations_by_city',
        limit_choices_to={'lookup_type__name': CoreLookups.CITY, 'is_active': True},
        help_text="City lookup (must be child of selected country)",
        null=True,
        blank=True
    )

    # Optional address fields
    zone = models.CharField(max_length=100, blank=True, help_text="Street zone/district")
    street = models.CharField(max_length=200, blank=True, help_text="Street name")
    building = models.CharField(max_length=100, blank=True, help_text="Building number/name")
    floor = models.CharField(max_length=50, blank=True, help_text="Floor number")
    office = models.CharField(max_length=50, blank=True, help_text="Office number")
    po_box = models.CharField(max_length=50, blank=True, help_text="PO Box")

    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Effective from date"
    )

    objects = SoftDeleteManager()

    class Meta:
        db_table = 'hr_location'
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'
        ordering = ['location_name']
        indexes = [
            models.Index(fields=['status', 'location_name']),
            models.Index(fields=['business_group', 'status']),
            models.Index(fields=['country', 'city']),
        ]

    def __str__(self):
        return f"{self.location_name}"

    def clean(self):
        """Validate location data"""
        super().clean()

        # Validation: Cannot change business_group if it was already set
        if self.pk:
            old_instance = Location.objects.get(pk=self.pk)
            if old_instance.business_group and self.business_group and old_instance.business_group != self.business_group:
                raise ValidationError({
                    'business_group': 'Cannot change business group once assigned. Location is already linked to a business group.'
                })

        # Validate country lookup
        if self.country:
            if self.country.lookup_type.name != CoreLookups.COUNTRY:
                raise ValidationError({'country': 'Must be a Country lookup value'})
            if not self.country.is_active:
                raise ValidationError({'country': 'Selected country is inactive'})

        # Validate city lookup
        if self.city:
            if self.city.lookup_type.name != CoreLookups.CITY:
                raise ValidationError({'city': 'Must be a City lookup value'})
            if not self.city.is_active:
                raise ValidationError({'city': 'Selected city is inactive'})

            # Validate city-country hierarchy
            if self.country and self.city.parent_id != self.country.id:
                raise ValidationError({
                    'city': f'City "{self.city.name}" does not belong to country "{self.country.name}"'
                })

        # Validate organization exists and is a root business group (basic check, more in service layer)
        if self.business_group_id:
            from .organization import Organization
            org = Organization.objects.filter(pk=self.business_group_id).first()
            if not org:
                raise ValidationError({'business_group': 'Invalid organization'})
            if not org.is_business_group:
                raise ValidationError({'business_group': 'Location must belong to a root organization (Business Group)'})

