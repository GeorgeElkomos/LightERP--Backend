"""
API Tests for Organization endpoints.
"""
from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.work_structures.models import Organization, Location
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module"""
    setup_core_data()


class OrganizationAPITest(TestCase):
    """Test Organization API endpoints."""

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
        self.org_type_lookup = LookupType.objects.create(name="Organization Type")
        self.org_class_type = LookupType.objects.create(name="Organization Classification")

        # Create Lookup Values
        self.org_type_bg = LookupValue.objects.create(
            lookup_type=self.org_type_lookup,
            name="Business Group",
            is_active=True
        )

        self.org_type_dept = LookupValue.objects.create(
            lookup_type=self.org_type_lookup,
            name="Department",
            is_active=True
        )

        self.class_hr = LookupValue.objects.create(
            lookup_type=self.org_class_type,
            name="HR",
            is_active=True
        )

        # Root Business Group
        self.bg = Organization.objects.create(
            organization_name="BG001",
            organization_type=self.org_type_bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

    def test_list_organizations(self):
        """Test GET /hr/work_structures/organizations/"""
        response = self.client.get('/hr/work_structures/organizations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check pagination results
        # Handle wrapped response from auto_paginate
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]['organization_name'], 'BG001')
        self.assertIn('business_group_id', results[0])

    def test_list_organizations_filter_by_is_business_group(self):
        """Test GET /hr/work_structures/organizations/?is_business_group=true"""
        # Create a non-BG organization
        Organization.objects.create(
            organization_name="DEPT_TEST",
            organization_type=self.org_type_dept,
            business_group=self.bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Filter for business groups (should only return BG001)
        response = self.client.get('/hr/work_structures/organizations/?is_business_group=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['organization_name'], 'BG001')

        # Filter for non-business groups (should only return DEPT_TEST)
        response = self.client.get('/hr/work_structures/organizations/?is_business_group=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['organization_name'], 'DEPT_TEST')

    def test_create_organization_success(self):
        """Test POST /hr/work_structures/organizations/"""
        data = {
            'organization_name': 'DEPT001',
            'organization_type_id': self.org_type_dept.id,
            'business_group_id': self.bg.id,
            'work_start_time': '09:00:00',
            'work_end_time': '17:00:00',
            'effective_start_date': str(date.today())
        }
        response = self.client.post('/hr/work_structures/organizations/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['organization_name'], 'DEPT001')
        
        # Verify in DB
        org = Organization.objects.get(organization_name='DEPT001')
        self.assertEqual(org.business_group_id, self.bg.id)

    def test_get_organization_detail(self):
        """Test GET /hr/work_structures/organizations/<id>/"""
        response = self.client.get(f'/hr/work_structures/organizations/{self.bg.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['organization_name'], 'BG001')

    def test_update_organization(self):
        """Test PATCH /hr/work_structures/organizations/<id>/"""
        data = {'work_start_time': '10:00:00'}
        response = self.client.patch(f'/hr/work_structures/organizations/{self.bg.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # work_start_time in response might be '10:00:00' or '10:00:00.000'
        self.assertTrue(response.data['work_start_time'].startswith('10:00'))

    def test_deactivate_organization(self):
        """Test DELETE /hr/work_structures/organizations/<id>/"""
        response = self.client.delete(f'/hr/work_structures/organizations/{self.bg.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deactivation
        self.bg.refresh_from_db()
        self.assertIsNotNone(self.bg.effective_end_date)
        self.assertTrue(self.bg.effective_end_date <= date.today())

    def test_organization_hierarchy(self):
        """Test GET /hr/work_structures/organizations/<id>/hierarchy/"""
        # Create a child
        Organization.objects.create(
            organization_name="DEPT002",
            organization_type=self.org_type_dept,
            business_group=self.bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        
        response = self.client.get(f'/hr/work_structures/organizations/{self.bg.id}/hierarchy/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('children', response.data)
        self.assertEqual(len(response.data['children']), 1)
