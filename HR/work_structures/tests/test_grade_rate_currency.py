from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date
from django.utils import timezone

from HR.work_structures.models import Grade, Organization, GradeRateType, GradeRate
from HR.work_structures.services.grade_service import GradeService
from HR.work_structures.dtos import GradeRateCreateDTO
from core.lookups.models import LookupType, LookupValue
from HR.lookup_config import CoreLookups

User = get_user_model()

class GradeRateCurrencyTest(TestCase):
    """Test Grade Rate Currency Lookup Integration"""

    @classmethod
    def setUpTestData(cls):
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

        # Create lookups
        cls.org_type = LookupValue.objects.create(
            lookup_type=org_type_lookup, name='Business Group', is_active=True
        )
        cls.grade_name = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Grade 1', is_active=True
        )
        cls.currency_usd = LookupValue.objects.create(
            lookup_type=currency_type, name='USD', is_active=True
        )
        cls.currency_eur = LookupValue.objects.create(
            lookup_type=currency_type, name='EUR', is_active=True
        )
        cls.currency_inactive = LookupValue.objects.create(
            lookup_type=currency_type, name='OLD', is_active=False
        )

        # Create Organization
        cls.org = Organization.objects.create(
            organization_name='Test BG',
            organization_type=cls.org_type,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create Grade
        cls.grade = Grade.objects.create(
            organization=cls.org,
            grade_name=cls.grade_name,
            sequence=1,
            effective_from=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create Grade Rate Type
        cls.rate_type = GradeRateType.objects.create(
            code='SALARY',
            description='Basic Salary',
            created_by=cls.user,
            updated_by=cls.user
        )

    def test_create_grade_rate_with_currency_lookup(self):
        """Test creating grade rate with valid currency lookup"""
        dto = GradeRateCreateDTO(
            grade_id=self.grade.id,
            rate_type_id=self.rate_type.id,
            min_amount=1000.00,
            max_amount=2000.00,
            currency_id=self.currency_usd.id,
            effective_start_date=date.today()
        )

        grade_rate = GradeService.create_grade_rate(self.user, dto)

        self.assertIsNotNone(grade_rate.id)
        self.assertEqual(grade_rate.currency, self.currency_usd)
        self.assertEqual(grade_rate.currency.name, 'USD')

    def test_create_grade_rate_without_currency(self):
        """Test creating grade rate without currency (optional)"""
        dto = GradeRateCreateDTO(
            grade_id=self.grade.id,
            rate_type_id=self.rate_type.id,
            min_amount=1000.00,
            max_amount=2000.00,
            currency_id=None,
            effective_start_date=date.today()
        )

        grade_rate = GradeService.create_grade_rate(self.user, dto)

        self.assertIsNotNone(grade_rate.id)
        self.assertIsNone(grade_rate.currency)
