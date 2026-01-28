"""
Tests for PersonType DFF (Descriptive Flexfield) Implementation

Tests that business users can configure custom fields for person subtypes,
and those fields are stored on the actual employee/applicant/worker/contact records.

Architecture:
- PersonTypeDFFConfig: Configuration (which fields exist for which type)
- Employee/Applicant/ContingentWorker/Contact: Data storage (DFFMixin provides 30 columns)
- PersonTypeDFFService: Service layer for CRUD operations
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

from HR.person.models import PersonType, PersonTypeDFFConfig, Employee, Applicant
from HR.person.services.dff_service import PersonTypeDFFService


# No setUpModule needed - tests create their own data


class PersonTypeDFFConfigTests(TestCase):
    """Test PersonTypeDFFConfig model"""

    def setUp(self):
        """Create person types for testing"""
        self.seconded_emp, _ = PersonType.objects.get_or_create(
            code='SECONDED_EMP',
            defaults={
                'name': 'Seconded Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

        self.temp_worker, _ = PersonType.objects.get_or_create(
            code='TEMP_WORKER',
            defaults={
                'name': 'Temporary Worker',
                'base_type': 'CWK',
                'is_active': True
            }
        )

    def test_create_text_field_config(self):
        """Business can configure a custom text field for a person type"""
        config = PersonTypeDFFConfig.objects.create(
            person_type=self.seconded_emp,
            field_name='home_organization',
            field_label='Home Organization',
            help_text='The organization where employee is permanently assigned',
            column_name='dff_char1',
            data_type='char',
            sequence=1,
            required=True,
            max_length=100
        )

        self.assertEqual(config.field_name, 'home_organization')
        self.assertEqual(config.data_type, 'char')
        self.assertTrue(config.required)

    def test_same_physical_column_different_types(self):
        """Same physical column can store different logical fields for different types"""
        # Seconded employee uses dff_char1 for home_organisation
        config1 = PersonTypeDFFConfig.objects.create(
            person_type=self.seconded_emp,
            field_name='home_organization',
            field_label='Home Organization',
            column_name='dff_char1',
            data_type='char',
            sequence=1
        )

        # Temp worker uses dff_char1 for agency_name
        config2 = PersonTypeDFFConfig.objects.create(
            person_type=self.temp_worker,
            field_name='agency_name',
            field_label='Agency Name',
            column_name='dff_char1',
            data_type='char',
            sequence=1
        )

        self.assertEqual(config1.column_name, config2.column_name)
        self.assertNotEqual(config1.field_name, config2.field_name)

    def test_validation_char_column_must_match_type(self):
        """Text fields must use dff_char columns"""
        config = PersonTypeDFFConfig(
            person_type=self.seconded_emp,
            field_name='test_field',
            field_label='Test Field',
            column_name='dff_date1',  # Wrong! Using date column for text
            data_type='char',
            sequence=1
        )

        with self.assertRaises(ValidationError) as context:
            config.full_clean()

        self.assertIn('column_name', context.exception.message_dict)


class EmployeeDFFIntegrationTests(TestCase):
    """Integration tests for DFF on Employee records"""

    def setUp(self):
        """Create employee types and configure DFF fields"""
        # Create seconded employee type
        self.seconded_emp_type, _ = PersonType.objects.get_or_create(
            code='SECONDED_EMP',
            defaults={
                'name': 'Seconded Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

        # Configure DFF fields for seconded employees
        PersonTypeDFFConfig.objects.create(
            person_type=self.seconded_emp_type,
            field_name='home_organization',
            field_label='Home Organization',
            column_name='dff_char1',
            data_type='char',
            sequence=1,
            required=True,
            max_length=100
        )

        PersonTypeDFFConfig.objects.create(
            person_type=self.seconded_emp_type,
            field_name='host_organization',
            field_label='Host Organization',
            column_name='dff_char2',
            data_type='char',
            sequence=2,
            required=False
        )

        PersonTypeDFFConfig.objects.create(
            person_type=self.seconded_emp_type,
            field_name='secondment_end_date',
            field_label='Secondment End Date',
            column_name='dff_date1',
            data_type='date',
            sequence=3,
            required=False
        )

    def test_employee_can_store_dff_data(self):
        """Employee records can store custom fields based on their type"""
        # Create a seconded employee
        employee = Employee.objects.create(
            first_name='Ahmed',
            last_name='Hassan',
            email_address='ahmed.hassan@example.com',
            date_of_birth=date(1990, 1, 1),
            employee_type=self.seconded_emp_type,
            employee_number='E001',
            hire_date=date(2025, 1, 1),
            effective_start_date=date(2025, 1, 1)
        )

        # Set DFF data
        dff_data = {
            'home_organization': 'Cairo Office',
            'host_organization': 'Dubai Office',
            'secondment_end_date': date(2026, 12, 31)
        }

        PersonTypeDFFService.set_dff_data(employee, 'employee_type', dff_data)
        employee.save()

        # Retrieve and verify
        employee = Employee.objects.get(pk=employee.pk)
        retrieved_data = PersonTypeDFFService.get_dff_data(employee, 'employee_type')

        self.assertEqual(retrieved_data['home_organization'], 'Cairo Office')
        self.assertEqual(retrieved_data['host_organization'], 'Dubai Office')
        self.assertEqual(retrieved_data['secondment_end_date'], date(2026, 12, 31))

        # Verify physical storage
        self.assertEqual(employee.dff_char1, 'Cairo Office')
        self.assertEqual(employee.dff_char2, 'Dubai Office')
        self.assertEqual(employee.dff_date1, date(2026, 12, 31))

    def test_different_employees_same_type_independent_data(self):
        """Different employees of same type have independent DFF data"""
        # Create first employee
        emp1 = Employee.objects.create(
            first_name='Ahmed',
            last_name='Hassan',
            email_address='ahmed@example.com',
            date_of_birth=date(1990, 1, 1),
            employee_type=self.seconded_emp_type,
            employee_number='E001',
            hire_date=date(2025, 1, 1),
            effective_start_date=date(2025, 1, 1)
        )

        PersonTypeDFFService.set_dff_data(emp1, 'employee_type', {
            'home_organization': 'Cairo Office',
            'secondment_end_date': date(2026, 6, 30)
        })
        emp1.save()

        # Create second employee
        emp2 = Employee.objects.create(
            first_name='Sara',
            last_name='Ali',
            email_address='sara@example.com',
            date_of_birth=date(1992, 5, 15),
            employee_type=self.seconded_emp_type,
            employee_number='E002',
            hire_date=date(2025, 2, 1),
            effective_start_date=date(2025, 2, 1)
        )

        PersonTypeDFFService.set_dff_data(emp2, 'employee_type', {
            'home_organization': 'Alexandria Office',
            'secondment_end_date': date(2026, 12, 31)
        })
        emp2.save()

        # Verify independent data
        emp1_data = PersonTypeDFFService.get_dff_data(
            Employee.objects.get(pk=emp1.pk),
            'employee_type'
        )
        emp2_data = PersonTypeDFFService.get_dff_data(
            Employee.objects.get(pk=emp2.pk),
            'employee_type'
        )

        self.assertEqual(emp1_data['home_organization'], 'Cairo Office')
        self.assertEqual(emp2_data['home_organization'], 'Alexandria Office')
        self.assertNotEqual(emp1_data['secondment_end_date'], emp2_data['secondment_end_date'])

    def test_validation_required_field(self):
        """Required DFF fields are validated"""
        employee = Employee.objects.create(
            first_name='Test',
            last_name='User',
            email_address='test@example.com',
            date_of_birth=date(1990, 1, 1),
            employee_type=self.seconded_emp_type,
            employee_number='E999',
            hire_date=date(2025, 1, 1),
            effective_start_date=date(2025, 1, 1)
        )

        # Missing required field 'home_organisation'
        dff_data = {
            'secondment_end_date': date(2026, 12, 31)
        }

        with self.assertRaises(ValidationError) as context:
            PersonTypeDFFService.set_dff_data(employee, 'employee_type', dff_data)

        self.assertIn('home_organization', str(context.exception))


class ApplicantDFFIntegrationTests(TestCase):
    """Integration tests for DFF on Applicant records"""

    def setUp(self):
        """Create applicant type and configure DFF fields"""
        self.internal_applicant_type, _ = PersonType.objects.get_or_create(
            code='INTERNAL_APL',
            defaults={
                'name': 'Internal Applicant',
                'base_type': 'APL',
                'is_active': True
            }
        )

        # Configure DFF fields for internal applicants
        PersonTypeDFFConfig.objects.create(
            person_type=self.internal_applicant_type,
            field_name='current_department',
            field_label='Current Department',
            column_name='dff_char1',
            data_type='char',
            sequence=1,
            required=True
        )

        PersonTypeDFFConfig.objects.create(
            person_type=self.internal_applicant_type,
            field_name='years_of_service',
            field_label='Years of Service',
            column_name='dff_number1',
            data_type='number',
            sequence=2,
            required=False,
            min_value=Decimal('0'),
            max_value=Decimal('50')
        )

    def test_applicant_can_store_dff_data(self):
        """Applicant records can store custom fields based on their type"""
        applicant = Applicant.objects.create(
            first_name='Mohamed',
            last_name='Ali',
            email_address='mohamed@example.com',
            date_of_birth=date(1995, 3, 20),
            applicant_type=self.internal_applicant_type,
            application_number='APL001',
            effective_start_date=date(2025, 1, 15),
            application_status='PENDING'
        )

        # Set DFF data
        dff_data = {
            'current_department': 'Engineering',
            'years_of_service': Decimal('5.5')
        }

        PersonTypeDFFService.set_dff_data(applicant, 'applicant_type', dff_data)
        applicant.save()

        # Retrieve and verify
        applicant = Applicant.objects.get(pk=applicant.pk)
        retrieved_data = PersonTypeDFFService.get_dff_data(applicant, 'applicant_type')

        self.assertEqual(retrieved_data['current_department'], 'Engineering')
        self.assertEqual(retrieved_data['years_of_service'], Decimal('5.5'))


class MultiTypeDFFTests(TestCase):
    """Test that same physical columns work for different types"""

    def setUp(self):
        """Create multiple person types using same physical columns"""
        self.perm_emp_type, _ = PersonType.objects.get_or_create(
            code='PERM_EMP',
            defaults={'name': 'Permanent Employee', 'base_type': 'EMP', 'is_active': True}
        )

        self.temp_emp_type, _ = PersonType.objects.get_or_create(
            code='TEMP_EMP',
            defaults={'name': 'Temporary Employee', 'base_type': 'EMP', 'is_active': True}
        )

        # Both types use dff_char1, but for different purposes
        PersonTypeDFFConfig.objects.create(
            person_type=self.perm_emp_type,
            field_name='pension_fund',
            field_label='Pension Fund',
            column_name='dff_char1',
            data_type='char',
            sequence=1
        )

        PersonTypeDFFConfig.objects.create(
            person_type=self.temp_emp_type,
            field_name='agency_name',
            field_label='Staffing Agency',
            column_name='dff_char1',
            data_type='char',
            sequence=1
        )

    def test_same_column_different_meaning_per_type(self):
        """Same physical column stores different logical fields per type"""
        # Create permanent employee
        perm_emp = Employee.objects.create(
            first_name='Permanent',
            last_name='Employee',
            email_address='perm@example.com',
            date_of_birth=date(1985, 6, 10),
            employee_type=self.perm_emp_type,
            employee_number='E100',
            hire_date=date(2025, 1, 1),
            effective_start_date=date(2025, 1, 1)
        )

        PersonTypeDFFService.set_dff_data(perm_emp, 'employee_type', {
            'pension_fund': 'National Pension Fund'
        })
        perm_emp.save()

        # Create temporary employee
        temp_emp = Employee.objects.create(
            first_name='Temporary',
            last_name='Employee',
            email_address='temp@example.com',
            date_of_birth=date(1992, 8, 15),
            employee_type=self.temp_emp_type,
            employee_number='E101',
            hire_date=date(2025, 1, 1),
            effective_start_date=date(2025, 1, 1)
        )

        PersonTypeDFFService.set_dff_data(temp_emp, 'employee_type', {
            'agency_name': 'QuickStaff Agency'
        })
        temp_emp.save()

        # Both use dff_char1 but for different purposes
        perm_emp = Employee.objects.get(pk=perm_emp.pk)
        temp_emp = Employee.objects.get(pk=temp_emp.pk)

        self.assertEqual(perm_emp.dff_char1, 'National Pension Fund')
        self.assertEqual(temp_emp.dff_char1, 'QuickStaff Agency')

        # Verify logical field names differ
        perm_data = PersonTypeDFFService.get_dff_data(perm_emp, 'employee_type')
        temp_data = PersonTypeDFFService.get_dff_data(temp_emp, 'employee_type')

        self.assertIn('pension_fund', perm_data)
        self.assertIn('agency_name', temp_data)
        self.assertNotIn('agency_name', perm_data)
        self.assertNotIn('pension_fund', temp_data)

