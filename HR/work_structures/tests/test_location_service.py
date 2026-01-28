"""
Unit tests for Location Service
Tests CRUD operations and business logic validations
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date

from HR.work_structures.models import Location, Organization
from HR.work_structures.services.location_service import LocationService
from HR.work_structures.dtos import LocationCreateDTO, LocationUpdateDTO
from core.lookups.models import LookupType, LookupValue
from core.base.models import StatusChoices

User = get_user_model()


class LocationServiceTest(TestCase):
    """Test LocationService business logic"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all tests"""
        # Create test user
        cls.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

        # Create lookup types
        org_type_lookup = LookupType.objects.create(name='Organization Type')
        country_type = LookupType.objects.create(
            name='Country'
        )
        city_type = LookupType.objects.create(
            name='City'
        )

        # Create organization type lookup
        cls.org_type = LookupValue.objects.create(
            lookup_type=org_type_lookup,
            name='Business Group',
            is_active=True
        )

        # Create root organization (business group) without location first
        cls.root_org = Organization.objects.create(
            organization_name='ORG01',
            organization_type=cls.org_type,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create country lookups
        cls.country_egypt = LookupValue.objects.create(
            lookup_type=country_type,
            name='Egypt',
            is_active=True
        )
        cls.country_usa = LookupValue.objects.create(
            lookup_type=country_type,
            name='United States',
            is_active=True
        )
        cls.country_inactive = LookupValue.objects.create(
            lookup_type=country_type,
            name='Inactive Country',
            is_active=False
        )

        # Create city lookups (children of countries)
        cls.city_cairo = LookupValue.objects.create(
            lookup_type=city_type,
            name='Cairo',
            parent=cls.country_egypt,
            is_active=True
        )
        cls.city_alex = LookupValue.objects.create(
            lookup_type=city_type,
            name='Alexandria',
            parent=cls.country_egypt,
            is_active=True
        )
        cls.city_ny = LookupValue.objects.create(
            lookup_type=city_type,
            name='New York',
            parent=cls.country_usa,
            is_active=True
        )
        cls.city_inactive = LookupValue.objects.create(
            lookup_type=city_type,
            name='Inactive City',
            parent=cls.country_egypt,
            is_active=False
        )

    def test_create_location_success(self):
        """Test successful location creation with valid data"""
        dto = LocationCreateDTO(
            business_group_id=self.root_org.id,
            location_name='LOC01',
            description='Main office in Cairo',
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id,
            zone='Nasr City',
            street='Abbas El Akkad',
            building='Building 10',
            floor='5th Floor',
            office='Office 501',
            po_box='12345',
            effective_from=timezone.now()
        )

        location = LocationService.create(self.user, dto)

        self.assertIsNotNone(location.id)
        self.assertEqual(location.location_name, 'LOC01')
        self.assertEqual(location.description, 'Main office in Cairo')
        self.assertEqual(location.country.id, self.country_egypt.id)
        self.assertEqual(location.city.id, self.city_cairo.id)
        self.assertEqual(location.zone, 'Nasr City')
        self.assertEqual(location.street, 'Abbas El Akkad')
        self.assertEqual(location.building, 'Building 10')
        self.assertEqual(location.floor, '5th Floor')
        self.assertEqual(location.office, 'Office 501')
        self.assertEqual(location.po_box, '12345')
        self.assertEqual(location.status, StatusChoices.ACTIVE)
        self.assertEqual(location.created_by, self.user)

    def test_create_location_minimal_fields(self):
        """Test location creation with only required fields"""
        dto = LocationCreateDTO(
            business_group_id=self.root_org.id,
            location_name='Alexandria Office',
            country_id=self.country_egypt.id,
            city_id=self.city_alex.id,
            effective_from=timezone.now()
        )

        location = LocationService.create(self.user, dto)

        self.assertIsNotNone(location.id)
        self.assertEqual(location.location_name, 'Alexandria Office')
        self.assertEqual(location.description, '')
        self.assertEqual(location.zone, '')
        self.assertEqual(location.status, StatusChoices.ACTIVE)

    def test_create_location_invalid_organization(self):
        """Test location creation with invalid organization"""
        dto = LocationCreateDTO(
            business_group_id=99999,
            location_name='Test Location',
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.create(self.user, dto)

        self.assertIn('business_group_id', str(context.exception))

    def test_create_location_invalid_country(self):
        """Test location creation with invalid country lookup"""
        dto = LocationCreateDTO(
            business_group_id=self.root_org.id,
            location_name='Test Location',
            country_id=99999,
            city_id=self.city_cairo.id,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.create(self.user, dto)

        self.assertIn('country_id', str(context.exception))

    def test_create_location_inactive_country(self):
        """Test location creation with inactive country"""
        dto = LocationCreateDTO(
            business_group_id=self.root_org.id,
            location_name='Test Location',
            country_id=self.country_inactive.id,
            city_id=self.city_cairo.id,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.create(self.user, dto)

        self.assertIn('inactive', str(context.exception).lower())

    def test_create_location_invalid_city(self):
        """Test location creation with invalid city lookup"""
        dto = LocationCreateDTO(
            business_group_id=self.root_org.id,
            location_name='Test Location',
            country_id=self.country_egypt.id,
            city_id=99999,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.create(self.user, dto)

        self.assertIn('city_id', str(context.exception))

    def test_create_location_inactive_city(self):
        """Test location creation with inactive city"""
        dto = LocationCreateDTO(
            business_group_id=self.root_org.id,
            location_name='Test Location',
            country_id=self.country_egypt.id,
            city_id=self.city_inactive.id,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.create(self.user, dto)

        self.assertIn('inactive', str(context.exception).lower())

    def test_create_location_city_country_mismatch(self):
        """Test location creation with city not belonging to selected country"""
        dto = LocationCreateDTO(
            business_group_id=self.root_org.id,
            location_name='Test Location',
            country_id=self.country_egypt.id,
            city_id=self.city_ny.id,  # New York belongs to USA, not Egypt
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('does not belong' in error_msg or 'hierarchy' in error_msg)

    def test_update_location_success(self):
        """Test successful location update"""
        # Create initial location
        location = Location.objects.create(
            business_group=self.root_org,
            location_name='Original Name',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )

        # Update location
        dto = LocationUpdateDTO(
            location_id=location.id,
            location_name='Updated Name',
            description='Updated description',
            zone='New Zone',
            street='New Street'
        )

        updated = LocationService.update(self.user, dto)

        self.assertEqual(updated.id, location.id)
        self.assertEqual(updated.location_name, 'Updated Name')
        self.assertEqual(updated.description, 'Updated description')
        self.assertEqual(updated.zone, 'New Zone')
        self.assertEqual(updated.street, 'New Street')
        self.assertEqual(updated.updated_by, self.user)

    def test_update_location_change_city(self):
        """Test updating location city (within same country)"""
        location = Location.objects.create(
            business_group=self.root_org,
            location_name='Test Location',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )

        dto = LocationUpdateDTO(
            location_id=location.id,
            city_id=self.city_alex.id  # Change to Alexandria (same country)
        )

        updated = LocationService.update(self.user, dto)

        self.assertEqual(updated.city.id, self.city_alex.id)
        self.assertEqual(updated.country.id, self.country_egypt.id)

    def test_update_location_change_country_and_city(self):
        """Test updating both country and city"""
        location = Location.objects.create(
            business_group=self.root_org,
            location_name='Test Location',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )

        dto = LocationUpdateDTO(
            location_id=location.id,
            country_id=self.country_usa.id,
            city_id=self.city_ny.id
        )

        updated = LocationService.update(self.user, dto)

        self.assertEqual(updated.country.id, self.country_usa.id)
        self.assertEqual(updated.city.id, self.city_ny.id)

    def test_update_location_city_country_mismatch(self):
        """Test update fails when city doesn't belong to country"""
        location = Location.objects.create(
            business_group=self.root_org,
            location_name='Test Location',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )

        # Try to change city to NY without changing country
        dto = LocationUpdateDTO(
            location_id=location.id,
            city_id=self.city_ny.id  # NY belongs to USA, not Egypt
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.update(self.user, dto)

        self.assertIn('does not belong', str(context.exception).lower())

    def test_update_location_not_found(self):
        """Test update fails for non-existent location"""
        dto = LocationUpdateDTO(
            location_id=99999,
            location_name='Updated Name'
        )

        with self.assertRaises(ValidationError) as context:
            LocationService.update(self.user, dto)

        error_str = str(context.exception)
        self.assertTrue('no active location found' in error_str.lower())

    def test_deactivate_location_success(self):
        """Test successful location deactivation"""
        location = Location.objects.create(
            business_group=self.root_org,
            location_name='Test Location',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = LocationService.deactivate(self.user, location.id)

        self.assertEqual(deactivated.id, location.id)
        self.assertEqual(deactivated.status, StatusChoices.INACTIVE)

        # Verify it's not in active queryset
        active_locations = Location.objects.active()
        self.assertNotIn(location.id, active_locations.values_list('id', flat=True))

    def test_deactivate_location_not_found(self):
        """Test deactivation fails for non-existent location"""
        with self.assertRaises(ValidationError) as context:
            LocationService.deactivate(self.user, 99999)

        error_str = str(context.exception)
        self.assertTrue('no active location found' in error_str.lower())

    def test_get_locations_by_organization(self):
        """Test retrieving locations by organization (business group)"""
        # Create another organization type lookup
        org_type_lookup = LookupType.objects.get(name='Organization Type')
        org_type_2 = LookupValue.objects.create(
            lookup_type=org_type_lookup,
            name='Second Business Group',
            is_active=True
        )

        # Create another root organization (business group)
        org2 = Organization.objects.create(
            organization_name='ORG02',
            organization_type=org_type_2,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create locations for both organizations
        loc1 = Location.objects.create(
            business_group=self.root_org,
            location_name='Location 1',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )
        loc2 = Location.objects.create(
            business_group=self.root_org,
            location_name='Location 2',
            country=self.country_egypt,
            city=self.city_alex,
            created_by=self.user,
            updated_by=self.user
        )
        loc3 = Location.objects.create(
            business_group=org2,
            location_name='Location 3',
            country=self.country_usa,
            city=self.city_ny,
            created_by=self.user,
            updated_by=self.user
        )

        # Get locations for first organization
        locations = LocationService.get_locations_by_organization(self.root_org.id)

        self.assertEqual(locations.count(), 2)
        names = [loc.location_name for loc in locations]
        self.assertIn('Location 1', names)
        self.assertIn('Location 2', names)
        self.assertNotIn('Location 3', names)

    def test_get_locations_by_country(self):
        """Test retrieving locations by country"""
        loc1 = Location.objects.create(
            business_group=self.root_org,
            location_name='Cairo Location',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )
        loc2 = Location.objects.create(
            business_group=self.root_org,
            location_name='Alex Location',
            country=self.country_egypt,
            city=self.city_alex,
            created_by=self.user,
            updated_by=self.user
        )
        loc3 = Location.objects.create(
            business_group=self.root_org,
            location_name='NY Location',
            country=self.country_usa,
            city=self.city_ny,
            created_by=self.user,
            updated_by=self.user
        )

        # Get locations in Egypt
        locations = LocationService.get_locations_by_country(self.country_egypt.id)

        self.assertEqual(locations.count(), 2)
        names = [loc.location_name for loc in locations]
        self.assertIn('Cairo Location', names)
        self.assertIn('Alex Location', names)
        self.assertNotIn('NY Location', names)

    def test_get_locations_by_city(self):
        """Test retrieving locations by city"""
        loc1 = Location.objects.create(
            business_group=self.root_org,
            location_name='Cairo Location 1',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )
        loc2 = Location.objects.create(
            business_group=self.root_org,
            location_name='Cairo Location 2',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )
        loc3 = Location.objects.create(
            business_group=self.root_org,
            location_name='Alex Location',
            country=self.country_egypt,
            city=self.city_alex,
            created_by=self.user,
            updated_by=self.user
        )

        # Get locations in Cairo
        locations = LocationService.get_locations_by_city(self.city_cairo.id)

        self.assertEqual(locations.count(), 2)
        names = [loc.location_name for loc in locations]
        self.assertIn('Cairo Location 1', names)
        self.assertIn('Cairo Location 2', names)
        self.assertNotIn('Alex Location', names)

    def test_query_methods_exclude_inactive(self):
        """Test that query methods only return active locations"""
        # Create active and inactive locations
        active_loc = Location.objects.create(
            business_group=self.root_org,
            location_name='Active Location',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )
        inactive_loc = Location.objects.create(
            business_group=self.root_org,
            location_name='Inactive Location',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )
        inactive_loc.deactivate()
        inactive_loc.save()

        # Test all query methods
        by_org = LocationService.get_locations_by_organization(self.root_org.id)
        by_country = LocationService.get_locations_by_country(self.country_egypt.id)
        by_city = LocationService.get_locations_by_city(self.city_cairo.id)

        for queryset in [by_org, by_country, by_city]:
            names = [loc.location_name for loc in queryset]
            self.assertIn('Active Location', names)
            self.assertNotIn('Inactive Location', names)

