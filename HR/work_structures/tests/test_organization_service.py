"""
Unit tests for Organization Service
Tests CRUD operations, hierarchy, versioning, and business logic validations
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, time, timedelta

from HR.work_structures.models import Organization, Location
from HR.work_structures.services.organization_service import OrganizationService
from HR.work_structures.dtos import OrganizationCreateDTO, OrganizationUpdateDTO
from core.lookups.models import LookupType, LookupValue

User = get_user_model()


class OrganizationServiceTest(TestCase):
    """Test OrganizationService business logic"""

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
        org_type_lookup = LookupType.objects.create(
            name='Organization Type'
        )
        org_class_type = LookupType.objects.create(
            name='Organization Classification'
        )
        country_type = LookupType.objects.create(
            name='Country'
        )
        city_type = LookupType.objects.create(
            name='City'
        )

        # Create organization type lookups
        cls.org_type_hq = LookupValue.objects.create(
            lookup_type=org_type_lookup,
            name='Business Group',
            is_active=True
        )
        cls.org_type_sales = LookupValue.objects.create(
            lookup_type=org_type_lookup,
            name='Sales Department',
            is_active=True
        )
        cls.org_type_it = LookupValue.objects.create(
            lookup_type=org_type_lookup,
            name='IT Department',
            is_active=True
        )
        cls.org_type_inactive = LookupValue.objects.create(
            lookup_type=org_type_lookup,
            name='Old Department',
            is_active=False
        )

        # Create classification lookups
        cls.class_cost_center = LookupValue.objects.create(
            lookup_type=org_class_type,
            name='Cost Center',
            is_active=True
        )
        cls.class_profit_center = LookupValue.objects.create(
            lookup_type=org_class_type,
            name='Profit Center',
            is_active=True
        )
        cls.class_inactive = LookupValue.objects.create(
            lookup_type=org_class_type,
            name='Old Classification',
            is_active=False
        )

        # Create country and city
        cls.country = LookupValue.objects.create(
            lookup_type=country_type,
            name='Egypt',
            is_active=True
        )
        cls.city = LookupValue.objects.create(
            lookup_type=city_type,
            name='Cairo',
            parent=cls.country,
            is_active=True
        )

        # Create a temporary root organization without location first
        cls.root_org = Organization.objects.create(
            organization_name='ROOT_ORG',
            organization_type=cls.org_type_hq,
            location=None,  # Temporarily None to break circular dependency
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create location referencing the root organization
        cls.location = Location.objects.create(
            business_group=cls.root_org,
            location_name='Cairo Office',
            country=cls.country,
            city=cls.city,
            street='Test Street',
            created_by=cls.user,
            updated_by=cls.user
        )

        # Update root_org to reference the location (completing the setup)
        Organization.objects.filter(pk=cls.root_org.pk).update(location=cls.location)
        cls.root_org.refresh_from_db()

    def test_create_business_group_success(self):
        """Test successful creation of root business group"""
        dto = OrganizationCreateDTO(
            organization_name='BG001',
            organization_type_id=self.org_type_hq.id,
            location_id=self.location.id,
            business_group_id=None,  # Root organization
            work_start_time=time(9, 0),
            work_end_time=time(17, 0),
            effective_start_date=date.today()
        )

        org = OrganizationService.create(self.user, dto)

        self.assertIsNotNone(org.id)
        self.assertEqual(org.organization_name, 'BG001')
        self.assertIsNone(org.business_group)
        self.assertTrue(org.is_business_group)
        self.assertEqual(org.hierarchy_level, 0)
        self.assertEqual(org.working_hours, 8.0)


    def test_create_child_organization_success(self):
        """Test successful creation of child organization"""
        # Create business group first
        bg = Organization.objects.create(
            organization_name='BG002',
            organization_type=self.org_type_hq,
            location=None,  # Temporarily None
            business_group=None,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        
        # Create location for this BG
        bg_location = Location.objects.create(
            business_group=bg,
            location_name='BG002 Location',
            country=self.country,
            city=self.city,
            street='BG002 Street',
            created_by=self.user,
            updated_by=self.user
        )
        
        # Update BG location
        bg.location = bg_location
        bg.save()

        # Create child
        dto = OrganizationCreateDTO(
            organization_name='DEPT001',
            organization_type_id=self.org_type_sales.id,
            location_id=bg_location.id,
            business_group_id=bg.id,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0)
        )

        child = OrganizationService.create(self.user, dto)

        self.assertIsNotNone(child.id)
        self.assertEqual(child.organization_name, 'DEPT001')
        self.assertEqual(child.business_group.id, bg.id)
        self.assertFalse(child.is_business_group)
        self.assertEqual(child.hierarchy_level, 1)
        self.assertEqual(child.working_hours, 9.0)

    def test_create_with_minimal_fields(self):
        """Test creation with minimal required fields"""
        dto = OrganizationCreateDTO(
            organization_name='BG003',
            organization_type_id=self.org_type_it.id,
            location_id=self.location.id
        )

        org = OrganizationService.create(self.user, dto)

        self.assertIsNotNone(org.id)
        self.assertEqual(org.work_start_time, time(9, 0))
        self.assertEqual(org.work_end_time, time(17, 0))
        self.assertEqual(org.effective_start_date, date.today())
        self.assertIsNone(org.effective_end_date)

    def test_create_invalid_location(self):
        """Test creation with invalid location"""
        dto = OrganizationCreateDTO(
            organization_name='BG006',
            organization_type_id=self.org_type_hq.id,
            location_id=99999
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationService.create(self.user, dto)

        self.assertIn('location_id', str(context.exception))

    def test_create_invalid_business_group(self):
        """Test creation with invalid business group"""
        dto = OrganizationCreateDTO(
            organization_name='DEPT002',
            organization_type_id=self.org_type_sales.id,
            location_id=self.location.id,
            business_group_id=99999
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationService.create(self.user, dto)

        self.assertIn('business_group_id', str(context.exception))

    def test_create_child_with_non_root_business_group(self):
        """Test that child organization cannot have non-root business group"""
        # Create root BG
        root = Organization.objects.create(
            organization_name='BG007',
            organization_type=self.org_type_hq,
            location=self.location,
            business_group=None,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create child (not root)
        child = Organization.objects.create(
            organization_name='DEPT003',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=root,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Try to use child as business group
        dto = OrganizationCreateDTO(
            organization_name='DEPT004',
            organization_type_id=self.org_type_it.id,
            location_id=self.location.id,
            business_group_id=child.id  # This is a child, not root
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('root' in error_msg or 'business group' in error_msg)

    def test_create_invalid_work_times(self):
        """Test creation with invalid work times (end before start)"""
        dto = OrganizationCreateDTO(
            organization_name='BG008',
            organization_type_id=self.org_type_hq.id,
            location_id=self.location.id,
            work_start_time=time(17, 0),
            work_end_time=time(9, 0)  # Before start time
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationService.create(self.user, dto)

        self.assertIn('work_end_time', str(context.exception).lower())

    def test_update_organization_success(self):
        """Test successful organization update"""
        org = Organization.objects.create(
            organization_name='BG010',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Update
        dto = OrganizationUpdateDTO(
            organization_id=org.id,
            organization_name='BG010_UPDATED',
            work_start_time=time(8, 0),
            work_end_time=time(16, 0)
        )

        updated = OrganizationService.update(self.user, dto)

        self.assertEqual(updated.id, org.id)
        self.assertEqual(updated.organization_name, 'BG010_UPDATED')
        self.assertEqual(updated.work_start_time, time(8, 0))
        self.assertEqual(updated.work_end_time, time(16, 0))
        self.assertEqual(updated.working_hours, 8.0)

    def test_update_classification(self):
        """Test updating M2M classifications"""
        org = Organization.objects.create(
            organization_name='BG011',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Update organization type
        dto = OrganizationUpdateDTO(
            organization_id=org.id,
            organization_type_id=self.org_type_sales.id
        )

        updated = OrganizationService.update(self.user, dto)

        self.assertEqual(updated.organization_type.id, self.org_type_sales.id)

    def test_update_not_found(self):
        """Test update fails for non-existent organization"""
        dto = OrganizationUpdateDTO(
            organization_id=99999,
            organization_name='SOME_NAME'
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationService.update(self.user, dto)

        error_str = str(context.exception)
        self.assertTrue('no active organization found' in error_str.lower())

    def test_deactivate_organization_success(self):
        """Test successful organization deactivation"""
        org = Organization.objects.create(
            organization_name='BG012',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = OrganizationService.deactivate(self.user, org.id)

        self.assertEqual(deactivated.id, org.id)
        self.assertIsNotNone(deactivated.effective_end_date)
        # VersionedMixin.deactivate() defaults to yesterday (so inactive today)
        self.assertEqual(deactivated.effective_end_date, date.today() - timedelta(days=1))

        # Verify not in active queryset (inactive today)
        active_orgs = Organization.objects.active_on(date.today())
        self.assertNotIn(org.id, active_orgs.values_list('id', flat=True))

    def test_deactivate_with_future_end_date(self):
        """Test deactivation with future end date"""
        from datetime import timedelta
        org = Organization.objects.create(
            organization_name='BG013',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        future_date = date.today() + timedelta(days=30)
        deactivated = OrganizationService.deactivate(self.user, org.id, future_date)

        self.assertEqual(deactivated.effective_end_date, future_date)

        # Should still be active today
        active_today = Organization.objects.active_on(date.today()).filter(id=org.id).exists()
        self.assertTrue(active_today)

    def test_deactivate_not_found(self):
        """Test deactivation fails for non-existent organization"""
        with self.assertRaises(ValidationError) as context:
            OrganizationService.deactivate(self.user, 99999)

        error_str = str(context.exception)
        self.assertTrue('no active organization found' in error_str.lower())

    def test_get_business_groups(self):
        """Test retrieving all root business groups"""
        # Create multiple business groups
        bg1 = Organization.objects.create(
            organization_name='BG014',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        bg2 = Organization.objects.create(
            organization_name='BG015',
            organization_type=self.org_type_it,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create child (should not be returned)
        child = Organization.objects.create(
            organization_name='DEPT005',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=bg1,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        business_groups = OrganizationService.get_business_groups()

        names = [bg.organization_name for bg in business_groups]
        self.assertIn('BG014', names)
        self.assertIn('BG015', names)
        self.assertNotIn('DEPT005', names)

    def test_get_children_success(self):
        """Test retrieving child organizations"""
        # Create business group
        bg = Organization.objects.create(
            organization_name='BG016',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create children
        child1 = Organization.objects.create(
            organization_name='DEPT006',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        child2 = Organization.objects.create(
            organization_name='DEPT007',
            organization_type=self.org_type_it,
            location=self.location,
            business_group=bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        children = OrganizationService.get_children(bg.id)

        names = [org.organization_name for org in children]
        self.assertEqual(len(names), 2)
        self.assertIn('DEPT006', names)
        self.assertIn('DEPT007', names)

    def test_get_organization_hierarchy(self):
        """Test retrieving organization hierarchy structure"""
        # Create business group
        bg = Organization.objects.create(
            organization_name='BG017',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create children
        child1 = Organization.objects.create(
            organization_name='DEPT008',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        hierarchy = OrganizationService.get_organization_hierarchy(bg.id)

        self.assertEqual(hierarchy['organization_name'], 'BG017')
        self.assertTrue(hierarchy['is_business_group'])
        self.assertEqual(hierarchy['hierarchy_level'], 0)
        self.assertEqual(len(hierarchy['children']), 1)
        self.assertEqual(hierarchy['children'][0]['organization_name'], 'DEPT008')

    def test_computed_property_working_hours(self):
        """Test working_hours computed property"""
        org = Organization.objects.create(
            organization_name='BG018',
            organization_type=self.org_type_hq,
            location=self.location,
            work_start_time=time(9, 0),
            work_end_time=time(17, 30),
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        self.assertEqual(org.working_hours, 8.5)

    def test_computed_property_hierarchy_level(self):
        """Test hierarchy_level computed property"""
        bg = Organization.objects.create(
            organization_name='BG019',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        child = Organization.objects.create(
            organization_name='DEPT009',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        self.assertEqual(bg.hierarchy_level, 0)
        self.assertEqual(child.hierarchy_level, 1)

    def test_get_root_business_group(self):
        """Test get_root_business_group method"""
        bg = Organization.objects.create(
            organization_name='BG020',
            organization_type=self.org_type_hq,
            location=self.location,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        child = Organization.objects.create(
            organization_name='DEPT010',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=bg,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Root of BG is itself
        self.assertEqual(bg.get_root_business_group().id, bg.id)

        # Root of child is BG
        self.assertEqual(child.get_root_business_group().id, bg.id)

