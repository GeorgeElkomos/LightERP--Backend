
from django.test import TestCase
from datetime import date
from django.contrib.auth import get_user_model
from HR.person.models import Employee, PersonType, Assignment, Applicant
from HR.person.services.employee_service import EmployeeService
from HR.work_structures.models import Organization, Position, Job, Grade, Location
from core.lookups.models import LookupType, LookupValue

User = get_user_model()

class EmployeeCreationAssignmentTests(TestCase):
    """Test separation of employee creation and assignment creation"""

    @classmethod
    def setUpTestData(cls):
        # Create user
        cls.user = User.objects.create_user(
            email='test_assign@example.com', 
            name='Test Assign User', 
            phone_number='1234567890', 
            password='password'
        )

        # Create Lookup Types/Values needed for FKs
        org_type = LookupType.objects.create(name='Organization Type')
        LookupType.objects.create(name='Probation Period')
        LookupType.objects.create(name='Termination Notice Period')
        LookupType.objects.create(name='Payroll')
        LookupType.objects.create(name='Salary Basis')
        cls.dept_val = LookupValue.objects.create(lookup_type=org_type, name='Department', is_active=True)
        
        # Create BG
        bg_val = LookupValue.objects.create(lookup_type=org_type, name='Business Group', is_active=True)
        cls.bg = Organization.objects.create(
            organization_name='BG1', organization_type=bg_val, effective_start_date=date(2020, 1, 1), created_by=cls.user
        )

        # Create Organization (Department)
        cls.dept_a = Organization.objects.create(
            organization_name='DEPT_A', organization_type=cls.dept_val, business_group=cls.bg, effective_start_date=date(2020, 1, 1), created_by=cls.user
        )

        cls.emp_type = PersonType.objects.create(code='PERM', name='Perm', base_type='EMP', is_active=True)
        cls.apl_type = PersonType.objects.create(code='EXT_APL', name='External Applicant', base_type='APL', is_active=True)

    def test_hire_direct_no_assignment(self):
        """Test hire_direct does NOT create assignment automatically"""
        person_data = {
            'first_name': 'Org', 'last_name': 'User', 'email_address': 'org@test.com',
            'date_of_birth': date(1990, 1, 1), 'gender': 'Male', 'nationality': 'US', 'marital_status': 'Single'
        }
        employee_data = {'employee_type': self.emp_type, 'employee_number': 'E001'}
        
        employee = EmployeeService.hire_direct(
            person_data=person_data,
            employee_data=employee_data,
            hire_date=date(2025, 1, 1)
        )
        
        # Verify employee created
        self.assertIsNotNone(employee)
        
        # Verify NO assignment created
        assignments = Assignment.objects.filter(person=employee.person)
        self.assertEqual(assignments.count(), 0)

    def test_hire_from_applicant_no_assignment(self):
        """Test hire_from_applicant does NOT create assignment automatically"""
        # Create applicant record directly (this will create the Person)
        applicant = Applicant.objects.create(
            # Person fields
            first_name='App', 
            last_name='User', 
            email_address='app@test.com',
            date_of_birth=date(1990, 1, 1), 
            gender='Female', 
            nationality='UK', 
            marital_status='Single',
            
            # Applicant fields
            applicant_type=self.apl_type,
            application_number='APP001',
            effective_start_date=date(2024, 6, 1)
        )
        
        employee_data = {'employee_type': self.emp_type, 'employee_number': 'E002'}
        
        employee = EmployeeService.hire_from_applicant(
            applicant_id=applicant.id,
            effective_start_date=date(2025, 1, 1),
            hire_date=date(2025, 1, 1),
            employee_data=employee_data
        )
        
        # Verify employee created
        self.assertIsNotNone(employee)
        
        # Verify NO assignment created
        assignments = Assignment.objects.filter(person=employee.person)
        self.assertEqual(assignments.count(), 0)
