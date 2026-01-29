from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date

from HR.person.models import (
    Competency, 
    CompetencyProficiency, 
    JobCompetencyRequirement, 
    PositionCompetencyRequirement,
    Person,
    Employee,
    PersonType,
    Qualification
)
from HR.person.services.competency_service import CompetencyService
from HR.work_structures.models import Job, Position, Organization
from core.lookups.models import LookupType, LookupValue
from HR.lookup_config import CoreLookups

User = get_user_model()

class CompetencyDependencyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='test@example.com', 
            name='Test User',
            phone_number='1234567890',
            password='password123'
        )
        
        # Create common lookups
        cls.create_lookups()
        
        # Create Competency
        cls.competency = Competency.objects.create(
            code='COMP-001',
            name='Test Competency',
            category=cls.comp_cat,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create Business Group (for Job/Position)
        cls.bg = Organization.objects.create(
            organization_name='Test BG',
            organization_type=cls.org_type_bg,
            effective_start_date=date(2020, 1, 1)
        )
        
        # Create Job
        cls.job = Job.objects.create(
            code='JOB-001',
            business_group=cls.bg,
            job_title=cls.job_title,
            job_category=cls.job_cat,
            effective_start_date=date(2020, 1, 1)
        )
        
        # Create Position
        cls.position = Position.objects.create(
            code='POS-001',
            organization=cls.bg,
            job=cls.job,
            position_title=cls.pos_title,
            position_status=cls.pos_status,
            position_type=cls.pos_type,
            payroll=cls.payroll,
            salary_basis=cls.salary_basis,
            effective_start_date=date(2020, 1, 1)
        )
        
        # Create Employee (which creates Person)
        cls.person_type, _ = PersonType.objects.get_or_create(
            code='EMP', 
            defaults={'name': 'Employee', 'base_type': 'EMP', 'is_active': True}
        )
        cls.employee = Employee.objects.create(
            first_name='John',
            last_name='Doe',
            gender='Male',
            date_of_birth=date(1990, 1, 1),
            nationality='US',
            email_address='john.doe@test.com',
            employee_number='E12345',
            employee_type=cls.person_type,
            hire_date=date(2020, 1, 1),
            effective_start_date=date(2020, 1, 1),
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.person = cls.employee.person

    @classmethod
    def create_lookups(cls):
        # Competency Category
        lt_comp = LookupType.objects.create(name='Competency Category')
        cls.comp_cat = LookupValue.objects.create(lookup_type=lt_comp, name='Technical', is_active=True)
        
        # Proficiency Level
        lt_prof = LookupType.objects.create(name='Proficiency Level')
        cls.prof_level = LookupValue.objects.create(lookup_type=lt_prof, name='Intermediate', is_active=True)
        
        # Proficiency Source
        lt_source = LookupType.objects.create(name='Proficiency Source')
        cls.prof_source = LookupValue.objects.create(lookup_type=lt_source, name='Self', is_active=True)
        
        # Organization Type
        lt_org = LookupType.objects.create(name='Organization Type')
        cls.org_type_bg = LookupValue.objects.create(lookup_type=lt_org, name='Business Group', is_active=True)
        
        # Job Title/Category
        lt_job = LookupType.objects.create(name='Job Title')
        cls.job_title = LookupValue.objects.create(lookup_type=lt_job, name='Developer', is_active=True)
        lt_cat = LookupType.objects.create(name='Job Category')
        cls.job_cat = LookupValue.objects.create(lookup_type=lt_cat, name='IT', is_active=True)
        
        # Position Title/Status/Type
        lt_pos = LookupType.objects.create(name='Position Title')
        cls.pos_title = LookupValue.objects.create(lookup_type=lt_pos, name='Senior Developer', is_active=True)
        lt_pos_status = LookupType.objects.create(name='Position Status')
        cls.pos_status = LookupValue.objects.create(lookup_type=lt_pos_status, name='Active', is_active=True)
        lt_pos_type = LookupType.objects.create(name='Position Type')
        cls.pos_type = LookupValue.objects.create(lookup_type=lt_pos_type, name='Permanent', is_active=True)
        lt_payroll = LookupType.objects.create(name='Payroll')
        cls.payroll = LookupValue.objects.create(lookup_type=lt_payroll, name='Monthly', is_active=True)
        lt_salary = LookupType.objects.create(name='Salary Basis')
        cls.salary_basis = LookupValue.objects.create(lookup_type=lt_salary, name='Annual', is_active=True)

        # Qualification Lookups
        lt_qual_type = LookupType.objects.create(name='Qualification Type')
        cls.qual_type = LookupValue.objects.create(lookup_type=lt_qual_type, name='Degree', is_active=True)
        lt_qual_title = LookupType.objects.create(name='Qualification Title')
        cls.qual_title = LookupValue.objects.create(lookup_type=lt_qual_title, name='BS CS', is_active=True)
        lt_awarding = LookupType.objects.create(name='Awarding Entity')
        cls.awarding = LookupValue.objects.create(lookup_type=lt_awarding, name='University', is_active=True)
        lt_status = LookupType.objects.create(name='Qualification Status')
        cls.qual_status = LookupValue.objects.create(lookup_type=lt_status, name='Completed', is_active=True)

    def test_deactivate_with_job_requirement(self):
        """Test deactivation fails when used in Job Requirement"""
        JobCompetencyRequirement.objects.create(
            job=self.job,
            competency=self.competency,
            proficiency_level=self.prof_level
        )
        
        with self.assertRaises(ValidationError) as context:
            CompetencyService.deactivate(self.user, self.competency.code)
        
        self.assertIn('required by one or more Jobs', str(context.exception))

    def test_deactivate_with_position_requirement(self):
        """Test deactivation fails when used in Position Requirement"""
        PositionCompetencyRequirement.objects.create(
            position=self.position,
            competency=self.competency,
            proficiency_level=self.prof_level
        )
        
        with self.assertRaises(ValidationError) as context:
            CompetencyService.deactivate(self.user, self.competency.code)
            
        self.assertIn('required by one or more Positions', str(context.exception))

    def test_deactivate_with_competency_proficiency(self):
        """Test deactivation fails when used in active Competency Proficiency"""
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.competency,
            proficiency_level=self.prof_level,
            proficiency_source=self.prof_source,
            effective_start_date=date(2020, 1, 1)
        )
        
        with self.assertRaises(ValidationError) as context:
            CompetencyService.deactivate(self.user, self.competency.code)
            
        self.assertIn('proficiency records', str(context.exception))

    def test_deactivate_with_qualification(self):
        """Test deactivation fails when linked to a Qualification"""
        qual = Qualification.objects.create(
            person=self.person,
            qualification_type=self.qual_type,
            qualification_title=self.qual_title,
            awarding_entity=self.awarding,
            qualification_status=self.qual_status
        )
        qual.competency_achieved.add(self.competency)
        
        with self.assertRaises(ValidationError) as context:
            CompetencyService.deactivate(self.user, self.competency.code)
            
        self.assertIn('active Qualifications', str(context.exception))
