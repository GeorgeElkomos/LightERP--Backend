from django.db import transaction
from django.core.exceptions import ValidationError
from HR.person.dtos import AddressCreateDTO, AddressUpdateDTO
from HR.person.models import Address, Person
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class AddressService:
    """Service for Address business logic"""

    @staticmethod
    @transaction.atomic
    def create(user, dto: AddressCreateDTO) -> Address:
        """
        Create new address with validation.

        Validates:
        - Person exists
        - Address type, country, and city lookups are valid and active
        - City belongs to selected country
        - At least one address field provided
        - If is_primary=True, unset other primary addresses
        """
        # Validate person exists
        try:
            person = Person.objects.get(pk=dto.person_id)
        except Person.DoesNotExist:
            raise ValidationError({'person_id': 'Person not found'})

        # Validate address_type lookup
        try:
            address_type = LookupValue.objects.get(pk=dto.address_type_id)
            if address_type.lookup_type.name != CoreLookups.ADDRESS_TYPE:
                raise ValidationError({'address_type_id': 'Must be an ADDRESS_TYPE lookup value'})
            if not address_type.is_active:
                raise ValidationError({'address_type_id': 'Selected address type is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'address_type_id': 'Address type lookup not found'})

        # Validate country lookup
        try:
            country = LookupValue.objects.get(pk=dto.country_id)
            if country.lookup_type.name != CoreLookups.COUNTRY:
                raise ValidationError({'country_id': 'Must be a COUNTRY lookup value'})
            if not country.is_active:
                raise ValidationError({'country_id': 'Selected country is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'country_id': 'Country lookup not found'})

        # Validate city lookup
        try:
            city = LookupValue.objects.get(pk=dto.city_id)
            if city.lookup_type.name != CoreLookups.CITY:
                raise ValidationError({'city_id': 'Must be a CITY lookup value'})
            if not city.is_active:
                raise ValidationError({'city_id': 'Selected city is inactive'})

            # Validate city-country hierarchy
            if city.parent_id != country.id:
                raise ValidationError({
                    'city_id': f'City "{city.name}" does not belong to country "{country.name}"'
                })
        except LookupValue.DoesNotExist:
            raise ValidationError({'city_id': 'City lookup not found'})

        # Validate at least one address field provided
        address_fields = [
            dto.street, dto.address_line_1, dto.address_line_2,
            dto.address_line_3, dto.building_number, dto.apartment_number
        ]
        if not any(address_fields):
            raise ValidationError(
                'At least one address field (street, address_line_1/2/3, building_number, or apartment_number) must be provided'
            )

        # If setting as primary, unset other primary addresses for this person
        if dto.is_primary:
            Address.objects.filter(person=person, is_primary=True).update(is_primary=False)

        # Create address
        address = Address(
            person=person,
            address_type=address_type,
            country=country,
            city=city,
            street=dto.street or '',
            address_line_1=dto.address_line_1 or '',
            address_line_2=dto.address_line_2 or '',
            address_line_3=dto.address_line_3 or '',
            building_number=dto.building_number or '',
            apartment_number=dto.apartment_number or '',
            is_primary=dto.is_primary,
            created_by=user,
            updated_by=user
        )
        address.full_clean()
        address.save()
        return address

    @staticmethod
    @transaction.atomic
    def update(user, dto: AddressUpdateDTO) -> Address:
        """
        Update existing address.

        Validates:
        - Address exists and is active
        - If lookups updated, validates them and hierarchy
        - If is_primary=True, unset other primary addresses
        """
        try:
            address = Address.objects.active().get(pk=dto.address_id)
        except Address.DoesNotExist:
            raise ValidationError(f"No active address found with ID '{dto.address_id}'")

        # Validate and update address_type if provided
        if dto.address_type_id is not None:
            try:
                address_type = LookupValue.objects.get(pk=dto.address_type_id)
                if address_type.lookup_type.name != CoreLookups.ADDRESS_TYPE:
                    raise ValidationError({'address_type_id': 'Must be an ADDRESS_TYPE lookup value'})
                if not address_type.is_active:
                    raise ValidationError({'address_type_id': 'Selected address type is inactive'})
                address.address_type = address_type
            except LookupValue.DoesNotExist:
                raise ValidationError({'address_type_id': 'Address type lookup not found'})

        # Validate and update country if provided
        if dto.country_id is not None:
            try:
                country = LookupValue.objects.get(pk=dto.country_id)
                if country.lookup_type.name != CoreLookups.COUNTRY:
                    raise ValidationError({'country_id': 'Must be a COUNTRY lookup value'})
                if not country.is_active:
                    raise ValidationError({'country_id': 'Selected country is inactive'})
                address.country = country
            except LookupValue.DoesNotExist:
                raise ValidationError({'country_id': 'Country lookup not found'})

        # Validate and update city if provided
        if dto.city_id is not None:
            try:
                city = LookupValue.objects.get(pk=dto.city_id)
                if city.lookup_type.name != CoreLookups.CITY:
                    raise ValidationError({'city_id': 'Must be a CITY lookup value'})
                if not city.is_active:
                    raise ValidationError({'city_id': 'Selected city is inactive'})

                # Use updated country if provided, otherwise use existing
                current_country = address.country if dto.country_id is None else country
                if city.parent_id != current_country.id:
                    raise ValidationError({
                        'city_id': f'City "{city.name}" does not belong to country "{current_country.name}"'
                    })
                address.city = city
            except LookupValue.DoesNotExist:
                raise ValidationError({'city_id': 'City lookup not found'})

        # Update address fields if provided
        if dto.street is not None:
            address.street = dto.street
        if dto.address_line_1 is not None:
            address.address_line_1 = dto.address_line_1
        if dto.address_line_2 is not None:
            address.address_line_2 = dto.address_line_2
        if dto.address_line_3 is not None:
            address.address_line_3 = dto.address_line_3
        if dto.building_number is not None:
            address.building_number = dto.building_number
        if dto.apartment_number is not None:
            address.apartment_number = dto.apartment_number


        # Handle primary flag
        if dto.is_primary is not None:
            if dto.is_primary:
                # Unset other primary addresses for this person
                Address.objects.filter(
                    person=address.person,
                    is_primary=True
                ).exclude(pk=address.pk).update(is_primary=False)
            address.is_primary = dto.is_primary

        address.updated_by = user
        address.full_clean()
        address.save()
        return address

    @staticmethod
    @transaction.atomic
    def deactivate(user, address_id: int) -> Address:
        """
        Deactivate address (soft delete).

        Args:
            user: User performing deactivation
            address_id: Address ID

        Returns:
            Deactivated address
        """
        try:
            address = Address.objects.active().get(pk=address_id)
        except Address.DoesNotExist:
            raise ValidationError(f"No active address found with ID '{address_id}'")

        address.deactivate()
        address.updated_by = user
        address.save()
        return address

    @staticmethod
    def get_addresses_by_person(person_id: int):
        """Get all active addresses for a person"""
        return Address.objects.active().filter(
            person_id=person_id
        ).select_related('person', 'address_type', 'country', 'city').order_by('-is_primary', 'address_type')

    @staticmethod
    def get_primary_address(person_id: int):
        """Get the primary address for a person (if exists)"""
        return Address.objects.active().filter(
            person_id=person_id,
            is_primary=True
        ).select_related('person', 'address_type', 'country', 'city').first()

    @staticmethod
    def get_addresses_by_type(person_id: int, address_type_name: str):
        """Get addresses by type name (e.g., 'Home', 'Work')"""
        return Address.objects.active().filter(
            person_id=person_id,
            address_type__name__iexact=address_type_name
        ).select_related('person', 'address_type', 'country', 'city')

