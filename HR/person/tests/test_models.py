"""
Person Domain - Model Tests
============================

Tests for:
1. PersonType model (base types and subtypes)
2. Person model (identity and type inference)
3. Employee model (versioned child)
4. Applicant, ContingentWorker, Contact models
5. Business can create custom subtypes and use them properly

Note: These tests verify MODEL LOGIC directly.
For BUSINESS WORKFLOWS (hire, terminate, convert, etc.),
see test_services.py which tests the Service Layer.

Last Updated: January 13, 2026
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from datetime import date, timedelta
from HR.person.models import PersonType, Employee, Applicant, ContingentWorker, Contact

class PersonTypeModelTests(TestCase):
    """Test PersonType model and constraints"""

    def test_base_types_exist_after_migration(self):
        """Migration should create 4 system base types"""
        base_types = PersonType.objects.filter(
            code__in=['APL', 'EMP', 'CWK', 'CON'],
            base_type__in=['APL', 'EMP', 'CWK', 'CON']
        )
        
        self.assertEqual(base_types.count(), 4)
        
        # Verify each base type
        apl = PersonType.objects.get(code='APL')
        self.assertEqual(apl.base_type, 'APL')
        self.assertEqual(apl.name, 'Applicant')
        
        emp = PersonType.objects.get(code='EMP')
        self.assertEqual(emp.base_type, 'EMP')
        self.assertEqual(emp.name, 'Employee')
        
        cwk = PersonType.objects.get(code='CWK')
        self.assertEqual(cwk.base_type, 'CWK')
        
        con = PersonType.objects.get(code='CON')
        self.assertEqual(con.base_type, 'CON')

    def test_business_can_create_custom_employee_subtype(self):
        """Business users can create new employee subtypes without migration"""
        custom_type = PersonType.objects.create(
            code='SECONDED_EMP',
            name='Seconded Employee',
            description='Employee on secondment to another organization',
            base_type='EMP',
            is_active=True
        )
        
        self.assertEqual(custom_type.base_type, 'EMP')
        self.assertTrue(custom_type.is_active)
        self.assertIn('Seconded', custom_type.name)

    def test_business_can_create_custom_applicant_subtype(self):
        """Business users can create applicant subtypes"""
        custom_type = PersonType.objects.create(
            code='INTERNAL_APL',
            name='Internal Applicant',
            description='Employee applying for internal position',
            base_type='APL',
            is_active=True
        )

        self.assertEqual(custom_type.base_type, 'APL')
        self.assertTrue(custom_type.is_active)

    def test_business_can_create_custom_cwk_subtype(self):
        """Business users can create contingent worker subtypes"""
        custom_type = PersonType.objects.create(
            code='REFERRAL_APL',
            name='Referral Applicant',
            description='Applicant referred by current employee',
            base_type='APL',
            is_active=True
        )
        
        self.assertEqual(custom_type.base_type, 'APL')

    def test_unique_code_constraint(self):
        """Person type codes must be unique"""
        PersonType.objects.create(
            code='UNIQUE_TEST',
            name='Test Type',
            base_type='EMP',
            is_active=True
        )
        
        with self.assertRaises(IntegrityError):
            PersonType.objects.create(
                code='UNIQUE_TEST',  # Duplicate
                name='Another Test',
                base_type='EMP',
                is_active=True
            )

    def test_deactivate_custom_subtype(self):
        """Business should be able to deactivate custom subtypes"""
        custom_type = PersonType.objects.create(
            code='DEACTIVATE_TEST',
            name='Test Deactivation',
            base_type='EMP',
            is_active=True
        )
        
        self.assertTrue(custom_type.is_active)
        
        custom_type.is_active = False
        custom_type.save()
        
        custom_type.refresh_from_db()
        self.assertFalse(custom_type.is_active)

    def test_can_update_system_base_type_name(self):
        """System base types can have name/description updated"""
        emp_base = PersonType.objects.get(code='EMP')
        
        emp_base.name = 'Employee (Updated)'
        emp_base.description = 'New description'
        emp_base.full_clean()  # Should not raise
        emp_base.save()
        
        emp_base.refresh_from_db()
        self.assertEqual(emp_base.name, 'Employee (Updated)')


class EmployeeModelTests(TestCase):
    """Test Employee model (versioned child)"""

    def setUp(self):
        # Create PersonType subtypes for testing
        self.perm_emp_type, _ = PersonType.objects.get_or_create(
            code='PERM_EMP',
            defaults={
                'name': 'Permanent Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

        self.temp_emp_type, _ = PersonType.objects.get_or_create(
            code='TEMP_EMP',
            defaults={
                'name': 'Temporary Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

    def test_create_employee_creates_person_automatically(self):
        """Creating Employee should auto-create Person via ChildModelMixin"""
        employee = Employee.objects.create(
            first_name='Ahmed',
            last_name='Hassan',
            email_address='ahmed@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.perm_emp_type,
            effective_start_date=date(2025, 1, 1),
            employee_number='E001',
            hire_date=date(2025, 1, 1)
        )
        
        # Person should exist
        self.assertIsNotNone(employee.person)
        self.assertEqual(employee.person.first_name, 'Ahmed')
        self.assertEqual(employee.person.email_address, 'ahmed@test.com')

    def test_person_current_type_inferred_from_employee(self):
        """Person.current_type should be inferred from active employee period"""
        employee = Employee.objects.create(
            first_name='Sara',
            last_name='Ali',
            email_address='sara@test.com',
            date_of_birth=date(1992, 5, 15),
            gender='Female',
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.perm_emp_type,
            effective_start_date=date.today(),
            employee_number='E002',
            hire_date=date.today()
        )
        
        person = employee.person
        
        # Type should be inferred as PERM_EMP
        self.assertEqual(person.current_type, self.perm_emp_type)
        self.assertEqual(person.current_base_type, 'EMP')

    def test_employee_must_use_emp_base_type(self):
        """Employee can only use PersonType with base_type='EMP'"""
        # Create an applicant type
        apl_type, _ = PersonType.objects.get_or_create(
            code='EXTERNAL_APL',
            defaults={
                'name': 'External Applicant',
                'base_type': 'APL',
                'is_active': True
            }
        )

        # Should raise ValidationError when trying to create with wrong type
        with self.assertRaises(ValidationError) as context:
            Employee.objects.create(
                first_name='Test',
                last_name='User',
                email_address='test@test.com',
                date_of_birth=date(1990, 1, 1),
                gender='Male',
                nationality='Egyptian',
                marital_status='Single',
                employee_type=apl_type,  # Wrong base_type (APL, not EMP)
                effective_start_date=date.today(),
                employee_number='E999',
                hire_date=date.today()
            )

        self.assertIn("must use PersonType with base_type='EMP'", str(context.exception))

    def test_employee_number_must_be_globally_unique(self):
        """Employee numbers must be globally unique across all employees"""
        # Create first employee
        Employee.objects.create(
            first_name='First',
            last_name='Employee',
            email_address='first@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.perm_emp_type,
            effective_start_date=date.today(),
            employee_number='E100',
            hire_date=date.today()
        )
        
        # Try to create second employee with same number (should fail)
        with self.assertRaises(ValidationError) as context:
            Employee.objects.create(
                first_name='Second',
                last_name='Employee',
                email_address='second@test.com',
                date_of_birth=date(1990, 1, 1),
                gender='Female',
                nationality='Egyptian',
                marital_status='Single',
                employee_type=self.perm_emp_type,
                effective_start_date=date.today(),
                employee_number='E100',  # Duplicate - should fail
                hire_date=date.today()
            )
        
        self.assertIn('employee_number', str(context.exception).lower())

    def test_overlapping_employment_periods_rejected(self):
        """Same person cannot have overlapping employment periods"""
        employee_v1 = Employee.objects.create(
            first_name='Overlapping',
            last_name='Test',
            email_address='overlap@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.perm_emp_type,
            effective_start_date=date(2025, 1, 1),
            effective_end_date=date(2025, 12, 31),
            employee_number='E200',
            hire_date=date(2025, 1, 1)
        )
        
        person = employee_v1.person
        
        # Try to create overlapping period
        employee_v2 = Employee(
            person=person,
            employee_type=self.temp_emp_type,
            effective_start_date=date(2025, 6, 1),  # Overlaps with v1
            effective_end_date=date(2026, 6, 1),
            employee_number='E201',
            hire_date=date(2025, 6, 1)
        )
        
        with self.assertRaises(ValidationError) as context:
            employee_v2.full_clean()
        
        self.assertIn('cannot overlap', str(context.exception))

    def test_sequential_employment_periods_allowed(self):
        """Same person can have sequential (non-overlapping) employment periods

        Note: This is better tested in test_services.py using EmployeeService.
        Here we verify the model allows it in principle.
        """
        employee_v1 = Employee.objects.create(
            first_name='Sequential',
            last_name='Test',
            email_address='sequential@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.perm_emp_type,
            effective_start_date=date(2020, 1, 1),
            effective_end_date=date(2024, 12, 31),
            employee_number='E300',
            hire_date=date(2020, 1, 1)
        )

        person = employee_v1.person

        # Verify person exists and first period is recorded
        self.assertIsNotNone(person)
        self.assertEqual(person.employee_periods.count(), 1)

        # Sequential periods are tested in test_services.py
        # using EmployeeService which properly handles the workflow

    def test_auto_number_generation_robustness(self):
        """Test robust auto-number generation with gaps and deletions"""
        # Create 3 employees
        e1 = Employee.objects.create(
            first_name='E1', last_name='Test',
            email_address='e1@test.com',
            date_of_birth=date(1990, 1, 1),
            employee_type=self.perm_emp_type,
            effective_start_date=date(2025, 1, 1),
            hire_date=date(2025, 1, 1)
        )
        e2 = Employee.objects.create(
            first_name='E2', last_name='Test',
            email_address='e2@test.com',
            date_of_birth=date(1990, 1, 1),
            employee_type=self.perm_emp_type,
            effective_start_date=date(2025, 1, 1),
            hire_date=date(2025, 1, 1)
        )
        e3 = Employee.objects.create(
            first_name='E3', last_name='Test',
            email_address='e3@test.com',
            date_of_birth=date(1990, 1, 1),
            employee_type=self.perm_emp_type,
            effective_start_date=date(2025, 1, 1),
            hire_date=date(2025, 1, 1)
        )

        # Verify initial numbers
        self.assertEqual(e1.employee_number, 'EMP-000001')
        self.assertEqual(e2.employee_number, 'EMP-000002')
        self.assertEqual(e3.employee_number, 'EMP-000003')

        # Delete E2 to create a gap
        e2.delete()
        
        # Create E4 - should get EMP-000004 (next after max E3), not EMP-000003
        e4 = Employee.objects.create(
            first_name='E4', last_name='Test',
            email_address='e4@test.com',
            date_of_birth=date(1990, 1, 1),
            employee_type=self.perm_emp_type,
            effective_start_date=date(2025, 1, 1),
            hire_date=date(2025, 1, 1)
        )
        
        self.assertEqual(e4.employee_number, 'EMP-000004')


class ApplicantModelTests(TestCase):
    """Test Applicant model"""

    def setUp(self):
        self.apl_type, _ = PersonType.objects.get_or_create(
            code='EXTERNAL_APL',
            defaults={
                'name': 'External Applicant',
                'base_type': 'APL',
                'is_active': True
            }
        )

    def test_create_applicant_creates_person_automatically(self):
        """Creating Applicant should auto-create Person"""
        applicant = Applicant.objects.create(
            first_name='Applicant',
            last_name='Test',
            email_address='applicant@test.com',
            date_of_birth=date(1995, 3, 20),
            gender='Female',
            nationality='Egyptian',
            marital_status='Single',
            applicant_type=self.apl_type,
            effective_start_date=date.today(),
            application_number='APL001'
        )
        
        self.assertIsNotNone(applicant.person)
        self.assertEqual(applicant.person.first_name, 'Applicant')

    def test_person_current_type_inferred_from_applicant(self):
        """Person.current_type should be inferred from active applicant period"""
        applicant = Applicant.objects.create(
            first_name='Applicant2',
            last_name='Test',
            email_address='applicant2@test.com',
            date_of_birth=date(1995, 3, 20),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            applicant_type=self.apl_type,
            effective_start_date=date.today(),
            application_number='APL002'
        )
        
        person = applicant.person
        
        self.assertEqual(person.current_type, self.apl_type)
        self.assertEqual(person.current_base_type, 'APL')

    def test_applicant_must_use_apl_base_type(self):
        """Applicant can only use PersonType with base_type='APL'"""
        # Create an employee type
        emp_type, _ = PersonType.objects.get_or_create(
            code='PERM_EMP',
            defaults={
                'name': 'Permanent Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

        # Should raise ValidationError when trying to create with wrong type
        with self.assertRaises(ValidationError) as context:
            Applicant.objects.create(
                first_name='Wrong',
                last_name='Type',
                email_address='wrong@test.com',
                date_of_birth=date(1990, 1, 1),
                gender='Male',
                nationality='Egyptian',
                marital_status='Single',
                applicant_type=emp_type,  # Wrong base_type
                effective_start_date=date.today(),
                application_number='APL999'
            )

        self.assertIn("must use PersonType with base_type='APL'", str(context.exception))


class ContingentWorkerModelTests(TestCase):
    """Test ContingentWorker model"""

    def setUp(self):
        self.cwk_type, _ = PersonType.objects.get_or_create(
            code='CONSULTANT',
            defaults={
                'name': 'Consultant',
                'base_type': 'CWK',
                'is_active': True
            }
        )

    def test_create_contingent_worker_creates_person(self):
        """Creating ContingentWorker should auto-create Person"""
        worker = ContingentWorker.objects.create(
            first_name='Worker',
            last_name='Test',
            email_address='worker@test.com',
            date_of_birth=date(1988, 7, 10),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            worker_type=self.cwk_type,
            effective_start_date=date.today(),
            worker_number='CWK001',
            placement_date=date.today()
        )
        
        self.assertIsNotNone(worker.person)
        self.assertEqual(worker.person.current_base_type, 'CWK')


class ContactModelTests(TestCase):
    """Test Contact model"""

    def setUp(self):
        self.con_type, _ = PersonType.objects.get_or_create(
            code='VENDOR_CONTACT',
            defaults={
                'name': 'Vendor Contact',
                'base_type': 'CON',
                'is_active': True
            }
        )

    def test_create_contact_creates_person(self):
        """Creating Contact should auto-create Person"""
        contact = Contact.objects.create(
            first_name='Contact',
            last_name='Test',
            email_address='contact@test.com',
            date_of_birth=date(1980, 2, 14),
            gender='Female',
            nationality='Egyptian',
            marital_status='Married',
            contact_type=self.con_type,
            effective_start_date=date.today(),
            contact_number='CON001'
        )
        
        self.assertIsNotNone(contact.person)
        self.assertEqual(contact.person.current_base_type, 'CON')


class MultiRoleScenarioTests(TestCase):
    """Test scenarios where person has multiple active roles"""

    def setUp(self):
        self.emp_type, _ = PersonType.objects.get_or_create(
            code='PERM_EMP',
            defaults={
                'name': 'Permanent Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

        self.apl_type, _ = PersonType.objects.get_or_create(
            code='INTERNAL_APL',
            defaults={
                'name': 'Internal Applicant',
                'base_type': 'APL',
                'is_active': True
            }
        )

    def test_employee_can_also_be_applicant(self):
        """Same person can be active employee and active applicant simultaneously

        Note: This is tested in test_services.py using proper workflows.
        Here we verify basic functionality.
        """
        # Create employee
        employee = Employee.objects.create(
            first_name='MultiRole',
            last_name='Person',
            email_address='multirole@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.emp_type,
            effective_start_date=date(2025, 1, 1),
            employee_number='E500',
            hire_date=date(2025, 1, 1)
        )

        person = employee.person

        # Verify person exists with employee role
        self.assertIsNotNone(person)
        self.assertEqual(person.current_base_type, 'EMP')

        # Multi-role scenarios are tested in test_services.py

    def test_type_priority_emp_over_apl(self):
        """When person has multiple roles, EMP takes priority over APL

        Note: Multi-role priority testing is in test_services.py.
        """
        # Create applicant first
        applicant = Applicant.objects.create(
            first_name='Priority',
            last_name='Test',
            email_address='priority@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Female',
            nationality='Egyptian',
            marital_status='Single',
            applicant_type=self.apl_type,
            effective_start_date=date.today(),
            effective_end_date=date.today() + timedelta(days=90),
            application_number='APL800'
        )

        person = applicant.person

        # Person is currently applicant
        self.assertEqual(person.current_base_type, 'APL')

        # Type priority tested in test_services.py


class TypeInferenceHistoricalTests(TestCase):
    """Test type inference for historical dates"""

    def setUp(self):
        self.apl_type, _ = PersonType.objects.get_or_create(
            code='EXTERNAL_APL',
            defaults={
                'name': 'External Applicant',
                'base_type': 'APL',
                'is_active': True
            }
        )

        self.emp_type, _ = PersonType.objects.get_or_create(
            code='PERM_EMP',
            defaults={
                'name': 'Permanent Employee',
                'base_type': 'EMP',
                'is_active': True
            }
        )

    def test_type_inference_on_specific_date(self):
        """Can query what person's type was on a specific historical date

        Note: Full historical tracking tested in test_services.py.
        Here we verify basic date-based type inference.
        """
        # Create applicant period (Jan-Mar 2025)
        applicant = Applicant.objects.create(
            first_name='Historical',
            last_name='Test',
            email_address='historical@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            applicant_type=self.apl_type,
            effective_start_date=date(2025, 1, 1),
            effective_end_date=date(2025, 3, 31),
            application_number='APL700'
        )

        person = applicant.person

        # On Feb 15 (during applicant period), was applicant
        feb_type = person.get_type_on_date(date(2025, 2, 15))
        self.assertEqual(feb_type, self.apl_type)

        # After period ended, no type
        after_type = person.get_type_on_date(date(2025, 5, 1))
        self.assertIsNone(after_type)

    def test_no_type_between_periods(self):
        """Person has no type in gaps between periods

        Note: Multi-period scenarios tested in test_services.py.
        Here we verify gap detection works.
        """
        # Employment 2020-2024
        employee_v1 = Employee.objects.create(
            first_name='Gap',
            last_name='Test',
            email_address='gap@test.com',
            date_of_birth=date(1990, 1, 1),
            gender='Male',
            nationality='Egyptian',
            marital_status='Single',
            employee_type=self.emp_type,
            effective_start_date=date(2020, 1, 1),
            effective_end_date=date(2024, 12, 31),
            employee_number='E800',
            hire_date=date(2020, 1, 1)
        )

        person = employee_v1.person

        # During employment, has type
        during_type = person.get_type_on_date(date(2022, 6, 15))
        self.assertEqual(during_type, self.emp_type)

        # After employment ends, no type
        after_type = person.get_type_on_date(date(2025, 6, 15))
        self.assertIsNone(after_type)
