"""
Unit tests for CompetencyProficiency Service
Tests proficiency tracking, overlap prevention, and date range validation
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta

from HR.person.models import Competency, CompetencyProficiency, Person, Employee, PersonType
from HR.person.services.competency_proficiency_service import CompetencyProficiencyService
from HR.person.dtos import CompetencyProficiencyCreateDTO, CompetencyProficiencyUpdateDTO
from core.lookups.models import LookupType, LookupValue
from core.base.models import StatusChoices

User = get_user_model()


class CompetencyProficiencyServiceTest(TestCase):
    """Test CompetencyProficiencyService business logic"""

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
        category_type = LookupType.objects.create(name='Competency Category')
        level_type = LookupType.objects.create(name='Proficiency Level')
        source_type = LookupType.objects.create(name='Proficiency Source')

        # Create lookups
        cls.category_technical = LookupValue.objects.create(
            lookup_type=category_type, name='Technical', is_active=True
        )
        cls.level_beginner = LookupValue.objects.create(
            lookup_type=level_type, name='Beginner', is_active=True
        )
        cls.level_intermediate = LookupValue.objects.create(
            lookup_type=level_type, name='Intermediate', is_active=True
        )
        cls.level_expert = LookupValue.objects.create(
            lookup_type=level_type, name='Expert', is_active=True
        )
        cls.level_inactive = LookupValue.objects.create(
            lookup_type=level_type, name='Inactive Level', is_active=False
        )
        cls.source_self = LookupValue.objects.create(
            lookup_type=source_type, name='Self Assessment', is_active=True
        )
        cls.source_manager = LookupValue.objects.create(
            lookup_type=source_type, name='Manager Assessment', is_active=True
        )

        # Create competencies
        cls.comp_python = Competency.objects.create(
            code='PYTHON',
            name='Python Programming',
            category=cls.category_technical,
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.comp_java = Competency.objects.create(
            code='JAVA',
            name='Java Programming',
            category=cls.category_technical,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create person type
        cls.person_type = PersonType.objects.create(
            code='PERM_EMP',
            name='Permanent Employee',
            base_type='EMP'
        )

        # Create employee (creates person automatically)
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

    def test_create_proficiency_success(self):
        """Test successful proficiency record creation"""
        dto = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_beginner.id,
            proficiency_source_id=self.source_self.id,
            effective_start_date=date.today() - timedelta(days=30)
        )

        proficiency = CompetencyProficiencyService.create(self.user, dto)

        self.assertIsNotNone(proficiency.id)
        self.assertEqual(proficiency.person.id, self.person.id)
        self.assertEqual(proficiency.competency.id, self.comp_python.id)
        self.assertEqual(proficiency.proficiency_level.id, self.level_beginner.id)
        self.assertIsNone(proficiency.effective_end_date)

    def test_create_proficiency_with_end_date(self):
        """Test creating proficiency with end date"""
        dto = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_beginner.id,
            proficiency_source_id=self.source_self.id,
            effective_start_date=date.today() - timedelta(days=60),
            effective_end_date=date.today() - timedelta(days=30)
        )

        proficiency = CompetencyProficiencyService.create(self.user, dto)

        self.assertIsNotNone(proficiency.effective_end_date)
        self.assertEqual(proficiency.effective_end_date, date.today() - timedelta(days=30))

    def test_create_proficiency_invalid_person(self):
        """Test creation fails with invalid person"""
        dto = CompetencyProficiencyCreateDTO(
            person_id=99999,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_beginner.id,
            proficiency_source_id=self.source_self.id,
            effective_start_date=date.today()
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyProficiencyService.create(self.user, dto)

        self.assertIn('person', str(context.exception).lower())

    def test_create_proficiency_inactive_competency(self):
        """Test creation fails with inactive competency"""
        # Deactivate competency
        self.comp_python.deactivate()
        self.comp_python.save()

        dto = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_beginner.id,
            proficiency_source_id=self.source_self.id,
            effective_start_date=date.today()
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyProficiencyService.create(self.user, dto)

        self.assertIn('competency', str(context.exception).lower())

        # Reactivate for other tests
        self.comp_python.reactivate()
        self.comp_python.save()

    def test_create_proficiency_future_start_date(self):
        """Test creation fails with future start date"""
        dto = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_beginner.id,
            proficiency_source_id=self.source_self.id,
            effective_start_date=date.today() + timedelta(days=30)
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyProficiencyService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('future' in error_msg or 'effective_start_date' in error_msg)

    def test_create_proficiency_end_before_start(self):
        """Test creation fails when end date before start date"""
        dto = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_beginner.id,
            proficiency_source_id=self.source_self.id,
            effective_start_date=date.today(),
            effective_end_date=date.today() - timedelta(days=1)
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyProficiencyService.create(self.user, dto)

        self.assertIn('effective_end_date', str(context.exception).lower())

    def test_create_proficiency_overlapping_fails(self):
        """Test creation fails with overlapping date range"""
        # Create first proficiency
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=60),
            created_by=self.user,
            updated_by=self.user
        )

        # Try to create overlapping proficiency
        dto = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_intermediate.id,
            proficiency_source_id=self.source_manager.id,
            effective_start_date=date.today() - timedelta(days=30)
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyProficiencyService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('overlap' in error_msg or 'effective_start_date' in error_msg)

    def test_create_proficiency_sequential_allowed(self):
        """Test sequential (non-overlapping) proficiencies are allowed"""
        # Create first proficiency with end date
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=90),
            effective_end_date=date.today() - timedelta(days=60),
            created_by=self.user,
            updated_by=self.user
        )

        # Create second proficiency starting after first ends
        dto = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_intermediate.id,
            proficiency_source_id=self.source_manager.id,
            effective_start_date=date.today() - timedelta(days=59)
        )

        proficiency = CompetencyProficiencyService.create(self.user, dto)

        self.assertIsNotNone(proficiency.id)
        self.assertEqual(proficiency.proficiency_level.id, self.level_intermediate.id)

    def test_create_same_competency_different_person_allowed(self):
        """Test same competency allowed for different people"""
        # Create employee 2
        employee2 = Employee.objects.create(
            first_name='Jane',
            last_name='Smith',
            email_address='jane.smith@test.com',
            gender='Female',
            date_of_birth=date(1992, 1, 1),
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.person_type,
            effective_start_date=date.today(),
            hire_date=date.today(),
            employee_number='E002',
            created_by=self.user,
            updated_by=self.user
        )

        # Create proficiency for person 1
        dto1 = CompetencyProficiencyCreateDTO(
            person_id=self.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_beginner.id,
            proficiency_source_id=self.source_self.id,
            effective_start_date=date.today() - timedelta(days=30)
        )
        prof1 = CompetencyProficiencyService.create(self.user, dto1)

        # Create proficiency for person 2 - should succeed
        dto2 = CompetencyProficiencyCreateDTO(
            person_id=employee2.person.id,
            competency_id=self.comp_python.id,
            proficiency_level_id=self.level_expert.id,
            proficiency_source_id=self.source_manager.id,
            effective_start_date=date.today() - timedelta(days=30)
        )
        prof2 = CompetencyProficiencyService.create(self.user, dto2)

        self.assertIsNotNone(prof2.id)
        self.assertNotEqual(prof1.person.id, prof2.person.id)

    def test_update_proficiency_level(self):
        """Test updating proficiency level"""
        proficiency = CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        dto = CompetencyProficiencyUpdateDTO(
            proficiency_id=proficiency.id,
            proficiency_level_id=self.level_intermediate.id
        )

        updated = CompetencyProficiencyService.update(self.user, dto)

        self.assertEqual(updated.id, proficiency.id)
        self.assertEqual(updated.proficiency_level.id, self.level_intermediate.id)

    def test_update_proficiency_end_date(self):
        """Test updating proficiency end date"""
        proficiency = CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=60),
            created_by=self.user,
            updated_by=self.user
        )

        dto = CompetencyProficiencyUpdateDTO(
            proficiency_id=proficiency.id,
            effective_end_date=date.today() - timedelta(days=30)
        )

        updated = CompetencyProficiencyService.update(self.user, dto)

        self.assertEqual(updated.effective_end_date, date.today() - timedelta(days=30))

    def test_deactivate_proficiency(self):
        """Test deactivating a proficiency record"""
        proficiency = CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = CompetencyProficiencyService.deactivate(self.user, proficiency.id)

        self.assertEqual(deactivated.id, proficiency.id)
        # VersionedMixin deactivate sets effective_end_date to tomorrow (so it's active today)
        self.assertEqual(deactivated.effective_end_date, date.today() + timedelta(days=1))

        # Verify not in active queryset (as of tomorrow)
        # VersionedManager.active() checks active TODAY. Since we set end_date=tomorrow, it is still active TODAY.
        # Wait, VersionedMixin uses inclusive end date? Memory says yes.
        # "VersionedMixin and VersionedQuerySet.active_on use INCLUSIVE end dates."
        # So if I deactivate today, effective_end_date = today.
        # It IS active on today.
        # It is NOT active on tomorrow.
        
        self.assertTrue(CompetencyProficiency.objects.active_on(date.today()).filter(id=proficiency.id).exists())
        self.assertFalse(CompetencyProficiency.objects.active_on(date.today() + timedelta(days=1)).filter(id=proficiency.id).exists())

    def test_get_proficiencies_by_person(self):
        """Test retrieving all proficiencies for a person"""
        # Create multiple proficiencies
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=60),
            effective_end_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_intermediate,
            proficiency_source=self.source_manager,
            effective_start_date=date.today() - timedelta(days=29),
            created_by=self.user,
            updated_by=self.user
        )
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_java,
            proficiency_level=self.level_expert,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user,
            updated_by=self.user
        )

        proficiencies = CompetencyProficiencyService.get_proficiencies_by_person(self.person.id)

        self.assertEqual(proficiencies.count(), 3)

    def test_get_current_proficiency(self):
        """Test getting current proficiency for person/competency"""
        # Create past proficiency (ended)
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=90),
            effective_end_date=date.today() - timedelta(days=60),
            created_by=self.user,
            updated_by=self.user
        )

        # Create current proficiency
        current = CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_intermediate,
            proficiency_source=self.source_manager,
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        found = CompetencyProficiencyService.get_current_proficiency(
            self.person.id,
            self.comp_python.id
        )

        self.assertIsNotNone(found)
        self.assertEqual(found.id, current.id)
        self.assertEqual(found.proficiency_level.id, self.level_intermediate.id)

    def test_get_proficiency_history(self):
        """Test getting proficiency history for person/competency"""
        # Create multiple proficiencies over time
        prof1 = CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=90),
            effective_end_date=date.today() - timedelta(days=60),
            created_by=self.user,
            updated_by=self.user
        )
        prof2 = CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_intermediate,
            proficiency_source=self.source_manager,
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        history = CompetencyProficiencyService.get_proficiency_history(
            self.person.id,
            self.comp_python.id
        )

        self.assertEqual(history.count(), 2)
        # Should be ordered by effective_start_date (newest first)
        self.assertEqual(history[0].id, prof2.id)
        self.assertEqual(history[1].id, prof1.id)

    def test_get_proficiencies_by_competency(self):
        """Test getting all people with a specific competency"""
        # Create employee 2
        employee2 = Employee.objects.create(
            first_name='Jane',
            last_name='Smith',
            email_address='jane.smith@test.com',
            gender='Female',
            date_of_birth=date(1992, 1, 1),
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.person_type,
            effective_start_date=date.today(),
            hire_date=date.today(),
            employee_number='E002',
            created_by=self.user,
            updated_by=self.user
        )

        # Create proficiencies for both
        CompetencyProficiency.objects.create(
            person=self.person,
            competency=self.comp_python,
            proficiency_level=self.level_beginner,
            proficiency_source=self.source_self,
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )
        CompetencyProficiency.objects.create(
            person=employee2.person,
            competency=self.comp_python,
            proficiency_level=self.level_expert,
            proficiency_source=self.source_manager,
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        proficiencies = CompetencyProficiencyService.get_proficiencies_by_competency(
            self.comp_python.id
        )

        self.assertEqual(proficiencies.count(), 2)

