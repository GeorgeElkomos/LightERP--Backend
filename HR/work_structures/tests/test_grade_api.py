"""
API Tests for Grade and GradeRate endpoints.
"""
from datetime import date
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.work_structures.models import Grade, GradeRate, GradeRateType, Organization
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module"""
    setup_core_data()


class GradeAPITest(TestCase):
    """Test Grade API endpoints."""

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
        self.org_type_lookup = LookupType.objects.get_or_create(name="Organization Type")[0]
        self.grade_name_type = LookupType.objects.get_or_create(name="Grade Name")[0]
        self.currency_type = LookupType.objects.get_or_create(name="Currency")[0]

        # Create Lookup Values
        self.org_type_bg = LookupValue.objects.create(
            lookup_type=self.org_type_lookup,
            name="Business Group",
            is_active=True
        )

        self.name_grade1 = LookupValue.objects.create(
            lookup_type=self.grade_name_type,
            name="Grade 1",
            is_active=True
        )

        self.currency_egp = LookupValue.objects.create(
            lookup_type=self.currency_type,
            name="EGP",
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

        # Test Grade
        self.grade = Grade.objects.create(
            organization=self.bg,
            sequence=1,
            grade_name=self.name_grade1,
            created_by=self.user,
            updated_by=self.user
        )

        # Rate Type
        self.rate_type = GradeRateType.objects.create(
            code="BASIC_SALARY",
        )
    
    def test_list_grades(self):
        """Test GET /hr/work_structures/grades/"""
        response = self.client.get('/hr/work_structures/grades/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check pagination
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['sequence'], 1)

    def test_list_grades_filter_by_business_group(self):
        """Test GET /hr/work_structures/grades/?business_group=<id>"""
        # Create another BG and Grade
        bg2 = Organization.objects.create(
            organization_name="BG002",
            organization_type=self.org_type_bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        Grade.objects.create(
            organization=bg2,
            sequence=2,
            grade_name=self.name_grade1,
            created_by=self.user,
            updated_by=self.user
        )

        # Filter by first BG
        response = self.client.get(f'/hr/work_structures/grades/?business_group={self.bg.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['sequence'], 1)

    def test_create_grade_success(self):
        """Test POST /hr/work_structures/grades/"""
        # Create a new grade name for this test to avoid unique constraint violation
        new_grade_name = LookupValue.objects.create(
            lookup_type=self.grade_name_type,
            name="Grade 2",
            is_active=True
        )
        
        data = {
            'business_group_id': self.bg.id,
            'grade_name_id': new_grade_name.id,
            'sequence': 2,
            'effective_from': timezone.now().date()
        }
        response = self.client.post('/hr/work_structures/grades/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['sequence'], 2)

    def test_update_grade(self):
        """Test PATCH /hr/work_structures/grades/<id>/"""
        data = {'sequence': 10}
        response = self.client.patch(f'/hr/work_structures/grades/{self.grade.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sequence'], 10)

    def test_deactivate_grade(self):
        """Test DELETE /hr/work_structures/grades/<id>/"""
        response = self.client.delete(f'/hr/work_structures/grades/{self.grade.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deactivation
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.status, 'inactive')

    def test_list_grade_rates(self):
        """Test GET /hr/work_structures/grade-rates/"""
        # Create a rate first
        GradeRate.objects.create(
            grade=self.grade,
            rate_type=self.rate_type,
            min_amount=1000,
            max_amount=2000,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        
        response = self.client.get('/hr/work_structures/grade-rates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)

    def test_create_grade_rate_success(self):
        """Test POST /hr/work_structures/grade-rates/"""
        data = {
            'grade_id': self.grade.id,
            'rate_type_id': self.rate_type.id,
            'min_amount': 5000,
            'max_amount': 10000,
            'currency': 'EGP'
        }
        response = self.client.post('/hr/work_structures/grade-rates/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['min_amount']), 5000.0)

    def test_update_grade_rate(self):
        """Test PATCH /hr/work_structures/grade-rates/<id>/"""
        rate = GradeRate.objects.create(
            grade=self.grade,
            rate_type=self.rate_type,
            min_amount=1000,
            max_amount=2000,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        
        data = {'min_amount': 1500}
        response = self.client.patch(f'/hr/work_structures/grade-rates/{rate.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['min_amount']), 1500.0)

    # GradeRateType Tests

    def test_list_grade_rate_types(self):
        """Test GET /hr/work_structures/grade-rate-types/"""
        response = self.client.get('/hr/work_structures/grade-rate-types/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) >= 1)  # Created in setUp

    def test_create_grade_rate_type(self):
        """Test POST /hr/work_structures/grade-rate-types/"""
        data = {
            'code': 'HOUSING',
            'description': 'Housing Allowance'
        }
        response = self.client.post('/hr/work_structures/grade-rate-types/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'HOUSING')

    def test_update_grade_rate_type(self):
        """Test PATCH /hr/work_structures/grade-rate-types/<id>/"""
        data = {'description': 'Basic Salary Updated'}
        response = self.client.patch(f'/hr/work_structures/grade-rate-types/{self.rate_type.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Basic Salary Updated')

    def test_delete_grade_rate_type(self):
        """Test DELETE /hr/work_structures/grade-rate-types/<id>/"""
        # Create a new unused type for deletion
        new_type = GradeRateType.objects.create(code="UNUSED")
        
        response = self.client.delete(f'/hr/work_structures/grade-rate-types/{new_type.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(GradeRateType.objects.filter(id=new_type.id).exists())
