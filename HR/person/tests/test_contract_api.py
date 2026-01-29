"""
API Tests for Contract endpoints.
"""
from datetime import date, timedelta
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from HR.person.models import Contract, PersonType, Employee
from core.lookups.models import LookupType, LookupValue
from core.base.test_utils import setup_core_data, setup_admin_permissions

User = get_user_model()


class ContractAPITest(TestCase):
    """Test Contract API endpoints."""

    def setUp(self):
        setup_core_data()
        self.client = APIClient()

        # Create test user with admin permissions
        self.user = User.objects.create_user(
            email="admin@test.com",
            name="Admin User",
            phone_number="1234567890",
            password="testpass123",
        )
        setup_admin_permissions(self.user)
        self.client.force_authenticate(user=self.user)

        # Create Lookup Types/Values
        self.types = {
            'CON_STATUS': LookupType.objects.get_or_create(name="Contract Status")[0],
            'CON_REASON': LookupType.objects.get_or_create(name="Contract End Reason")[0],
            'PAYROLL': LookupType.objects.get_or_create(name="Payroll")[0],
            'SAL_BASIS': LookupType.objects.get_or_create(name="Salary Basis")[0],
        }
        
        self.values = {
            'ACTIVE': LookupValue.objects.create(lookup_type=self.types['CON_STATUS'], name="Active", is_active=True),
            'ENDED': LookupValue.objects.create(lookup_type=self.types['CON_STATUS'], name="Ended", is_active=True),
            'RESIGN': LookupValue.objects.create(lookup_type=self.types['CON_REASON'], name="Resignation", is_active=True),
        }

        # Create Person
        self.person_type = PersonType.objects.create(
            code="PERM",
            name="Permanent",
            base_type="EMP",
            is_active=True
        )

        self.employee = Employee.objects.create(
            first_name="John",
            last_name="Doe",
            email_address="john@test.com",
            gender="Male",
            date_of_birth=date(1990, 1, 1),
            nationality="American",
            marital_status="Single",
            employee_type=self.person_type,
            employee_number="E001",
            hire_date=date.today(),
            effective_start_date=date.today(),
            created_by=self.user,
            updated_by=self.user
        )
        self.person = self.employee.person

        # Create Contract
        self.contract = Contract.objects.create(
            contract_reference="REF001",
            person=self.person,
            contract_status=self.values['ACTIVE'],
            description="Initial Contract",
            contract_duration=12,
            contract_period="Months",
            contract_start_date=date(2023, 1, 1),
            contract_end_date=date(2023, 12, 31),
            contractual_job_position="Software Engineer",
            basic_salary=5000.00,
            effective_start_date=date(2023, 1, 1),
            created_by=self.user,
            updated_by=self.user
        )

    def test_list_contracts(self):
        """Test GET /hr/person/contracts/"""
        response = self.client.get(f'/hr/person/contracts/?person={self.person.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'results' in response.data['data']:
            results = response.data['data']['results']
        else:
            results = response.data.get('results', response.data)
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['contract_reference'], 'REF001')

    def test_create_contract(self):
        """Test POST /hr/person/contracts/"""
        data = {
            'contract_reference': 'REF002',
            'person_id': self.person.id,
            'contract_status_id': self.values['ACTIVE'].id,
            'description': 'Second Contract',
            'contract_duration': '2',
            'contract_period': 'Years',
            'contract_start_date': '2024-01-01',
            'contract_end_date': '2025-12-31',
            'contractual_job_position': 'Senior Engineer',
            'basic_salary': '6000.00',
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post('/hr/person/contracts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Contract.objects.count(), 2)

    def test_update_contract_correction(self):
        """Test PATCH /hr/person/contracts/<id>/ (Correction)"""
        # Correction: Same effective date
        data = {
            'basic_salary': '5500.00',
            'effective_start_date': str(self.contract.effective_start_date)
        }
        response = self.client.patch(f'/hr/person/contracts/{self.contract.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.basic_salary, 5500.00)
        # Should NOT create new version
        self.assertEqual(Contract.objects.filter(contract_reference='REF001').count(), 1)

    def test_update_contract_new_version(self):
        """Test PATCH /hr/person/contracts/<id>/ (New Version)"""
        # New Version: Newer effective date
        new_date = self.contract.effective_start_date + timedelta(days=30)
        data = {
            'basic_salary': '5800.00',
            'effective_start_date': str(new_date)
        }
        response = self.client.patch(f'/hr/person/contracts/{self.contract.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should now have 2 versions
        versions = Contract.objects.filter(contract_reference='REF001').order_by('-effective_start_date')
        self.assertEqual(versions.count(), 2)
        self.assertEqual(versions[0].basic_salary, 5800.00)
        self.assertEqual(versions[1].basic_salary, 5000.00) # Old value

    def test_deactivate_contract(self):
        """Test DELETE /hr/person/contracts/<id>/"""
        response = self.client.delete(f'/hr/person/contracts/{self.contract.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        self.contract.refresh_from_db()
        # Status property checks if today is <= effective_end_date.
        # If effective_end_date is yesterday, status is 'inactive'.
        self.assertEqual(self.contract.status, 'inactive')
        self.assertEqual(self.contract.effective_end_date, date.today() - timedelta(days=1))

    def test_validation_date_order(self):
        """Test validation for contract dates"""
        data = {
            'contract_reference': 'REF003',
            'person_id': self.person.id,
            'contract_status_id': self.values['ACTIVE'].id,
            'contract_duration': '1',
            'contract_period': 'Years',
            'contract_start_date': '2024-01-01',
            'contract_end_date': '2023-12-31', # End before start
            'contractual_job_position': 'Dev',
            'basic_salary': '5000.00',
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post('/hr/person/contracts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('contract_end_date', response.data)
