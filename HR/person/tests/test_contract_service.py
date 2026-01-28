from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal
from HR.person.models import Contract, Person, PersonType, Employee
from HR.person.services.contract_service import ContractService
from HR.person.dtos import ContractCreateDTO, ContractUpdateDTO
from core.lookups.models import LookupType, LookupValue

User = get_user_model()

class ContractServiceTest(TestCase):
    """Test ContractService business logic"""

    @classmethod
    def setUpTestData(cls):
        # Create test user
        cls.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

        # Create Lookup Types
        cls.status_type = LookupType.objects.create(name='Contract Status')
        cls.end_reason_type = LookupType.objects.create(name='Contract End Reason')
        LookupType.objects.create(name='Payroll')
        LookupType.objects.create(name='Salary Basis')

        # Create Lookup Values
        cls.active_status = LookupValue.objects.create(
            lookup_type=cls.status_type, name='Active', is_active=True
        )
        cls.ended_status = LookupValue.objects.create(
            lookup_type=cls.status_type, name='Ended', is_active=True
        )
        cls.expired_reason = LookupValue.objects.create(
            lookup_type=cls.end_reason_type, name='Expired', is_active=True
        )

        # Create Person (via Employee)
        cls.person_type = PersonType.objects.create(
            code='PERM_EMP', name='Permanent Employee', base_type='EMP'
        )
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

    def test_create_contract(self):
        """Test creating a basic contract"""
        dto = ContractCreateDTO(
            contract_reference='CON-001',
            person_id=self.person.id,
            contract_status_id=self.active_status.id,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=365),
            contractual_job_position='Software Engineer',
            basic_salary=Decimal('10000.00'),
            effective_start_date=date.today()
        )
        contract = ContractService.create(self.user, dto)
        self.assertIsNotNone(contract.id)
        self.assertEqual(contract.contract_reference, 'CON-001')
        self.assertEqual(contract.basic_salary, Decimal('10000.00'))

    def test_create_contract_with_extension(self):
        """Test creating a contract with extension fields"""
        dto = ContractCreateDTO(
            contract_reference='CON-002',
            person_id=self.person.id,
            contract_status_id=self.active_status.id,
            contract_duration=Decimal('6'),
            contract_period='Months',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=180),
            contractual_job_position='Manager',
            basic_salary=Decimal('20000.00'),
            effective_start_date=date.today(),
            extension_duration=Decimal('3'),
            extension_period='Months',
            extension_start_date=date.today() + timedelta(days=181),
            extension_end_date=date.today() + timedelta(days=270)
        )
        contract = ContractService.create(self.user, dto)
        self.assertEqual(contract.extension_duration, Decimal('3.00'))
        self.assertEqual(contract.extension_period, 'Months')

    def test_invalid_date_relationship(self):
        """Test that end date before start date fails"""
        dto = ContractCreateDTO(
            contract_reference='CON-ERR',
            person_id=self.person.id,
            contract_status_id=self.active_status.id,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() - timedelta(days=1),
            contractual_job_position='Dev',
            basic_salary=Decimal('5000'),
            effective_start_date=date.today()
        )
        with self.assertRaises(ValidationError):
            ContractService.create(self.user, dto)

    def test_contract_correction(self):
        """Test updating a contract in correction mode"""
        contract = Contract.objects.create(
            contract_reference='CON-003',
            person=self.person,
            contract_status=self.active_status,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=365),
            contractual_job_position='Engineer',
            basic_salary=Decimal('10000.00'),
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        
        dto = ContractUpdateDTO(
            contract_reference='CON-003',
            effective_start_date=date.today(),
            basic_salary=Decimal('12000.00')
        )
        updated = ContractService.update(self.user, dto)
        self.assertEqual(updated.id, contract.id)
        self.assertEqual(updated.basic_salary, Decimal('12000.00'))

    def test_contract_new_version(self):
        """Test creating a new version of a contract"""
        start_date = date.today() - timedelta(days=30)
        contract = Contract.objects.create(
            contract_reference='CON-V1',
            person=self.person,
            contract_status=self.active_status,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=start_date,
            contract_end_date=start_date + timedelta(days=365),
            contractual_job_position='Engineer',
            basic_salary=Decimal('10000.00'),
            effective_start_date=start_date,
            created_by=self.user,
            updated_by=self.user
        )
        
        new_start_date = date.today()
        dto = ContractUpdateDTO(
            contract_reference='CON-V1',
            effective_start_date=new_start_date,
            basic_salary=Decimal('15000.00')
        )
        # Note: ContractService.update calls update_version. 
        # If new_start_date differs from current, it creates NEW version.
        updated = ContractService.update(self.user, dto)
        
        self.assertNotEqual(updated.id, contract.id)
        self.assertEqual(updated.basic_salary, Decimal('15000.00'))
        
        # Original version should be end-dated
        contract.refresh_from_db()
        self.assertEqual(contract.effective_end_date, new_start_date - timedelta(days=1))

    def test_deactivate_contract(self):
        """Test deactivating a contract"""
        start_date = date.today() - timedelta(days=10)
        contract = Contract.objects.create(
            contract_reference='CON-DEAD',
            person=self.person,
            contract_status=self.active_status,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=start_date,
            contract_end_date=start_date + timedelta(days=365),
            contractual_job_position='Engineer',
            basic_salary=Decimal('10000.00'),
            effective_start_date=start_date,
            created_by=self.user,
            updated_by=self.user
        )
        
        ContractService.deactivate(self.user, 'CON-DEAD')
        contract.refresh_from_db()
        self.assertEqual(contract.effective_end_date, date.today() - timedelta(days=1))

    def test_query_methods(self):
        """Test contract query methods"""
        Contract.objects.create(
            contract_reference='CON-Q1',
            person=self.person,
            contract_status=self.active_status,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=365),
            contractual_job_position='Engineer',
            basic_salary=Decimal('10000.00'),
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        
        contracts = ContractService.get_contracts_by_person(self.person.id)
        self.assertEqual(len(contracts), 1)
        
        active = ContractService.get_active_contract(self.person.id)
        self.assertIsNotNone(active)
        self.assertEqual(active.contract_reference, 'CON-Q1')

    def test_create_contract_invalid_person(self):
        """Test creating contract with non-existent person"""
        dto = ContractCreateDTO(
            contract_reference='CON-INV',
            person_id=99999,
            contract_status_id=self.active_status.id,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=365),
            contractual_job_position='Dev',
            basic_salary=Decimal('1000'),
            effective_start_date=date.today()
        )
        with self.assertRaises(ValidationError) as cm:
            ContractService.create(self.user, dto)
        self.assertIn('person_id', cm.exception.message_dict)

    def test_create_contract_invalid_status(self):
        """Test creating contract with invalid status lookup type"""
        # Create a lookup with different type
        wrong_type = LookupType.objects.create(name='Wrong')
        wrong_val = LookupValue.objects.create(lookup_type=wrong_type, name='X')
        
        dto = ContractCreateDTO(
            contract_reference='CON-INV-STAT',
            person_id=self.person.id,
            contract_status_id=wrong_val.id,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=365),
            contractual_job_position='Dev',
            basic_salary=Decimal('1000'),
            effective_start_date=date.today()
        )
        with self.assertRaises(ValidationError) as cm:
            ContractService.create(self.user, dto)
        self.assertIn('contract_status_id', cm.exception.message_dict)

    def test_get_contract_by_reference(self):
        """Test retrieving all versions by reference"""
        Contract.objects.create(
            contract_reference='CON-REF',
            person=self.person,
            contract_status=self.active_status,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=365),
            contractual_job_position='Engineer',
            basic_salary=Decimal('10000.00'),
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        versions = ContractService.get_contract_by_reference('CON-REF')
        self.assertEqual(len(versions), 1)

    def test_create_contract_negative_salary(self):
        """Test that negative salary fails (CheckConstraint)"""
        dto = ContractCreateDTO(
            contract_reference='CON-NEG',
            person_id=self.person.id,
            contract_status_id=self.active_status.id,
            contract_duration=Decimal('1'),
            contract_period='Years',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=365),
            contractual_job_position='Dev',
            basic_salary=Decimal('-100.00'),
            effective_start_date=date.today()
        )
        with self.assertRaises(ValidationError):
            # full_clean() should catch this via the constraint or validator if added
            contract = ContractService.create(self.user, dto)
            contract.full_clean()
