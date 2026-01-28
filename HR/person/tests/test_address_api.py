"""
API Tests for Person Address endpoints.
"""
from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.person.models import Address, Person, PersonType, Employee
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module"""
    setup_core_data()


class AddressAPITest(TestCase):
    """Test Address API endpoints."""

    def setUp(self):
        self.client = APIClient()

        # Create test user with admin permissions
        self.user = User.objects.create_user(
            email="admin@test.com",
            name="Admin User",
            phone_number="1234567890",
            password="testpass123",
        )
        setup_admin_permissions(self.user)
        self.client.force_authenticate(user=self.user)

        # Create Lookup Types
        self.types = {
            'ADDR_TYPE': LookupType.objects.get_or_create(name="Address Type")[0],
            'COUNTRY': LookupType.objects.get_or_create(name="Country")[0],
            'CITY': LookupType.objects.get_or_create(name="City")[0],
        }
        
        self.lookups = {
            'HOME': LookupValue.objects.create(lookup_type=self.types['ADDR_TYPE'], name="Home", is_active=True),
            'EGYPT': LookupValue.objects.create(lookup_type=self.types['COUNTRY'], name="Egypt", is_active=True),
        }
        self.lookups['CAIRO'] = LookupValue.objects.create(
            lookup_type=self.types['CITY'], 
            name="Cairo", 
            is_active=True,
            parent=self.lookups['EGYPT']
        )

        # Create Person (via Employee)
        self.person_type = PersonType.objects.create(
            code="PERM",
            name="Permanent",
            base_type="EMP",
            is_active=True
        )

        # Note: Employee.objects.create handles Person creation automatically via ChildModelMixin
        self.employee = Employee.objects.create(
            first_name="Donia",
            last_name="Elkomos",
            email_address="donia@test.com",
            gender="Female",
            date_of_birth=date(1990, 1, 1),
            nationality="Egyptian",
            marital_status="Single",
            employee_type=self.person_type,
            employee_number="E001",
            hire_date=date.today(),
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        self.person = self.employee.person

        # Test Address
        self.address = Address.objects.create(
            person=self.person,
            address_type=self.lookups['HOME'],
            country=self.lookups['EGYPT'],
            city=self.lookups['CAIRO'],
            street="Tahrir Square",
            address_line_1="Building 1",
            is_primary=True,
            created_by=self.user,
            updated_by=self.user
        )

    def test_list_addresses(self):
        """Test GET /hr/person/addresses/"""
        response = self.client.get('/hr/person/addresses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['street'], 'Tahrir Square')

    def test_list_addresses_by_person(self):
        """Test GET /hr/person/addresses/?person=<id>"""
        response = self.client.get(f'/hr/person/addresses/?person={self.person.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)

    def test_create_address_success(self):
        """Test POST /hr/person/addresses/"""
        data = {
            'person_id': self.person.id,
            'address_type_id': self.lookups['HOME'].id,
            'country_id': self.lookups['EGYPT'].id,
            'city_id': self.lookups['CAIRO'].id,
            'street': 'New Street',
            'is_primary': False
        }
        response = self.client.post('/hr/person/addresses/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['street'], 'New Street')

    def test_update_address(self):
        """Test PATCH /hr/person/addresses/<id>/"""
        data = {'street': 'Updated Street'}
        response = self.client.patch(f'/hr/person/addresses/{self.address.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['street'], 'Updated Street')

    def test_deactivate_address(self):
        """Test DELETE /hr/person/addresses/<id>/"""
        response = self.client.delete(f'/hr/person/addresses/{self.address.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deactivation
        self.address.refresh_from_db()
        self.assertEqual(self.address.status, 'inactive')

    def test_primary_address(self):
        """Test GET /hr/person/persons/<id>/primary-address/"""
        response = self.client.get(f'/hr/person/persons/{self.person.id}/primary-address/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_primary'])
        self.assertEqual(response.data['street'], 'Tahrir Square')
