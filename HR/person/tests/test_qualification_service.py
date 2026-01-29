"""
Unit tests for Qualification Service
Tests qualification CRUD operations with status-based validation
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from HR.person.models import Qualification, Person, Employee, PersonType, Competency
from HR.person.services.qualification_service import QualificationService
from HR.person.dtos import QualificationCreateDTO, QualificationUpdateDTO
from core.lookups.models import LookupType, LookupValue
from core.base.models import StatusChoices

User = get_user_model()


class QualificationServiceTest(TestCase):
    """Test QualificationService business logic"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all tests"""
        # Create test user
        cls.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

        # Create lookup types
        qual_type_type = LookupType.objects.get_or_create(name='Qualification Type')[0]
        qual_title_type = LookupType.objects.get_or_create(name='Qualification Title')[0]
        qual_status_type = LookupType.objects.get_or_create(name='Qualification Status')[0]
        awarding_type = LookupType.objects.get_or_create(name='Awarding Entity')[0]
        tuition_method_type = LookupType.objects.get_or_create(name='Tuition Method')[0]
        currency_type = LookupType.objects.get_or_create(name='Currency')[0]
        comp_category_type = LookupType.objects.get_or_create(name='Competency Category')[0]

        # Create lookups
        cls.qual_type_bachelor = LookupValue.objects.create(
            lookup_type=qual_type_type, name='Bachelor', is_active=True
        )
        cls.qual_type_master = LookupValue.objects.create(
            lookup_type=qual_type_type, name='Master Degree', is_active=True
        )

        cls.qual_title_cs = LookupValue.objects.create(
            lookup_type=qual_title_type, name='Computer Science', is_active=True
        )
        cls.qual_title_others = LookupValue.objects.create(
            lookup_type=qual_title_type, name='Others', is_active=True
        )

        cls.status_completed = LookupValue.objects.create(
            lookup_type=qual_status_type, name='Completed', is_active=True
        )
        cls.status_in_progress = LookupValue.objects.create(
            lookup_type=qual_status_type, name='In Progress', is_active=True
        )

        cls.entity_harvard = LookupValue.objects.create(
            lookup_type=awarding_type, name='Harvard University', is_active=True
        )
        cls.entity_mit = LookupValue.objects.create(
            lookup_type=awarding_type, name='MIT', is_active=True
        )

        cls.tuition_self = LookupValue.objects.create(
            lookup_type=tuition_method_type, name='Self-funded', is_active=True
        )
        cls.tuition_company = LookupValue.objects.create(
            lookup_type=tuition_method_type, name='Company-sponsored', is_active=True
        )

        cls.currency_usd = LookupValue.objects.create(
            lookup_type=currency_type, name='US Dollar', is_active=True
        )
        cls.currency_egp = LookupValue.objects.create(
            lookup_type=currency_type, name='Egyptian Pound', is_active=True
        )

        # Create competencies
        comp_category = LookupValue.objects.create(
            lookup_type=comp_category_type, name='Technical', is_active=True
        )
        cls.comp_python = Competency.objects.create(
            code='PYTHON',
            name='Python Programming',
            category=comp_category,
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.comp_java = Competency.objects.create(
            code='JAVA',
            name='Java Programming',
            category=comp_category,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create person type and employee
        cls.person_type = PersonType.objects.create(
            code='PERM_EMP',
            name='Permanent Employee',
            base_type='EMP'
        )

        cls.employee = Employee.objects.create(
            first_name='John',
            last_name='Doe',
            email_address='john.doe@test.com',
            gender='Male',
            date_of_birth=date(1990, 1, 1),
            nationality='Egyptian',
            marital_status='Single',
            employee_type=cls.person_type,
            effective_start_date=date.today() - timedelta(days=365),
            hire_date=date.today() - timedelta(days=365),
            employee_number='E001',
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.person = cls.employee.person

    def test_create_completed_qualification(self):
        """Test creating a completed qualification"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_bachelor.id,
            qualification_title_id=self.qual_title_cs.id,
            qualification_status_id=self.status_completed.id,
            awarding_entity_id=self.entity_harvard.id,
            grade='3.8 GPA',
            awarded_date=date(2020, 6, 1),
            study_start_date=date(2016, 9, 1),
            study_end_date=date(2020, 6, 1),
            competency_achieved_ids=[self.comp_python.id, self.comp_java.id]
        )

        qual = QualificationService.create(self.user, dto)

        self.assertIsNotNone(qual.id)
        self.assertEqual(qual.person.id, self.person.id)
        self.assertEqual(qual.qualification_status.name, 'Completed')
        self.assertEqual(qual.grade, '3.8 GPA')
        self.assertEqual(qual.competency_achieved.count(), 2)

    def test_create_in_progress_qualification(self):
        """Test creating an in-progress qualification"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_master.id,
            qualification_title_id=self.qual_title_cs.id,
            qualification_status_id=self.status_in_progress.id,
            awarding_entity_id=self.entity_mit.id,
            projected_completion_date=date.today() + timedelta(days=365),
            completed_percentage=60,
            study_start_date=date.today() - timedelta(days=180),
            tuition_method_id=self.tuition_company.id,
            tuition_fees=50000.00,
            tuition_fees_currency_id=self.currency_usd.id
        )

        qual = QualificationService.create(self.user, dto)

        self.assertIsNotNone(qual.id)
        self.assertEqual(qual.qualification_status.name, 'In Progress')
        self.assertEqual(qual.completed_percentage, 60)
        self.assertEqual(qual.tuition_fees, Decimal('50000.00'))

    def test_create_completed_without_awarded_date_fails(self):
        """Test that completed qualification requires awarded_date"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_bachelor.id,
            qualification_title_id=self.qual_title_cs.id,
            qualification_status_id=self.status_completed.id,
            awarding_entity_id=self.entity_harvard.id,
            grade='3.8 GPA',
            study_start_date=date(2016, 9, 1),
            study_end_date=date(2020, 6, 1)
            # Missing awarded_date
        )

        with self.assertRaises(ValidationError) as context:
            QualificationService.create(self.user, dto)

        self.assertIn('awarded_date', str(context.exception).lower())

    def test_create_completed_without_grade_fails(self):
        """Test that completed qualification requires grade"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_bachelor.id,
            qualification_title_id=self.qual_title_cs.id,
            qualification_status_id=self.status_completed.id,
            awarding_entity_id=self.entity_harvard.id,
            awarded_date=date(2020, 6, 1),
            study_start_date=date(2016, 9, 1),
            study_end_date=date(2020, 6, 1)
            # Missing grade
        )

        with self.assertRaises(ValidationError) as context:
            QualificationService.create(self.user, dto)

        self.assertIn('grade', str(context.exception).lower())

    def test_create_in_progress_without_projected_date_fails(self):
        """Test that in-progress qualification requires projected_completion_date"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_master.id,
            qualification_title_id=self.qual_title_cs.id,
            qualification_status_id=self.status_in_progress.id,
            awarding_entity_id=self.entity_mit.id,
            completed_percentage=60,
            study_start_date=date.today() - timedelta(days=180)
            # Missing projected_completion_date
        )

        with self.assertRaises(ValidationError) as context:
            QualificationService.create(self.user, dto)

        self.assertIn('projected', str(context.exception).lower())

    def test_create_in_progress_without_percentage_fails(self):
        """Test that in-progress qualification requires completed_percentage"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_master.id,
            qualification_title_id=self.qual_title_cs.id,
            qualification_status_id=self.status_in_progress.id,
            awarding_entity_id=self.entity_mit.id,
            projected_completion_date=date.today() + timedelta(days=365),
            study_start_date=date.today() - timedelta(days=180)
            # Missing completed_percentage
        )

        with self.assertRaises(ValidationError) as context:
            QualificationService.create(self.user, dto)

        self.assertIn('percentage', str(context.exception).lower())

    def test_create_with_others_title_requires_title_if_others(self):
        """Test that 'Others' title requires title_if_others field"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_bachelor.id,
            qualification_title_id=self.qual_title_others.id,
            qualification_status_id=self.status_completed.id,
            awarding_entity_id=self.entity_harvard.id,
            grade='Excellent',
            awarded_date=date(2020, 6, 1),
            study_start_date=date(2016, 9, 1),
            study_end_date=date(2020, 6, 1)
            # Missing title_if_others
        )

        with self.assertRaises(ValidationError) as context:
            QualificationService.create(self.user, dto)

        self.assertIn('title_if_others', str(context.exception).lower())

    def test_create_with_tuition_fees_requires_currency(self):
        """Test that tuition_fees requires currency"""
        dto = QualificationCreateDTO(
            person_id=self.person.id,
            qualification_type_id=self.qual_type_bachelor.id,
            qualification_title_id=self.qual_title_cs.id,
            qualification_status_id=self.status_completed.id,
            awarding_entity_id=self.entity_harvard.id,
            grade='3.8 GPA',
            awarded_date=date(2020, 6, 1),
            study_start_date=date(2016, 9, 1),
            study_end_date=date(2020, 6, 1),
            tuition_fees=30000.00
            # Missing tuition_fees_currency_id
        )

        with self.assertRaises(ValidationError) as context:
            QualificationService.create(self.user, dto)

        self.assertIn('currency', str(context.exception).lower())

    def test_update_qualification_status(self):
        """Test updating qualification from in-progress to completed"""
        # Create in-progress qualification
        qual = Qualification.objects.create(
            person=self.person,
            qualification_type=self.qual_type_master,
            qualification_title=self.qual_title_cs,
            qualification_status=self.status_in_progress,
            awarding_entity=self.entity_mit,
            projected_completion_date=date.today() + timedelta(days=180),
            completed_percentage=80,
            study_start_date=date.today() - timedelta(days=365),
            created_by=self.user,
            updated_by=self.user
        )

        # Update to completed
        dto = QualificationUpdateDTO(
            qualification_id=qual.id,
            qualification_status_id=self.status_completed.id,
            grade='4.0 GPA',
            awarded_date=date.today(),
            study_end_date=date.today()
        )

        updated = QualificationService.update(self.user, dto)

        self.assertEqual(updated.qualification_status.name, 'Completed')
        self.assertEqual(updated.grade, '4.0 GPA')
        self.assertIsNotNone(updated.awarded_date)

    def test_get_qualifications_by_person(self):
        """Test retrieving all qualifications for a person"""
        # Create multiple qualifications
        Qualification.objects.create(
            person=self.person,
            qualification_type=self.qual_type_bachelor,
            qualification_title=self.qual_title_cs,
            qualification_status=self.status_completed,
            awarding_entity=self.entity_harvard,
            grade='3.5 GPA',
            awarded_date=date(2015, 6, 1),
            study_start_date=date(2011, 9, 1),
            study_end_date=date(2015, 6, 1),
            created_by=self.user,
            updated_by=self.user
        )
        Qualification.objects.create(
            person=self.person,
            qualification_type=self.qual_type_master,
            qualification_title=self.qual_title_cs,
            qualification_status=self.status_in_progress,
            awarding_entity=self.entity_mit,
            projected_completion_date=date.today() + timedelta(days=365),
            completed_percentage=50,
            study_start_date=date.today() - timedelta(days=180),
            created_by=self.user,
            updated_by=self.user
        )

        quals = QualificationService.get_qualifications_by_person(self.person.id)

        self.assertEqual(quals.count(), 2)

    def test_get_completed_qualifications(self):
        """Test retrieving only completed qualifications"""
        # Create completed and in-progress qualifications
        Qualification.objects.create(
            person=self.person,
            qualification_type=self.qual_type_bachelor,
            qualification_title=self.qual_title_cs,
            qualification_status=self.status_completed,
            awarding_entity=self.entity_harvard,
            grade='3.5 GPA',
            awarded_date=date(2015, 6, 1),
            study_start_date=date(2011, 9, 1),
            study_end_date=date(2015, 6, 1),
            created_by=self.user,
            updated_by=self.user
        )
        Qualification.objects.create(
            person=self.person,
            qualification_type=self.qual_type_master,
            qualification_title=self.qual_title_cs,
            qualification_status=self.status_in_progress,
            awarding_entity=self.entity_mit,
            projected_completion_date=date.today() + timedelta(days=365),
            completed_percentage=50,
            study_start_date=date.today() - timedelta(days=180),
            created_by=self.user,
            updated_by=self.user
        )

        completed = QualificationService.get_completed_qualifications(self.person.id)

        self.assertEqual(completed.count(), 1)
        self.assertEqual(completed[0].qualification_status.name, 'Completed')

    def test_deactivate_qualification(self):
        """Test deactivating a qualification"""
        qual = Qualification.objects.create(
            person=self.person,
            qualification_type=self.qual_type_bachelor,
            qualification_title=self.qual_title_cs,
            qualification_status=self.status_completed,
            awarding_entity=self.entity_harvard,
            grade='3.5 GPA',
            awarded_date=date(2015, 6, 1),
            study_start_date=date(2011, 9, 1),
            study_end_date=date(2015, 6, 1),
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = QualificationService.deactivate(self.user, qual.id)

        self.assertEqual(deactivated.id, qual.id)
        self.assertEqual(deactivated.status, StatusChoices.INACTIVE)

        # Verify not in active queryset
        active_quals = Qualification.objects.active().filter(id=qual.id)
        self.assertEqual(active_quals.count(), 0)

