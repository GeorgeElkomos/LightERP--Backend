"""
API Tests for Location endpoints.
Tests all CRUD operations for Location model via REST API.
"""
from datetime import date
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.work_structures.models import Organization, Location
from core.lookups.models import LookupType, LookupValue
from core.job_roles.models import JobRole, Page, Action, PageAction
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module - setup shared data"""
    setup_core_data()


class LocationAPITest(TestCase):
    """Test Location API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test user with admin permissions
        self.user = User.objects.create_user(
            email="testuser@test.com",
            name="Test User",
            phone_number="1234567890",
            password="testpass123",
        )
        setup_admin_permissions(self.user)

        # Authenticate
        self.client.force_authenticate(user=self.user)

        # Create lookup types and values for Organization
        self.org_type_lookup = LookupType.objects.create(name="Organization Type")
        self.org_type_bg = LookupValue.objects.create(
            lookup_type=self.org_type_lookup,
            name="Business Group",
            is_active=True
        )

        # Create test organization (root business group)
        self.org = Organization.objects.create(
            organization_name="BG001",
            organization_type=self.org_type_bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create lookup types and values
        self.country_type = LookupType.objects.create(name="Country")
        self.city_type = LookupType.objects.create(name="City")

        self.country_egypt = LookupValue.objects.create(
            lookup_type=self.country_type,
            name="Egypt",
            is_active=True
        )

        self.city_cairo = LookupValue.objects.create(
            lookup_type=self.city_type,
            name="Cairo",
            parent=self.country_egypt,
            is_active=True
        )

        self.city_alex = LookupValue.objects.create(
            lookup_type=self.city_type,
            name="Alexandria",
            parent=self.country_egypt,
            is_active=True
        )

        # Create test location
        self.location1 = Location.objects.create(
            business_group=self.org,
            location_name="Main Office",
            description="Headquarters",
            country=self.country_egypt,
            city=self.city_cairo,
            street="Test Street",
            building="Building 1",
            created_by=self.user,
            updated_by=self.user
        )

    def test_list_locations(self):
        """Test GET /hr/work_structures/locations/"""
        response = self.client.get('/hr/work_structures/locations/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertGreaterEqual(len(results), 1)

        # Check structure
        location_data = results[0]
        self.assertIn('id', location_data)
        self.assertIn('location_name', location_data)
        self.assertIn('business_group_name', location_data)
        self.assertIn('country_name', location_data)
        self.assertIn('city_name', location_data)

    def test_list_locations_filter_by_business_group(self):
        """Test GET /hr/work_structures/locations/?business_group=BG001"""
        response = self.client.get(f'/hr/work_structures/locations/?business_group={self.org.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['location_name'], 'Main Office')

    def test_list_locations_filter_by_country(self):
        """Test GET /hr/work_structures/locations/?country=EG"""
        response = self.client.get(f'/hr/work_structures/locations/?country={self.country_egypt.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertGreaterEqual(len(results), 1)

    def test_list_locations_filter_by_city(self):
        """Test GET /hr/work_structures/locations/?city=CAI"""
        response = self.client.get(f'/hr/work_structures/locations/?city={self.city_cairo.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertGreaterEqual(len(results), 1)

    def test_list_locations_search(self):
        """Test GET /hr/work_structures/locations/?search=Main"""
        response = self.client.get('/hr/work_structures/locations/?search=Main')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['location_name'], 'Main Office')

    def test_create_location_success(self):
        """Test POST /hr/work_structures/locations/ with valid data"""
        data = {
            'business_group_id': self.org.id,
            'location_name': 'Branch Office',
            'description': 'Branch in Alexandria',
            'country_id': self.country_egypt.id,
            'city_id': self.city_alex.id,
            'street': 'Alexandria Street',
            'building': 'Building 5',
            'floor': '3rd Floor',
            'office': 'Office 301',
            'effective_from': str(date.today())
        }

        response = self.client.post('/hr/work_structures/locations/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['location_name'], 'Branch Office')
        self.assertEqual(response.data['city_name'], 'Alexandria')

        # Verify in database
        location = Location.objects.get(location_name='Branch Office')
        self.assertEqual(location.location_name, 'Branch Office')
        self.assertEqual(location.city.name, 'Alexandria')

    def test_create_location_duplicate_code(self):
        """Test POST /hr/work_structures/locations/ with duplicate location_name"""
        data = {
            'business_group_id': self.org.id,
            'location_name': 'Main Office',  # Already exists
            'country_id': self.country_egypt.id,
            'city_id': self.city_cairo.id
        }

        response = self.client.post('/hr/work_structures/locations/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('location_name', response.data)

    def test_create_location_invalid_organization(self):
        """Test POST /hr/work_structures/locations/ with invalid organization"""
        data = {
            'business_group_id': 99999,
            'location_name': 'Invalid Org Location',
            'country_id': self.country_egypt.id,
            'city_id': self.city_cairo.id,
            'effective_from': str(date.today())
        }

        response = self.client.post('/hr/work_structures/locations/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('business_group_id', response.data)

    def test_create_location_city_country_mismatch(self):
        """Test POST /hr/work_structures/locations/ with city not belonging to country"""
        # Create a different country
        country_usa = LookupValue.objects.create(
            lookup_type=self.country_type,
            name="USA",
            is_active=True
        )

        data = {
            'business_group_id': self.org.id,
            'location_name': 'Mismatch Location',
            'country_id': country_usa.id,
            'city_id': self.city_cairo.id  # Cairo belongs to Egypt, not USA
        }

        response = self.client.post('/hr/work_structures/locations/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_location_detail(self):
        """Test GET /hr/work_structures/locations/<id>/"""
        response = self.client.get(f'/hr/work_structures/locations/{self.location1.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['location_name'], 'Main Office')
        self.assertEqual(response.data['street'], 'Test Street')

    def test_get_location_not_found(self):
        """Test GET /hr/work_structures/locations/99999/"""
        response = self.client.get('/hr/work_structures/locations/99999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_location_put(self):
        """Test PUT /hr/work_structures/locations/<id>/"""
        data = {
            'location_name': 'Updated Main Office',
            'description': 'Updated description',
            'street': 'New Street',
            'building': 'Building 10'
        }

        response = self.client.put(
            f'/hr/work_structures/locations/{self.location1.id}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['location_name'], 'Updated Main Office')
        self.assertEqual(response.data['street'], 'New Street')

        # Verify in database
        self.location1.refresh_from_db()
        self.assertEqual(self.location1.location_name, 'Updated Main Office')
        self.assertEqual(self.location1.street, 'New Street')

    def test_update_location_patch(self):
        """Test PATCH /hr/work_structures/locations/<id>/ (partial update)"""
        data = {
            'location_name': 'Partially Updated Office'
        }

        response = self.client.patch(
            f'/hr/work_structures/locations/{self.location1.id}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['location_name'], 'Partially Updated Office')

        # Verify other fields unchanged
        self.location1.refresh_from_db()
        self.assertEqual(self.location1.location_name, 'Partially Updated Office')
        self.assertEqual(self.location1.street, 'Test Street')  # Unchanged

    def test_update_location_change_city(self):
        """Test PUT /hr/work_structures/locations/<id>/ changing city"""
        data = {
            'city_id': self.city_alex.id
        }

        response = self.client.patch(
            f'/hr/work_structures/locations/{self.location1.id}/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['city_name'], 'Alexandria')

        # Verify in database
        self.location1.refresh_from_db()
        self.assertEqual(self.location1.city.name, 'Alexandria')

    def test_delete_location(self):
        """Test DELETE /hr/work_structures/locations/<id>/ (soft delete)"""
        response = self.client.delete(f'/hr/work_structures/locations/{self.location1.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify soft delete
        self.location1.refresh_from_db()
        self.assertEqual(self.location1.status, 'inactive')

        # Verify not in active queryset
        active_locations = Location.objects.active().filter(location_name='Main Office')
        self.assertEqual(active_locations.count(), 0)

    def test_list_filters_inactive_locations(self):
        """Test GET /hr/work_structures/locations/ filtering behavior"""
        # Deactivate location
        self.location1.deactivate()
        self.location1.save()

        # Default should include all (including inactive)
        response_all = self.client.get('/hr/work_structures/locations/')
        self.assertEqual(response_all.status_code, status.HTTP_200_OK)
        
        if 'data' in response_all.data and 'results' in response_all.data['data']:
            results_all = response_all.data['data']['results']
        else:
            results_all = response_all.data.get('results', response_all.data)
            
        names_all = [loc['location_name'] for loc in results_all]
        self.assertIn('Main Office', names_all)

        # Filter by status=ACTIVE should exclude inactive
        response_active = self.client.get('/hr/work_structures/locations/?status=ACTIVE')
        self.assertEqual(response_active.status_code, status.HTTP_200_OK)
        
        if 'data' in response_active.data and 'results' in response_active.data['data']:
            results_active = response_active.data['data']['results']
        else:
            results_active = response_active.data.get('results', response_active.data)
            
        names_active = [loc['location_name'] for loc in results_active]
        self.assertNotIn('Main Office', names_active)

    def test_unauthorized_access(self):
        """Test API access without authentication"""
        self.client.force_authenticate(user=None)

        response = self.client.get('/hr/work_structures/locations/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_location_without_business_group(self):
        """Test creating location without business group"""
        data = {
            'location_name': 'Global Location',
            'description': 'Location without BG',
            'country_id': self.country_egypt.id,
            'city_id': self.city_cairo.id,
            'effective_from': str(date.today())
        }
        response = self.client.post('/hr/work_structures/locations/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['business_group_name'])
        
        # Verify in DB
        location = Location.objects.get(location_name='Global Location')
        self.assertIsNone(location.business_group)

    def test_update_location_assign_business_group(self):
        """Test assigning business group to a location that didn't have one"""
        # Create location without BG
        location = Location.objects.create(
            location_name='Global Location Update',
            country=self.country_egypt,
            city=self.city_cairo,
            created_by=self.user,
            updated_by=self.user
        )
        self.assertIsNone(location.business_group)

        # Update with BG
        data = {
            'business_group_id': self.org.id
        }
        response = self.client.put(f'/hr/work_structures/locations/{location.id}/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['business_group_name'], self.org.organization_name)

        location.refresh_from_db()
        self.assertEqual(location.business_group, self.org)
