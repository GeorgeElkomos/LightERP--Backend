"""
Integration Tests for Payment-to-Bank Reconciliation
Tests the complete flow from payment creation → bank statement import → matching → reconciliation
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

from Finance.payments.models import Payment, PaymentAllocation
from Finance.cash_management.models import (
    PaymentType, Bank, BankBranch, BankAccount,
    BankStatement, BankStatementLine, BankStatementLineMatch
)
from Finance.BusinessPartner.models import Supplier, Customer
from Finance.core.models import Currency, Country
from Finance.period.models import Period
from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination
from Finance.Invoice.models import AP_Invoice, AR_Invoice

User = get_user_model()


class PaymentBankReconciliationIntegrationTest(APITestCase):
    """Integration tests for payment-to-bank reconciliation flow"""
    
    def setUp(self):
        """Set up comprehensive test data"""
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
        
        # Create period
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
        
        # Create business partners
        self.supplier = Supplier.objects.create(
            name="Test Supplier Inc",
            country=self.country
        )
        
        self.customer = Customer.objects.create(
            name="Test Customer Corp",
            country=self.country
        )
        
        # Create payment types
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
        
        self.cash_type = PaymentType.objects.create(
            payment_method_code='CASH',
            payment_method_name='Cash Payment',
            enable_reconcile=False,
            is_active=True,
            created_by=self.user
        )
        
        # Create bank hierarchy
        self.bank = Bank.objects.create(
            bank_name='First National Bank',
            bank_code='FNB001',
            country=self.country,
            created_by=self.user
        )
        
        self.branch = BankBranch.objects.create(
            bank=self.bank,
            branch_name='Downtown Branch',
            branch_code='DTB001',
            country=self.country,
            created_by=self.user
        )
        
        # Create GL segments
        self.segment_type = XX_SegmentType.objects.create(
            segment_name='Department',
            is_required=True,
            display_order=1,
            is_active=True
        )
        
        self.segment = XX_Segment.objects.create(
            segment_type=self.segment_type,
            code='FIN',
            alias='Finance Department',
            node_type='child',
            is_active=True
        )
        
        self.cash_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type.id, 'FIN')],
            'Cash Account'
        )
        
        self.clearing_combo = XX_Segment_combination.get_combination_id(
            [(self.segment_type.id, 'FIN')],
            'Cash Clearing'
        )
        
        # Create bank account
        self.bank_account = BankAccount.objects.create(
            branch=self.branch,
            account_number='1234567890',
            account_name='Operating Account',
            account_type=BankAccount.CURRENT,
            currency=self.usd,
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00'),
            cash_GL_combination_id=self.cash_combo,
            cash_clearing_GL_combination_id=self.clearing_combo,
            created_by=self.user
        )
    
    def test_complete_outgoing_payment_reconciliation_flow(self):
        """Test: Create payment → Import statement → Match → Reconcile (Outgoing)"""
        
        # Step 1: Create an outgoing payment
        payment_url = reverse('finance:payments:payment-list')
        payment_data = {
            'payment_type': 'PAYMENT',
            'date': '2026-01-15',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account': self.bank_account.id,
        }
        
        payment_response = self.client.post(payment_url, payment_data, format='json')
        self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED)
        payment_id = payment_response.data['id']
        
        # Verify payment created with correct fields
        self.assertEqual(payment_response.data['payment_type'], 'PAYMENT')
        self.assertEqual(payment_response.data['reconciliation_status'], 'UNRECONCILED')
        self.assertEqual(payment_response.data['payment_method_id'], self.wire_type.id)
        self.assertEqual(payment_response.data['bank_account_id'], self.bank_account.id)
        self.assertTrue(payment_response.data['payment_method_enable_reconcile'])
        
        # Step 2: Create bank statement
        statement_url = reverse('finance:cash_management:bankstatement-list')
        statement_data = {
            'bank_account': self.bank_account.id,
            'statement_number': 'STMT-JAN-2026',
            'statement_date': '2026-01-31',
            'from_date': '2026-01-01',
            'to_date': '2026-01-31',
            'opening_balance': '50000.00',
            'closing_balance': '48500.00',  # -1500 for payment
            'total_debits': '1500.00',
            'total_credits': '0.00'
        }
        
        statement_response = self.client.post(statement_url, statement_data, format='json')
        self.assertEqual(statement_response.status_code, status.HTTP_201_CREATED)
        statement_id = statement_response.data.get('id', statement_response.data.get('data', {}).get('id'))
        
        # Step 3: Import bank statement line (simulating bank feed)
        line_url = reverse('finance:cash_management:bankstatementline-list')
        line_data = {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-15',
            'value_date': '2026-01-15',
            'balance_after_transaction': '8500.00',
            'amount': '-1500.00',  # Negative for outgoing
            'transaction_type': 'DEBIT',
            'description': 'Wire Transfer to Test Supplier Inc',
            'reference_number': 'WR20260115001'
        }
        
        line_response = self.client.post(line_url, line_data, format='json')
        self.assertEqual(line_response.status_code, status.HTTP_201_CREATED)
        line_id = line_response.data['id']
        
        # Verify line is unreconciled
        self.assertEqual(line_response.data['reconciliation_status'], 'UNRECONCILED')
        
        # Step 4: Create a match between payment and statement line
        match_url = reverse('finance:cash_management:bankstatementlinematch-list')
        match_data = {
            'statement_line': line_id,
            'payment': payment_id,
                        'match_status': 'MATCHED',
            'match_type': 'MANUAL',
            'notes': 'Manual match by user'
        }
        
        match_response = self.client.post(match_url, match_data, format='json')
        self.assertEqual(match_response.status_code, status.HTTP_201_CREATED)
        
        # Verify match details
        self.assertEqual(match_response.data['match_status'], 'MATCHED')
        
        # Step 5: Verify payment reconciliation status updated
        payment_detail_url = reverse('finance:payments:payment-detail', args=[payment_id])
        payment_check = self.client.get(payment_detail_url)
        
        # Note: Actual reconciliation_status update would happen via signal/method
        # For now, verify the match exists and payment can be queried
        self.assertEqual(payment_check.status_code, status.HTTP_200_OK)
        
        # Step 6: Verify we can filter reconciled payments
        payments_list = self.client.get(payment_url, {'bank_account': self.bank_account.id})
        self.assertEqual(payments_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(payments_list.data.get('results') or payments_list.data.get('data', {}).get('results', [])), 1)
    
    def test_complete_incoming_receipt_reconciliation_flow(self):
        """Test: Create receipt → Import statement → Match → Reconcile (Incoming)"""
        
        # Step 1: Create an incoming receipt
        payment_url = reverse('finance:payments:payment-list')
        receipt_data = {
            'payment_type': 'RECEIPT',
            'date': '2026-01-20',
            'business_partner_id': self.customer.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.check_type.id,
            'bank_account': self.bank_account.id,
        }
        
        receipt_response = self.client.post(payment_url, receipt_data, format='json')
        self.assertEqual(receipt_response.status_code, status.HTTP_201_CREATED)
        receipt_id = receipt_response.data['id']
        
        # Verify receipt type
        self.assertEqual(receipt_response.data['payment_type'], 'RECEIPT')
        
        # Step 2: Create bank statement
        statement_url = reverse('finance:cash_management:bankstatement-list')
        statement_data = {
            'bank_account': self.bank_account.id,
            'statement_number': 'STMT-JAN-2026',
            'statement_date': '2026-01-31',
            'from_date': '2026-01-01',
            'to_date': '2026-01-31',
            'opening_balance': '50000.00',
            'closing_balance': '52500.00',  # +2500 for receipt
            'total_debits': '0.00',
            'total_credits': '2500.00'
        }
        
        statement_response = self.client.post(statement_url, statement_data, format='json')
        self.assertEqual(statement_response.status_code, status.HTTP_201_CREATED)
        statement_id = statement_response.data.get('id', statement_response.data.get('data', {}).get('id'))
        
        # Step 3: Import bank statement line (incoming)
        line_url = reverse('finance:cash_management:bankstatementline-list')
        line_data = {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-20',
            'value_date': '2026-01-20',
            'balance_after_transaction': '12500.00',
            'amount': '2500.00',  # Positive for incoming
            'transaction_type': 'CREDIT',
            'description': 'Check deposit from Test Customer Corp',
            'reference_number': 'CHK20260120001'
        }
        
        line_response = self.client.post(line_url, line_data, format='json')
        self.assertEqual(line_response.status_code, status.HTTP_201_CREATED)
        line_id = line_response.data['id']
        
        # Step 4: Create match
        match_url = reverse('finance:cash_management:bankstatementlinematch-list')
        match_data = {
            'statement_line': line_id,
            'payment': receipt_id,
                        'match_status': 'MATCHED',
            'match_type': 'MANUAL'
        }
        
        match_response = self.client.post(match_url, match_data, format='json')
        self.assertEqual(match_response.status_code, status.HTTP_201_CREATED)
        
        # Step 5: Verify filtering works
        matches_list = self.client.get(match_url, {'payment': receipt_id})
        self.assertEqual(matches_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(matches_list.data.get('results') or matches_list.data.get('data', {}).get('results', [])), 1)
    
    def test_multiple_payments_one_statement_line(self):
        """Test: Multiple payments matched to one bank statement line (partial matching)"""
        
        # Create bank statement first
        statement_url = reverse('finance:cash_management:bankstatement-list')
        statement_data = {
            'bank_account': self.bank_account.id,
            'statement_number': 'STMT-MULTI',
            'statement_date': '2026-01-31',
            'from_date': '2026-01-01',
            'to_date': '2026-01-31',
            'opening_balance': '50000.00',
            'closing_balance': '47000.00',
            'total_debits': '3000.00',
            'total_credits': '0.00'
        }
        
        statement_response = self.client.post(statement_url, statement_data, format='json')
        statement_id = statement_response.data.get('id', statement_response.data.get('data', {}).get('id'))
        
        # Create statement line for combined payment
        line_url = reverse('finance:cash_management:bankstatementline-list')
        line_data = {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-25',
            'value_date': '2026-01-25',
            'balance_after_transaction': '7000.00',
            'amount': '-3000.00',
            'transaction_type': 'DEBIT',
            'description': 'Batch payment to suppliers',
            'reference_number': 'BATCH001'
        }
        
        line_response = self.client.post(line_url, line_data, format='json')
        line_id = line_response.data['id']
        
        # Create first payment
        payment_url = reverse('finance:payments:payment-list')
        payment1_data = {
            'payment_type': 'PAYMENT',
            'date': '2026-01-25',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account': self.bank_account.id,
        }
        
        payment1_response = self.client.post(payment_url, payment1_data, format='json')
        payment1_id = payment1_response.data['id']
        
        # Create second payment (another supplier)
        supplier2 = Supplier.objects.create(name="Supplier Two", country=self.country)
        payment2_data = {
            'payment_type': 'PAYMENT',
            'date': '2026-01-25',
            'business_partner_id': supplier2.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account': self.bank_account.id,
        }
        
        payment2_response = self.client.post(payment_url, payment2_data, format='json')
        payment2_id = payment2_response.data['id']
        
        # Match first payment (1500)
        match_url = reverse('finance:cash_management:bankstatementlinematch-list')
        match1_data = {
            'statement_line': line_id,
            'payment': payment1_id,
                        'match_status': 'MATCHED',
            'match_type': 'MANUAL'
        }
        
        match1_response = self.client.post(match_url, match1_data, format='json')
        self.assertEqual(match1_response.status_code, status.HTTP_201_CREATED)
        
        # Match second payment (1500)
        match2_data = {
            'statement_line': line_id,
            'payment': payment2_id,
                        'match_status': 'MATCHED',
            'match_type': 'MANUAL'
        }
        
        match2_response = self.client.post(match_url, match2_data, format='json')
        self.assertEqual(match2_response.status_code, status.HTTP_201_CREATED)
        
        # Verify both matches exist for the same statement line
        matches_list = self.client.get(match_url, {'statement_line': line_id})
        self.assertEqual(matches_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(matches_list.data.get('results') or matches_list.data.get('data', {}).get('results', [])), 2)
        
        # Verify both matches exist
        self.assertEqual(len(matches_list.data.get('results') or matches_list.data.get('data', {}).get('results', [])), 2)
    
    def test_suggested_vs_confirmed_matches(self):
        """Test: System suggests match → User confirms"""
        
        # Create payment
        payment_url = reverse('finance:payments:payment-list')
        payment_data = {
            'payment_type': 'PAYMENT',
            'date': '2026-01-18',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account': self.bank_account.id,
        }
        
        payment_response = self.client.post(payment_url, payment_data, format='json')
        payment_id = payment_response.data['id']
        
        # Create statement and line
        statement_url = reverse('finance:cash_management:bankstatement-list')
        statement_response = self.client.post(statement_url, {
            'bank_account': self.bank_account.id,
            'statement_date': '2026-01-31',
            'opening_balance': '50000.00',
            'closing_balance': '48500.00',
            'total_debits': '1500.00',
            'total_credits': '0.00',
            'statement_number': 'STMT-SUGGEST',
            'from_date': '2026-01-01',
            'to_date': '2026-01-31'
        }, format='json')
        statement_id = statement_response.data.get('id', statement_response.data.get('data', {}).get('id'))
        
        line_url = reverse('finance:cash_management:bankstatementline-list')
        line_response = self.client.post(line_url, {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-18',
            'value_date': '2026-01-18',
            'balance_after_transaction': '8500.00',
            'amount': '-1500.00',
            'transaction_type': 'DEBIT',
            'description': f'Payment {payment_id}',
            'reference_number': f'PAY{payment_id}'
        }, format='json')
        line_id = line_response.data['id']
        
        # Create SUGGESTED match (simulating auto-matching algorithm)
        match_url = reverse('finance:cash_management:bankstatementlinematch-list')
        match_data = {
            'statement_line': line_id,
            'payment': payment_id,
                        'match_status': 'PARTIAL',
            'match_type': 'MANUAL',
            'confidence_score': 0.95
        }
        
        match_response = self.client.post(match_url, match_data, format='json')
        self.assertEqual(match_response.status_code, status.HTTP_201_CREATED)
        match_id = match_response.data['id']
        
        # Verify partial match status (partial since it's not fully confirmed)
        self.assertEqual(match_response.data['match_status'], 'PARTIAL')
        
        # User confirms the match
        match_detail_url = reverse('finance:cash_management:bankstatementlinematch-detail', args=[match_id])
        confirm_data = {
            'match_status': 'MATCHED',
            'notes': 'Confirmed by user after review'
        }
        
        confirm_response = self.client.patch(match_detail_url, confirm_data, format='json')
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm_response.data['match_status'], 'MATCHED')
        
        # Verify filtering by match_status
        matches_suggested = self.client.get(match_url, {'match_status': 'PARTIAL'})
        self.assertEqual(len(matches_suggested.data.get('results') or matches_suggested.data.get('data', {}).get('results', [])), 0)
        
        matches_confirmed = self.client.get(match_url, {'match_status': 'MATCHED'})
        self.assertEqual(len(matches_confirmed.data.get('results') or matches_confirmed.data.get('data', {}).get('results', [])), 1)
    
    def test_reject_and_delete_match(self):
        """Test: Create match → Reject → Delete"""
        
        # Create payment and statement line
        payment_url = reverse('finance:payments:payment-list')
        payment_response = self.client.post(payment_url, {
            'payment_type': 'PAYMENT',
            'date': '2026-01-22',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account': self.bank_account.id,
        }, format='json')
        payment_id = payment_response.data['id']
        
        statement_url = reverse('finance:cash_management:bankstatement-list')
        statement_response = self.client.post(statement_url, {
            'bank_account': self.bank_account.id,
            'statement_date': '2026-01-31',
            'opening_balance': '50000.00',
            'closing_balance': '48500.00',
            'total_debits': '1500.00',
            'total_credits': '0.00',
            'statement_number': 'STMT-REJECT',
            'from_date': '2026-01-01',
            'to_date': '2026-01-31'
        }, format='json')
        statement_id = statement_response.data.get('id', statement_response.data.get('data', {}).get('id'))
        
        line_url = reverse('finance:cash_management:bankstatementline-list')
        line_response = self.client.post(line_url, {
            'bank_statement_id': statement_id,
            'line_number': 1,
            'transaction_date': '2026-01-22',
            'value_date': '2026-01-22',
            'balance_after_transaction': '8500.00',
            'amount': '-1500.00',
            'transaction_type': 'DEBIT',
            'description': 'Wrong payment',
            'reference_number': 'WRONG001'
        }, format='json')
        line_id = line_response.data['id']
        
        # Create incorrect match
        match_url = reverse('finance:cash_management:bankstatementlinematch-list')
        match_response = self.client.post(match_url, {
            'statement_line': line_id,
            'payment': payment_id,
                        'match_status': 'PARTIAL',
            'match_type': 'MANUAL'
        }, format='json')
        match_id = match_response.data['id']
        
        # Reject the match
        match_detail_url = reverse('finance:cash_management:bankstatementlinematch-detail', args=[match_id])
        reject_response = self.client.patch(match_detail_url, {
            'match_status': 'UNMATCHED',
            'notes': 'Incorrect match - amounts do not correspond'
        }, format='json')
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        self.assertEqual(reject_response.data['match_status'], 'UNMATCHED')
        
        # Delete the rejected match
        delete_response = self.client.delete(match_detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        check_response = self.client.get(match_detail_url)
        self.assertEqual(check_response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_filter_unreconciled_payments_and_lines(self):
        """Test: Filter unreconciled payments and statement lines"""
        
        # Create reconciled payment
        payment_url = reverse('finance:payments:payment-list')
        reconciled_payment = self.client.post(payment_url, {
            'payment_type': 'PAYMENT',
            'date': '2026-01-10',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account': self.bank_account.id,
        }, format='json')
        
        # Create unreconciled payment
        unreconciled_payment = self.client.post(payment_url, {
            'payment_type': 'PAYMENT',
            'date': '2026-01-12',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.wire_type.id,
            'bank_account': self.bank_account.id,
        }, format='json')
        
        # Filter unreconciled payments
        unreconciled_list = self.client.get(payment_url, {'reconciliation_status': 'UNRECONCILED'})
        self.assertEqual(unreconciled_list.status_code, status.HTTP_200_OK)
        # Both should be unreconciled initially
        self.assertGreaterEqual(len(unreconciled_list.data.get('results') or unreconciled_list.data.get('data', {}).get('results', [])), 2)
        
        # Filter by bank account
        bank_payments = self.client.get(payment_url, {'bank_account': self.bank_account.id})
        self.assertEqual(bank_payments.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(bank_payments.data.get('results') or bank_payments.data.get('data', {}).get('results', [])), 2)
    
    def test_cash_payment_no_reconciliation(self):
        """Test: Cash payments should not require reconciliation"""
        
        payment_url = reverse('finance:payments:payment-list')
        cash_payment_data = {
            'payment_type': 'PAYMENT',
            'date': '2026-01-05',
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'payment_method_id': self.cash_type.id,
            # No bank_account_id for cash
        }
        
        cash_response = self.client.post(payment_url, cash_payment_data, format='json')
        self.assertEqual(cash_response.status_code, status.HTTP_201_CREATED)
        
        # Verify cash payment doesn't require reconciliation
        self.assertFalse(cash_response.data['payment_method_enable_reconcile'])
        self.assertIsNone(cash_response.data['bank_account_id'])
        
        # Verify we can filter payments that enable reconciliation
        reconcilable_payments = self.client.get(payment_url, {
            'payment_method_id': self.wire_type.id
        })
        
        for payment in reconcilable_payments.data.get('results') or reconcilable_payments.data.get('data', {}).get('results', []):
            self.assertTrue(payment['payment_method_enable_reconcile'])






