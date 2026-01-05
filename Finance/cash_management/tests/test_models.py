"""
Cash Management Model Tests
Tests for Bank, BankBranch, and BankAccount models.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

from Finance.cash_management.models import Bank, BankBranch, BankAccount
from Finance.core.models import Country, Currency
from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination


class BankModelTests(TestCase):
    """Test Bank model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.country = Country.objects.create(code='US', name='United States')
    
    def test_create_bank(self):
        """Test creating a bank"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            swift_code='TESTUS33',
            created_by=self.user
        )
        
        self.assertEqual(bank.bank_name, 'Test Bank')
        self.assertEqual(bank.bank_code, 'TB001')
        self.assertTrue(bank.is_active)
    
    def test_bank_str(self):
        """Test bank string representation"""
        bank = Bank.objects.create(
            bank_name='ABC Bank',
            bank_code='ABC',
            country=self.country,
            created_by=self.user
        )
        
        self.assertEqual(str(bank), 'ABC Bank (United States)')
    
    def test_get_branches(self):
        """Test getting bank branches"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user
        )
        
        # Create branches
        branch1 = BankBranch.objects.create(
            bank=bank,
            branch_name='Branch 1',
            branch_code='B1',
            address='Address 1',
            country=self.country,
            created_by=self.user
        )
        branch2 = BankBranch.objects.create(
            bank=bank,
            branch_name='Branch 2',
            branch_code='B2',
            address='Address 2',
            country=self.country,
            is_active=False,
            created_by=self.user
        )
        
        # Get all branches
        all_branches = bank.get_branches()
        self.assertEqual(all_branches.count(), 2)
        
        # Get active only
        active_branches = bank.get_branches(active_only=True)
        self.assertEqual(active_branches.count(), 1)
    
    def test_get_summary(self):
        """Test getting bank summary"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user
        )
        
        summary = bank.get_summary()
        
        self.assertEqual(summary['bank_name'], 'Test Bank')
        self.assertEqual(summary['bank_code'], 'TB001')
        self.assertEqual(summary['total_branches'], 0)
        self.assertEqual(summary['total_accounts'], 0)
    
    def test_activate_deactivate(self):
        """Test activating and deactivating bank"""
        bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user
        )
        
        # Deactivate
        result = bank.deactivate(user=self.user)
        self.assertFalse(bank.is_active)
        self.assertEqual(result['status'], 'deactivated')
        
        # Activate
        bank.activate(user=self.user)
        self.assertTrue(bank.is_active)


class BankBranchModelTests(TestCase):
    """Test BankBranch model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.country = Country.objects.create(code='US', name='United States')
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user
        )
    
    def test_create_branch(self):
        """Test creating a bank branch"""
        branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Downtown Branch',
            branch_code='DTN',
            address='123 Main St',
            city='New York',
            country=self.country,
            created_by=self.user
        )
        
        self.assertEqual(branch.branch_name, 'Downtown Branch')
        self.assertEqual(branch.bank, self.bank)
        self.assertTrue(branch.is_active)
    
    def test_branch_str(self):
        """Test branch string representation"""
        branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Main Branch',
            branch_code='MAIN',
            address='123 Main St',
            country=self.country,
            created_by=self.user
        )
        
        self.assertEqual(str(branch), 'Test Bank - Main Branch (MAIN)')
    
    def test_get_full_address(self):
        """Test getting full formatted address"""
        branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Branch',
            branch_code='BR',
            address='123 Main St',
            city='New York',
            postal_code='10001',
            country=self.country,
            created_by=self.user
        )
        
        full_address = branch.get_full_address()
        self.assertIn('123 Main St', full_address)
        self.assertIn('New York', full_address)
        self.assertIn('10001', full_address)


class BankAccountModelTests(TestCase):
    """Test BankAccount model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.country = Country.objects.create(code='US', name='United States')
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )
        
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
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
        
        # Create GL combination
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
    
    def test_create_account(self):
        """Test creating a bank account"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='123456789',
            account_name='Main Account',
            account_type=BankAccount.CURRENT,
            currency=self.currency,
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1000.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        self.assertEqual(account.account_number, '123456789')
        self.assertEqual(account.current_balance, Decimal('1000.00'))
        self.assertTrue(account.is_active)
    
    def test_update_balance_increase(self):
        """Test increasing account balance"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='123456789',
            account_name='Test Account',
            currency=self.currency,
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1000.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        new_balance = account.update_balance(Decimal('500.00'), user=self.user, increase=True)
        
        self.assertEqual(new_balance, Decimal('1500.00'))
        self.assertEqual(account.current_balance, Decimal('1500.00'))
    
    def test_update_balance_decrease(self):
        """Test decreasing account balance"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='123456789',
            account_name='Test Account',
            currency=self.currency,
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1000.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        new_balance = account.update_balance(Decimal('300.00'), user=self.user, increase=False)
        
        self.assertEqual(new_balance, Decimal('700.00'))
        self.assertEqual(account.current_balance, Decimal('700.00'))
    
    def test_insufficient_balance_error(self):
        """Test that insufficient balance raises error"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='123456789',
            account_name='Test Account',
            currency=self.currency,
            opening_balance=Decimal('100.00'),
            current_balance=Decimal('100.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        with self.assertRaises(ValidationError):
            account.update_balance(Decimal('500.00'), user=self.user, increase=False)
    
    def test_check_sufficient_balance(self):
        """Test checking sufficient balance"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='123456789',
            account_name='Test Account',
            currency=self.currency,
            current_balance=Decimal('1000.00'),
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        self.assertTrue(account.check_sufficient_balance(Decimal('500.00')))
        self.assertFalse(account.check_sufficient_balance(Decimal('1500.00')))
    
    def test_freeze_unfreeze(self):
        """Test freezing and unfreezing account"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='123456789',
            account_name='Test Account',
            currency=self.currency,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        # Freeze
        account.freeze(user=self.user)
        self.assertFalse(account.is_active)
        
        # Unfreeze
        account.unfreeze(user=self.user)
        self.assertTrue(account.is_active)
    
    def test_get_full_hierarchy(self):
        """Test getting full hierarchy"""
        account = BankAccount.objects.create(
            branch=self.branch,
            account_number='123456789',
            account_name='Test Account',
            currency=self.currency,
            cash_GL_combination=self.gl_combination,
            cash_clearing_GL_combination=self.gl_combination,
            created_by=self.user
        )
        
        hierarchy = account.get_full_hierarchy()
        
        self.assertIn('bank', hierarchy)
        self.assertIn('branch', hierarchy)
        self.assertIn('account', hierarchy)
        self.assertEqual(hierarchy['bank']['name'], 'Test Bank')
        self.assertEqual(hierarchy['branch']['name'], 'Main Branch')
        self.assertEqual(hierarchy['account']['number'], '123456789')
