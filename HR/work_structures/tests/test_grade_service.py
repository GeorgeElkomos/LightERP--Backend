"""
Unit tests for Grade Service
Tests grade operations, sequence management, and business logic validations
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, datetime
from django.utils import timezone

from HR.work_structures.models import Grade, Organization, Location, GradeRate, GradeRateType
from HR.work_structures.services.grade_service import GradeService
from HR.work_structures.dtos import GradeCreateDTO, GradeUpdateDTO, GradeRateCreateDTO, GradeRateUpdateDTO
from core.lookups.models import LookupType, LookupValue
from core.base.models import StatusChoices

User = get_user_model()


class GradeServiceTest(TestCase):
    """Test GradeService business logic"""

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
        org_type_lookup = LookupType.objects.create(name='Organization Type')
        grade_name_type = LookupType.objects.create(name='Grade Name')
        currency_type, _ = LookupType.objects.get_or_create(name='Currency')
        country_type = LookupType.objects.create(name='Country')
        city_type = LookupType.objects.create(name='City')

        # Create lookups
        cls.org_type = LookupValue.objects.create(
            lookup_type=org_type_lookup, name='Business Group', is_active=True
        )
        cls.dept_type = LookupValue.objects.create(
            lookup_type=org_type_lookup, name='Department', is_active=True
        )
        cls.grade_name_1 = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Grade 1', is_active=True
        )
        cls.grade_name_2 = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Grade 2', is_active=True
        )
        cls.grade_name_inactive = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Inactive Grade', is_active=False
        )

        country = LookupValue.objects.create(
            lookup_type=country_type, name='Egypt', is_active=True
        )
        city = LookupValue.objects.create(
            lookup_type=city_type, name='Cairo', parent=country, is_active=True
        )

        # Create root organization without location first
        cls.root_org = Organization.objects.create(
            organization_name='BG001',
            organization_type=cls.org_type,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create location
        cls.location = Location.objects.create(
            business_group=cls.root_org,
            location_name='Cairo Office',
            country=country,
            city=city,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Update root org with location
        Organization.objects.filter(pk=cls.root_org.pk).update(location=cls.location)
        cls.root_org.refresh_from_db()

        # Create second root organization
        cls.root_org_2 = Organization.objects.create(
            organization_name='BG002',
            organization_type=cls.org_type,
            location=cls.location,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create child organization (department)
        cls.department = Organization.objects.create(
            organization_name='DEPT001',
            organization_type=cls.dept_type,
            location=cls.location,
            business_group=cls.root_org,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

    def test_create_grade_success(self):
        """Test successful grade creation"""
        dto = GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=self.grade_name_1.id,
            sequence=1,
            effective_from=timezone.now()
        )

        grade = GradeService.create(self.user, dto)

        self.assertIsNotNone(grade.id)
        self.assertEqual(grade.organization.id, self.root_org.id)
        self.assertEqual(grade.grade_name.id, self.grade_name_1.id)
        self.assertEqual(grade.sequence, 1)

    def test_create_grade_invalid_organization(self):
        """Test creation fails with invalid organization"""
        dto = GradeCreateDTO(
            business_group_id=99999,
            grade_name_id=self.grade_name_1.id,
            sequence=1,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.create(self.user, dto)

        self.assertIn('business_group_id', str(context.exception))

    def test_create_grade_non_root_organization(self):
        """Test creation fails when organization is not root"""
        dto = GradeCreateDTO(
            business_group_id=self.department.id,  # Child organization
            grade_name_id=self.grade_name_1.id,
            sequence=1,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('root' in error_msg or 'business group' in error_msg)

    def test_create_grade_invalid_grade_name_lookup(self):
        """Test creation fails with invalid grade name lookup"""
        dto = GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=99999,
            sequence=1,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.create(self.user, dto)

        self.assertIn('grade_name_id', str(context.exception))

    def test_create_grade_inactive_grade_name_lookup(self):
        """Test creation fails with inactive grade name lookup"""
        dto = GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=self.grade_name_inactive.id,
            sequence=1,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.create(self.user, dto)

        self.assertIn('inactive', str(context.exception).lower())

    def test_create_grade_negative_sequence(self):
        """Test creation fails with negative sequence"""
        dto = GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=self.grade_name_1.id,
            sequence=-1,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.create(self.user, dto)

        self.assertIn('sequence', str(context.exception).lower())

    def test_create_grade_zero_sequence(self):
        """Test creation fails with zero sequence"""
        dto = GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=self.grade_name_1.id,
            sequence=0,
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.create(self.user, dto)

        self.assertIn('sequence', str(context.exception).lower())

    def test_create_grade_duplicate_sequence(self):
        """Test creation fails with duplicate sequence in same business group"""
        # Create first grade
        Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        # Try to create another grade with same sequence
        dto = GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=self.grade_name_2.id,
            sequence=1,  # Duplicate
            effective_from=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('sequence' in error_msg and 'already exists' in error_msg)

    def test_create_grade_same_sequence_different_org_allowed(self):
        """Test same sequence allowed in different business groups"""
        # Create grade in first org
        grade1 = GradeService.create(self.user, GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=self.grade_name_1.id,
            sequence=1,
            effective_from=timezone.now()
        ))

        # Create grade with same sequence in second org - should succeed
        grade2 = GradeService.create(self.user, GradeCreateDTO(
            business_group_id=self.root_org_2.id,
            grade_name_id=self.grade_name_1.id,
            sequence=1,
            effective_from=timezone.now()
        ))

        self.assertIsNotNone(grade2.id)
        self.assertEqual(grade2.sequence, 1)
        self.assertNotEqual(grade1.organization.id, grade2.organization.id)

    def test_update_grade_name(self):
        """Test updating grade name"""
        grade = Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        dto = GradeUpdateDTO(
            grade_id=grade.id,
            grade_name_id=self.grade_name_2.id
        )

        updated = GradeService.update(self.user, dto)

        self.assertEqual(updated.id, grade.id)
        self.assertEqual(updated.grade_name.id, self.grade_name_2.id)

    def test_update_grade_sequence(self):
        """Test updating grade sequence"""
        grade = Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        dto = GradeUpdateDTO(
            grade_id=grade.id,
            sequence=5
        )

        updated = GradeService.update(self.user, dto)

        self.assertEqual(updated.sequence, 5)

    def test_update_grade_duplicate_sequence_fails(self):
        """Test updating to duplicate sequence fails"""
        # Create two grades
        Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )
        grade2 = Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_2,
            sequence=2,
            created_by=self.user,
            updated_by=self.user
        )

        # Try to update G2 to sequence 1 (duplicate)
        dto = GradeUpdateDTO(
            grade_id=grade2.id,
            sequence=1
        )

        with self.assertRaises(ValidationError) as context:
            GradeService.update(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('sequence' in error_msg and 'already exists' in error_msg)

    def test_deactivate_grade(self):
        """Test deactivating a grade"""
        grade = Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = GradeService.deactivate(self.user, grade.id)

        self.assertEqual(deactivated.id, grade.id)
        # Compare with StatusChoices enum value
        self.assertEqual(deactivated.status, StatusChoices.INACTIVE)

        # Verify not in active queryset
        active_grades = Grade.objects.active().filter(id=grade.id)
        self.assertEqual(active_grades.count(), 0)

    def test_get_grades_by_organization(self):
        """Test retrieving grades by organization"""
        # Create multiple grades
        Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=2,
            created_by=self.user,
            updated_by=self.user
        )
        Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_2,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        grades = GradeService.get_grades_by_organization(self.root_org.id)

        self.assertEqual(grades.count(), 2)
        # Should be ordered by sequence
        self.assertEqual(grades[0].sequence, 1)
        self.assertEqual(grades[1].sequence, 2)

    def test_get_next_sequence(self):
        """Test getting next available sequence"""
        # No grades yet - should return 1
        next_seq = GradeService.get_next_sequence(self.root_org.id)
        self.assertEqual(next_seq, 1)

        # Create grade with sequence 1
        Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        # Should return 2
        next_seq = GradeService.get_next_sequence(self.root_org.id)
        self.assertEqual(next_seq, 2)

        # Create grade with sequence 5 (gap)
        Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_2,
            sequence=5,
            created_by=self.user,
            updated_by=self.user
        )

        # Should return 6 (max + 1)
        next_seq = GradeService.get_next_sequence(self.root_org.id)
        self.assertEqual(next_seq, 6)

    def test_get_grade_by_sequence(self):
        """Test getting grade by sequence"""
        Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        found = GradeService.get_grade_by_sequence(self.root_org.id, 1)

        self.assertIsNotNone(found)
        self.assertEqual(found.grade_name.id, self.grade_name_1.id)

    def test_get_grade_by_sequence(self):
        """Test getting grade by organization and sequence"""
        grade = Grade.objects.create(
            organization=self.root_org,
            grade_name=self.grade_name_1,
            sequence=1,
            created_by=self.user,
            updated_by=self.user
        )

        found = GradeService.get_grade_by_sequence(self.root_org.id, 1)

        self.assertIsNotNone(found)
        self.assertEqual(found.id, grade.id)

    def test_grades_isolated_by_organization(self):
        """Test that grades are properly isolated by organization"""
        # Create grades in first org
        grade1 = GradeService.create(self.user, GradeCreateDTO(
            business_group_id=self.root_org.id,
            grade_name_id=self.grade_name_1.id,
            sequence=1,
            effective_from=timezone.now()
        ))

        # Create grades in second org
        grade2 = GradeService.create(self.user, GradeCreateDTO(
            business_group_id=self.root_org_2.id,
            grade_name_id=self.grade_name_1.id,
            sequence=1,
            effective_from=timezone.now()
        ))

        # Get grades for first org
        grades1 = GradeService.get_grades_by_organization(self.root_org.id)
        self.assertEqual(grades1.count(), 1)
        self.assertEqual(grades1[0].id, grade1.id)

        # Get grades for second org
        grades2 = GradeService.get_grades_by_organization(self.root_org_2.id)
        self.assertEqual(grades2.count(), 1)
        self.assertEqual(grades2[0].id, grade2.id)

class GradeRateServiceTest(TestCase):
    """Test GradeRate Service business logic"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='test_rate@example.com',
            name='Test Rate User',
            phone_number='1234567890',
            password='testpass123'
        )

        # Create lookup types
        org_type_lookup = LookupType.objects.create(name='Organization Type')
        grade_name_type = LookupType.objects.create(name='Grade Name')
        currency_type, _ = LookupType.objects.get_or_create(name='Currency')
        
        # Create lookups
        cls.org_type = LookupValue.objects.create(
            lookup_type=org_type_lookup, name='Business Group', is_active=True
        )
        cls.grade_name = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Grade 1', is_active=True
        )
        cls.currency = LookupValue.objects.create(
            lookup_type=currency_type, name='USD', is_active=True
        )

        # Create root organization
        cls.root_org = Organization.objects.create(
            organization_name='BG001',
            organization_type=cls.org_type,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create Grade
        cls.grade = Grade.objects.create(
            organization=cls.root_org,
            grade_name=cls.grade_name,
            sequence=1,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create Rate Type
        cls.rate_type = GradeRateType.objects.create(
            code='BASIC_SALARY',
            description='Basic Salary',
            created_by=cls.user,
            updated_by=cls.user
        )

    def test_switch_from_range_to_fixed(self):
        """Test switching from Min/Max to Fixed Amount"""
        # Create initial rate with Min/Max
        create_dto = GradeRateCreateDTO(
            grade_id=self.grade.id,
            rate_type_id=self.rate_type.id,
            min_amount=1000,
            max_amount=2000,
            currency_id=self.currency.id,
            effective_start_date=date(2023, 1, 1)
        )
        rate = GradeService.create_grade_rate(self.user, create_dto)
        
        self.assertEqual(rate.min_amount, 1000)
        self.assertEqual(rate.max_amount, 2000)
        self.assertIsNone(rate.fixed_amount)

        # Update with Fixed Amount
        update_dto = GradeRateUpdateDTO(
            grade_id=self.grade.id,
            rate_type_id=self.rate_type.id,
            fixed_amount=1500,
            new_start_date=date(2023, 6, 1)
        )
        
        updated_rate = GradeService.update_grade_rate(self.user, update_dto)
        
        # Verify switch
        self.assertEqual(updated_rate.fixed_amount, 1500)
        self.assertIsNone(updated_rate.min_amount)
        self.assertIsNone(updated_rate.max_amount)
        
        # Verify versioning
        self.assertNotEqual(rate.id, updated_rate.id)
        self.assertEqual(updated_rate.effective_start_date, date(2023, 6, 1))

    def test_switch_from_fixed_to_range(self):
        """Test switching from Fixed Amount to Min/Max"""
        # Create initial rate with Fixed Amount
        create_dto = GradeRateCreateDTO(
            grade_id=self.grade.id,
            rate_type_id=self.rate_type.id,
            fixed_amount=1500,
            currency_id=self.currency.id,
            effective_start_date=date(2024, 1, 1)
        )
        rate = GradeService.create_grade_rate(self.user, create_dto)
        
        self.assertEqual(rate.fixed_amount, 1500)
        self.assertIsNone(rate.min_amount)

        # Update with Min/Max
        update_dto = GradeRateUpdateDTO(
            grade_id=self.grade.id,
            rate_type_id=self.rate_type.id,
            min_amount=1200,
            max_amount=1800,
            new_start_date=date(2024, 6, 1)
        )
        
        updated_rate = GradeService.update_grade_rate(self.user, update_dto)
        
        # Verify switch
        self.assertEqual(updated_rate.min_amount, 1200)
        self.assertEqual(updated_rate.max_amount, 1800)
        self.assertIsNone(updated_rate.fixed_amount)

    def test_create_grade_rate_with_effective_end_date(self):
        """Test creating grade rate with effective end date"""
        start_date = date(2024, 1, 1)
        end_date = date(2025, 12, 31)
        dto = GradeRateCreateDTO(
            grade_id=self.grade.id,
            rate_type_id=self.rate_type.id,
            fixed_amount=2000,
            currency_id=self.currency.id,
            effective_start_date=start_date,
            effective_end_date=end_date
        )
        
        rate = GradeService.create_grade_rate(self.user, dto)
        
        self.assertEqual(rate.effective_end_date, end_date)
        self.assertEqual(rate.effective_start_date, start_date)
