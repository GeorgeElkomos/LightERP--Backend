"""
Unit tests for OrganizationManager Service
Tests manager assignment operations, overlap prevention, and business logic validations
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta

from HR.work_structures.models import OrganizationManager, Organization, Location
from HR.work_structures.services.organization_manager_service import OrganizationManagerService
from HR.work_structures.dtos import OrganizationManagerCreateDTO, OrganizationManagerUpdateDTO
from HR.person.models import Person, Employee, PersonType
from core.lookups.models import LookupType, LookupValue

User = get_user_model()


class OrganizationManagerServiceTest(TestCase):
    """Test OrganizationManagerService business logic"""

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
        country_type = LookupType.objects.create(name='Country')
        city_type = LookupType.objects.create(name='City')

        # Create lookups
        cls.org_type_hq = LookupValue.objects.create(
            lookup_type=org_type_lookup, name='Business Group', is_active=True
        )
        cls.org_type_sales = LookupValue.objects.create(
            lookup_type=org_type_lookup, name='Sales Department', is_active=True
        )
        cls.country = LookupValue.objects.create(
            lookup_type=country_type, name='Egypt', is_active=True
        )
        cls.city = LookupValue.objects.create(
            lookup_type=city_type, name='Cairo', parent=cls.country, is_active=True
        )

        # Create root organization (for location)
        cls.root_org_for_location = Organization.objects.create(
            organization_name='ROOT_SETUP',
            organization_type=cls.org_type_hq,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create location
        cls.location = Location.objects.create(
            business_group=cls.root_org_for_location,
            location_name='Cairo Office',
            country=cls.country,
            city=cls.city,
            street='Test Street',
            created_by=cls.user,
            updated_by=cls.user
        )

        # Update root org with location
        Organization.objects.filter(pk=cls.root_org_for_location.pk).update(location=cls.location)
        cls.root_org_for_location.refresh_from_db()

        # Create business group
        cls.business_group = Organization.objects.create(
            organization_name='BG001',
            organization_type=cls.org_type_hq,
            location=cls.location,
            business_group=None,  # Root
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create department (child organization)
        cls.department = Organization.objects.create(
            organization_name='DEPT001',
            organization_type=cls.org_type_sales,
            location=cls.location,
            business_group=cls.business_group,
            effective_start_date=date.today(),
            created_by=cls.user,
            updated_by=cls.user
        )

        # Create person type for employee
        cls.person_type = PersonType.objects.create(
            code='PERM_EMP',
            name='Permanent Employee',
            base_type='EMP'
        )

        # Create employee (creates person automatically)
        cls.employee = Employee.objects.create(
            first_name='John',
            last_name='Manager',
            email_address='john.manager@test.com',
            gender='Male',
            date_of_birth=date(1985, 1, 1),
            nationality='Egyptian',
            marital_status='Single',
            employee_type=cls.person_type,
            effective_start_date=date.today(),
            hire_date=date.today(),
            employee_number='E001',
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.person = cls.employee.person

        # Create second employee for testing
        cls.employee2 = Employee.objects.create(
            first_name='Jane',
            last_name='Manager',
            email_address='jane.manager@test.com',
            gender='Female',
            date_of_birth=date(1987, 1, 1),
            nationality='Egyptian',
            marital_status='Single',
            employee_type=cls.person_type,
            effective_start_date=date.today(),
            hire_date=date.today(),
            employee_number='E002',
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.person2 = cls.employee2.person

        # Create terminated employee (no longer active) for testing
        cls.terminated_employee = Employee.objects.create(
            first_name='Bob',
            last_name='Terminated',
            email_address='bob.terminated@test.com',
            gender='Male',
            date_of_birth=date(1990, 1, 1),
            nationality='Egyptian',
            marital_status='Single',
            employee_type=cls.person_type,
            effective_start_date=date.today() - timedelta(days=365),
            effective_end_date=date.today() - timedelta(days=100),  # Terminated
            hire_date=date.today() - timedelta(days=365),
            employee_number='E003',
            created_by=cls.user,
            updated_by=cls.user
        )
        cls.terminated_person = cls.terminated_employee.person

    def test_create_manager_assignment_success(self):
        """Test successful manager assignment creation"""
        dto = OrganizationManagerCreateDTO(
            organization_id=self.department.id,
            person_id=self.person.id,
            effective_start_date=date.today()
        )

        assignment = OrganizationManagerService.create(self.user, dto)

        self.assertIsNotNone(assignment.id)
        self.assertEqual(assignment.organization.id, self.department.id)
        self.assertEqual(assignment.person.id, self.person.id)
        self.assertEqual(assignment.business_group.id, self.business_group.id)
        self.assertEqual(assignment.effective_start_date, date.today())
        self.assertIsNone(assignment.effective_end_date)

    def test_create_without_business_group(self):
        """Test creating assignment without specifying business_group"""
        dto = OrganizationManagerCreateDTO(
            organization_id=self.department.id,
            person_id=self.person.id,
            effective_start_date=date.today()
        )

        assignment = OrganizationManagerService.create(self.user, dto)

        self.assertIsNotNone(assignment.id)
        # business_group is now a property that returns the root org
        self.assertEqual(assignment.business_group.id, self.business_group.id)

    def test_create_with_end_date(self):
        """Test creating assignment with specified end date"""
        dto = OrganizationManagerCreateDTO(
            organization_id=self.department.id,
            person_id=self.person.id,
            effective_start_date=date.today(),
            effective_end_date=date.today() + timedelta(days=365)
        )

        assignment = OrganizationManagerService.create(self.user, dto)

        self.assertIsNotNone(assignment.effective_end_date)
        self.assertEqual(assignment.effective_end_date, date.today() + timedelta(days=365))

    def test_create_invalid_organization(self):
        """Test creation fails with invalid organization"""
        dto = OrganizationManagerCreateDTO(
            organization_id=99999,
            person_id=self.person.id,
            effective_start_date=date.today()
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationManagerService.create(self.user, dto)

        self.assertIn('organization_id', str(context.exception))

    def test_create_invalid_person(self):
        """Test creation fails with invalid person"""
        dto = OrganizationManagerCreateDTO(
            organization_id=self.department.id,
            person_id=99999,
            effective_start_date=date.today()
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationManagerService.create(self.user, dto)

        self.assertIn('person_id', str(context.exception))

    def test_create_person_not_employee(self):
        """Test creation fails when person is not an active employee"""
        dto = OrganizationManagerCreateDTO(
            organization_id=self.department.id,
            person_id=self.terminated_person.id,  # Terminated employee
            effective_start_date=date.today()
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationManagerService.create(self.user, dto)

        error_msg = str(context.exception).lower()
        self.assertTrue('employee' in error_msg or 'active' in error_msg)

    def test_create_overlapping_assignment_fails(self):
        """Test that overlapping assignments are prevented"""
        # Create first assignment
        OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Try to create overlapping assignment
        dto = OrganizationManagerCreateDTO(
            organization_id=self.department.id,
            person_id=self.person2.id,
            effective_start_date=date.today() + timedelta(days=10)
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationManagerService.create(self.user, dto)

        # VersionedMixin.clean() produces: "Date range overlaps with existing organization_id=X"
        # We just verify that a ValidationError was raised, which confirms overlap detection works
        self.assertIsNotNone(context.exception)

    def test_create_sequential_assignments_allowed(self):
        """Test that sequential (non-overlapping) assignments are allowed"""
        # Create first assignment with end date
        OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            effective_end_date=date.today() + timedelta(days=30),
            created_by=self.user,
            updated_by=self.user
        )

        # Create second assignment starting after first ends
        dto = OrganizationManagerCreateDTO(
            organization_id=self.department.id,
            person_id=self.person2.id,
            effective_start_date=date.today() + timedelta(days=31)
        )

        assignment = OrganizationManagerService.create(self.user, dto)

        self.assertIsNotNone(assignment.id)
        self.assertEqual(assignment.person.id, self.person2.id)

    def test_update_end_assignment(self):
        """Test updating assignment to set end date"""
        assignment = OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        dto = OrganizationManagerUpdateDTO(
            assignment_id=assignment.id,
            effective_end_date=date.today() + timedelta(days=30)
        )

        updated = OrganizationManagerService.update(self.user, dto)

        self.assertEqual(updated.id, assignment.id)
        self.assertEqual(updated.effective_end_date, date.today() + timedelta(days=30))

    def test_update_invalid_end_date(self):
        """Test update fails when end date is before start date"""
        assignment = OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        dto = OrganizationManagerUpdateDTO(
            assignment_id=assignment.id,
            effective_end_date=date.today() - timedelta(days=1)
        )

        with self.assertRaises(ValidationError) as context:
            OrganizationManagerService.update(self.user, dto)

        self.assertIn('end date', str(context.exception).lower())

    def test_deactivate_assignment(self):
        """Test deactivating (ending) an assignment"""
        assignment = OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today() - timedelta(days=10),
            created_by=self.user,
            updated_by=self.user
        )

        deactivated = OrganizationManagerService.deactivate(self.user, assignment.id)

        self.assertEqual(deactivated.id, assignment.id)
        # VersionedMixin.deactivate() defaults to yesterday (so inactive today)
        self.assertEqual(deactivated.effective_end_date, date.today() - timedelta(days=1))

    def test_deactivate_with_future_date(self):
        """Test deactivating assignment with future end date"""
        assignment = OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        future_date = date.today() + timedelta(days=60)
        deactivated = OrganizationManagerService.deactivate(self.user, assignment.id, future_date)

        self.assertEqual(deactivated.effective_end_date, future_date)

    def test_get_current_manager(self):
        """Test retrieving current manager for an organization"""
        assignment = OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        current = OrganizationManagerService.get_current_manager(self.department.id)

        self.assertIsNotNone(current)
        self.assertEqual(current.id, assignment.id)
        self.assertEqual(current.person.id, self.person.id)

    def test_get_current_manager_none(self):
        """Test get_current_manager returns None when no manager assigned"""
        current = OrganizationManagerService.get_current_manager(self.department.id)

        self.assertIsNone(current)

    def test_get_current_manager_ended_assignment(self):
        """Test get_current_manager returns None for ended assignments"""
        OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today() - timedelta(days=60),
            effective_end_date=date.today() - timedelta(days=1),
            created_by=self.user,
            updated_by=self.user
        )

        current = OrganizationManagerService.get_current_manager(self.department.id)

        self.assertIsNone(current)

    def test_get_manager_history(self):
        """Test retrieving all manager assignments for an organization"""
        # Create multiple assignments
        OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today() - timedelta(days=365),
            effective_end_date=date.today() - timedelta(days=180),
            created_by=self.user,
            updated_by=self.user
        )
        OrganizationManager.objects.create(
            organization=self.department,
            person=self.person2,
            effective_start_date=date.today() - timedelta(days=179),
            created_by=self.user,
            updated_by=self.user
        )

        history = OrganizationManagerService.get_manager_history(self.department.id)

        self.assertEqual(history.count(), 2)
        # Should be ordered by start date (newest first)
        self.assertEqual(history[0].person.id, self.person2.id)
        self.assertEqual(history[1].person.id, self.person.id)

    def test_get_organizations_managed_by_person(self):
        """Test retrieving all organizations managed by a person"""
        # Create second department
        dept2 = Organization.objects.create(
            organization_name='DEPT002',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=self.business_group,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Assign person to manage both departments
        OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        OrganizationManager.objects.create(
            organization=dept2,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        managed_orgs = OrganizationManagerService.get_organizations_managed_by_person(self.person.id)

        self.assertEqual(managed_orgs.count(), 2)
        org_ids = [assignment.organization.id for assignment in managed_orgs]
        self.assertIn(self.department.id, org_ids)
        self.assertIn(dept2.id, org_ids)

    def test_get_all_managers_in_business_group(self):
        """Test retrieving all manager assignments within a business group"""
        # Create second department
        dept2 = Organization.objects.create(
            organization_name='DEPT002',
            organization_type=self.org_type_sales,
            location=self.location,
            business_group=self.business_group,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        # Create assignments
        OrganizationManager.objects.create(
            organization=self.department,
            person=self.person,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        OrganizationManager.objects.create(
            organization=dept2,
            person=self.person2,
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )

        managers = OrganizationManagerService.get_all_managers_in_business_group(self.business_group.id)

        self.assertEqual(managers.count(), 2)

