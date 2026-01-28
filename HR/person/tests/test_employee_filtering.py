
from django.test import TestCase
from datetime import date
from django.contrib.auth import get_user_model
from HR.person.models import Employee, PersonType, Assignment
from HR.person.services.employee_service import EmployeeService
from HR.work_structures.models import Organization, Position, Job, Grade, Location
from core.lookups.models import LookupType, LookupValue

User = get_user_model()

class EmployeeFilteringTests(TestCase):
    """Test filtering employees by assignment attributes"""

    @classmethod
    def setUpTestData(cls):
        # Create user
        cls.user = User.objects.create_user(
            email='test_filter@example.com', 
            name='Test Filter User', 
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
        
        job_title_type = LookupType.objects.create(name='Job Title')
        cls.job_title_val = LookupValue.objects.create(lookup_type=job_title_type, name='Developer', is_active=True)

        job_cat_type = LookupType.objects.create(name='Job Category')
        cls.job_cat_val = LookupValue.objects.create(lookup_type=job_cat_type, name='Technical', is_active=True)
        
        job_fam_type = LookupType.objects.create(name='Job Family')
        cls.job_fam_val = LookupValue.objects.create(lookup_type=job_fam_type, name='IT', is_active=True)
        
        pos_title_type = LookupType.objects.create(name='Position Title')
        cls.pos_title_val = LookupValue.objects.create(lookup_type=pos_title_type, name='Developer', is_active=True)
        
        pos_status_type = LookupType.objects.create(name='Position Status')
        cls.pos_status_val = LookupValue.objects.create(lookup_type=pos_status_type, name='Active', is_active=True)

        pos_type_type = LookupType.objects.create(name='Position Type')
        cls.pos_type_val = LookupValue.objects.create(lookup_type=pos_type_type, name='Regular', is_active=True)

        grade_name_type = LookupType.objects.create(name='Grade Name')
        cls.grade_val = LookupValue.objects.create(lookup_type=grade_name_type, name='Grade 1', is_active=True)

        asg_reason_type = LookupType.objects.create(name='Reason')
        cls.hire_reason = LookupValue.objects.create(lookup_type=asg_reason_type, name='Hire', is_active=True)
        
        asg_status_type = LookupType.objects.create(name='Status')
        cls.active_status = LookupValue.objects.create(lookup_type=asg_status_type, name='Active', is_active=True)

        # Create BG
        bg_val = LookupValue.objects.create(lookup_type=org_type, name='Business Group', is_active=True)
        cls.bg = Organization.objects.create(
            organization_name='BG1', organization_type=bg_val, effective_start_date=date(2020, 1, 1), created_by=cls.user
        )

        # Create Location
        cls.loc = Location.objects.create(
            location_name='Main Office', business_group=cls.bg, created_by=cls.user
        )

        # Create Organizations (Departments)
        cls.dept_a = Organization.objects.create(
            organization_name='DEPT_A', organization_type=cls.dept_val, business_group=cls.bg, effective_start_date=date(2020, 1, 1), created_by=cls.user
        )
        cls.dept_b = Organization.objects.create(
            organization_name='DEPT_B', organization_type=cls.dept_val, business_group=cls.bg, effective_start_date=date(2020, 1, 1), created_by=cls.user
        )

        # Create Job & Grade (needed for Position)
        cls.job = Job.objects.create(
            code='JOB1', 
            job_title=cls.job_title_val, 
            job_category=cls.job_cat_val,
            business_group=cls.bg, 
            effective_start_date=date(2020, 1, 1), 
            created_by=cls.user
        )
        cls.grade = Grade.objects.create(
        sequence=1, grade_name=cls.grade_val, organization=cls.bg, created_by=cls.user
    )

        # Create Positions
        cls.pos_a = Position.objects.create(
            code='POS_A', organization=cls.dept_a, job=cls.job, grade=cls.grade, location=cls.loc,
            position_title=cls.pos_title_val, position_status=cls.pos_status_val,
            position_type=cls.pos_type_val,
            effective_start_date=date(2020, 1, 1), created_by=cls.user
        )
        cls.pos_b = Position.objects.create(
            code='POS_B', organization=cls.dept_b, job=cls.job, grade=cls.grade, location=cls.loc,
            position_title=cls.pos_title_val, position_status=cls.pos_status_val,
            position_type=cls.pos_type_val,
            effective_start_date=date(2020, 1, 1), created_by=cls.user
        )

        # Create Employees
        cls.emp_type = PersonType.objects.create(code='PERM', name='Perm', base_type='EMP', is_active=True)
        
        cls.emp_a = Employee.objects.create(
            first_name='Alice', last_name='A', email_address='alice@test.com',
            employee_type=cls.emp_type, employee_number='E001', hire_date=date(2025, 1, 1),
            date_of_birth=date(1990, 1, 1),
            effective_start_date=date(2025, 1, 1), created_by=cls.user
        )
        
        cls.emp_b = Employee.objects.create(
            first_name='Bob', last_name='B', email_address='bob@test.com',
            employee_type=cls.emp_type, employee_number='E002', hire_date=date(2025, 1, 1),
            date_of_birth=date(1990, 1, 1),
            effective_start_date=date(2025, 1, 1), created_by=cls.user
        )
        
        cls.emp_no_asg = Employee.objects.create(
            first_name='Charlie', last_name='C', email_address='charlie@test.com',
            employee_type=cls.emp_type, employee_number='E003', hire_date=date(2025, 1, 1),
            date_of_birth=date(1990, 1, 1),
            effective_start_date=date(2025, 1, 1), created_by=cls.user
        )

        # Create Assignments
        Assignment.objects.create(
            person=cls.emp_a.person,
            assignment_no='ASG001',
            business_group=cls.bg,
            department=cls.dept_a,
            position=cls.pos_a,
            job=cls.job,
            grade=cls.grade,
            assignment_action_reason=cls.hire_reason,
            assignment_status=cls.active_status,
            primary_assignment=True,
            effective_start_date=date(2025, 1, 1),
            created_by=cls.user
        )
        
        Assignment.objects.create(
            person=cls.emp_b.person,
            assignment_no='ASG002',
            business_group=cls.bg,
            department=cls.dept_b,
            position=cls.pos_b,
            job=cls.job,
            grade=cls.grade,
            assignment_action_reason=cls.hire_reason,
            assignment_status=cls.active_status,
            primary_assignment=True,
            effective_start_date=date(2025, 1, 1),
            created_by=cls.user
        )

    def test_filter_by_organization(self):
        """Test filtering employees by organization (department) via Assignment"""
        # Filter for Dept A -> Should get Emp A
        results = EmployeeService.list_employees({'organization_id': self.dept_a.id})
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.emp_a)
        
        # Filter for Dept B -> Should get Emp B
        results = EmployeeService.list_employees({'organization_id': self.dept_b.id})
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.emp_b)

    def test_filter_by_position(self):
        """Test filtering employees by position via Assignment"""
        # Filter for Pos A -> Should get Emp A
        results = EmployeeService.list_employees({'position_id': self.pos_a.id})
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.emp_a)
        
        # Filter for Pos B -> Should get Emp B
        results = EmployeeService.list_employees({'position_id': self.pos_b.id})
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.emp_b)
        
    def test_filter_no_results(self):
        """Test filtering where no match exists"""
        # Create unused dept
        unused_dept = Organization.objects.create(
            organization_name='UNUSED', organization_type=self.dept_val, effective_start_date=date(2020, 1, 1), created_by=self.user
        )
        results = EmployeeService.list_employees({'organization_id': unused_dept.id})
        self.assertEqual(results.count(), 0)

    def test_list_all_includes_unassigned(self):
        """Listing all should include employees without assignments"""
        results = EmployeeService.list_employees({})
        self.assertIn(self.emp_a, results)
        self.assertIn(self.emp_b, results)
        self.assertIn(self.emp_no_asg, results)
