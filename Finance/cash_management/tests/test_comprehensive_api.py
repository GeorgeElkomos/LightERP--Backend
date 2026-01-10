"""
Comprehensive Cash Management API Tests
Tests all endpoints: PaymentType, Bank, BankBranch, BankAccount, BankStatement, BankStatementLine, BankStatementLineMatch
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from datetime import date, datetime
from django.contrib.auth import get_user_model

from Finance.cash_management.models import (
    PaymentType, Bank, BankBranch, BankAccount,
    BankStatement, BankStatementLine, BankStatementLineMatch
)
from Finance.payments.models import Payment
from Finance.BusinessPartner.models import Supplier, BusinessPartner
from Finance.core.models import Currency, Country
from Finance.period.models import Period
from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination

User = get_user_model()


class PaymentTypeAPITestCase(APITestCase):
    """Test PaymentType API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create payment types
        self.cash_type = PaymentType.objects.create(
            payment_method_code='CASH',
            payment_method_name='Cash Payment',
            enable_reconcile=False,
            is_active=True,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.wire_type = PaymentType.objects.create(
            payment_method_code='WIRE',
            payment_method_name='Wire Transfer',
            enable_reconcile=True,
            is_active=True,
            created_by=self.user,
            updated_by=self.user
        )
    
    def test_list_payment_types(self):
        """Test listing all payment types"""
        url = reverse('finance:cash_management:paymenttype-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_filter_payment_types_by_is_active(self):
        """Test filtering payment types by is_active"""
        PaymentType.objects.create(
            payment_method_code='CHECK',
            payment_method_name='Check',
            enable_reconcile=True,
            is_active=False,
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:paymenttype-list')
        response = self.client.get(url, {'is_active': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        for item in response.data['results']:
            self.assertTrue(item['is_active'])
    
    def test_filter_payment_types_by_enable_reconcile(self):
        """Test filtering by enable_reconcile"""
        url = reverse('finance:cash_management:paymenttype-list')
        response = self.client.get(url, {'enable_reconcile': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['payment_method_code'], 'WIRE')
    
    def test_search_payment_types(self):
        """Test searching payment types"""
        url = reverse('finance:cash_management:paymenttype-list')
        response = self.client.get(url, {'search': 'Wire'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['payment_method_name'], 'Wire Transfer')
    
    def test_create_payment_type(self):
        """Test creating a new payment type"""
        url = reverse('finance:cash_management:paymenttype-list')
        data = {
            'payment_method_code': 'ACH',
            'payment_method_name': 'ACH Transfer',
            'enable_reconcile': True,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment_method_code'], 'ACH')
        self.assertTrue(response.data['enable_reconcile'])
    
    def test_update_payment_type(self):
        """Test updating a payment type"""
        url = reverse('finance:cash_management:paymenttype-detail', args=[self.cash_type.id])
        data = {
            'payment_method_name': 'Cash Payment Updated',
            'enable_reconcile': True
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment_method_name'], 'Cash Payment Updated')
        self.assertTrue(response.data['enable_reconcile'])
    
    def test_delete_payment_type(self):
        """Test deleting a payment type"""
        payment_type = PaymentType.objects.create(
            payment_method_code='DEL',
            payment_method_name='To Delete',
            enable_reconcile=False,
            is_active=True,
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:paymenttype-detail', args=[payment_type.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PaymentType.objects.filter(id=payment_type.id).exists())


class BankStatementAPITestCase(APITestCase):
    """Test BankStatement API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create supporting data
        self.country = Country.objects.create(name="United States", code="US")
        self.usd = Currency.objects.create(name="US Dollar", code="USD", symbol="$", is_base_currency=True)
        
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Main Branch',
            branch_code='MB001',
            country=self.country,
            updated_by=self.user,
            created_by=self.user
        )
        
        # Create segment types for GL
        self.segment_type1 = XX_SegmentType.objects.create(
            segment_name='Department',
            is_required=True,
            display_order=1,
            is_active=True
        )
        
        self.segment1 = XX_Segment.objects.create(
            segment_type=self.segment_type1,
            code='SALES',
            alias='Sales Department',
            node_type='child',
            is_active=True
        )
        
        self.cash_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type1.id, 'SALES')],
            'Cash Account'
        )
        
        self.clearing_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type1.id, 'SALES')],
            'Cash Clearing'
        )
        
        self.bank_account = BankAccount.objects.create(
            branch=self.branch,
            account_number='ACC001',
            account_name='Main Operating Account',
            account_type=BankAccount.CURRENT,
            currency=self.usd,
            opening_balance=Decimal('10000.00'),
            current_balance=Decimal('10000.00'),
            cash_GL_combination_id=self.cash_combo,
            cash_clearing_GL_combination_id=self.clearing_combo,
            created_by=self.user,
            updated_by=self.user
        )
    
    def test_list_bank_statements(self):
        """Test listing bank statements"""
        BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 1, 31),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
            opening_balance=Decimal('10000.00'),
            closing_balance=Decimal('11500.00'),
            total_credits=Decimal('1500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT002',            created_by=self.user,            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatement-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_statements_by_bank_account(self):
        """Test filtering statements by bank account"""
        BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 1, 31),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
            opening_balance=Decimal('10000.00'),
            closing_balance=Decimal('11500.00'),
            total_credits=Decimal('1500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT002',
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatement-list')
        response = self.client.get(url, {'bank_account': self.bank_account.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_statements_by_reconciliation_status(self):
        """Test filtering by reconciliation status"""
        stmt1 = BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 1, 31),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
            opening_balance=Decimal('10000.00'),
            closing_balance=Decimal('11500.00'),
            total_credits=Decimal('1500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT002',
            reconciliation_status='NOT_STARTED',
            created_by=self.user,
            updated_by=self.user
        )
        
        stmt2 = BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 2, 28),
            from_date=date(2026, 2, 1),
            to_date=date(2026, 2, 28),
            opening_balance=Decimal('11500.00'),
            closing_balance=Decimal('12000.00'),
            total_credits=Decimal('500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT003',
            reconciliation_status='RECONCILED',
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatement-list')
        response = self.client.get(url, {'reconciliation_status': 'NOT_STARTED'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['statement_number'], 'STMT002')
    
    def test_filter_statements_by_date_range(self):
        """Test filtering by date range"""
        BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 1, 31),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
            opening_balance=Decimal('10000.00'),
            closing_balance=Decimal('11500.00'),
            total_credits=Decimal('1500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT002',
            created_by=self.user,
            updated_by=self.user
        )
        
        BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 3, 31),
            from_date=date(2026, 3, 1),
            to_date=date(2026, 3, 31),
            opening_balance=Decimal('12000.00'),
            closing_balance=Decimal('13000.00'),
            total_credits=Decimal('1000.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT003',
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatement-list')
        response = self.client.get(url, {
            'statement_date_from': '2026-01-01',
            'statement_date_to': '2026-02-28'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        # Both STMT002 and STMT003 should be in results
        statement_numbers = [r['statement_number'] for r in response.data['results']]
        self.assertIn('STMT002', statement_numbers)
        self.assertIn('STMT003', statement_numbers)
    
    def test_create_bank_statement(self):
        """Test creating a bank statement"""
        url = reverse('finance:cash_management:bankstatement-list')
        data = {
            'bank_account': self.bank_account.id,
            'statement_number': 'STMT001',
            'statement_date': '2026-01-31',
            'from_date': '2026-01-01',
            'to_date': '2026-01-31',
            'opening_balance': '10000.00',
            'closing_balance': '11500.00',
            'total_credits': '1500.00',
            'total_debits': '0.00'
        }
        
        response = self.client.post(url, data, format='json')
        
        if response.status_code != status.HTTP_201_CREATED:
            print("ERROR:", response.data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['statement_number'], 'STMT001')
        self.assertEqual(Decimal(response.data['opening_balance']), Decimal('10000.00'))
    
    def test_update_bank_statement(self):
        """Test updating a bank statement"""
        statement = BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 1, 31),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
            opening_balance=Decimal('10000.00'),
            closing_balance=Decimal('11500.00'),
            total_credits=Decimal('1500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT002',            created_by=self.user,            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatement-detail', args=[statement.id])
        data = {
            'closing_balance': '12000.00',
            'total_credits': '2000.00',
            'reconciliation_status': 'IN_PROGRESS'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['closing_balance']), Decimal('12000.00'))
        self.assertEqual(response.data['reconciliation_status'], 'IN_PROGRESS')


class BankStatementLineAPITestCase(APITestCase):
    """Test BankStatementLine API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create supporting data
        self.country = Country.objects.create(name="United States", code="US")
        self.usd = Currency.objects.create(name="US Dollar", code="USD", symbol="$", is_base_currency=True)
        
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Main Branch',
            branch_code='MB001',
            country=self.country,
            updated_by=self.user,
            created_by=self.user
        )
        
        # Create GL segments
        self.segment_type1 = XX_SegmentType.objects.create(
            segment_name='Department',
            is_required=True,
            display_order=1,
            is_active=True
        )
        
        self.segment1 = XX_Segment.objects.create(
            segment_type=self.segment_type1,
            code='SALES',
            alias='Sales Department',
            node_type='child',
            is_active=True
        )
        
        self.cash_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type1.id, 'SALES')],
            'Cash Account'
        )
        
        self.clearing_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type1.id, 'SALES')],
            'Cash Clearing'
        )
        
        self.bank_account = BankAccount.objects.create(
            branch=self.branch,
            account_number='ACC001',
            account_name='Main Operating Account',
            account_type=BankAccount.CURRENT,
            currency=self.usd,
            opening_balance=Decimal('10000.00'),
            current_balance=Decimal('10000.00'),
            cash_GL_combination_id=self.cash_combo,
            cash_clearing_GL_combination_id=self.clearing_combo,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.statement = BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 1, 31),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
            opening_balance=Decimal('10000.00'),
            closing_balance=Decimal('11500.00'),
            total_credits=Decimal('1500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT002',
            created_by=self.user,
            updated_by=self.user
        )
    
    def test_list_statement_lines(self):
        """Test listing statement lines"""
        BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=1,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            credit_amount=Decimal('1500.00'),
            debit_amount=Decimal('0.00'),
            description='Customer payment',
            reference_number='REF001',
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatementline-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_lines_by_bank_statement(self):
        """Test filtering lines by bank statement"""
        BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=1,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            credit_amount=Decimal('1500.00'),
            debit_amount=Decimal('0.00'),
            description='Customer payment',
            reference_number='REF001',
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatementline-list')
        response = self.client.get(url, {'bank_statement': self.statement.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_lines_by_reconciliation_status(self):
        """Test filtering by reconciliation status"""
        line1 = BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=1,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            credit_amount=Decimal('1500.00'),
            debit_amount=Decimal('0.00'),
            description='Customer payment',
            reference_number='REF001',
            reconciliation_status='UNRECONCILED',
            created_by=self.user,
            updated_by=self.user
        )
        
        line2 = BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=2,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 16),
            value_date=date(2026, 1, 16),
            debit_amount=Decimal('500.00'),
            credit_amount=Decimal('0.00'),
            description='Vendor payment',
            reference_number='REF002',
            reconciliation_status='UNRECONCILED',
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatementline-list')
        response = self.client.get(url, {'reconciliation_status': 'UNRECONCILED'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['results'][0]['reference_number'], 'REF001')
    
    def test_filter_lines_has_match(self):
        """Test filtering by has_match"""
        line1 = BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=1,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            credit_amount=Decimal('1500.00'),
            debit_amount=Decimal('0.00'),
            description='Customer payment',
            reference_number='REF001',
            created_by=self.user,
            updated_by=self.user
        )
        
        line2 = BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=2,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 16),
            value_date=date(2026, 1, 16),
            debit_amount=Decimal('500.00'),
            credit_amount=Decimal('0.00'),
            description='Vendor payment',
            reference_number='REF002',
            created_by=self.user,
            updated_by=self.user
        )
        
        # Create a match for line1
        supplier = Supplier.objects.create(name="Test Supplier", country=self.country)
        payment = Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 15)
        )
        
        BankStatementLineMatch.objects.create(
            statement_line=line1,
            payment=payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='MATCHED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        url = reverse('finance:cash_management:bankstatementline-list')
        response = self.client.get(url, {'has_match': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['reference_number'], 'REF001')
    
    def test_create_statement_line(self):
        """Test creating a statement line"""
        url = reverse('finance:cash_management:bankstatementline-list')
        data = {
            'bank_statement_id': self.statement.id,
            'line_number': 2,
            'transaction_date': '2026-01-15',
            'value_date': '2026-01-15',
            'balance_after_transaction': '13000.00',
            'amount': '1500.00',
            'transaction_type': 'CREDIT',
            'description': 'Customer payment',
            'reference_number': 'REF001'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['reference_number'], 'REF001')
        self.assertEqual(response.data['description'], 'Customer payment')
    
    def test_update_statement_line(self):
        """Test updating a statement line"""
        line = BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=1,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            credit_amount=Decimal('1500.00'),
            debit_amount=Decimal('0.00'),
            description='Customer payment',
            reference_number='REF001',
            created_by=self.user,
            updated_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatementline-detail', args=[line.id])
        data = {
            'description': 'Customer payment - updated'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Customer payment - updated')


class BankStatementLineMatchAPITestCase(APITestCase):
    """Test BankStatementLineMatch API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create supporting data
        self.country = Country.objects.create(name="United States", code="US")
        self.usd = Currency.objects.create(name="US Dollar", code="USD", symbol="$", is_base_currency=True)
        
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Main Branch',
            branch_code='MB001',
            country=self.country,
            updated_by=self.user,
            created_by=self.user
        )
        
        # Create GL segments
        self.segment_type1 = XX_SegmentType.objects.create(
            segment_name='Department',
            is_required=True,
            display_order=1,
            is_active=True
        )
        
        self.segment1 = XX_Segment.objects.create(
            segment_type=self.segment_type1,
            code='SALES',
            alias='Sales Department',
            node_type='child',
            is_active=True
        )
        
        self.cash_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type1.id, 'SALES')],
            'Cash Account'
        )
        
        self.clearing_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type1.id, 'SALES')],
            'Cash Clearing'
        )
        
        self.bank_account = BankAccount.objects.create(
            branch=self.branch,
            account_number='ACC001',
            account_name='Main Operating Account',
            account_type=BankAccount.CURRENT,
            currency=self.usd,
            opening_balance=Decimal('10000.00'),
            current_balance=Decimal('10000.00'),
            cash_GL_combination_id=self.cash_combo,
            cash_clearing_GL_combination_id=self.clearing_combo,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.statement = BankStatement.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 1, 31),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
            opening_balance=Decimal('10000.00'),
            closing_balance=Decimal('11500.00'),
            total_credits=Decimal('1500.00'),
            total_debits=Decimal('0.00'),
            statement_number='STMT002',
            created_by=self.user,
            updated_by=self.user
        )
        
        self.line = BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=1,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            credit_amount=Decimal('1500.00'),
            debit_amount=Decimal('0.00'),
            description='Customer payment',
            reference_number='REF001',
            created_by=self.user,
            updated_by=self.user
        )
        
        # Create payment
        self.supplier = Supplier.objects.create(name="Test Supplier", country=self.country)
        self.payment = Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 15)
        )
    
    def test_list_matches(self):
        """Test listing matches"""
        BankStatementLineMatch.objects.create(
            statement_line=self.line,
            payment=self.payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='MATCHED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        url = reverse('finance:cash_management:bankstatementlinematch-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_matches_by_statement_line(self):
        """Test filtering by statement line"""
        BankStatementLineMatch.objects.create(
            statement_line=self.line,
            payment=self.payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='MATCHED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        url = reverse('finance:cash_management:bankstatementlinematch-list')
        response = self.client.get(url, {'statement_line': self.line.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_matches_by_payment(self):
        """Test filtering by payment"""
        BankStatementLineMatch.objects.create(
            statement_line=self.line,
            payment=self.payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='MATCHED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        url = reverse('finance:cash_management:bankstatementlinematch-list')
        response = self.client.get(url, {'payment': self.payment.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_matches_by_match_status(self):
        """Test filtering by match status"""
        match1 = BankStatementLineMatch.objects.create(
            statement_line=self.line,
            payment=self.payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='MATCHED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        # Create another line and match with different status
        line2 = BankStatementLine.objects.create(
            bank_statement=self.statement,
            line_number=2,
            balance=Decimal('11500.00'),
            transaction_date=date(2026, 1, 16),
            value_date=date(2026, 1, 16),
            debit_amount=Decimal('500.00'),
            credit_amount=Decimal('0.00'),
            description='Vendor payment',
            reference_number='REF002',
            created_by=self.user,
            updated_by=self.user
        )
        
        payment2 = Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 16)
        )
        
        match2 = BankStatementLineMatch.objects.create(
            statement_line=line2,
            payment=payment2,
            discrepancy_amount=Decimal('500.00'),
            match_status='SUGGESTED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        url = reverse('finance:cash_management:bankstatementlinematch-list')
        response = self.client.get(url, {'match_status': 'MATCHED'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['match_status'], 'MATCHED')
    
    def test_filter_matches_by_match_type(self):
        """Test filtering by match type"""
        BankStatementLineMatch.objects.create(
            statement_line=self.line,
            payment=self.payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='MATCHED',
            match_type='MANUAL',
            matched_by=self.user
        )
        
        url = reverse('finance:cash_management:bankstatementlinematch-list')
        response = self.client.get(url, {'match_type': 'MANUAL'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_match(self):
        """Test creating a match"""
        url = reverse('finance:cash_management:bankstatementlinematch-list')
        data = {
            'statement_line': self.line.id,
            'payment': self.payment.id,
            'discrepancy_amount': '0.00',
            'match_status': 'MATCHED',
            'match_type': 'MANUAL'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data['discrepancy_amount']), Decimal('1500.00'))
        self.assertEqual(response.data['match_status'], 'MATCHED')
    
    def test_update_match_status(self):
        """Test updating match status"""
        match = BankStatementLineMatch.objects.create(
            statement_line=self.line,
            payment=self.payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='SUGGESTED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        url = reverse('finance:cash_management:bankstatementlinematch-detail', args=[match.id])
        data = {
            'match_status': 'MATCHED',
            'notes': 'Confirmed by user'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['match_status'], 'MATCHED')
        self.assertEqual(response.data['notes'], 'Confirmed by user')
    
    def test_delete_match(self):
        """Test deleting a match"""
        match = BankStatementLineMatch.objects.create(
            statement_line=self.line,
            payment=self.payment,
            discrepancy_amount=Decimal('1500.00'),
            match_status='SUGGESTED',
            matched_by=self.user,
            match_type='MANUAL'
        )
        
        url = reverse('finance:cash_management:bankstatementlinematch-detail', args=[match.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BankStatementLineMatch.objects.filter(id=match.id).exists())
