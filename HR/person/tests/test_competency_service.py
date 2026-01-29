"""
Unit tests for Competency Service
Tests competency CRUD operations and business logic validations
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date

from HR.person.models import Competency
from HR.person.services.competency_service import CompetencyService
from HR.person.dtos import CompetencyCreateDTO, CompetencyUpdateDTO
from core.lookups.models import LookupType, LookupValue
from core.base.models import StatusChoices

User = get_user_model()


class CompetencyServiceTest(TestCase):
    """Test CompetencyService business logic"""

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

        # Create lookups
        cls.category_technical = LookupValue.objects.create(
            lookup_type=category_type, name='Technical', is_active=True
        )
        cls.category_behavioral = LookupValue.objects.create(
            lookup_type=category_type, name='Behavioral', is_active=True
        )
        cls.category_inactive = LookupValue.objects.create(
            lookup_type=category_type, name='Inactive Category', is_active=False
        )

    def test_create_competency_success(self):
        """Test successful competency creation"""
        dto = CompetencyCreateDTO(
            code='PYTHON',
            name='Python Programming',
            competency_category_id=self.category_technical.id,
            description='Advanced Python programming skills'
        )

        competency = CompetencyService.create(self.user, dto)

        self.assertIsNotNone(competency.id)
        self.assertEqual(competency.code, 'PYTHON')
        self.assertEqual(competency.name, 'Python Programming')
        self.assertEqual(competency.category.id, self.category_technical.id)
        self.assertEqual(competency.description, 'Advanced Python programming skills')

    def test_create_competency_without_description(self):
        """Test creating competency without description"""
        dto = CompetencyCreateDTO(
            code='LEAD',
            name='Leadership',
            competency_category_id=self.category_behavioral.id
        )

        competency = CompetencyService.create(self.user, dto)

        self.assertIsNotNone(competency.id)
        self.assertEqual(competency.description, '')

    def test_create_competency_duplicate_code(self):
        """Test creation fails with duplicate code"""
        # Create first competency
        Competency.objects.create(
            code='DUP',
            name='First',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )

        # Try to create another with same code
        dto = CompetencyCreateDTO(
            code='DUP',
            name='Second',
            competency_category_id=self.category_technical.id
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyService.create(self.user, dto)

        self.assertIn('code', str(context.exception).lower())

    def test_create_competency_invalid_category(self):
        """Test creation fails with invalid category"""
        dto = CompetencyCreateDTO(
            code='TEST',
            name='Test',
            competency_category_id=99999
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyService.create(self.user, dto)

        self.assertIn('competency_category_id', str(context.exception).lower())

    def test_create_competency_inactive_category(self):
        """Test creation fails with inactive category"""
        dto = CompetencyCreateDTO(
            code='TEST',
            name='Test',
            competency_category_id=self.category_inactive.id
        )

        with self.assertRaises(ValidationError) as context:
            CompetencyService.create(self.user, dto)

        self.assertIn('inactive', str(context.exception).lower())

    def test_update_competency_name(self):
        """Test updating competency name"""
        competency = Competency.objects.create(
            code='UPDATE',
            name='Original Name',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )

        dto = CompetencyUpdateDTO(
            code='UPDATE',
            name='Updated Name'
        )

        updated = CompetencyService.update(self.user, dto)

        self.assertEqual(updated.id, competency.id)
        self.assertEqual(updated.name, 'Updated Name')

    def test_update_competency_category(self):
        """Test updating competency category"""
        competency = Competency.objects.create(
            code='UPDATE',
            name='Test',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )

        dto = CompetencyUpdateDTO(
            code='UPDATE',
            competency_category_id=self.category_behavioral.id
        )

        updated = CompetencyService.update(self.user, dto)

        self.assertEqual(updated.category.id, self.category_behavioral.id)

    def test_update_competency_description(self):
        """Test updating competency description"""
        competency = Competency.objects.create(
            code='UPDATE',
            name='Test',
            category=self.category_technical,
            description='Old description',
            created_by=self.user,
            updated_by=self.user
        )

        dto = CompetencyUpdateDTO(
            code='UPDATE',
            description='New description'
        )

        updated = CompetencyService.update(self.user, dto)

        self.assertEqual(updated.description, 'New description')

    def test_deactivate_competency(self):
        """Test deactivating a competency"""
        competency = Competency.objects.create(
            code='DEACT',
            name='Test',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = CompetencyService.deactivate(self.user, 'DEACT')

        self.assertEqual(deactivated.id, competency.id)
        self.assertEqual(deactivated.status, StatusChoices.INACTIVE)

        # Verify not in active queryset
        active_competencies = Competency.objects.active().filter(code='DEACT')
        self.assertEqual(active_competencies.count(), 0)

    def test_get_competencies_by_category(self):
        """Test retrieving competencies by category"""
        # Create multiple competencies
        Competency.objects.create(
            code='TECH1',
            name='Python',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )
        Competency.objects.create(
            code='TECH2',
            name='Java',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )
        Competency.objects.create(
            code='BEH1',
            name='Communication',
            category=self.category_behavioral,
            created_by=self.user,
            updated_by=self.user
        )

        technical = CompetencyService.get_competencies_by_category('Technical')

        self.assertEqual(technical.count(), 2)
        codes = [c.code for c in technical]
        self.assertIn('TECH1', codes)
        self.assertIn('TECH2', codes)
        self.assertNotIn('BEH1', codes)

    def test_search_competencies(self):
        """Test searching competencies"""
        # Create test competencies
        Competency.objects.create(
            code='PYTHON',
            name='Python Programming',
            description='Advanced Python',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )
        Competency.objects.create(
            code='JAVA',
            name='Java Programming',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )
        Competency.objects.create(
            code='LEAD',
            name='Leadership',
            category=self.category_behavioral,
            created_by=self.user,
            updated_by=self.user
        )

        # Search by name
        results = CompetencyService.search_competencies('Python')
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].code, 'PYTHON')

        # Search by code
        results = CompetencyService.search_competencies('JAVA')
        self.assertEqual(results.count(), 1)

        # Search by description
        results = CompetencyService.search_competencies('Advanced')
        self.assertEqual(results.count(), 1)

        # Search with no term returns all
        results = CompetencyService.search_competencies('')
        self.assertEqual(results.count(), 3)

    def test_get_competency_by_code(self):
        """Test getting competency by code"""
        competency = Competency.objects.create(
            code='FIND',
            name='Find Me',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )

        found = CompetencyService.get_competency_by_code('FIND')

        self.assertIsNotNone(found)
        self.assertEqual(found.id, competency.id)

    def test_get_all_competencies(self):
        """Test getting all competencies"""
        # Create competencies in different categories
        Competency.objects.create(
            code='C1',
            name='First',
            category=self.category_behavioral,
            created_by=self.user,
            updated_by=self.user
        )
        Competency.objects.create(
            code='C2',
            name='Second',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )

        all_competencies = CompetencyService.get_all_competencies()

        self.assertEqual(all_competencies.count(), 2)
        self.assertEqual(all_competencies[0].category.name, 'Behavioral')  # Behavioral comes before Technical

    def test_active_inactive_filtering(self):
        """Test that queries only return active competencies"""
        # Create active competency
        active = Competency.objects.create(
            code='ACTIVE',
            name='Active',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )

        # Create and deactivate competency
        inactive = Competency.objects.create(
            code='INACTIVE',
            name='Inactive',
            category=self.category_technical,
            created_by=self.user,
            updated_by=self.user
        )
        inactive.deactivate()
        inactive.save()

        # Test all query methods return only active
        all_comps = CompetencyService.get_all_competencies()
        self.assertEqual(all_comps.count(), 1)
        self.assertEqual(all_comps[0].code, 'ACTIVE')

        by_category = CompetencyService.get_competencies_by_category('Technical')
        self.assertEqual(by_category.count(), 1)

        search_results = CompetencyService.search_competencies('Active')
        self.assertEqual(search_results.count(), 1)

