"""
Payment Reconciliation Tests
Tests for payment reconciliation features including payment_type, payment_method, bank_account, and reconciliation_status.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import AP_Invoice, AR_Invoice
from Finance.BusinessPartner.models import Customer, Supplier, BusinessPartner
from Finance.core.models import Currency, Country
from Finance.cash_management.models import PaymentType, Bank, BankBranch, BankAccount
from Finance.period.models import Period
from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination

User = get_user_model()


class PaymentReconciliationTestCase(APITestCase):
    """Test payment reconciliation features"""
    
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
        
        # Create currency
        self.usd = Currency.objects.create(
            name="US Dollar",
            code="USD",
            symbol="$",
            is_base_currency=True
        )
        
        # Create January 2026 period
        self.period = Period.objects.create(
            name='January 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            fiscal_year=2026,
            period_number=1
        )
        self.period.ar_period.state = 'open'
        self.period.ar_period.save()
        self.period.ap_period.state = 'open'
        self.period.ap_period.save()
        self.period.gl_period.state = 'open'
        self.period.gl_period.save()
        
        # Create country
        self.country = Country.objects.create(
            name="United States",
            code="US"
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            name="Test Supplier",
            country=self.country
        )
        
        # Create customer
        self.customer = Customer.objects.create(
            name="Test Customer",
            country=self.country
        )
        
        # Create payment types
        self.cash_type = PaymentType.objects.create(
            payment_method_code='CASH',
            payment_method_name='Cash Payment',
            enable_reconcile=False,
            is_active=True,
            created_by=self.user
        )
        
        self.wire_type = PaymentType.objects.create(
            payment_method_code='WIRE',
            payment_method_name='Wire Transfer',
            enable_reconcile=True,
            is_active=True,
            created_by=self.user
        )
        
        self.check_type = PaymentType.objects.create(
            payment_method_code='CHECK',
            payment_method_name='Check Payment',
            enable_reconcile=True,
            is_active=True,
            created_by=self.user
        )
        
        # Create bank hierarchy
        self.bank = Bank.objects.create(
            bank_name='Test Bank',
            bank_code='TB001',
            country=self.country,
            created_by=self.user
        )
        
        self.branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Main Branch',
            branch_code='MB001',
            country=self.country,
            created_by=self.user
        )
        
        # Create segment types and segments for GL
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
        
        # Create GL combinations for bank account
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
            created_by=self.user
        )
    
    def test_create_payment_with_payment_type(self):
        """Test creating payment with payment_type field"""
        url = reverse('finance:payments:payment-list')
        data = {
            'payment_type': 'PAYMENT',
            'date': '2026-01-15',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account_id': self.bank_account.id
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment_type'], 'PAYMENT')
        self.assertEqual(response.data['payment_method_id'], self.wire_type.id)
        self.assertEqual(response.data['bank_account_id'], self.bank_account.id)
        self.assertEqual(response.data['reconciliation_status'], 'UNRECONCILED')
    
    def test_create_receipt_payment(self):
        """Test creating receipt (incoming payment)"""
        url = reverse('finance:payments:payment-list')
        data = {
            'payment_type': 'RECEIPT',
            'date': '2026-01-15',
            'business_partner_id': self.customer.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account_id': self.bank_account.id
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment_type'], 'RECEIPT')
    
    def test_create_payment_without_bank_account(self):
        """Test creating cash payment without bank account"""
        url = reverse('finance:payments:payment-list')
        data = {
            'payment_type': 'PAYMENT',
            'date': '2026-01-15',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.cash_type.id,
            # No bank_account_id for cash
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['bank_account_id'])
        self.assertFalse(response.data['payment_method_enable_reconcile'])
    
    def test_filter_payments_by_payment_type(self):
        """Test filtering payments by payment_type"""
        # Create payments
        Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 10),
            payment_method=self.wire_type,
            bank_account=self.bank_account
        )
        
        Payment.objects.create(
            payment_type='RECEIPT',
            business_partner=self.customer.business_partner,
            currency=self.usd,
            date=date(2026, 1, 11),
            payment_method=self.wire_type,
            bank_account=self.bank_account
        )
        
        # Filter by PAYMENT
        url = reverse('finance:payments:payment-list')
        response = self.client.get(url, {'payment_type': 'PAYMENT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('results', response.data.get('data', {}).get('results', response.data))), 1)
        self.assertEqual(response.data.get('results', response.data.get('data', {}).get('results', response.data))[0]['payment_type'], 'PAYMENT')
    
    def test_filter_payments_by_payment_method(self):
        """Test filtering payments by payment_method_id"""
        Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 10),
            payment_method=self.wire_type,
            bank_account=self.bank_account
        )
        
        Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 11),
            payment_method=self.check_type,
            bank_account=self.bank_account
        )
        
        url = reverse('finance:payments:payment-list')
        response = self.client.get(url, {'payment_method_id': self.wire_type.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('results', response.data.get('data', {}).get('results', response.data))), 1)
        self.assertEqual(response.data.get('results', response.data.get('data', {}).get('results', response.data))[0]['payment_method_id'], self.wire_type.id)
    
    def test_filter_payments_by_bank_account(self):
        """Test filtering payments by bank_account_id"""
        # Create another bank account
        bank_account2 = BankAccount.objects.create(
            branch=self.branch,
            account_number='ACC002',
            account_name='Secondary Account',
            account_type=BankAccount.CURRENT,
            currency=self.usd,
            opening_balance=Decimal('5000.00'),
            current_balance=Decimal('5000.00'),
            cash_GL_combination_id=self.cash_combo,
            cash_clearing_GL_combination_id=self.clearing_combo,
            created_by=self.user
        )
        
        Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 10),
            payment_method=self.wire_type,
            bank_account=self.bank_account
        )
        
        Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 11),
            payment_method=self.wire_type,
            bank_account=bank_account2
        )
        
        url = reverse('finance:payments:payment-list')
        response = self.client.get(url, {'bank_account_id': self.bank_account.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('results', response.data.get('data', {}).get('results', response.data))), 1)
        self.assertEqual(response.data.get('results', response.data.get('data', {}).get('results', response.data))[0]['bank_account_id'], self.bank_account.id)
    
    def test_filter_payments_by_reconciliation_status(self):
        """Test filtering payments by reconciliation_status"""
        # Create unreconciled payment
        payment1 = Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 10),
            payment_method=self.wire_type,
            bank_account=self.bank_account,
            reconciliation_status='UNRECONCILED'
        )
        
        # Create reconciled payment
        payment2 = Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 11),
            payment_method=self.wire_type,
            bank_account=self.bank_account,
            reconciliation_status='RECONCILED',
            reconciled_by=self.user
        )
        
        # Filter by UNRECONCILED
        url = reverse('finance:payments:payment-list')
        response = self.client.get(url, {'reconciliation_status': 'UNRECONCILED'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('results', response.data.get('data', {}).get('results', response.data))), 1)
        self.assertEqual(response.data.get('results', response.data.get('data', {}).get('results', response.data))[0]['reconciliation_status'], 'UNRECONCILED')
        
        # Filter by RECONCILED
        response = self.client.get(url, {'reconciliation_status': 'RECONCILED'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('results', response.data.get('data', {}).get('results', response.data))), 1)
        self.assertEqual(response.data.get('results', response.data.get('data', {}).get('results', response.data))[0]['reconciliation_status'], 'RECONCILED')
    
    def test_update_payment_method_and_bank_account(self):
        """Test updating payment_method and bank_account"""
        payment = Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 10),
            payment_method=self.wire_type,
            bank_account=self.bank_account
        )
        
        url = reverse('finance:payments:payment-detail', args=[payment.id])
        data = {
            'payment_method_id': self.check_type.id
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment_method_id'], self.check_type.id)
        
        # Verify in database
        payment.refresh_from_db()
        self.assertEqual(payment.payment_method, self.check_type)
    
    def test_payment_detail_includes_reconciliation_fields(self):
        """Test that payment detail includes all reconciliation fields"""
        payment = Payment.objects.create(
            payment_type='PAYMENT',
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2026, 1, 10),
            payment_method=self.wire_type,
            bank_account=self.bank_account,
            reconciliation_status='RECONCILED',
            reconciled_by=self.user
        )
        
        url = reverse('finance:payments:payment-detail', args=[payment.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('payment_type', response.data)
        self.assertIn('payment_method_id', response.data)
        self.assertIn('payment_method_name', response.data)
        self.assertIn('payment_method_enable_reconcile', response.data)
        self.assertIn('bank_account_id', response.data)
        self.assertIn('bank_account_name', response.data)
        self.assertIn('bank_account_number', response.data)
        self.assertIn('reconciliation_status', response.data)
        self.assertIn('reconciled_date', response.data)
        self.assertIn('reconciled_by', response.data)
        self.assertIn('reconciled_by_name', response.data)
        
        self.assertEqual(response.data['reconciliation_status'], 'RECONCILED')
        self.assertEqual(response.data['reconciled_by_name'], self.user.email)

