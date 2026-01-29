"""
API Tests for Qualification endpoints.
"""
from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.person.models import Qualification, PersonType, Employee, Competency
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


def setUpModule():
    """Run once per test module"""
    setup_core_data()


class QualificationAPITest(TestCase):
    """Test Qualification API endpoints."""

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
            'QUAL_TYPE': LookupType.objects.get_or_create(name="Qualification Type")[0],
            'QUAL_TITLE': LookupType.objects.get_or_create(name="Qualification Title")[0],
            'QUAL_STATUS': LookupType.objects.get_or_create(name="Qualification Status")[0],
            'AWARD_ENTITY': LookupType.objects.get_or_create(name="Awarding Entity")[0],
            'COMP_CAT': LookupType.objects.get_or_create(name="Competency Category")[0],
            'TUITION': LookupType.objects.get_or_create(name="Tuition Method")[0],
            'CURRENCY': LookupType.objects.get_or_create(name="Currency")[0],
        }

        # Create Lookup Values
        self.lookups = {
            'TYPE_BACH': LookupValue.objects.create(lookup_type=self.types['QUAL_TYPE'], name="Bachelor", is_active=True),
            'TITLE_CS': LookupValue.objects.create(lookup_type=self.types['QUAL_TITLE'], name="Computer Science", is_active=True),
            'STAT_COMP': LookupValue.objects.create(lookup_type=self.types['QUAL_STATUS'], name="Completed", is_active=True),
            'STAT_PROG': LookupValue.objects.create(lookup_type=self.types['QUAL_STATUS'], name="In Progress", is_active=True),
            'ENT_UNIV': LookupValue.objects.create(lookup_type=self.types['AWARD_ENTITY'], name="University", is_active=True),
            'CAT_TECH': LookupValue.objects.create(lookup_type=self.types['COMP_CAT'], name="Technical", is_active=True),
        }

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

        # Create Competency
        self.competency = Competency.objects.create(
            code="PYTHON",
            name="Python Programming",
            category=self.lookups['CAT_TECH'],
            created_by=self.user,
            updated_by=self.user
        )

        # Create Qualification
        self.qualification = Qualification.objects.create(
            person=self.person,
            qualification_type=self.lookups['TYPE_BACH'],
            qualification_title=self.lookups['TITLE_CS'],
            qualification_status=self.lookups['STAT_COMP'],
            awarding_entity=self.lookups['ENT_UNIV'],
            grade="GPA 3.8",
            awarded_date=date(2012, 6, 1),
            study_end_date=date(2012, 5, 30),
            created_by=self.user,
            updated_by=self.user
        )
        self.qualification.competency_achieved.add(self.competency)

    def test_list_qualifications(self):
        """Test GET /hr/person/qualifications/"""
        response = self.client.get(f'/hr/person/qualifications/?person={self.person.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['qualification_type_name'], 'Bachelor')

    def test_create_qualification_completed(self):
        """Test POST /hr/person/qualifications/ - Completed"""
        data = {
            'person_id': self.person.id,
            'qualification_type_id': self.lookups['TYPE_BACH'].id,
            'qualification_title_id': self.lookups['TITLE_CS'].id,
            'qualification_status_id': self.lookups['STAT_COMP'].id,
            'awarding_entity_id': self.lookups['ENT_UNIV'].id,
            'grade': 'Excellent',
            'awarded_date': '2015-06-01',
            'study_end_date': '2015-05-30',
            'competency_achieved_ids': [self.competency.id]
        }
        response = self.client.post('/hr/person/qualifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['grade'], 'Excellent')

    def test_create_qualification_in_progress(self):
        """Test POST /hr/person/qualifications/ - In Progress"""
        data = {
            'person_id': self.person.id,
            'qualification_type_id': self.lookups['TYPE_BACH'].id,
            'qualification_title_id': self.lookups['TITLE_CS'].id,
            'qualification_status_id': self.lookups['STAT_PROG'].id,
            'awarding_entity_id': self.lookups['ENT_UNIV'].id,
            'projected_completion_date': str(date.today()),
            'completed_percentage': 50
        }
        response = self.client.post('/hr/person/qualifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['completed_percentage'], 50)

    def test_validation_missing_completed_fields(self):
        """Test validation error for missing fields in Completed status"""
        data = {
            'person_id': self.person.id,
            'qualification_type_id': self.lookups['TYPE_BACH'].id,
            'qualification_title_id': self.lookups['TITLE_CS'].id,
            'qualification_status_id': self.lookups['STAT_COMP'].id,
            'awarding_entity_id': self.lookups['ENT_UNIV'].id,
            # Missing grade, awarded_date, study_end_date
        }
        response = self.client.post('/hr/person/qualifications/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check specific validation errors from model.clean() are returned
        # Note: Model validation stops at the first error in the sequence
        self.assertIn('awarded_date', response.data)

    def test_update_qualification(self):
        """Test PATCH /hr/person/qualifications/<id>/"""
        data = {'grade': 'GPA 4.0'}
        response = self.client.patch(f'/hr/person/qualifications/{self.qualification.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['grade'], 'GPA 4.0')

    def test_deactivate_qualification(self):
        """Test DELETE /hr/person/qualifications/<id>/"""
        response = self.client.delete(f'/hr/person/qualifications/{self.qualification.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.qualification.refresh_from_db()
        self.assertEqual(self.qualification.status, 'inactive')
