"""
Tests for Payment Utility Functions

This test suite validates utility functions in Finance.payments.utils,
specifically the process_invoice_payment_to_plan function that applies
payments to payment plan installments.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

from Finance.payments.models import InvoicePaymentPlan, PaymentPlanInstallment
from Finance.payments.utils import process_invoice_payment_to_plan
from Finance.Invoice.models import Invoice, AP_Invoice
from Finance.BusinessPartner.models import Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry


class ProcessInvoicePaymentToPlanTestCase(TestCase):
    """Tests for process_invoice_payment_to_plan utility function"""
    
    def setUp(self):
        """Set up test data"""
        # Create currency
        self.currency = Currency.objects.create(
            name="US Dollar",
            code="USD",
            symbol="$",
            is_base_currency=True
        )
        
        # Create country
        self.country = Country.objects.create(
            name="United States",
            code="US"
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            name="Test Supplier Co",
            country=self.country
        )
        
        # Create GL journal entry for invoices
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo="Test Entry",
            posted=False
        )
    
    def create_invoice_with_payment_plan(self, total=3000.00, num_installments=3):
        """Helper to create an invoice with a payment plan"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=total,
            total=total,
            gl_distributions=self.journal_entry
        )
        
        # Create payment plan on the base Invoice model
        plan = InvoicePaymentPlan.objects.create(
            invoice=ap_invoice.invoice,
            total_amount=Decimal(str(total)),
            status='pending',
            description='Test payment plan'
        )
        
        # Create installments
        installment_amount = Decimal(str(total)) / num_installments
        for i in range(1, num_installments + 1):
            due_date = date.today() + relativedelta(months=i-1)
            
            # Last installment gets any remaining amount due to rounding
            if i == num_installments:
                amount = Decimal(str(total)) - (installment_amount * (num_installments - 1))
            else:
                amount = installment_amount
            
            PaymentPlanInstallment.objects.create(
                payment_plan=plan,
                installment_number=i,
                due_date=due_date,
                amount=amount.quantize(Decimal('0.01')),
                paid_amount=Decimal('0.00'),
                status='pending'
            )
        
        return ap_invoice.invoice, plan
    
    def test_process_payment_to_plan_full_payment(self):
        """Test applying payment that fully pays all installments"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Apply full payment
        result = process_invoice_payment_to_plan(invoice, Decimal('3000.00'))
        
        # Verify result structure
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['invoice_id'], invoice.id)
        self.assertEqual(result['payment_plan_id'], plan.id)
        self.assertEqual(result['allocation_amount'], 3000.00)
        self.assertEqual(result['payment_plan_status'], 'paid')
        self.assertEqual(len(result['updated_installments']), 3)
        
        # Verify all installments are paid
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'paid')
        self.assertEqual(plan.get_remaining_balance(), Decimal('0.00'))
        
        for installment in plan.installments.all():
            self.assertEqual(installment.status, 'paid')
            self.assertEqual(installment.paid_amount, installment.amount)
    
    def test_process_payment_to_plan_partial_payment(self):
        """Test applying payment that partially pays installments"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Apply partial payment (1500 - should pay first installment fully and second partially)
        result = process_invoice_payment_to_plan(invoice, Decimal('1500.00'))
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['payment_plan_status'], 'partial')
        self.assertEqual(len(result['updated_installments']), 2)
        
        # Verify installment states
        plan.refresh_from_db()
        installments = list(plan.installments.order_by('installment_number'))
        
        # First installment should be fully paid
        self.assertEqual(installments[0].status, 'paid')
        self.assertEqual(installments[0].paid_amount, installments[0].amount)
        
        # Second installment should be partially paid
        self.assertEqual(installments[1].status, 'partial')
        self.assertGreater(installments[1].paid_amount, Decimal('0.00'))
        self.assertLess(installments[1].paid_amount, installments[1].amount)
        
        # Third installment should be unpaid
        self.assertEqual(installments[2].status, 'pending')
        self.assertEqual(installments[2].paid_amount, Decimal('0.00'))
    
    def test_process_payment_to_plan_single_installment(self):
        """Test applying payment to first installment only"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Apply payment for exactly one installment
        result = process_invoice_payment_to_plan(invoice, Decimal('1000.00'))
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['updated_installments']), 1)
        
        # Verify only first installment is paid
        plan.refresh_from_db()
        installments = list(plan.installments.order_by('installment_number'))
        
        self.assertEqual(installments[0].status, 'paid')
        self.assertEqual(installments[1].status, 'pending')
        self.assertEqual(installments[2].status, 'pending')
    
    def test_process_payment_to_plan_waterfall_allocation(self):
        """Test that payments are applied to installments in chronological order (waterfall)"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Make first payment
        result1 = process_invoice_payment_to_plan(invoice, Decimal('800.00'))
        
        # Verify first installment is partially paid
        installments = list(plan.installments.order_by('installment_number'))
        self.assertEqual(installments[0].paid_amount, Decimal('800.00'))
        self.assertEqual(installments[1].paid_amount, Decimal('0.00'))
        
        # Make second payment - should complete first installment and start second
        result2 = process_invoice_payment_to_plan(invoice, Decimal('700.00'))
        
        # Refresh installments
        for inst in installments:
            inst.refresh_from_db()
        
        # First should be fully paid
        self.assertEqual(installments[0].status, 'paid')
        self.assertEqual(installments[0].paid_amount, installments[0].amount)
        
        # Second should have the overflow from first payment
        expected_second = Decimal('700.00') - (installments[0].amount - Decimal('800.00'))
        self.assertEqual(installments[1].paid_amount, expected_second)
    
    def test_process_payment_no_payment_plan(self):
        """Test applying payment to invoice without payment plan (should skip)"""
        # Create invoice WITHOUT payment plan
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=3000.00,
            total=3000.00,
            gl_distributions=self.journal_entry
        )
        
        # Apply payment to base Invoice
        result = process_invoice_payment_to_plan(ap_invoice.invoice, Decimal('1000.00'))
        
        # Verify it was skipped
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'No active payment plan')
        self.assertNotIn('payment_plan_id', result)
        self.assertNotIn('updated_installments', result)
    
    def test_process_payment_to_cancelled_plan(self):
        """Test applying payment to invoice with cancelled payment plan (should skip)"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Cancel the payment plan
        plan.status = 'cancelled'
        plan.save()
        
        # Apply payment
        result = process_invoice_payment_to_plan(invoice, Decimal('1000.00'))
        
        # Verify it was skipped (cancelled plans are not "active")
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'No active payment plan')
    
    def test_process_payment_to_already_paid_plan(self):
        """Test applying payment to invoice with already-paid payment plan (should skip)"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Mark plan as paid
        plan.status = 'paid'
        plan.save()
        
        # Try to apply payment
        result = process_invoice_payment_to_plan(invoice, Decimal('1000.00'))
        
        # Verify it was skipped
        self.assertEqual(result['status'], 'skipped')
    
    def test_process_payment_atomic_transaction(self):
        """Test that payment processing is atomic (all-or-nothing)"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Get initial state
        initial_paid_amounts = [
            inst.paid_amount for inst in plan.installments.order_by('installment_number')
        ]
        
        # Apply payment within transaction
        with transaction.atomic():
            result = process_invoice_payment_to_plan(invoice, Decimal('1500.00'))
            
            # Verify changes were made
            plan.refresh_from_db()
            self.assertGreater(plan.get_total_paid(), Decimal('0.00'))
        
        # Verify changes persisted after transaction commit
        plan.refresh_from_db()
        self.assertEqual(plan.get_total_paid(), Decimal('1500.00'))
    
    def test_process_payment_zero_amount(self):
        """Test that zero payment amount raises ValidationError"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Try to apply zero payment
        with self.assertRaises(ValidationError) as context:
            process_invoice_payment_to_plan(invoice, Decimal('0.00'))
        
        self.assertIn('must be greater than zero', str(context.exception))
    
    def test_process_payment_negative_amount(self):
        """Test that negative payment amount raises ValidationError"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Try to apply negative payment
        with self.assertRaises(ValidationError) as context:
            process_invoice_payment_to_plan(invoice, Decimal('-100.00'))
        
        self.assertIn('must be greater than zero', str(context.exception))
    
    def test_process_payment_overpayment(self):
        """Test applying payment larger than remaining balance"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Apply overpayment
        result = process_invoice_payment_to_plan(invoice, Decimal('5000.00'))
        
        # Verify all installments are paid, but no more
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'paid')
        self.assertEqual(plan.get_total_paid(), Decimal('3000.00'))
        
        # Verify result structure includes remaining_payment
        self.assertIn('remaining_payment', result)
        self.assertEqual(result['remaining_payment'], 2000.00)  # 5000 - 3000
        self.assertEqual(result['payment_applied'], 3000.00)
    
    def test_process_payment_updates_plan_status(self):
        """Test that payment processing correctly updates payment plan status"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        # Initially pending
        self.assertEqual(plan.status, 'pending')
        
        # Apply partial payment
        process_invoice_payment_to_plan(invoice, Decimal('1000.00'))
        plan.refresh_from_db()
        self.assertIn(plan.status, ['partial', 'paid'])
        
        # Apply remaining payment
        process_invoice_payment_to_plan(invoice, Decimal('2000.00'))
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'paid')
    
    def test_process_payment_result_structure(self):
        """Test that result dict has correct structure for success case"""
        invoice, plan = self.create_invoice_with_payment_plan(total=3000.00, num_installments=3)
        
        result = process_invoice_payment_to_plan(invoice, Decimal('1000.00'))
        
        # Verify required keys
        self.assertIn('invoice_id', result)
        self.assertIn('payment_plan_id', result)
        self.assertIn('allocation_amount', result)
        self.assertIn('status', result)
        self.assertIn('payment_plan_status', result)
        self.assertIn('updated_installments', result)
        
        # Verify types
        self.assertIsInstance(result['invoice_id'], int)
        self.assertIsInstance(result['payment_plan_id'], int)
        self.assertIsInstance(result['allocation_amount'], float)
        self.assertIsInstance(result['status'], str)
        self.assertIsInstance(result['updated_installments'], list)
    
    def test_process_payment_result_structure_skipped(self):
        """Test that result dict has correct structure for skipped case"""
        # Create invoice without payment plan
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=3000.00,
            total=3000.00,
            gl_distributions=self.journal_entry
        )
        
        result = process_invoice_payment_to_plan(ap_invoice.invoice, Decimal('1000.00'))
        
        # Verify required keys for skipped case
        self.assertIn('invoice_id', result)
        self.assertIn('allocation_amount', result)
        self.assertIn('status', result)
        self.assertIn('reason', result)
        self.assertEqual(result['status'], 'skipped')
        
        # Verify success-specific keys are NOT present
        self.assertNotIn('payment_plan_id', result)
        self.assertNotIn('updated_installments', result)
