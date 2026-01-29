"""
API Tests for Position endpoints.
"""
from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.work_structures.models import Position, Organization, Job, Grade, Location
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module"""
    setup_core_data()


class PositionAPITest(TestCase):
    """Test Position API endpoints."""

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
            'JOB_CAT': LookupType.objects.get_or_create(name="Job Category")[0],
            'JOB_TITLE': LookupType.objects.get_or_create(name="Job Title")[0],
            'GRADE_NAME': LookupType.objects.get_or_create(name="Grade Name")[0],
            'POS_TITLE': LookupType.objects.get_or_create(name="Position Title")[0],
            'POS_TYPE': LookupType.objects.get_or_create(name="Position Type")[0],
            'POS_STATUS': LookupType.objects.get_or_create(name="Position Status")[0],
            'BG_TYPE': LookupType.objects.get_or_create(name="Organization Type")[0],
            'COUNTRY': LookupType.objects.get_or_create(name="Country")[0],
            'CITY': LookupType.objects.get_or_create(name="City")[0],

            'PAYROLL': LookupType.objects.get_or_create(name="Payroll")[0],
            'SALARY_BASIS': LookupType.objects.get_or_create(name="Salary Basis")[0],
        }

        # Create Lookup Values
        self.lookups = {
            'BG_TYPE': LookupValue.objects.create(lookup_type=self.types['BG_TYPE'], name="Headquarters", is_active=True),
            'CAT_TECH': LookupValue.objects.create(lookup_type=self.types['JOB_CAT'], name="Technical", is_active=True),
            'TITLE_DEV': LookupValue.objects.create(lookup_type=self.types['JOB_TITLE'], name="Developer", is_active=True),
            'G1_NAME': LookupValue.objects.create(lookup_type=self.types['GRADE_NAME'], name="Grade 1", is_active=True),
            'PT_SENIOR': LookupValue.objects.create(lookup_type=self.types['POS_TITLE'], name="Senior Developer", is_active=True),
            'TYPE_REG': LookupValue.objects.create(lookup_type=self.types['POS_TYPE'], name="Regular", is_active=True),
            'STATUS_ACTIVE': LookupValue.objects.create(lookup_type=self.types['POS_STATUS'], name="Active", is_active=True),
        }

        # Root Business Group
        self.bg = Organization.objects.create(
            organization_name="BG001",
            organization_type=self.lookups['BG_TYPE'],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Country/City for Location
        self.country = LookupValue.objects.create(lookup_type=self.types['COUNTRY'], name="Egypt", is_active=True)
        self.city = LookupValue.objects.create(lookup_type=self.types['CITY'], name="Cairo", parent=self.country, is_active=True)

        # Location
        self.loc = Location.objects.create(
            location_name="Main Office",
            business_group=self.bg,
            country=self.country,
            city=self.city,
            created_by=self.user,
            updated_by=self.user
        )

        # Grade
        self.grade = Grade.objects.create(
            organization=self.bg,
            sequence=1,
            grade_name=self.lookups['G1_NAME'],
            created_by=self.user,
            updated_by=self.user
        )

        # Job
        self.job = Job.objects.create(
            code="JOB001",
            business_group=self.bg,
            job_category=self.lookups['CAT_TECH'],
            job_title=self.lookups['TITLE_DEV'],
            job_description="Test Job",
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Test Position
        self.pos = Position.objects.create(
            code="POS001",
            organization=self.bg,
            job=self.job,
            position_title=self.lookups['PT_SENIOR'],
            position_type=self.lookups['TYPE_REG'],
            position_status=self.lookups['STATUS_ACTIVE'],
            location=self.loc,
            grade=self.grade,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

    def test_list_positions(self):
        """Test GET /hr/work_structures/positions/"""
        response = self.client.get('/hr/work_structures/positions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['code'], 'POS001')

    def test_create_position_success(self):
        """Test POST /hr/work_structures/positions/"""
        data = {
            'code': 'POS002',
            'organization_id': self.bg.id,
            'job_id': self.job.id,
            'position_title_id': self.lookups['PT_SENIOR'].id,
            'position_type_id': self.lookups['TYPE_REG'].id,
            'position_status_id': self.lookups['STATUS_ACTIVE'].id,
            'location_id': self.loc.id,
            'grade_id': self.grade.id,
            'full_time_equivalent': 1.0,
            'head_count': 1,
            'effective_start_date': str(date.today())
        }
        response = self.client.post('/hr/work_structures/positions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'POS002')

    def test_update_position(self):
        """Test PATCH /hr/work_structures/positions/<id>/"""
        data = {'head_count': 5}
        response = self.client.patch(f'/hr/work_structures/positions/{self.pos.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['head_count'], 5)

    def test_deactivate_position(self):
        """Test DELETE /hr/work_structures/positions/<id>/"""
        response = self.client.delete(f'/hr/work_structures/positions/{self.pos.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deactivation
        self.pos.refresh_from_db()
        self.assertIsNotNone(self.pos.effective_end_date)

    def test_position_versions(self):
        """Test GET /hr/work_structures/positions/POS001/versions/"""
        # Create a new version
        new_start = date(2030, 1, 1)
        self.pos.update_version(
            field_updates={'head_count': 10},
            new_start_date=new_start
        )
        
        response = self.client.get(f'/hr/work_structures/positions/{self.pos.id}/versions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have 2 versions
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['head_count'], 10)
