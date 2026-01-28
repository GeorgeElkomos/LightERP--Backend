from django.db import models
from django.core.exceptions import ValidationError
from core.base.models import SoftDeleteMixin, AuditMixin
from core.base.managers import SoftDeleteManager
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from .person import Person


class Address(SoftDeleteMixin, AuditMixin, models.Model):
    """
    Person address information.

    Mixins:
    - SoftDeleteMixin: Soft delete with status field (ACTIVE/INACTIVE)
    - AuditMixin: Tracks created_by, updated_by, created_at, updated_at

    Fields:
    - person: FK to Person
    - address_type: FK to LookupValue (Address Type: Home, Work, Mailing, etc.)
    - country: FK to LookupValue (Country)
    - city: FK to LookupValue (City, child of country)
    - street: Street name
    - address_line_1/2/3: Detailed address lines
    - building_number: Building number
    - apartment_number: Apartment/unit number
    - is_primary: Primary address flag
    """
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='addresses',
        help_text="Person this address belongs to"
    )

    address_type = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='addresses_by_type',
        limit_choices_to={'lookup_type__name': CoreLookups.ADDRESS_TYPE, 'is_active': True},
        help_text="Address type (Home, Work, Mailing, etc.)"
    )

    # Location fields using lookups
    country = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='person_addresses_by_country',
        limit_choices_to={'lookup_type__name': CoreLookups.COUNTRY, 'is_active': True},
        help_text="Country lookup"
    )
    city = models.ForeignKey(
        LookupValue,
        on_delete=models.PROTECT,
        related_name='person_addresses_by_city',
        limit_choices_to={'lookup_type__name': CoreLookups.CITY, 'is_active': True},
        help_text="City lookup (must be child of selected country)"
    )

    # Detailed address fields
    street = models.CharField(max_length=200, blank=True, help_text="Street name")
    address_line_1 = models.CharField(max_length=255, blank=True, help_text="Address line 1")
    address_line_2 = models.CharField(max_length=255, blank=True, help_text="Address line 2")
    address_line_3 = models.CharField(max_length=255, blank=True, help_text="Address line 3")
    building_number = models.CharField(max_length=50, blank=True, help_text="Building number")
    apartment_number = models.CharField(max_length=50, blank=True, help_text="Apartment/unit number")

    # Primary flag
    is_primary = models.BooleanField(
        default=False,
        help_text="Is this the primary address for the person?"
    )

    objects = SoftDeleteManager()

    class Meta:
        db_table = 'person_address'
        verbose_name = 'Person Address'
        verbose_name_plural = 'Person Addresses'
        ordering = ['-is_primary', 'address_type', 'created_at']
        indexes = [
            models.Index(fields=['person', 'status']),
            models.Index(fields=['person', 'is_primary']),
            models.Index(fields=['address_type', 'status']),
            models.Index(fields=['country', 'city']),
        ]

    def __str__(self):
        address_parts = [
            self.street,
            self.address_line_1,
            self.city.name if self.city else '',
            self.country.name if self.country else ''
        ]
        address_str = ', '.join(p for p in address_parts if p)
        return f"{self.person.full_name} - {self.address_type.name}: {address_str}"

    def clean(self):
        """Validate address data"""
        super().clean()

        # Validate address_type lookup
        if self.address_type:
            if self.address_type.lookup_type.name != CoreLookups.ADDRESS_TYPE:
                raise ValidationError({'address_type': 'Must be an Address Type lookup value'})
            if not self.address_type.is_active:
                raise ValidationError({'address_type': 'Selected address type is inactive'})

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

        # Validate at least one address field is provided
        address_fields = [
            self.street, self.address_line_1, self.address_line_2,
            self.address_line_3, self.building_number, self.apartment_number
        ]
        if not any(address_fields):
            raise ValidationError(
                'At least one address field (street, address_line_1/2/3, building_number, or apartment_number) must be provided'
            )

