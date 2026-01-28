"""
API Tests for Job endpoints.
"""
from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.work_structures.models import Job, Organization, Grade
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module"""
    setup_core_data()


class JobAPITest(TestCase):
    """Test Job API endpoints."""

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
        self.lookup_types = {
            'ORGANIZATION_TYPE': LookupType.objects.get_or_create(name="Organization Type")[0],
            'JOB_CATEGORY': LookupType.objects.get_or_create(name="Job Category")[0],
            'JOB_TITLE': LookupType.objects.get_or_create(name="Job Title")[0],
            'GRADE_NAME': LookupType.objects.get_or_create(name="Grade Name")[0],
        }

        # Create Lookup Values
        self.lookups = {
            'BG_TYPE': LookupValue.objects.create(lookup_type=self.lookup_types['ORGANIZATION_TYPE'], name="Business Group", is_active=True),
            'CATEGORY_TECH': LookupValue.objects.create(lookup_type=self.lookup_types['JOB_CATEGORY'], name="Technical", is_active=True),
            'TITLE_DEV': LookupValue.objects.create(lookup_type=self.lookup_types['JOB_TITLE'], name="Developer", is_active=True),
            'GRADE_1': LookupValue.objects.create(lookup_type=self.lookup_types['GRADE_NAME'], name="Grade 1", is_active=True),
        }

        # Root Business Group
        self.bg = Organization.objects.create(
            organization_name="BG001",
            organization_type=self.lookups['BG_TYPE'],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Test Job
        self.job = Job.objects.create(
            code="JOB001",
            business_group=self.bg,
            job_category=self.lookups['CATEGORY_TECH'],
            job_title=self.lookups['TITLE_DEV'],
            job_description="Test Job Description",
            responsibilities=["Task 1", "Task 2"],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

    def test_list_jobs(self):
        """Test GET /hr/work_structures/jobs/"""
        response = self.client.get('/hr/work_structures/jobs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['code'], 'JOB001')

    def test_create_job_success(self):
        """Test POST /hr/work_structures/jobs/"""
        data = {
            'code': 'JOB002',
            'business_group_id': self.bg.id,
            'job_category_id': self.lookups['CATEGORY_TECH'].id,
            'job_title_id': self.lookups['TITLE_DEV'].id,
            'job_description': 'Another Job',
            'responsibilities': ['Responsibility A'],
            'effective_start_date': str(date.today())
        }
        response = self.client.post('/hr/work_structures/jobs/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'JOB002')

    def test_update_job(self):
        """Test PATCH /hr/work_structures/jobs/<id>/"""
        data = {'job_description': 'Updated Description'}
        response = self.client.patch(f'/hr/work_structures/jobs/{self.job.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['job_description'], 'Updated Description')

    def test_deactivate_job(self):
        """Test DELETE /hr/work_structures/jobs/<id>/"""
        response = self.client.delete(f'/hr/work_structures/jobs/{self.job.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deactivation
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.effective_end_date)

    def test_job_versions(self):
        """Test GET /hr/work_structures/jobs/JOB001/versions/"""
        # Create a new version
        new_start = date(2030, 1, 1)
        self.job.update_version(
            field_updates={'job_description': 'New version'},
            new_start_date=new_start
        )
        
        response = self.client.get(f'/hr/work_structures/jobs/{self.job.id}/versions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have 2 versions
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['job_description'], 'New version')
