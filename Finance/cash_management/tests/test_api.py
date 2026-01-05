"""
Cash Management API Tests
Comprehensive tests for all cash management API endpoints.
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

from Finance.cash_management.models import Bank, BankBranch, BankAccount
from Finance.core.models import Country, Currency
from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination


class BankAPITests(APITestCase):
    """Test Bank API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        self.country_us = Country.objects.create(code='US', name='United States')
        self.country_uk = Country.objects.create(code='UK', name='United Kingdom')
    
    def test_bank_list_get(self):
        """GET /banks/ - List all banks"""
        Bank.objects.create(
            bank_name='Bank A',
            bank_code='BA',
            country=self.country_us,
            created_by=self.user
        )
        Bank.objects.create(
            bank_name='Bank B',
            bank_code='BB',
            country=self.country_uk,
            created_by=self.user
        )
        
        response = self.client.get('/finance/cash/banks/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_bank_create(self):
        """POST /banks/ - Create new bank"""
        data = {
            'bank_name': 'New Bank',
            'bank_code': 'NB001',
            'country': self.country_us.id,
            'swift_code': 'NEWBUS33',
            'address': '123 Banking St',
            'phone': '+1-555-1234',
            'email': 'info@newbank.com'
        }
        
        response = self.client.post('/finance/cash/banks/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['bank_name'], 'New Bank')
        self.assertEqual(response.data['bank_code'], 'NB001')
        
        # Verify in database
        bank = Bank.objects.get(bank_code='NB001')
        self.assertEqual(bank.bank_name, 'New Bank')
        self.assertEqual(bank.created_by, self.user)
    
    def test_bank_detail_get(self):
        """GET /banks/{id}/ - Get bank details"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country_us,
            swift_code='TESTUS33',
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/banks/{bank.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bank_name'], 'Test Bank')
        self.assertEqual(response.data['swift_code'], 'TESTUS33')
    
    def test_bank_update(self):
        """PUT /banks/{id}/ - Update bank"""
        bank = Bank.objects.create(
            bank_name='Original Bank',
            bank_code='OB',
            country=self.country_us,
            created_by=self.user
        )
        
        update_data = {
            'bank_name': 'Updated Bank',
            'bank_code': 'OB',
            'country': self.country_uk.id,
            'phone': '+44-123-4567'
        }
        
        response = self.client.put(f'/finance/cash/banks/{bank.id}/', update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bank_name'], 'Updated Bank')
        
        # Verify in database
        bank.refresh_from_db()
        self.assertEqual(bank.bank_name, 'Updated Bank')
        self.assertEqual(bank.country, self.country_uk)
    
    def test_bank_delete(self):
        """DELETE /banks/{id}/ - Delete bank"""
        bank = Bank.objects.create(
            bank_name='To Delete',
            bank_code='DEL',
            country=self.country_us,
            created_by=self.user
        )
        
        bank_id = bank.id
        response = self.client.delete(f'/finance/cash/banks/{bank_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Bank.objects.filter(id=bank_id).exists())
    
    def test_bank_summary_action(self):
        """GET /banks/{id}/summary/ - Get bank summary"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB',
            country=self.country_us,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/banks/{bank.id}/summary/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('bank_name', response.data)
        self.assertIn('total_branches', response.data)
        self.assertIn('total_accounts', response.data)
    
    def test_bank_activate_action(self):
        """POST /banks/{id}/activate/ - Activate bank"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB',
            country=self.country_us,
            is_active=False,
            created_by=self.user
        )
        
        response = self.client.post(f'/finance/cash/banks/{bank.id}/activate/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        bank.refresh_from_db()
        self.assertTrue(bank.is_active)
    
    def test_bank_deactivate_action(self):
        """POST /banks/{id}/deactivate/ - Deactivate bank"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB',
            country=self.country_us,
            created_by=self.user
        )
        
        response = self.client.post(f'/finance/cash/banks/{bank.id}/deactivate/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        bank.refresh_from_db()
        self.assertFalse(bank.is_active)
    
    def test_bank_filter_by_country(self):
        """Test filtering banks by country"""
        Bank.objects.create(bank_name='US Bank', bank_code='US', country=self.country_us, created_by=self.user)
        Bank.objects.create(bank_name='UK Bank', bank_code='UK', country=self.country_uk, created_by=self.user)
        
        response = self.client.get(f'/finance/cash/banks/?country={self.country_us.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['bank_name'], 'US Bank')


class BankBranchAPITests(APITestCase):
    """Test BankBranch API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        self.country = Country.objects.create(code='US', name='United States')
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB',
            country=self.country,
            created_by=self.user
        )
    
    def test_branch_list_get(self):
        """GET /branches/ - List all branches"""
        BankBranch.objects.create(
            bank=self.bank,
            branch_name='Branch A',
            branch_code='BA',
            address='Address A',
            country=self.country,
            created_by=self.user
        )
        BankBranch.objects.create(
            bank=self.bank,
            branch_name='Branch B',
            branch_code='BB',
            address='Address B',
            country=self.country,
            created_by=self.user
        )
        
        response = self.client.get('/finance/cash/branches/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_branch_create(self):
        """POST /branches/ - Create new branch"""
        data = {
            'bank': self.bank.id,
            'branch_name': 'New Branch',
            'branch_code': 'NB',
            'address': '123 Branch St',
            'city': 'New York',
            'country': self.country.id,
            'phone': '+1-555-1234'
        }
        
        response = self.client.post('/finance/cash/branches/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['branch_name'], 'New Branch')
        self.assertEqual(response.data['branch_code'], 'NB')
    
    def test_branch_detail_get(self):
        """GET /branches/{id}/ - Get branch details"""
        branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Test Branch',
            branch_code='TB',
            address='123 Test St',
            city='Test City',
            country=self.country,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/branches/{branch.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['branch_name'], 'Test Branch')
        self.assertEqual(response.data['city'], 'Test City')
    
    def test_branch_total_balance_action(self):
        """GET /branches/{id}/total_balance/ - Get total balance"""
        branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Test Branch',
            branch_code='TB',
            address='Address',
            country=self.country,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/branches/{branch.id}/total_balance/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_balance', response.data)
        self.assertIn('branch', response.data)


class BankAccountAPITests(APITestCase):
    """Test BankAccount API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        self.country = Country.objects.create(code='US', name='United States')
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )
        
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB',
            country=self.country,
            created_by=self.user
        )
        
        self.branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Main Branch',
            branch_code='MAIN',
            address='123 Main St',
            country=self.country,
            created_by=self.user
        )
        
        # Create GL combinations
        segment_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True
        )
        segment = XX_Segment.objects.create(
            segment_type=segment_type,
            code='1000',
            alias='Cash'
        )
        self.gl_combination = XX_Segment_combination.objects.create()
    
    def test_account_list_get(self):
        """GET /accounts/ - List all accounts"""
        BankAccount.objects.create(
            branch=self.branch,
            account_number='ACC001',
            account_name='Account 1',
            currency=self.currency,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        BankAccount.objects.create(
            branch=self.branch,
            account_number='ACC002',
            account_name='Account 2',
            currency=self.currency,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.get('/finance/cash/accounts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_account_create(self):
        """POST /accounts/ - Create new account"""
        data = {
            'branch': self.branch.id,
            'account_number': 'NEW001',
            'account_name': 'New Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '1000.00',
            'cash_GL_combination': self.gl_combination.id,
            'cash_clearing_GL_combination': self.gl_combination.id
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['account_number'], 'NEW001')
        self.assertEqual(response.data['account_name'], 'New Account')
    
    def test_account_detail_get(self):
        """GET /accounts/{id}/ - Get account details"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='TEST001',
            account_name='Test Account',
            currency=self.currency,
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1000.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/accounts/{account.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['account_number'], 'TEST001')
        self.assertEqual(float(response.data['current_balance']), 1000.00)
    
    def test_account_update_balance_action(self):
        """POST /accounts/{id}/update_balance/ - Update account balance"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='TEST001',
            account_name='Test Account',
            currency=self.currency,
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1000.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        data = {
            'amount': '500.00',
            'increase': True
        }
        
        response = self.client.post(f'/finance/cash/accounts/{account.id}/update_balance/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['new_balance']), 1500.00)
        
        # Verify in database
        account.refresh_from_db()
        self.assertEqual(account.current_balance, Decimal('1500.00'))
    
    def test_account_freeze_action(self):
        """POST /accounts/{id}/freeze/ - Freeze account"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='TEST001',
            account_name='Test Account',
            currency=self.currency,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.post(f'/finance/cash/accounts/{account.id}/freeze/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        account.refresh_from_db()
        self.assertFalse(account.is_active)
    
    def test_account_unfreeze_action(self):
        """POST /accounts/{id}/unfreeze/ - Unfreeze account"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='TEST001',
            account_name='Test Account',
            currency=self.currency,
            is_active=False,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.post(f'/finance/cash/accounts/{account.id}/unfreeze/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        account.refresh_from_db()
        self.assertTrue(account.is_active)
    
    def test_account_check_balance_action(self):
        """GET /accounts/{id}/check_balance/ - Check sufficient balance"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='TEST001',
            account_name='Test Account',
            currency=self.currency,
            current_balance=Decimal('1000.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/accounts/{account.id}/check_balance/?amount=500')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['sufficient_balance'])
        
        # Check insufficient balance
        response = self.client.get(f'/finance/cash/accounts/{account.id}/check_balance/?amount=2000')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['sufficient_balance'])
    
    def test_account_hierarchy_action(self):
        """GET /accounts/{id}/hierarchy/ - Get full hierarchy"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='TEST001',
            account_name='Test Account',
            currency=self.currency,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/accounts/{account.id}/hierarchy/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('bank', response.data)
        self.assertIn('branch', response.data)
        self.assertIn('account', response.data)
    
    def test_account_balance_action(self):
        """GET /accounts/{id}/balance/ - Get balance summary"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='TEST001',
            account_name='Test Account',
            currency=self.currency,
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1500.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/accounts/{account.id}/balance/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['opening_balance']), 1000.00)
        self.assertEqual(float(response.data['current_balance']), 1500.00)
        self.assertEqual(float(response.data['change']), 500.00)
    
    def test_account_filter_by_branch(self):
        """Test filtering accounts by branch"""
        account1 = BankAccount.objects.create(
            branch=self.branch,
            account_number='ACC001',
            account_name='Account 1',
            currency=self.currency,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        response = self.client.get(f'/finance/cash/accounts/?branch={self.branch.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['account_number'], 'ACC001')
