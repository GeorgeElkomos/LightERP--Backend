from django.db import transaction
from django.db.models import Q, QuerySet
from django.core.exceptions import ValidationError
from datetime import date
from HR.work_structures.dtos import LocationCreateDTO, LocationUpdateDTO
from HR.work_structures.models import Location, Organization
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class LocationService:
    """Service for Location business logic"""

    @staticmethod
    @transaction.atomic
    def create(user, dto: LocationCreateDTO) -> Location:
        """
        Create new location with validation.

        Validates:
        - Organization exists and is a root business group
        - Country and city lookups are valid and active
        - City belongs to selected country
        """
        # Validate organization exists and is a root business group
        organization = None
        if dto.business_group_id:
            try:
                today = date.today()
                organization = Organization.objects.active_on(today).get(pk=dto.business_group_id)
                if not organization.is_business_group:
                    raise ValidationError({'business_group_id': 'Location must belong to a root organization (Business Group)'})
            except Organization.DoesNotExist:
                raise ValidationError({'business_group_id': 'Organization not found or inactive'})

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

        # Create location
        location = Location(
            business_group=organization,
            location_name=dto.location_name,
            description=dto.description or '',
            country=country,
            city=city,
            zone=dto.zone or '',
            street=dto.street or '',
            building=dto.building or '',
            floor=dto.floor or '',
            office=dto.office or '',
            po_box=dto.po_box or '',
            effective_from=dto.effective_from,
            created_by=user,
            updated_by=user
        )
        location.full_clean()
        location.save()
        return location

    @staticmethod
    @transaction.atomic
    def update(user, dto: LocationUpdateDTO) -> Location:
        """
        Update existing location.

        Uses SoftDeleteMixin.update_fields() for consistent update pattern.

        Validates:
        - Location exists and is active
        - If country/city updated, validates lookups and hierarchy
        """
        try:
            location = Location.objects.active().get(pk=dto.location_id)
        except Location.DoesNotExist:
            raise ValidationError(f"No active location found with ID '{dto.location_id}'")

        # Build field updates dictionary
        field_updates = {}

        # Basic field updates
        if dto.location_name is not None:
            field_updates['location_name'] = dto.location_name
        if dto.description is not None:
            field_updates['description'] = dto.description

        # Validate and prepare business group update
        if dto.business_group_id is not None:
            try:
                today = date.today()
                organization = Organization.objects.active_on(today).get(pk=dto.business_group_id)
                if not organization.is_business_group:
                    raise ValidationError({'business_group_id': 'Location must belong to a root organization (Business Group)'})
                field_updates['business_group'] = organization
            except Organization.DoesNotExist:
                raise ValidationError({'business_group_id': 'Organization not found or inactive'})

        # Validate and prepare country update
        if dto.country_id is not None:
            try:
                country = LookupValue.objects.get(pk=dto.country_id)
                if country.lookup_type.name != CoreLookups.COUNTRY:
                    raise ValidationError({'country_id': 'Must be a COUNTRY lookup value'})
                if not country.is_active:
                    raise ValidationError({'country_id': 'Selected country is inactive'})
                field_updates['country'] = country
            except LookupValue.DoesNotExist:
                raise ValidationError({'country_id': 'Country lookup not found'})

        # Validate and prepare city update
        if dto.city_id is not None:
            try:
                city = LookupValue.objects.get(pk=dto.city_id)
                if city.lookup_type.name != CoreLookups.CITY:
                    raise ValidationError({'city_id': 'Must be a CITY lookup value'})
                if not city.is_active:
                    raise ValidationError({'city_id': 'Selected city is inactive'})

                # Use updated country if provided, otherwise use existing
                current_country = field_updates.get('country', location.country)
                if city.parent_id != current_country.id:
                    raise ValidationError({
                        'city_id': f'City "{city.name}" does not belong to country "{current_country.name}"'
                    })
                field_updates['city'] = city
            except LookupValue.DoesNotExist:
                raise ValidationError({'city_id': 'City lookup not found'})

        # Address field updates
        if dto.zone is not None:
            field_updates['zone'] = dto.zone
        if dto.street is not None:
            field_updates['street'] = dto.street
        if dto.building is not None:
            field_updates['building'] = dto.building
        if dto.floor is not None:
            field_updates['floor'] = dto.floor
        if dto.office is not None:
            field_updates['office'] = dto.office
        if dto.po_box is not None:
            field_updates['po_box'] = dto.po_box

        # Use SoftDeleteMixin.update_fields() method
        # This handles validation and saving consistently
        location.update_fields(field_updates)

        location.updated_by = user
        location.save(update_fields=['updated_by'])
        return location

    @staticmethod
    @transaction.atomic
    def deactivate(user, location_id: int) -> Location:
        """
        Deactivate location (soft delete).

        Args:
            user: User performing deactivation
            location_id: Location ID

        Returns:
            Deactivated location
        """
        try:
            location = Location.objects.active().get(pk=location_id)
        except Location.DoesNotExist:
            raise ValidationError(f"No active location found with ID '{location_id}'")

        location.deactivate()
        location.updated_by = user
        location.save()
        return location

    @staticmethod
    def list_locations(filters: dict = None) -> QuerySet:
        """
        List locations with flexible filtering.

        Args:
            filters: Dictionary of filters
                - status: 'ALL' (default), 'ACTIVE', or 'INACTIVE'
                - business_group: ID
                - country_id: ID
                - city_id: ID
                - search: Search query string

        Returns:
            QuerySet of Location objects
        """
        filters = filters or {}
        status_filter = filters.get('status', 'ALL')

        # Base queryset based on status
        if status_filter == 'ALL':
            queryset = Location.objects.all()
        elif status_filter == 'INACTIVE':
            queryset = Location.objects.inactive()
        else:
            queryset = Location.objects.active()

        queryset = queryset.select_related('business_group', 'country', 'city').order_by('location_name')

        # Apply filters
        business_group = filters.get('business_group')
        if business_group:
             queryset = queryset.filter(business_group_id=business_group)

        country_id = filters.get('country_id')
        if country_id:
            queryset = queryset.filter(country_id=country_id)

        city_id = filters.get('city_id')
        if city_id:
            queryset = queryset.filter(city_id=city_id)

        search_query = filters.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(location_name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        return queryset

    @staticmethod
    def get_locations_by_organization(organization_id: int):
        """Get all active locations for an organization (root business group)"""
        return Location.objects.active().filter(
            business_group_id=organization_id
        ).select_related('business_group', 'country', 'city').order_by('location_name')

    @staticmethod
    def get_locations_by_country(country_id: int):
        """Get all active locations in a country"""
        return Location.objects.active().filter(
            country_id=country_id
        ).select_related('business_group', 'country', 'city').order_by('location_name')

    @staticmethod
    def get_locations_by_city(city_id: int):
        """Get all active locations in a city"""
        return Location.objects.active().filter(
            city_id=city_id
        ).select_related('business_group', 'country', 'city').order_by('location_name')
