"""
Tests for Bank Account creation with segment-based GL combinations

This test file verifies the new functionality that allows users to create
bank accounts by providing GL segment details directly (similar to Invoice,
Payment, and Journal Entry creation) instead of requiring pre-existing
combination IDs.
"""
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal

from core.user_accounts.models import CustomUser as User
from Finance.core.models import Country, Currency
from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination
from Finance.cash_management.models import Bank, BankBranch, BankAccount


class BankAccountSegmentCreationTests(APITestCase):
    """Test bank account creation using segment details"""
    
    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create country and currency
        self.country = Country.objects.create(code='US', name='United States')
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )
        
        # Create bank and branch
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
        
        # Create segment types and segments
        self.entity_type = XX_SegmentType.objects.create(
            segment_name='Entity',
            is_required=True,
            display_order=1,
            is_active=True
        )
        
        self.account_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            display_order=2,
            is_active=True
        )
        
        self.entity_100 = XX_Segment.objects.create(
            segment_type=self.entity_type,
            code='100',
            alias='Main Entity',
            node_type='child',
            is_active=True
        )
        
        self.account_1010 = XX_Segment.objects.create(
            segment_type=self.account_type,
            code='1010',
            alias='Cash',
            node_type='child',
            is_active=True
        )
        
        self.account_1020 = XX_Segment.objects.create(
            segment_type=self.account_type,
            code='1020',
            alias='Cash Clearing',
            node_type='child',
            is_active=True
        )
        
        # Create a pre-existing GL combination for ID-based tests
        self.existing_combo = XX_Segment_combination.get_combination_id(
            [(self.entity_type.id, '100'), (self.account_type.id, '1010')],
            'Pre-existing Combo'
        )
    
    def test_create_account_with_segments(self):
        """Test creating bank account with segment details (new approach)"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC001',
            'account_name': 'Main Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '10000.00',
            'cash_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1010'}
            ],
            'cash_clearing_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1020'}
            ]
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['account_number'], 'ACC001')
        self.assertIsNotNone(response.data['cash_GL_combination'])
        self.assertIsNotNone(response.data['cash_clearing_GL_combination'])
        
        # Verify account was created in database
        account = BankAccount.objects.get(account_number='ACC001')
        self.assertEqual(account.current_balance, Decimal('10000.00'))
        self.assertIsNotNone(account.cash_GL_combination)
        self.assertIsNotNone(account.cash_clearing_GL_combination)
    
    def test_create_account_with_combination_ids(self):
        """Test creating bank account with combination IDs (original approach)"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC002',
            'account_name': 'Second Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '5000.00',
            'cash_GL_combination': self.existing_combo,
            'cash_clearing_GL_combination': self.existing_combo
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['account_number'], 'ACC002')
        self.assertEqual(response.data['cash_GL_combination'], self.existing_combo)
    
    def test_segments_create_or_reuse_combinations(self):
        """Test that segments reuse existing combinations if available"""
        # Create first account with segments
        data1 = {
            'branch': self.branch.id,
            'account_number': 'ACC003',
            'account_name': 'Third Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '1000.00',
            'cash_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1010'}
            ],
            'cash_clearing_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1020'}
            ]
        }
        
        response1 = self.client.post('/finance/cash/accounts/', data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        combo1_id = response1.data['cash_GL_combination']
        
        # Create second account with same segments
        data2 = {
            'branch': self.branch.id,
            'account_number': 'ACC004',
            'account_name': 'Fourth Account',
            'account_type': 'SAVINGS',
            'currency': self.currency.id,
            'opening_balance': '2000.00',
            'cash_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1010'}
            ],
            'cash_clearing_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1020'}
            ]
        }
        
        response2 = self.client.post('/finance/cash/accounts/', data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        combo2_id = response2.data['cash_GL_combination']
        
        # Should reuse the same combination
        self.assertEqual(combo1_id, combo2_id)
    
    def test_validation_requires_cash_gl(self):
        """Test validation error when neither ID nor segments provided for cash GL"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC005',
            'account_name': 'Fifth Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '1000.00',
            # Missing cash_GL_combination and cash_GL_segments
            'cash_clearing_GL_combination': self.existing_combo
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check error message contains reference to cash_GL_combination
        self.assertIn('cash_GL_combination', str(response.data))
    
    def test_validation_requires_clearing_gl(self):
        """Test validation error when neither ID nor segments provided for clearing GL"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC006',
            'account_name': 'Sixth Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '1000.00',
            'cash_GL_combination': self.existing_combo
            # Missing cash_clearing_GL_combination and cash_clearing_GL_segments
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check error message contains reference to cash_clearing_GL_combination
        self.assertIn('cash_clearing_GL_combination', str(response.data))
    
    def test_validation_cannot_provide_both(self):
        """Test validation error when both ID and segments provided"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC007',
            'account_name': 'Seventh Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '1000.00',
            # Providing both ID and segments (not allowed)
            'cash_GL_combination': self.existing_combo,
            'cash_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1010'}
            ],
            'cash_clearing_GL_combination': self.existing_combo
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check error message contains reference to providing both
        self.assertIn('Cannot provide both', str(response.data))
    
    def test_validation_empty_segments(self):
        """Test validation error when empty segments array provided"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC008',
            'account_name': 'Eighth Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '1000.00',
            'cash_GL_segments': [],  # Empty array
            'cash_clearing_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1020'}
            ]
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Empty array is treated as not providing, so error mentions must provide
        self.assertIn('cash_GL', str(response.data))
    
    def test_segments_not_in_response(self):
        """Test that segment fields (write_only) don't appear in response"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC009',
            'account_name': 'Ninth Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '1000.00',
            'cash_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1010'}
            ],
            'cash_clearing_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1020'}
            ]
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Segments should not appear in response (write_only)
        self.assertNotIn('cash_GL_segments', response.data)
        self.assertNotIn('cash_clearing_GL_segments', response.data)
        # But combination IDs should appear
        self.assertIn('cash_GL_combination', response.data)
        self.assertIn('cash_clearing_GL_combination', response.data)
    
    def test_different_segments_for_cash_and_clearing(self):
        """Test using different segments for cash and clearing accounts"""
        data = {
            'branch': self.branch.id,
            'account_number': 'ACC010',
            'account_name': 'Tenth Account',
            'account_type': 'CURRENT',
            'currency': self.currency.id,
            'opening_balance': '15000.00',
            'cash_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1010'}
            ],
            'cash_clearing_GL_segments': [
                {'segment_type_id': self.entity_type.id, 'segment_code': '100'},
                {'segment_type_id': self.account_type.id, 'segment_code': '1020'}
            ]
        }
        
        response = self.client.post('/finance/cash/accounts/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        account = BankAccount.objects.get(account_number='ACC010')
        # Verify different combinations created
        self.assertNotEqual(
            account.cash_GL_combination_id,
            account.cash_clearing_GL_combination_id
        )
