"""
API Tests for Person Type endpoints.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse

from HR.person.models import PersonType
from core.base.test_utils import setup_admin_permissions

User = get_user_model()

class PersonTypeAPITest(TestCase):
    """Test Person Type API endpoints."""

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

        # Create Person Types
        self.emp_type = PersonType.objects.create(
            code='EMP_PERM',
            name='Permanent Employee',
            base_type='EMP',
            is_active=True
        )
        self.apl_type = PersonType.objects.create(
            code='APL_EXT',
            name='External Applicant',
            base_type='APL',
            is_active=True
        )
        self.inactive_type = PersonType.objects.create(
            code='EMP_OLD',
            name='Old Employee Type',
            base_type='EMP',
            is_active=False
        )

        self.url = reverse('hr:person:person_type_list')

    def test_list_person_types(self):
        """Test GET /person/types/ returns all types by default"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        elif 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data

        # Should return all types
        codes = [t['code'] for t in results]
        self.assertIn('EMP_PERM', codes)
        self.assertIn('APL_EXT', codes)
        self.assertIn('EMP_OLD', codes)

    def test_filter_by_base_type(self):
        """Test filtering by base_type"""
        response = self.client.get(self.url, {'base_type': 'EMP'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        elif 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        codes = [t['code'] for t in results]
        self.assertIn('EMP_PERM', codes)
        self.assertIn('EMP_OLD', codes)
        self.assertNotIn('APL_EXT', codes)

    def test_filter_by_is_active(self):
        """Test filtering by is_active"""
        response = self.client.get(self.url, {'is_active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        elif 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        codes = [t['code'] for t in results]
        self.assertIn('EMP_PERM', codes)
        self.assertIn('APL_EXT', codes)
        self.assertNotIn('EMP_OLD', codes)

    def test_create_person_type_success(self):
        """Test creating a new person type successfully"""
        data = {
            'code': 'CWK_AGENCY',
            'name': 'Agency Contractor',
            'base_type': 'CWK',
            'description': 'Contractors from agency',
            'is_active': True
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'CWK_AGENCY')
        self.assertEqual(response.data['base_type'], 'CWK')
        
        # Verify DB
        self.assertTrue(PersonType.objects.filter(code='CWK_AGENCY').exists())

    def test_create_person_type_duplicate_code(self):
        """Test creating a person type with duplicate code fails"""
        data = {
            'code': 'EMP_PERM',  # Already exists
            'name': 'Duplicate Code',
            'base_type': 'EMP',
            'is_active': True
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)

    def test_create_person_type_invalid_base_type(self):
        """Test creating a person type with invalid base type fails"""
        data = {
            'code': 'INVALID_TYPE',
            'name': 'Invalid Type',
            'base_type': 'INVALID',  # Not in choices
            'is_active': True
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('base_type', response.data)
