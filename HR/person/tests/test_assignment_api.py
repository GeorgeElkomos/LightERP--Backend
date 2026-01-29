"""
API Tests for Assignment endpoints.
"""
from datetime import date, timedelta, time
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.person.models import Assignment, PersonType, Employee
from HR.work_structures.models import Organization, Job, Position, Grade, Location
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


class AssignmentAPITest(TestCase):
    """Test Assignment API endpoints."""

    def setUp(self):
        setup_core_data()
        self.client = APIClient()

        # Create test user with permissions
        self.user = User.objects.create_user(
            email="admin@test.com",
            name="Admin User",
            phone_number="1234567890",
            password="testpass123",
        )
        setup_admin_permissions(self.user)
        self.client.force_authenticate(user=self.user)

        # Create Lookups
        self.types = {
            'ORG_TYPE': LookupType.objects.get_or_create(name='Organization Type')[0],
            'LOC_TYPE': LookupType.objects.get_or_create(name='Location Type')[0],
            'GRADE_TYPE': LookupType.objects.get_or_create(name='Grade Type')[0],
            'JOB_FAM': LookupType.objects.get_or_create(name='Job Family')[0],
            'JOB_FUNC': LookupType.objects.get_or_create(name='Job Function')[0],
            'ASS_REASON': LookupType.objects.get_or_create(name='Assignment Action Reason')[0],
            'ASS_STATUS': LookupType.objects.get_or_create(name='Assignment Status')[0],
            'PAYROLL': LookupType.objects.get_or_create(name='Payroll')[0],
            'SAL_BASIS': LookupType.objects.get_or_create(name='Salary Basis')[0],
            'ORG_NAME': LookupType.objects.get_or_create(name='Organization Name')[0],
            'JOB_CAT': LookupType.objects.get_or_create(name='Job Category')[0],
            'JOB_TTL': LookupType.objects.get_or_create(name='Job Title')[0],
            'POS_FAM': LookupType.objects.get_or_create(name='Position Family')[0],
            'POS_CAT': LookupType.objects.get_or_create(name='Position Category')[0],
            'POS_TTL': LookupType.objects.get_or_create(name='Position Title')[0],
            'POS_TYPE': LookupType.objects.get_or_create(name='Position Type')[0],
            'POS_STAT': LookupType.objects.get_or_create(name='Position Status')[0],
            'GRADE_NM': LookupType.objects.get_or_create(name='Grade Name')[0],
            'PROB_PERIOD': LookupType.objects.get_or_create(name='Probation Period')[0],
            'TERM_NOTICE': LookupType.objects.get_or_create(name='Termination Notice Period')[0],
        }

        self.lookups = {
            'BG': LookupValue.objects.get_or_create(lookup_type=self.types['ORG_TYPE'], name='Business Group', is_active=True)[0],
            'DEPT': LookupValue.objects.get_or_create(lookup_type=self.types['ORG_TYPE'], name='Department', is_active=True)[0],
            'LOC_OFF': LookupValue.objects.get_or_create(lookup_type=self.types['LOC_TYPE'], name='Office', is_active=True)[0],
            'GRD_MGT': LookupValue.objects.get_or_create(lookup_type=self.types['GRADE_TYPE'], name='Management', is_active=True)[0],
            'JOB_IT': LookupValue.objects.get_or_create(lookup_type=self.types['JOB_FAM'], name='IT', is_active=True)[0],
            'REASON_HIRE': LookupValue.objects.get_or_create(lookup_type=self.types['ASS_REASON'], name='New Hire', is_active=True)[0],
            'STATUS_ACTIVE': LookupValue.objects.get_or_create(lookup_type=self.types['ASS_STATUS'], name='Active', is_active=True)[0],
            'PAY_MTH': LookupValue.objects.get_or_create(lookup_type=self.types['PAYROLL'], name='Monthly', is_active=True)[0],
            'SAL_FIXED': LookupValue.objects.get_or_create(lookup_type=self.types['SAL_BASIS'], name='Fixed', is_active=True)[0],
            'NAME_GC': LookupValue.objects.get_or_create(lookup_type=self.types['ORG_NAME'], name='Global Corp', is_active=True)[0],
            'NAME_IT': LookupValue.objects.get_or_create(lookup_type=self.types['ORG_NAME'], name='IT Department', is_active=True)[0],
            'J_CAT_TECH': LookupValue.objects.get_or_create(lookup_type=self.types['JOB_CAT'], name='Technical', is_active=True)[0],
            'J_TTL_SWE': LookupValue.objects.get_or_create(lookup_type=self.types['JOB_TTL'], name='Software Engineer', is_active=True)[0],
            'P_TTL_SNR': LookupValue.objects.get_or_create(lookup_type=self.types['POS_TTL'], name='Senior SWE', is_active=True)[0],
            'P_TYPE_REG': LookupValue.objects.get_or_create(lookup_type=self.types['POS_TYPE'], name='Regular', is_active=True)[0],
            'P_STAT_ACT': LookupValue.objects.get_or_create(lookup_type=self.types['POS_STAT'], name='Active', is_active=True)[0],
            'G_NM_1': LookupValue.objects.get_or_create(lookup_type=self.types['GRADE_NM'], name='Grade 1', is_active=True)[0],
        }

        # Create Business Group (Root)
        self.bg = Organization.objects.create(
            organization_name='GC001',
            organization_type=self.lookups['BG'],
            created_by=self.user,
            updated_by=self.user,
            effective_start_date=date.today()
        )

        # Create Location (requires BG)
        self.location = Location.objects.create(
            location_name='HQ',
            business_group=self.bg,
            created_by=self.user,
            updated_by=self.user
        )
        
        # Link Location back to BG
        self.bg.location = self.location
        self.bg.save()

        # Create Department
        self.dept = Organization.objects.create(
            organization_name='IT001',
            organization_type=self.lookups['DEPT'],
            location=self.location,
            business_group=self.bg,
            created_by=self.user,
            updated_by=self.user,
            effective_start_date=date.today()
        )

        # Create Job
        self.job = Job.objects.create(
            code='SWE001',
            # name removed
            job_title=self.lookups['J_TTL_SWE'],
            job_category=self.lookups['J_CAT_TECH'],
            job_description='Develop software',
            business_group=self.bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create Organization for Position (usually department)
        # Position links to Organization, which links to BG
        
        # Create Grade
        self.grade = Grade.objects.create(
            # name removed
            grade_name=self.lookups['G_NM_1'],
            sequence=1,
            organization=self.bg, # Grade linked to BG
            # grade_type removed? check model. Grade has grade_name. 
            # Original code had grade_type=self.lookups['GRD_MGT'].
            # Checking Grade model trace: 'grade_type' is NOT in fields I saw (I saw grade_name, sequence, organization).
            # Wait, let me check Grade model again.
            # Grade fields: code, organization, sequence, grade_name. NO grade_type.
            created_by=self.user,
            updated_by=self.user
        )

        # Create Position
        self.position = Position.objects.create(
            code='SWE001-POS',
            # name removed
            position_title=self.lookups['P_TTL_SNR'],
            position_type=self.lookups['P_TYPE_REG'],
            position_status=self.lookups['P_STAT_ACT'],
            organization=self.dept, # Dept is in BG
            job=self.job,
            grade=self.grade,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create Person
        self.person_type = PersonType.objects.create(code='PERM', name='Permanent', base_type='EMP', is_active=True)
        self.employee = Employee.objects.create(
            first_name="Jane", last_name="Smith",
            email_address="jane@test.com", gender="Female",
            date_of_birth=date(1990, 1, 1), nationality="UK",
            marital_status="Single", employee_type=self.person_type,
            employee_number="E002", hire_date=date(2022, 1, 1),
            effective_start_date=date(2022, 1, 1), created_by=self.user, updated_by=self.user
        )
        self.person = self.employee.person

        # Create Assignment
        self.assignment = Assignment.objects.create(
            person=self.person,
            business_group=self.bg,
            assignment_no="ASN001",
            department=self.dept,
            job=self.job,
            position=self.position,
            grade=self.grade,
            assignment_action_reason=self.lookups['REASON_HIRE'],
            assignment_status=self.lookups['STATUS_ACTIVE'],
            primary_assignment=True,
            effective_start_date=date(2023, 1, 1),
            created_by=self.user,
            updated_by=self.user
        )

    def test_list_assignments(self):
        """Test GET /hr/person/assignments/"""
        response = self.client.get(f'/hr/person/assignments/?person={self.person.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['assignment_no'], 'ASN001')

    def test_create_assignment(self):
        """Test POST /hr/person/assignments/"""
        data = {
            'person_id': self.person.id,
            'business_group_id': self.bg.id,
            'assignment_no': 'ASN002',
            'department_id': self.dept.id,
            'job_id': self.job.id,
            'position_id': self.position.id,
            'grade_id': self.grade.id,
            'assignment_action_reason_id': self.lookups['REASON_HIRE'].id,
            'assignment_status_id': self.lookups['STATUS_ACTIVE'].id,
            'effective_start_date': '2024-01-01',
            'primary_assignment': False, # Secondary assignment
            'work_start_time': '09:00:00',
            'work_end_time': '17:00:00'
        }
        response = self.client.post('/hr/person/assignments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Assignment.objects.count(), 2)

    def test_update_assignment_new_version(self):
        """Test PATCH /hr/person/assignments/<id>/"""
        new_date = self.assignment.effective_start_date + timedelta(days=60)
        data = {
            'work_start_time': '10:00:00',
            'effective_start_date': str(new_date)
        }
        response = self.client.patch(f'/hr/person/assignments/{self.assignment.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        versions = Assignment.objects.filter(assignment_no='ASN001').order_by('-effective_start_date')
        self.assertEqual(versions.count(), 2)
        self.assertEqual(str(versions[0].work_start_time), '10:00:00')

    def test_primary_assignment_switch(self):
        """Test that creating a new primary assignment unchecks the old one"""
        data = {
            'person_id': self.person.id,
            'business_group_id': self.bg.id,
            'assignment_no': 'ASN003',
            'department_id': self.dept.id,
            'job_id': self.job.id,
            'position_id': self.position.id,
            'grade_id': self.grade.id,
            'assignment_action_reason_id': self.lookups['REASON_HIRE'].id,
            'assignment_status_id': self.lookups['STATUS_ACTIVE'].id,
            'effective_start_date': '2024-06-01',
            'primary_assignment': True # This should takeover primary status
        }
        response = self.client.post('/hr/person/assignments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check original assignment
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.primary_assignment)
        
        # Check new assignment
        new_assign = Assignment.objects.get(assignment_no='ASN003')
        self.assertTrue(new_assign.primary_assignment)

    def test_get_primary_assignment(self):
        """Test GET /hr/person/assignments/primary/<person_id>/"""
        response = self.client.get(f'/hr/person/assignments/primary/{self.person.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['assignment_no'], 'ASN001')

    def test_validation_work_time(self):
        """Test invalid work times"""
        data = {
            'person_id': self.person.id,
            'business_group_id': self.bg.id,
            'assignment_no': 'ASN004',
            'department_id': self.dept.id,
            'job_id': self.job.id,
            'position_id': self.position.id,
            'grade_id': self.grade.id,
            'assignment_action_reason_id': self.lookups['REASON_HIRE'].id,
            'assignment_status_id': self.lookups['STATUS_ACTIVE'].id,
            'effective_start_date': '2024-01-01',
            'work_start_time': '17:00:00',
            'work_end_time': '09:00:00' # End before start
        }
        response = self.client.post('/hr/person/assignments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('work_end_time', response.data)
