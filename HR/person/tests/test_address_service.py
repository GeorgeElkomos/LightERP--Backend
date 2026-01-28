"""
Unit tests for Address Service
Tests CRUD operations and business logic validations
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date

from HR.person.models import Address, Employee, PersonType
from HR.person.services.address_service import AddressService
from HR.person.dtos import AddressCreateDTO, AddressUpdateDTO
from core.lookups.models import LookupType, LookupValue
from core.base.models import StatusChoices

User = get_user_model()


class AddressServiceTest(TestCase):
    """Test AddressService business logic"""

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

        # Create person type for employee
        cls.person_type = PersonType.objects.create(
            code='PERM_EMP',
            name='Permanent Employee',
            base_type='EMP'
        )

        # Create employee (which creates person automatically)
        cls.employee = Employee.objects.create(
            first_name='John',
            last_name='Doe',
            email_address='john.doe@test.com',
            gender='Male',
            date_of_birth=date(1990, 1, 1),
            nationality='Egyptian',
            marital_status='Single',
            employee_type=cls.person_type,
            effective_start_date=date.today(),
            hire_date=date.today(),
            employee_number='E001',
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.person = cls.employee.person

        # Create lookup types
        address_type_lookup = LookupType.objects.create(
            name='Address Type'
        )
        country_type = LookupType.objects.create(
            name='Country'
        )
        city_type = LookupType.objects.create(
            name='City'
        )

        # Create address type lookups
        cls.address_type_home = LookupValue.objects.create(
            lookup_type=address_type_lookup,
            name='Home',
            is_active=True
        )
        cls.address_type_work = LookupValue.objects.create(
            lookup_type=address_type_lookup,
            name='Work',
            is_active=True
        )
        cls.address_type_inactive = LookupValue.objects.create(
            lookup_type=address_type_lookup,
            name='Old Type',
            is_active=False
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

    def test_create_address_success(self):
        """Test successful address creation with valid data"""
        dto = AddressCreateDTO(
            person_id=self.person.id,
            address_type_id=self.address_type_home.id,
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id,
            street='Abbas El Akkad Street',
            address_line_1='Building 10, Floor 5',
            address_line_2='Apartment 501',
            building_number='10',
            apartment_number='501',
            is_primary=True
        )

        address = AddressService.create(self.user, dto)

        self.assertIsNotNone(address.id)
        self.assertEqual(address.person.id, self.person.id)
        self.assertEqual(address.address_type.id, self.address_type_home.id)
        self.assertEqual(address.country.id, self.country_egypt.id)
        self.assertEqual(address.city.id, self.city_cairo.id)
        self.assertEqual(address.street, 'Abbas El Akkad Street')
        self.assertEqual(address.address_line_1, 'Building 10, Floor 5')
        self.assertEqual(address.building_number, '10')
        self.assertEqual(address.apartment_number, '501')
        self.assertTrue(address.is_primary)
        self.assertEqual(address.status, StatusChoices.ACTIVE)

    def test_create_address_minimal_fields(self):
        """Test address creation with only required fields"""
        dto = AddressCreateDTO(
            person_id=self.person.id,
            address_type_id=self.address_type_work.id,
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id,
            street='Main Street'  # At least one address field required
        )

        address = AddressService.create(self.user, dto)

        self.assertIsNotNone(address.id)
        self.assertEqual(address.street, 'Main Street')
        self.assertEqual(address.address_line_1, '')
        self.assertFalse(address.is_primary)

    def test_create_address_no_address_fields(self):
        """Test address creation fails without any address fields"""
        dto = AddressCreateDTO(
            person_id=self.person.id,
            address_type_id=self.address_type_home.id,
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id
        )

        with self.assertRaises(ValidationError) as context:
            AddressService.create(self.user, dto)

        self.assertIn('at least one address field', str(context.exception).lower())

    def test_create_address_invalid_person(self):
        """Test address creation with invalid person"""
        dto = AddressCreateDTO(
            person_id=99999,
            address_type_id=self.address_type_home.id,
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id,
            street='Test Street'
        )

        with self.assertRaises(ValidationError) as context:
            AddressService.create(self.user, dto)

        self.assertIn('person_id', str(context.exception))

    def test_create_address_invalid_address_type(self):
        """Test address creation with invalid address type"""
        dto = AddressCreateDTO(
            person_id=self.person.id,
            address_type_id=99999,
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id,
            street='Test Street'
        )

        with self.assertRaises(ValidationError) as context:
            AddressService.create(self.user, dto)

        self.assertIn('address_type_id', str(context.exception))

    def test_create_address_inactive_address_type(self):
        """Test address creation with inactive address type"""
        dto = AddressCreateDTO(
            person_id=self.person.id,
            address_type_id=self.address_type_inactive.id,
            country_id=self.country_egypt.id,
            city_id=self.city_cairo.id,
            street='Test Street'
        )

        with self.assertRaises(ValidationError) as context:
            AddressService.create(self.user, dto)

        self.assertIn('inactive', str(context.exception).lower())

    def test_create_address_city_country_mismatch(self):
        """Test address creation with city not belonging to selected country"""
        dto = AddressCreateDTO(
            person_id=self.person.id,
            address_type_id=self.address_type_home.id,
            country_id=self.country_egypt.id,
            city_id=self.city_ny.id,  # New York belongs to USA, not Egypt
            street='Test Street'
        )

        with self.assertRaises(ValidationError) as context:
            AddressService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('does not belong' in error_msg or 'hierarchy' in error_msg)

    def test_create_address_primary_flag(self):
        """Test that setting primary address unsets other primary addresses"""
        # Create first address as primary
        addr1 = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='First Street',
            is_primary=True,
            created_by=self.user,
            updated_by=self.user
        )
        self.assertTrue(addr1.is_primary)

        # Create second address as primary
        dto = AddressCreateDTO(
            person_id=self.person.id,
            address_type_id=self.address_type_work.id,
            country_id=self.country_egypt.id,
            city_id=self.city_alex.id,
            street='Second Street',
            is_primary=True
        )
        addr2 = AddressService.create(self.user, dto)

        # Verify addr2 is primary and addr1 is not
        self.assertTrue(addr2.is_primary)
        addr1.refresh_from_db()
        self.assertFalse(addr1.is_primary)

    def test_update_address_success(self):
        """Test successful address update"""
        # Create initial address
        address = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Original Street',
            created_by=self.user,
            updated_by=self.user
        )

        # Update address
        dto = AddressUpdateDTO(
            address_id=address.id,
            street='Updated Street',
            address_line_1='New Address Line',
            building_number='20'
        )

        updated = AddressService.update(self.user, dto)

        self.assertEqual(updated.id, address.id)
        self.assertEqual(updated.street, 'Updated Street')
        self.assertEqual(updated.address_line_1, 'New Address Line')
        self.assertEqual(updated.building_number, '20')
        # Unchanged fields
        self.assertEqual(updated.city.id, self.city_cairo.id)

    def test_update_address_change_city(self):
        """Test updating address city (within same country)"""
        address = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Test Street',
            created_by=self.user,
            updated_by=self.user
        )

        dto = AddressUpdateDTO(
            address_id=address.id,
            city_id=self.city_alex.id  # Change to Alexandria (same country)
        )

        updated = AddressService.update(self.user, dto)

        self.assertEqual(updated.city.id, self.city_alex.id)
        self.assertEqual(updated.country.id, self.country_egypt.id)

    def test_update_address_change_country_and_city(self):
        """Test updating both country and city"""
        address = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Test Street',
            created_by=self.user,
            updated_by=self.user
        )

        dto = AddressUpdateDTO(
            address_id=address.id,
            country_id=self.country_usa.id,
            city_id=self.city_ny.id
        )

        updated = AddressService.update(self.user, dto)

        self.assertEqual(updated.country.id, self.country_usa.id)
        self.assertEqual(updated.city.id, self.city_ny.id)

    def test_update_address_city_country_mismatch(self):
        """Test update fails when city doesn't belong to country"""
        address = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Test Street',
            created_by=self.user,
            updated_by=self.user
        )

        # Try to change city to NY without changing country
        dto = AddressUpdateDTO(
            address_id=address.id,
            city_id=self.city_ny.id  # NY belongs to USA, not Egypt
        )

        with self.assertRaises(ValidationError) as context:
            AddressService.update(self.user, dto)

        self.assertIn('does not belong', str(context.exception).lower())

    def test_update_address_set_primary(self):
        """Test updating address to primary unsets other primary addresses"""
        # Create two addresses
        addr1 = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='First Street',
            is_primary=True,
            created_by=self.user,
            updated_by=self.user
        )
        addr2 = Address.objects.create(
            person=self.person,
            address_type=self.address_type_work,
            country=self.country_egypt,
            city=self.city_alex,
            street='Second Street',
            is_primary=False,
            created_by=self.user,
            updated_by=self.user
        )

        # Update addr2 to primary
        dto = AddressUpdateDTO(
            address_id=addr2.id,
            is_primary=True
        )
        updated = AddressService.update(self.user, dto)

        # Verify addr2 is primary and addr1 is not
        self.assertTrue(updated.is_primary)
        addr1.refresh_from_db()
        self.assertFalse(addr1.is_primary)

    def test_update_address_not_found(self):
        """Test update fails for non-existent address"""
        dto = AddressUpdateDTO(
            address_id=99999,
            street='Updated Street'
        )

        with self.assertRaises(ValidationError) as context:
            AddressService.update(self.user, dto)

        error_str = str(context.exception)
        self.assertTrue('not found' in error_str.lower() or '99999' in error_str)

    def test_deactivate_address_success(self):
        """Test successful address deactivation"""
        address = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Test Street',
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = AddressService.deactivate(self.user, address.id)

        self.assertEqual(deactivated.id, address.id)
        self.assertEqual(deactivated.status, StatusChoices.INACTIVE)

        # Verify it's not in active queryset
        active_addresses = Address.objects.active()
        self.assertNotIn(address.id, active_addresses.values_list('id', flat=True))

    def test_deactivate_address_not_found(self):
        """Test deactivation fails for non-existent address"""
        with self.assertRaises(ValidationError) as context:
            AddressService.deactivate(self.user, 99999)

        error_str = str(context.exception)
        self.assertTrue('not found' in error_str.lower() or '99999' in error_str)

    def test_get_addresses_by_person(self):
        """Test retrieving addresses by person"""
        # Create multiple addresses
        addr1 = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Home Street',
            is_primary=True,
            created_by=self.user,
            updated_by=self.user
        )
        addr2 = Address.objects.create(
            person=self.person,
            address_type=self.address_type_work,
            country=self.country_egypt,
            city=self.city_alex,
            street='Work Street',
            created_by=self.user,
            updated_by=self.user
        )

        addresses = AddressService.get_addresses_by_person(self.person.id)

        self.assertEqual(addresses.count(), 2)
        # Primary should be first
        self.assertEqual(addresses[0].id, addr1.id)
        self.assertTrue(addresses[0].is_primary)

    def test_get_primary_address(self):
        """Test retrieving primary address"""
        # Create non-primary address
        Address.objects.create(
            person=self.person,
            address_type=self.address_type_work,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Work Street',
            is_primary=False,
            created_by=self.user,
            updated_by=self.user
        )

        # Create primary address
        primary = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_alex,
            street='Home Street',
            is_primary=True,
            created_by=self.user,
            updated_by=self.user
        )

        result = AddressService.get_primary_address(self.person.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, primary.id)
        self.assertTrue(result.is_primary)

    def test_get_primary_address_none_exists(self):
        """Test get_primary_address returns None when no primary exists"""
        # Create only non-primary address
        Address.objects.create(
            person=self.person,
            address_type=self.address_type_work,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Work Street',
            is_primary=False,
            created_by=self.user,
            updated_by=self.user
        )

        result = AddressService.get_primary_address(self.person.id)

        self.assertIsNone(result)

    def test_get_addresses_by_type(self):
        """Test retrieving addresses by type code"""
        # Create addresses of different types
        home_addr = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Home Street',
            created_by=self.user,
            updated_by=self.user
        )
        work_addr = Address.objects.create(
            person=self.person,
            address_type=self.address_type_work,
            country=self.country_egypt,
            city=self.city_alex,
            street='Work Street',
            created_by=self.user,
            updated_by=self.user
        )

        home_addresses = AddressService.get_addresses_by_type(self.person.id, 'HOME')

        self.assertEqual(home_addresses.count(), 1)
        self.assertEqual(home_addresses[0].id, home_addr.id)

    def test_query_methods_exclude_inactive(self):
        """Test that query methods only return active addresses"""
        # Create active and inactive addresses
        active_addr = Address.objects.create(
            person=self.person,
            address_type=self.address_type_home,
            country=self.country_egypt,
            city=self.city_cairo,
            street='Active Street',
            created_by=self.user,
            updated_by=self.user
        )
        inactive_addr = Address.objects.create(
            person=self.person,
            address_type=self.address_type_work,
            country=self.country_egypt,
            city=self.city_alex,
            street='Inactive Street',
            created_by=self.user,
            updated_by=self.user
        )
        inactive_addr.deactivate()
        inactive_addr.save()

        # Test all query methods
        by_person = AddressService.get_addresses_by_person(self.person.id)
        by_type = AddressService.get_addresses_by_type(self.person.id, 'HOME')

        for queryset in [by_person]:
            ids = [addr.id for addr in queryset]
            self.assertIn(active_addr.id, ids)
            self.assertNotIn(inactive_addr.id, ids)

