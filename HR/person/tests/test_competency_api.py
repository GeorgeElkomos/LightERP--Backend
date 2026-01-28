"""
API Tests for Competency and CompetencyProficiency endpoints.
"""
from datetime import date, timedelta
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.person.models import Competency, CompetencyProficiency, PersonType, Employee
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module"""
    setup_core_data()


class CompetencyAPITest(TestCase):
    """Test Competency and CompetencyProficiency API endpoints."""

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
            'COMP_CAT': LookupType.objects.get_or_create(name="Competency Category")[0],
            'PROF_LVL': LookupType.objects.get_or_create(name="Proficiency Level")[0],
            'PROF_SRC': LookupType.objects.get_or_create(name="Proficiency Source")[0],
        }

        # Create Lookup Values
        self.lookups = {
            'CAT_TECH': LookupValue.objects.create(lookup_type=self.types['COMP_CAT'], name="Technical", is_active=True),
            'LVL_BEG': LookupValue.objects.create(lookup_type=self.types['PROF_LVL'], name="Beginner", is_active=True),
            'SRC_SELF': LookupValue.objects.create(lookup_type=self.types['PROF_SRC'], name="Self Assessment", is_active=True),
        }

        # Create Competency
        self.competency = Competency.objects.create(
            code="PYTHON",
            name="Python Programming",
            description="Ability to write Python code",
            category=self.lookups['CAT_TECH'],
            created_by=self.user,
            updated_by=self.user
        )

        # Create Person (via Employee)
        self.person_type = PersonType.objects.create(
            code="PERM",
            name="Permanent",
            base_type="EMP",
            is_active=True
        )

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

        # Create Proficiency
        self.proficiency = CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.competency,
            proficiency_level=self.lookups['LVL_BEG'],
            proficiency_source=self.lookups['SRC_SELF'],
            effective_start_date=date.today() - timedelta(days=365),
            created_by=self.user,
            updated_by=self.user
        )

    # --- Competency Tests ---

    def test_list_competencies(self):
        """Test GET /hr/person/competencies/"""
        response = self.client.get('/hr/person/competencies/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['code'], 'PYTHON')

    def test_create_competency(self):
        """Test POST /hr/person/competencies/"""
        data = {
            'code': 'JAVA',
            'name': 'Java Programming',
            'competency_category_id': self.lookups['CAT_TECH'].id
        }
        response = self.client.post('/hr/person/competencies/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'JAVA')

    def test_update_competency(self):
        """Test PATCH /hr/person/competencies/<id>/"""
        data = {'name': 'Advanced Python'}
        response = self.client.patch(f'/hr/person/competencies/{self.competency.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Advanced Python')

    def test_deactivate_competency(self):
        """Test DELETE /hr/person/competencies/<id>/"""
        # Create a new competency without dependencies
        comp_to_delete = Competency.objects.create(
            code="DELETE_ME",
            name="To Delete",
            category=self.lookups['CAT_TECH'],
            created_by=self.user,
            updated_by=self.user
        )
        response = self.client.delete(f'/hr/person/competencies/{comp_to_delete.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        comp_to_delete.refresh_from_db()
        self.assertEqual(comp_to_delete.status, 'inactive')

    # --- Proficiency Tests ---

    def test_list_proficiencies(self):
        """Test GET /hr/person/competency-proficiencies/"""
        response = self.client.get(f'/hr/person/competency-proficiencies/?person={self.person.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if isinstance(response.data, dict):
            if 'data' in response.data and 'results' in response.data['data']:
                results = response.data['data']['results']
            else:
                results = response.data.get('results', response.data)
        else:
            results = response.data
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['competency_code'], 'PYTHON')

    def test_create_proficiency(self):
        """Test POST /hr/person/competency-proficiencies/"""
        # Create another competency
        new_comp = Competency.objects.create(
            code="SQL",
            name="SQL",
            category=self.lookups['CAT_TECH'],
            created_by=self.user,
            updated_by=self.user
        )
        
        data = {
            'person_id': self.person.id,
            'competency_id': new_comp.id,
            'proficiency_level_id': self.lookups['LVL_BEG'].id,
            'proficiency_source_id': self.lookups['SRC_SELF'].id,
            'effective_start_date': str(date.today())
        }
        response = self.client.post('/hr/person/competency-proficiencies/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['competency_code'], 'SQL')

    def test_update_proficiency_end_date(self):
        """Test PATCH /hr/person/competency-proficiencies/<id>/"""
        end_date = date.today()
        data = {'effective_end_date': str(end_date)}
        response = self.client.patch(f'/hr/person/competency-proficiencies/{self.proficiency.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['effective_end_date'], str(end_date))

    def test_overlap_validation(self):
        """Test creating overlapping proficiency returns error"""
        data = {
            'person_id': self.person.id,
            'competency_id': self.competency.id,
            'proficiency_level_id': self.lookups['LVL_BEG'].id,
            'proficiency_source_id': self.lookups['SRC_SELF'].id,
            'effective_start_date': str(date.today() - timedelta(days=10)) # Overlaps with existing which starts 365 days ago
        }
        response = self.client.post('/hr/person/competency-proficiencies/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('effective_start_date', response.data)
