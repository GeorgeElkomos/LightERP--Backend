"""
Person Domain - Service Tests
==============================

Tests for business logic workflows.
All state transitions should go through services.

Tests for:
1. EmployeeService - Hire, terminate, rehire, type conversion
2. ApplicantService - Application lifecycle, status updates
3. ContingentWorkerService - Placement management
4. ContactService - Contact relationships, emergency contacts
5. Integration scenarios - Applicant → Employee transitions

Last Updated: January 13, 2026
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from HR.person.models import PersonType, Employee, Applicant, ContingentWorker, Contact
from HR.person.services import (
    EmployeeService,
    ApplicantService,
    ContingentWorkerService,
    ContactService
)
from core.lookups.models import LookupType


class EmployeeServiceTests(TestCase):
    """Test EmployeeService business logic"""

    def setUp(self):
        # Create common lookups to avoid warnings
        LookupType.objects.get_or_create(name='Probation Period')
        LookupType.objects.get_or_create(name='Termination Notice Period')
        LookupType.objects.get_or_create(name='Payroll')
        LookupType.objects.get_or_create(name='Salary Basis')

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

    def test_hire_direct(self):
        """Can hire employee directly (not from applicant pool)"""
        employee = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Ahmed',
                'last_name': 'Hassan',
                'email_address': 'ahmed@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E001'
            },
            hire_date=date(2025, 1, 1)
        )

        # Employee created
        self.assertIsNotNone(employee)
        self.assertEqual(employee.employee_number, 'E001')
        self.assertEqual(employee.hire_date, date(2025, 1, 1))

        # Person auto-created
        self.assertIsNotNone(employee.person)
        self.assertEqual(employee.person.first_name, 'Ahmed')

        # Person type inferred
        self.assertEqual(employee.person.current_type, self.perm_emp_type)
        self.assertEqual(employee.person.current_base_type, 'EMP')

    def test_hire_direct_existing_person(self):
        """Can hire employee using existing person"""
        # 1. Create initial employee to generate a Person
        emp1 = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Reuse',
                'last_name': 'Me',
                'email_address': 'reuse@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E_OLD'
            },
            hire_date=date(2024, 1, 1)
        )
        person = emp1.person

        # Terminate first employee to allow rehire
        EmployeeService.terminate(emp1.id, date(2024, 12, 31))

        # 2. Hire as new employee using existing Person (e.g. concurrent job)
        emp2 = EmployeeService.hire_direct(
            person_data={}, # Should be ignored
            employee_data={
                'employee_type': self.temp_emp_type,
                'employee_number': 'E_NEW'
            },
            hire_date=date(2025, 1, 1),
            person=person
        )

        self.assertEqual(emp2.person, person)
        self.assertEqual(emp2.employee_number, 'E_NEW')
        self.assertNotEqual(emp1.id, emp2.id)

    def test_terminate_employee(self):
        """Can terminate employment"""
        # Hire employee
        employee = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Sara',
                'last_name': 'Ali',
                'email_address': 'sara@test.com',
                'date_of_birth': date(1992, 5, 15),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E002'
            },
            hire_date=date(2025, 1, 1)
        )

        person = employee.person

        # Terminate
        EmployeeService.terminate(
            employee_id=employee.id,
            termination_date=date(2025, 12, 31),
            reason='End of contract'
        )

        # Employee period ended
        employee.refresh_from_db()
        self.assertEqual(employee.effective_end_date, date(2025, 12, 31))

        # Person has no current type (no active periods)
        person.refresh_from_db()
        self.assertIsNone(person.current_type)

    def test_rehire_employee(self):
        """Can rehire previously terminated employee"""
        # Hire and terminate
        employee_v1 = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Rehire',
                'last_name': 'Test',
                'email_address': 'rehire@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E003'
            },
            hire_date=date(2020, 1, 1)
        )

        person = employee_v1.person

        EmployeeService.terminate(
            employee_id=employee_v1.id,
            termination_date=date(2024, 12, 31)
        )

        # Rehire
        employee_v2 = EmployeeService.rehire(
            person_id=person.id,
            effective_start_date=date(2026, 1, 1),
            hire_date=date(2026, 1, 1),
            employee_data={
                'employee_type': self.temp_emp_type,
                'employee_number': 'E003-NEW'
            }
        )

        # New employment period created
        self.assertIsNotNone(employee_v2)
        self.assertNotEqual(employee_v2.id, employee_v1.id)
        self.assertEqual(employee_v2.hire_date, date(2026, 1, 1))

        # Person has 2 employment periods
        person.refresh_from_db()
        self.assertEqual(person.employee_periods.count(), 2)

        # Person type is now EMP again
        self.assertEqual(person.current_base_type, 'EMP')

    def test_cannot_rehire_active_employee(self):
        """Cannot rehire person with active employment"""
        employee = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Active',
                'last_name': 'Employee',
                'email_address': 'active@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E004'
            }
        )

        # Try to rehire (should fail)
        with self.assertRaises(ValidationError) as context:
            EmployeeService.rehire(
                person_id=employee.person.id,
                effective_start_date=date.today(),
                hire_date=date.today(),
                employee_data={
                    'employee_type': self.perm_emp_type,
                    'employee_number': 'E004-NEW'
                }
            )

        self.assertIn('already has active employment', str(context.exception))

    def test_list_employees(self):
        """Test listing employees with filters"""
        # Create active employee
        active_emp = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Active',
                'last_name': 'List',
                'email_address': 'active_list@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E005'
            },
            hire_date=date(2025, 1, 1)
        )
        
        # Create terminated employee
        term_emp = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Terminated',
                'last_name': 'List',
                'email_address': 'term_list@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E006'
            },
            hire_date=date(2024, 1, 1)
        )
        EmployeeService.terminate(
            employee_id=term_emp.id,
            termination_date=date(2024, 12, 31)
        )
        
        # Test default (ALL records)
        all_emps = EmployeeService.list_employees()
        self.assertIn(active_emp, all_emps)
        self.assertIn(term_emp, all_emps)
        
        # Test active on date (2025-06-01) - only active_emp
        active_2025 = EmployeeService.list_employees({'as_of_date': date(2025, 6, 1)})
        self.assertIn(active_emp, active_2025)
        self.assertNotIn(term_emp, active_2025)
        
        # Test active on date (2024-06-01) - only term_emp
        active_2024 = EmployeeService.list_employees({'as_of_date': date(2024, 6, 1)})
        self.assertNotIn(active_emp, active_2024) # Not hired yet
        self.assertIn(term_emp, active_2024)
        
        # Test search
        search_res = EmployeeService.list_employees({'search': 'Terminated'})
        self.assertNotIn(active_emp, search_res)
        self.assertIn(term_emp, search_res)

    def test_convert_employee_type(self):
        """Can convert employee from temp to permanent (updates in-place, same number)"""
        # Hire as temp
        employee = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Convert',
                'last_name': 'Test',
                'email_address': 'convert@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.temp_emp_type,
                'employee_number': 'E005'
            },
            hire_date=date(2025, 1, 1)
        )

        person = employee.person
        employee_id = employee.id

        # Verify initially temp
        self.assertEqual(employee.employee_type, self.temp_emp_type)

        # Convert to permanent (updates in place, no new version)
        updated_employee = EmployeeService.convert_employee_type(
            employee_id=employee.id,
            new_type=self.perm_emp_type,
            effective_date=date(2025, 6, 1)
        )

        # Same employee record (updated in place)
        self.assertEqual(updated_employee.id, employee_id)
        self.assertEqual(updated_employee.employee_number, 'E005')  # SAME NUMBER
        self.assertEqual(updated_employee.employee_type, self.perm_emp_type)

        # Original hire date preserved
        self.assertEqual(updated_employee.hire_date, date(2025, 1, 1))

        # Still active (no end date)
        self.assertIsNone(updated_employee.effective_end_date)

        # Person type updated
        person.refresh_from_db()
        self.assertEqual(person.current_type, self.perm_emp_type)

    def test_get_active_employees(self):
        """Can query active employees on specific date"""
        # Hire employee 1 (2025-2025)
        EmployeeService.hire_direct(
            person_data={
                'first_name': 'Emp1',
                'last_name': 'Test',
                'email_address': 'emp1@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E006'
            },
            hire_date=date(2025, 1, 1)
        )

        # Hire employee 2 (2026-)
        EmployeeService.hire_direct(
            person_data={
                'first_name': 'Emp2',
                'last_name': 'Test',
                'email_address': 'emp2@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            employee_data={
                'employee_type': self.perm_emp_type,
                'employee_number': 'E007'
            },
            hire_date=date(2026, 1, 1)
        )

        # Query as of 2025-06-15 (only emp1 active)
        active_2025 = EmployeeService.get_active_employees(as_of_date=date(2025, 6, 15))
        self.assertEqual(active_2025.count(), 1)
        self.assertEqual(active_2025.first().employee_number, 'E006')

        # Query as of 2026-06-15 (both active)
        active_2026 = EmployeeService.get_active_employees(as_of_date=date(2026, 6, 15))
        self.assertEqual(active_2026.count(), 2)


class ApplicantServiceTests(TestCase):
    """Test ApplicantService business logic"""

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

    def test_create_application(self):
        """Can create job application"""
        applicant = ApplicantService.create_application(
            person_data={
                'first_name': 'Applicant',
                'last_name': 'Test',
                'email_address': 'applicant@test.com',
                'date_of_birth': date(1995, 3, 20),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            applicant_data={
                'applicant_type': self.apl_type,
                'application_number': 'APL001',
                'application_source': 'LinkedIn'
            },
            effective_start_date=date(2025, 1, 15)
        )

        # Applicant created
        self.assertIsNotNone(applicant)
        self.assertEqual(applicant.application_number, 'APL001')
        self.assertEqual(applicant.application_status, 'applied')

        # Person auto-created
        self.assertIsNotNone(applicant.person)
        self.assertEqual(applicant.person.current_base_type, 'APL')

    def test_update_application_status(self):
        """Can move applicant through hiring pipeline"""
        applicant = ApplicantService.create_application(
            person_data={
                'first_name': 'Pipeline',
                'last_name': 'Test',
                'email_address': 'pipeline@test.com',
                'date_of_birth': date(1995, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            applicant_data={
                'applicant_type': self.apl_type,
                'application_number': 'APL002'
            }
        )

        # Move through pipeline
        ApplicantService.update_application_status(applicant.id, 'screening')
        applicant.refresh_from_db()
        self.assertEqual(applicant.application_status, 'screening')

        ApplicantService.update_application_status(applicant.id, 'interview')
        applicant.refresh_from_db()
        self.assertEqual(applicant.application_status, 'interview')

        ApplicantService.update_application_status(applicant.id, 'offer')
        applicant.refresh_from_db()
        self.assertEqual(applicant.application_status, 'offer')

    def test_reject_application(self):
        """Can reject application"""
        applicant = ApplicantService.create_application(
            person_data={
                'first_name': 'Reject',
                'last_name': 'Test',
                'email_address': 'reject@test.com',
                'date_of_birth': date(1995, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            applicant_data={
                'applicant_type': self.apl_type,
                'application_number': 'APL003'
            }
        )

        # Reject
        ApplicantService.reject_application(
            applicant_id=applicant.id,
            rejection_date=date.today(),
            reason='Not qualified'
        )

        # Application closed
        applicant.refresh_from_db()
        self.assertEqual(applicant.application_status, 'rejected')
        self.assertIsNotNone(applicant.effective_end_date)

    def test_cannot_update_rejected_application(self):
        """Cannot update status of rejected application"""
        applicant = ApplicantService.create_application(
            person_data={
                'first_name': 'Terminal',
                'last_name': 'Test',
                'email_address': 'terminal@test.com',
                'date_of_birth': date(1995, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            applicant_data={
                'applicant_type': self.apl_type,
                'application_number': 'APL004'
            }
        )

        ApplicantService.reject_application(applicant.id)

        # Try to update (should fail)
        with self.assertRaises(ValidationError) as context:
            ApplicantService.update_application_status(applicant.id, 'interview')

        self.assertIn('already rejected', str(context.exception))


class ApplicantToEmployeeIntegrationTests(TestCase):
    """Test applicant → employee transition"""

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

    def test_hire_from_applicant(self):
        """Can hire applicant as employee"""
        # Create application
        applicant = ApplicantService.create_application(
            person_data={
                'first_name': 'Hired',
                'last_name': 'Applicant',
                'email_address': 'hired@test.com',
                'date_of_birth': date(1995, 1, 1),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            applicant_data={
                'applicant_type': self.apl_type,
                'application_number': 'APL005'
            },
            effective_start_date=date(2025, 1, 1)
        )

        person = applicant.person

        # Initially applicant
        self.assertEqual(person.current_base_type, 'APL')

        # Hire
        employee = EmployeeService.hire_from_applicant(
            applicant_id=applicant.id,
            effective_start_date=date(2025, 3, 1),
            hire_date=date(2025, 3, 1),
            employee_data={
                'employee_type': self.emp_type,
                'employee_number': 'E100'
            }
        )

        # Applicant period ended
        applicant.refresh_from_db()
        self.assertEqual(applicant.effective_end_date, date(2025, 2, 28))
        self.assertEqual(applicant.application_status, 'hired')

        # Employee period started
        self.assertIsNotNone(employee)
        self.assertEqual(employee.effective_start_date, date(2025, 3, 1))
        self.assertEqual(employee.person, person)

        # Person type changed
        person.refresh_from_db()
        self.assertEqual(person.current_base_type, 'EMP')

    def test_cannot_hire_already_hired_applicant(self):
        """Cannot hire applicant twice"""
        applicant = ApplicantService.create_application(
            person_data={
                'first_name': 'Double',
                'last_name': 'Hire',
                'email_address': 'doublehire@test.com',
                'date_of_birth': date(1995, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            applicant_data={
                'applicant_type': self.apl_type,
                'application_number': 'APL101'
            },
            effective_start_date=date(2025, 1, 1)
        )

        # Hire once
        EmployeeService.hire_from_applicant(
            applicant_id=applicant.id,
            effective_start_date=date(2025, 3, 1),
            hire_date=date(2025, 3, 1),
            employee_data={
                'employee_type': self.emp_type,
                'employee_number': 'E101'
            }
        )

        # Try to hire again (should fail)
        with self.assertRaises(ValidationError) as context:
            EmployeeService.hire_from_applicant(
                applicant_id=applicant.id,
                effective_start_date=date(2025, 4, 1),
                hire_date=date(2025, 4, 1),
                employee_data={
                    'employee_type': self.emp_type,
                    'employee_number': 'E102'
                }
            )

        self.assertIn('already hired', str(context.exception))


class ContingentWorkerServiceTests(TestCase):
    """Test ContingentWorkerService business logic"""

    def setUp(self):
        self.cwk_type, _ = PersonType.objects.get_or_create(
            code='CONSULTANT',
            defaults={
                'name': 'Consultant',
                'base_type': 'CWK',
                'is_active': True
            }
        )

    def test_create_placement(self):
        """Can create contingent worker placement"""
        worker = ContingentWorkerService.create_placement(
            person_data={
                'first_name': 'Worker',
                'last_name': 'Test',
                'email_address': 'worker@test.com',
                'date_of_birth': date(1988, 7, 10),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            worker_data={
                'worker_type': self.cwk_type,
                'worker_number': 'CWK001',
                'vendor_name': 'Consulting Inc'
            },
            placement_date=date(2025, 1, 1)
        )

        # Worker created
        self.assertIsNotNone(worker)
        self.assertEqual(worker.worker_number, 'CWK001')
        self.assertEqual(worker.vendor_name, 'Consulting Inc')

        # Person auto-created
        self.assertIsNotNone(worker.person)
        self.assertEqual(worker.person.current_base_type, 'CWK')

    def test_end_placement(self):
        """Can end contingent worker placement"""
        worker = ContingentWorkerService.create_placement(
            person_data={
                'first_name': 'End',
                'last_name': 'Test',
                'email_address': 'end@test.com',
                'date_of_birth': date(1988, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Single'
            },
            worker_data={
                'worker_type': self.cwk_type,
                'worker_number': 'CWK002'
            }
        )

        # End placement
        ContingentWorkerService.end_placement(
            worker_id=worker.id,
            end_date=date.today(),
            reason='Contract completion'
        )

        # Placement ended
        worker.refresh_from_db()
        self.assertIsNotNone(worker.effective_end_date)


class ContactServiceTests(TestCase):
    """Test ContactService business logic"""

    def setUp(self):
        self.con_type, _ = PersonType.objects.get_or_create(
            code='EMERGENCY_CONTACT',
            defaults={
                'name': 'Emergency Contact',
                'base_type': 'CON',
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

    def test_create_contact(self):
        """Can create contact"""
        contact = ContactService.create_contact(
            person_data={
                'first_name': 'Contact',
                'last_name': 'Test',
                'email_address': 'contact@test.com',
                'date_of_birth': date(1980, 2, 14),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Married'
            },
            contact_data={
                'contact_type': self.con_type,
                'contact_number': 'CON001',
                'organization_name': 'Test Org'
            }
        )

        # Contact created
        self.assertIsNotNone(contact)
        self.assertEqual(contact.contact_number, 'CON001')
        self.assertEqual(contact.organization_name, 'Test Org')

        # Person auto-created
        self.assertIsNotNone(contact.person)
        self.assertEqual(contact.person.current_base_type, 'CON')

    def test_add_emergency_contact(self):
        """Can add emergency contact for employee"""
        # Create employee
        employee = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Employee',
                'last_name': 'WithContact',
                'email_address': 'empcontact@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Married'
            },
            employee_data={
                'employee_type': self.emp_type,
                'employee_number': 'E200'
            }
        )

        # Add emergency contact
        contact = ContactService.add_emergency_contact(
            employee_id=employee.id,
            person_data={
                'first_name': 'Emergency',
                'last_name': 'Contact',
                'email_address': 'emergency@test.com',
                'date_of_birth': date(1992, 1, 1),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Married'
            },
            contact_data={
                'contact_type': self.con_type,
                'contact_number': 'EC001'
            },
            relationship='Spouse',
            is_primary=True
        )

        # Contact created and linked
        self.assertIsNotNone(contact)
        self.assertEqual(contact.emergency_for_employee, employee)
        self.assertEqual(contact.emergency_relationship, 'Spouse')
        self.assertTrue(contact.is_primary_contact)

    def test_get_emergency_contacts_for_employee(self):
        """Can retrieve all emergency contacts for employee"""
        # Create employee
        employee = EmployeeService.hire_direct(
            person_data={
                'first_name': 'Multi',
                'last_name': 'Contact',
                'email_address': 'multicontact@test.com',
                'date_of_birth': date(1990, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Married'
            },
            employee_data={
                'employee_type': self.emp_type,
                'employee_number': 'E201'
            }
        )

        # Add primary contact
        contact1 = ContactService.add_emergency_contact(
            employee_id=employee.id,
            person_data={
                'first_name': 'Primary',
                'last_name': 'Contact',
                'email_address': 'primary@test.com',
                'date_of_birth': date(1992, 1, 1),
                'gender': 'Female',
                'nationality': 'Egyptian',
                'marital_status': 'Married'
            },
            contact_data={
                'contact_type': self.con_type,
                'contact_number': 'EC002'
            },
            relationship='Spouse',
            is_primary=True
        )

        # Add secondary contact
        contact2 = ContactService.add_emergency_contact(
            employee_id=employee.id,
            person_data={
                'first_name': 'Secondary',
                'last_name': 'Contact',
                'email_address': 'secondary@test.com',
                'date_of_birth': date(1965, 1, 1),
                'gender': 'Male',
                'nationality': 'Egyptian',
                'marital_status': 'Married'
            },
            contact_data={
                'contact_type': self.con_type,
                'contact_number': 'EC003'
            },
            relationship='Parent',
            is_primary=False
        )

        # Retrieve contacts
        contacts = ContactService.get_emergency_contacts_for_employee(employee.id)

        # Both contacts returned
        self.assertEqual(contacts.count(), 2)

        # Primary contact first
        self.assertEqual(contacts.first(), contact1)
