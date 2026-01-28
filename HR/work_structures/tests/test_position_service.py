"""
Unit tests for Position Service
Tests position CRUD operations with versioning and FK cross-validation
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from HR.work_structures.models import Position, Organization, Job, Grade, Location
from HR.work_structures.services.position_service import PositionService
from HR.work_structures.dtos import PositionCreateDTO, PositionUpdateDTO
from core.lookups.models import LookupType, LookupValue

User = get_user_model()


class PositionServiceTest(TestCase):
    """Test PositionService business logic"""

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
        org_type_lookup_type = LookupType.objects.create(name='Organization Type')
        grade_name_type = LookupType.objects.create(name='Grade Name')
        job_category_type = LookupType.objects.create(name='Job Category')
        job_title_type = LookupType.objects.create(name='Job Title')
        position_title_type = LookupType.objects.create(name='Position Title')
        position_type_type = LookupType.objects.create(name='Position Type')
        position_status_type = LookupType.objects.create(name='Position Status')
        country_type = LookupType.objects.create(name='Country')
        city_type = LookupType.objects.create(name='City')
        LookupType.objects.create(name='Payroll')
        LookupType.objects.create(name='Salary Basis')

        # Create lookups
        cls.org_type = LookupValue.objects.create(
            lookup_type=org_type_lookup_type, name='Business Group', is_active=True
        )
        cls.dept_type = LookupValue.objects.create(
            lookup_type=org_type_lookup_type, name='Department', is_active=True
        )
        cls.grade_name = LookupValue.objects.create(
            lookup_type=grade_name_type, name='Grade 5', is_active=True
        )
        cls.job_category = LookupValue.objects.create(
            lookup_type=job_category_type, name='Technical', is_active=True
        )
        cls.job_title_lookup = LookupValue.objects.create(
            lookup_type=job_title_type, name='Software Developer', is_active=True
        )
        cls.position_title = LookupValue.objects.create(
            lookup_type=position_title_type, name='Senior Developer', is_active=True
        )
        cls.position_type = LookupValue.objects.create(
            lookup_type=position_type_type, name='Regular', is_active=True
        )
        cls.position_status = LookupValue.objects.create(
            lookup_type=position_status_type, name='Active', is_active=True
        )

        country = LookupValue.objects.create(
            lookup_type=country_type, name='Egypt', is_active=True
        )
        city = LookupValue.objects.create(
            lookup_type=city_type, name='Cairo', parent=country, is_active=True
        )

        # Create root organization (business group)
        cls.root_org = Organization.objects.create(
            organization_name='BG001',
            organization_type=cls.org_type,
            effective_start_date=date.today() - timedelta(days=365),
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

        # Create department (child organization)
        cls.department = Organization.objects.create(
            organization_name='DEPT001',
            organization_type=cls.dept_type,
            business_group=cls.root_org,
            location=cls.location,
            effective_start_date=date.today() - timedelta(days=180),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create grade
        cls.grade = Grade.objects.create(
            organization=cls.root_org,
            sequence=5,
            grade_name=cls.grade_name,
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create job
        cls.job = Job.objects.create(
            code='JOB001',
            business_group=cls.root_org,
            job_category=cls.job_category,
            job_title=cls.job_title_lookup,
            job_description='Software development',
            responsibilities=['Code', 'Review'],
            effective_start_date=date.today() - timedelta(days=100),
            created_by=cls.user,
            updated_by=cls.user
        )

    def test_create_position_success(self):
        """Test successful position creation"""
        dto = PositionCreateDTO(
            code='POS001',
            organization_id=self.department.id,
            job_id=self.job.id,
            position_title_id=self.position_title.id,
            position_type_id=self.position_type.id,
            position_status_id=self.position_status.id,
            location_id=self.location.id,
            grade_id=self.grade.id,
            full_time_equivalent=1.0,
            head_count=1
        )

        position = PositionService.create(self.user, dto)

        self.assertIsNotNone(position.id)
        self.assertEqual(position.code, 'POS001')
        self.assertEqual(position.business_group.id, self.root_org.id)
        self.assertEqual(position.organization.id, self.department.id)
        self.assertEqual(position.full_time_equivalent, Decimal('1.0'))
        self.assertEqual(position.head_count, 1)

    def test_create_position_job_not_in_bg_fails(self):
        """Test that job must belong to business group"""
        # Create second business group
        root_org_2 = Organization.objects.create(
            organization_name='BG002',
            organization_type=self.org_type,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create job in second BG
        job_2 = Job.objects.create(
            code='JOB002',
            business_group=root_org_2,
            job_category=self.job_category,
            job_title=self.job_title_lookup,
            job_description='Test',
            responsibilities=[],
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        dto = PositionCreateDTO(
            code='POS003',
            organization_id=self.department.id,
            job_id=job_2.id,  # Job from different BG
            position_title_id=self.position_title.id,
            position_type_id=self.position_type.id,
            position_status_id=self.position_status.id,
            location_id=self.location.id,
            grade_id=self.grade.id
        )

        with self.assertRaises(ValidationError) as context:
            PositionService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('job' in error_msg and 'business group' in error_msg)

    def test_create_position_invalid_fte_fails(self):
        """Test FTE validation"""
        # Test FTE too low
        dto = PositionCreateDTO(
            code='POS004',
            organization_id=self.department.id,
            job_id=self.job.id,
            position_title_id=self.position_title.id,
            position_type_id=self.position_type.id,
            position_status_id=self.position_status.id,
            location_id=self.location.id,
            grade_id=self.grade.id,
            full_time_equivalent=0.05  # Too low
        )

        with self.assertRaises(ValidationError) as context:
            PositionService.create(self.user, dto)

        self.assertIn('fte', str(context.exception).lower())

        # Test FTE too high
        dto.full_time_equivalent = 2.0  # Too high
        with self.assertRaises(ValidationError) as context:
            PositionService.create(self.user, dto)

        self.assertIn('fte', str(context.exception).lower())

    def test_create_position_invalid_headcount_fails(self):
        """Test head count validation"""
        dto = PositionCreateDTO(
            code='POS005',
            organization_id=self.department.id,
            job_id=self.job.id,
            position_title_id=self.position_title.id,
            position_type_id=self.position_type.id,
            position_status_id=self.position_status.id,
            location_id=self.location.id,
            grade_id=self.grade.id,
            head_count=0  # Invalid
        )

        with self.assertRaises(ValidationError) as context:
            PositionService.create(self.user, dto)

        self.assertIn('head', str(context.exception).lower())

    def test_update_position_correction_mode(self):
        """Test updating position in correction mode"""
        position = Position.objects.create(
            code='POS006',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user,
            updated_by=self.user
        )

        # Update in correction mode
        dto = PositionUpdateDTO(
            position_id=position.id,
            full_time_equivalent=0.8,
            head_count=2
        )

        updated = PositionService.update(self.user, dto)

        self.assertEqual(updated.id, position.id)  # Same record
        self.assertEqual(updated.full_time_equivalent, Decimal('0.8'))
        self.assertEqual(updated.head_count, 2)

    def test_update_position_new_version_mode(self):
        """Test creating new version of position"""
        position = Position.objects.create(
            code='POS007',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        # Create new version
        new_start = date.today() + timedelta(days=10)
        dto = PositionUpdateDTO(
            position_id=position.id,
            full_time_equivalent=0.5,
            new_start_date=new_start
        )

        updated = PositionService.update(self.user, dto)

        self.assertNotEqual(updated.id, position.id)  # New record
        self.assertEqual(updated.effective_start_date, new_start)
        self.assertEqual(updated.full_time_equivalent, Decimal('0.5'))

        # Old version should be end-dated
        position.refresh_from_db()
        self.assertIsNotNone(position.effective_end_date)

    def test_deactivate_position(self):
        """Test deactivating a position"""
        position = Position.objects.create(
            code='POS008',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = PositionService.deactivate(self.user, position.id)

        self.assertEqual(deactivated.id, position.id)
        self.assertIsNotNone(deactivated.effective_end_date)

        # Should not be in active queryset
        active_positions = Position.objects.active_on(date.today()).filter(code='POS008')
        self.assertEqual(active_positions.count(), 0)

    def test_get_positions_by_organization(self):
        """Test retrieving positions by organization"""
        Position.objects.create(
            code='POS009',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        Position.objects.create(
            code='POS010',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        positions = PositionService.get_positions_by_organization(self.department.id)

        self.assertEqual(positions.count(), 2)

    def test_get_positions_by_job(self):
        """Test retrieving positions by job"""
        Position.objects.create(
            code='POS011',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        positions = PositionService.get_positions_by_job(self.job.id)

        self.assertEqual(positions.count(), 1)
        self.assertEqual(positions[0].job.id, self.job.id)

    def test_get_position_by_code(self):
        """Test getting position by code"""
        position = Position.objects.create(
            code='POS012',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        found = PositionService.get_position_by_code('POS012')

        self.assertIsNotNone(found)
        self.assertEqual(found.id, position.id)

    def test_get_position_versions(self):
        """Test retrieving all versions of a position"""
        # Create original version
        pos1 = Position.objects.create(
            code='POS013',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('1.0'),
            head_count=1,
            effective_start_date=date.today() - timedelta(days=60),
            effective_end_date=date.today() - timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        # Create new version
        pos2 = Position.objects.create(
            code='POS013',
            organization=self.department,
            job=self.job,
            position_title=self.position_title,
            position_type=self.position_type,
            position_status=self.position_status,
            location=self.location,
            grade=self.grade,
            full_time_equivalent=Decimal('0.8'),
            head_count=1,
            effective_start_date=date.today() - timedelta(days=29),
            created_by=self.user,
            updated_by=self.user
        )

        versions = PositionService.get_position_versions(pos1.id)

        self.assertEqual(versions.count(), 2)
        # Should be ordered newest first
        self.assertEqual(versions[0].id, pos2.id)
        self.assertEqual(versions[1].id, pos1.id)

    def test_create_position_with_part_time_fte(self):
        """Test creating part-time position"""
        dto = PositionCreateDTO(
            code='POS014',
            organization_id=self.department.id,
            job_id=self.job.id,
            position_title_id=self.position_title.id,
            position_type_id=self.position_type.id,
            position_status_id=self.position_status.id,
            location_id=self.location.id,
            grade_id=self.grade.id,
            full_time_equivalent=0.5,  # Part-time
            head_count=1
        )

        position = PositionService.create(self.user, dto)

        self.assertEqual(position.full_time_equivalent, Decimal('0.5'))

    def test_create_position_with_effective_end_date(self):
        """Test creating position with effective end date"""
        start_date = date(2024, 1, 1)
        end_date = date(2025, 12, 31)
        dto = PositionCreateDTO(
            code='POS015',
            organization_id=self.department.id,
            job_id=self.job.id,
            position_title_id=self.position_title.id,
            position_type_id=self.position_type.id,
            position_status_id=self.position_status.id,
            location_id=self.location.id,
            grade_id=self.grade.id,
            effective_start_date=start_date,
            effective_end_date=end_date
        )
        position = PositionService.create(self.user, dto)
        
        self.assertEqual(position.effective_end_date, end_date)

