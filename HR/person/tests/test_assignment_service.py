from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta, time
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from HR.person.models import Assignment, Person, PersonType, Employee
from HR.person.services.assignment_service import AssignmentService
from HR.person.dtos import AssignmentCreateDTO, AssignmentUpdateDTO
from HR.work_structures.models import Organization, Job, Position, Grade, Location
from core.lookups.models import LookupType, LookupValue

User = get_user_model()

class AssignmentServiceTest(TestCase):
    """Test AssignmentService business logic"""

    @classmethod
    def setUpTestData(cls):
        # Create test user
        cls.user = User.objects.create_user(
            email='test_asg@example.com',
            name='Test User',
            phone_number='1234567891',
            password='testpass123'
        )

        # Create Lookup Types
        cls.org_type = LookupType.objects.create(name='Organization Type')
        cls.asg_action_type = LookupType.objects.create(name='Assignment Action Reason')
        cls.asg_status_type = LookupType.objects.create(name='Assignment Status')
        cls.probation_type = LookupType.objects.create(name='Probation Period')
        cls.job_title_type = LookupType.objects.create(name='Job Title')
        cls.job_family_type = LookupType.objects.create(name='Job Family')
        cls.job_cat_type = LookupType.objects.create(name='Job Category')
        cls.pos_title_type = LookupType.objects.create(name='Position Title')
        cls.pos_type_type = LookupType.objects.create(name='Position Type')
        cls.pos_status_type = LookupType.objects.create(name='Position Status')
        cls.grade_name_type = LookupType.objects.create(name='Grade Name')
        cls.payroll_type = LookupType.objects.create(name='Payroll')
        cls.salary_basis_type = LookupType.objects.create(name='Salary Basis')

        # Create Lookup Values
        cls.dept_type_val = LookupValue.objects.create(lookup_type=cls.org_type, name='Department', is_active=True)
        cls.bg_type_val = LookupValue.objects.create(lookup_type=cls.org_type, name='Business Group', is_active=True)
        cls.hire_action = LookupValue.objects.create(lookup_type=cls.asg_action_type, name='Hire', is_active=True)
        cls.active_asg_status = LookupValue.objects.create(lookup_type=cls.asg_status_type, name='Active', is_active=True)
        cls.probation_3m = LookupValue.objects.create(lookup_type=cls.probation_type, name='3 Months', is_active=True)
        cls.job_title_val = LookupValue.objects.create(lookup_type=cls.job_title_type, name='Developer', is_active=True)
        cls.job_cat_val = LookupValue.objects.create(lookup_type=cls.job_cat_type, name='Technical', is_active=True)
        cls.pos_title_val = LookupValue.objects.create(lookup_type=cls.pos_title_type, name='Developer', is_active=True)
        cls.pos_type_val = LookupValue.objects.create(lookup_type=cls.pos_type_type, name='Regular', is_active=True)
        cls.pos_status_val = LookupValue.objects.create(lookup_type=cls.pos_status_type, name='Active', is_active=True)
        cls.grade_name_val = LookupValue.objects.create(lookup_type=cls.grade_name_type, name='Grade 1', is_active=True)

        # Create BG and Dept
        cls.bg = Organization.objects.create(
            organization_name='BG1', organization_type=cls.bg_type_val, effective_start_date=date(2000, 1, 1), created_by=cls.user
        )
        cls.dept = Organization.objects.create(
            organization_name='DEPT1', organization_type=cls.dept_type_val, business_group=cls.bg, 
            effective_start_date=date(2000, 1, 1), created_by=cls.user
        )

        # Create Location
        cls.loc = Location.objects.create(
            location_name='Main Office', business_group=cls.bg, created_by=cls.user
        )

        # Create Job
        cls.job = Job.objects.create(
            code='JOB1', business_group=cls.bg, 
            job_title=cls.job_title_val, 
            job_category=cls.job_cat_val,
            job_description='Test Job', effective_start_date=date(2000, 1, 1), 
            created_by=cls.user, updated_by=cls.user
        )

        # Create Grade
        cls.grade = Grade.objects.create(
        organization=cls.bg, sequence=1, grade_name=cls.grade_name_val,
        created_by=cls.user, updated_by=cls.user
    )

        # Create Position
        cls.pos = Position.objects.create(
            code='POS1', organization=cls.dept, job=cls.job, position_title=cls.pos_title_val,
            position_type=cls.pos_type_val, position_status=cls.pos_status_val,
            location=cls.loc, grade=cls.grade, effective_start_date=date(2000, 1, 1),
            created_by=cls.user, updated_by=cls.user
        )

        # Create Person
        cls.person_type = PersonType.objects.create(code='PERM_EMP', name='Perm', base_type='EMP')
        cls.employee = Employee.objects.create(
            first_name='Jane', last_name='Doe', email_address='jane.doe@test.com',
            gender='Female', date_of_birth=date(1995, 1, 1), nationality='Egyptian',
            marital_status='Single', employee_type=cls.person_type,
            effective_start_date=date(2020, 1, 1), hire_date=date(2020, 1, 1),
            employee_number='E999', created_by=cls.user
        )
        cls.person = cls.employee.person

    def test_create_assignment(self):
        """Test basic assignment creation and probation end date calculation"""
        dto = AssignmentCreateDTO(
            person_id=self.person.id,
            business_group_id=self.bg.id,
            assignment_no='ASG-001',
            department_id=self.dept.id,
            job_id=self.job.id,
            position_id=self.pos.id,
            grade_id=self.grade.id,
            assignment_action_reason_id=self.hire_action.id,
            assignment_status_id=self.active_asg_status.id,
            effective_start_date=date.today(),
            probation_period_start=date.today(),
            probation_period_id=self.probation_3m.id,
            primary_assignment=True
        )
        asg = AssignmentService.create(self.user, dto)
        self.assertIsNotNone(asg.id)
        self.assertEqual(asg.assignment_no, 'ASG-001')
        # Check probation end (today + 3 months)
        expected_end = date.today() + relativedelta(months=3)
        self.assertEqual(asg.probation_period_end, expected_end)
        self.assertTrue(asg.primary_assignment)

    def test_primary_assignment_logic(self):
        """Test that creating a new primary assignment deactivates the old one"""
        # Create first primary
        asg1 = Assignment.objects.create(
            person=self.person, business_group=self.bg, assignment_no='ASG-1',
            department=self.dept, job=self.job, position=self.pos, grade=self.grade,
            assignment_action_reason=self.hire_action, assignment_status=self.active_asg_status,
            primary_assignment=True, effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user, updated_by=self.user
        )
        
        # Create second primary via service
        dto = AssignmentCreateDTO(
            person_id=self.person.id, business_group_id=self.bg.id, assignment_no='ASG-2',
            department_id=self.dept.id, job_id=self.job.id, position_id=self.pos.id,
            grade_id=self.grade.id, assignment_action_reason_id=self.hire_action.id,
            assignment_status_id=self.active_asg_status.id, effective_start_date=date.today(),
            primary_assignment=True
        )
        asg2 = AssignmentService.create(self.user, dto)
        
        asg1.refresh_from_db()
        self.assertFalse(asg1.primary_assignment)
        self.assertTrue(asg2.primary_assignment)

    def test_cross_validation_bg_mismatch(self):
        """Test that BG mismatch between assignment and dept fails"""
        other_bg = Organization.objects.create(
            organization_name='BG2', organization_type=self.bg_type_val, effective_start_date=date(2000, 1, 1), created_by=self.user
        )
        
        dto = AssignmentCreateDTO(
            person_id=self.person.id,
            business_group_id=other_bg.id, # Mismatch with dept
            assignment_no='ASG-FAIL',
            department_id=self.dept.id, # Belongs to BG1
            job_id=self.job.id,
            position_id=self.pos.id,
            grade_id=self.grade.id,
            assignment_action_reason_id=self.hire_action.id,
            assignment_status_id=self.active_asg_status.id,
            effective_start_date=date.today()
        )
        with self.assertRaises(ValidationError):
            AssignmentService.create(self.user, dto)

    def test_working_hours_property(self):
        """Test working_hours property calculation"""
        asg = Assignment(
            work_start_time=time(9, 0),
            work_end_time=time(17, 30)
        )
        self.assertEqual(asg.working_hours, 8.5)

    def test_calculate_probation_end_variations(self):
        """Test probation end calculation for various codes"""
        start = date(2024, 1, 1)
        
        # 2 weeks
        lv_2w = LookupValue.objects.create(lookup_type=self.probation_type, name='2 Weeks')
        self.assertEqual(AssignmentService.calculate_probation_end(start, lv_2w), date(2024, 1, 15))
        
        # 1 month
        lv_1m = LookupValue.objects.create(lookup_type=self.probation_type, name='1 Month')
        self.assertEqual(AssignmentService.calculate_probation_end(start, lv_1m), date(2024, 2, 1))
        
        # 6 months
        lv_6m = LookupValue.objects.create(lookup_type=self.probation_type, name='6 Months')
        self.assertEqual(AssignmentService.calculate_probation_end(start, lv_6m), date(2024, 7, 1))

    def test_create_assignment_invalid_ids(self):
        """Test creating assignment with invalid FK IDs"""
        dto_base = AssignmentCreateDTO(
            person_id=self.person.id, business_group_id=self.bg.id, assignment_no='FAIL',
            department_id=self.dept.id, job_id=self.job.id, position_id=self.pos.id,
            grade_id=self.grade.id, assignment_action_reason_id=self.hire_action.id,
            assignment_status_id=self.active_asg_status.id, effective_start_date=date.today()
        )
        
        # Invalid Person
        dto_base.person_id = 9999
        with self.assertRaises(ValidationError):
            AssignmentService.create(self.user, dto_base)
        dto_base.person_id = self.person.id
        
        # Invalid Dept
        dto_base.department_id = 9999
        with self.assertRaises(ValidationError):
            AssignmentService.create(self.user, dto_base)

    def test_assignment_update_correction(self):
        """Test assignment correction (same start date)"""
        asg = Assignment.objects.create(
            person=self.person, business_group=self.bg, assignment_no='ASG-U1',
            department=self.dept, job=self.job, position=self.pos, grade=self.grade,
            assignment_action_reason=self.hire_action, assignment_status=self.active_asg_status,
            effective_start_date=date.today(), created_by=self.user, updated_by=self.user
        )
        
        dto = AssignmentUpdateDTO(
            assignment_no='ASG-U1',
            effective_start_date=date.today(),
            title='New Title'
        )
        updated = AssignmentService.update(self.user, dto)
        self.assertEqual(updated.id, asg.id)
        self.assertEqual(updated.title, 'New Title')

    def test_assignment_update_new_version(self):
        """Test assignment new version (different start date)"""
        old_start = date.today() - timedelta(days=10)
        asg = Assignment.objects.create(
            person=self.person, business_group=self.bg, assignment_no='ASG-V',
            department=self.dept, job=self.job, position=self.pos, grade=self.grade,
            assignment_action_reason=self.hire_action, assignment_status=self.active_asg_status,
            effective_start_date=old_start, created_by=self.user, updated_by=self.user
        )
        
        new_start = date.today()
        dto = AssignmentUpdateDTO(
            assignment_no='ASG-V',
            effective_start_date=new_start,
            title='Future Manager'
        )
        updated = AssignmentService.update(self.user, dto)
        self.assertNotEqual(updated.id, asg.id)
        self.assertEqual(updated.title, 'Future Manager')
        
        # Check old version end-dated
        asg.refresh_from_db()
        self.assertEqual(asg.effective_end_date, new_start - timedelta(days=1))

    def test_query_methods(self):
        """Test various query methods in AssignmentService"""
        # Create an assignment
        asg = Assignment.objects.create(
            person=self.person, business_group=self.bg, assignment_no='ASG-Q',
            department=self.dept, job=self.job, position=self.pos, grade=self.grade,
            assignment_action_reason=self.hire_action, assignment_status=self.active_asg_status,
            primary_assignment=True, effective_start_date=date.today(),
            created_by=self.user, updated_by=self.user
        )
        
        self.assertEqual(len(AssignmentService.get_assignments_by_person(self.person.id)), 1)
        self.assertIsNotNone(AssignmentService.get_primary_assignment(self.person.id))
        self.assertEqual(len(AssignmentService.get_assignments_by_department(self.dept.id)), 1)
        self.assertEqual(len(AssignmentService.get_assignments_by_job(self.job.id)), 1)

    def test_deactivate_assignment(self):
        """Test assignment deactivation"""
        old_start = date.today() - timedelta(days=5)
        asg = Assignment.objects.create(
            person=self.person, business_group=self.bg, assignment_no='ASG-DEL',
            department=self.dept, job=self.job, position=self.pos, grade=self.grade,
            assignment_action_reason=self.hire_action, assignment_status=self.active_asg_status,
            effective_start_date=old_start, created_by=self.user, updated_by=self.user
        )
        
        AssignmentService.deactivate(self.user, 'ASG-DEL')
        asg.refresh_from_db()
        self.assertEqual(asg.effective_end_date, date.today() - timedelta(days=1))
