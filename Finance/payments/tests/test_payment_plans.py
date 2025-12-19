"""
Tests for Invoice Payment Plan System

This test suite validates:
1. Payment plan creation and management
2. Installment tracking and status updates
3. Waterfall payment allocation logic
4. Status transitions and calculations
"""

from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from Finance.payments.models import InvoicePaymentPlan, PaymentPlanInstallment
from Finance.Invoice.models import Invoice, AP_Invoice, AR_Invoice
from Finance.BusinessPartner.models import BusinessPartner, Customer, Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry


class PaymentPlanTestCase(TestCase):
    """Base test case with common setup for payment plan tests"""
    
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
        
        # Create customer for AR tests
        self.customer = Customer.objects.create(
            name="Test Customer Co",
            country=self.country
        )
        
        # Create GL journal entry for invoices
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo="Test Entry",
            posted=False
        )
    
    def create_ap_invoice(self, total=3000.00):
        """Helper to create an AP invoice"""
        return AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=total,
            total=total,
            gl_distributions=self.journal_entry
        )
    
    def create_ar_invoice(self, total=3000.00):
        """Helper to create an AR invoice"""
        return AR_Invoice.objects.create(
            customer=self.customer,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=total,
            total=total,
            gl_distributions=self.journal_entry
        )


class PaymentPlanCreationTests(PaymentPlanTestCase):
    """Tests for creating payment plans"""
    
    def test_create_payment_plan_manually(self):
        """Test creating a payment plan with manual installments"""
        invoice = self.create_ap_invoice(total=3000.00)
        
        # Create payment plan
        plan = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=Decimal('3000.00'),
            description="3 monthly payments"
        )
        
        self.assertEqual(plan.status, 'pending')
        self.assertEqual(plan.total_amount, Decimal('3000.00'))
        self.assertEqual(plan.invoice, invoice.invoice)
        
        # Create installments
        for i in range(1, 4):
            PaymentPlanInstallment.objects.create(
                payment_plan=plan,
                installment_number=i,
                due_date=date.today() + relativedelta(months=i-1),
                amount=Decimal('1000.00'),
                description=f"Installment {i} of 3"
            )
        
        self.assertEqual(plan.installments.count(), 3)
    
    def test_suggest_schedule_monthly(self):
        """Test generating a monthly payment schedule suggestion"""
        suggestion = InvoicePaymentPlan.suggest_schedule(
            invoice_total=3000.00,
            start_date=date(2025, 1, 1),
            num_installments=3,
            frequency='monthly'
        )
        
        self.assertEqual(len(suggestion), 3)
        
        # Check first installment
        self.assertEqual(suggestion[0]['installment_number'], 1)
        self.assertEqual(suggestion[0]['due_date'], '2025-01-01')
        self.assertEqual(suggestion[0]['amount'], 1000.00)
        self.assertEqual(suggestion[0]['paid_amount'], 0.00)
        self.assertEqual(suggestion[0]['status'], 'pending')
        
        # Check second installment (one month later)
        self.assertEqual(suggestion[1]['due_date'], '2025-02-01')
        
        # Check third installment (two months later)
        self.assertEqual(suggestion[2]['due_date'], '2025-03-01')
        
        # Check total adds up
        total = sum(inst['amount'] for inst in suggestion)
        self.assertEqual(total, 3000.00)
    
    def test_suggest_schedule_weekly(self):
        """Test generating a weekly payment schedule"""
        suggestion = InvoicePaymentPlan.suggest_schedule(
            invoice_total=1000.00,
            start_date=date(2025, 1, 1),
            num_installments=4,
            frequency='weekly'
        )
        
        self.assertEqual(len(suggestion), 4)
        self.assertEqual(suggestion[0]['due_date'], '2025-01-01')
        self.assertEqual(suggestion[1]['due_date'], '2025-01-08')
        self.assertEqual(suggestion[2]['due_date'], '2025-01-15')
        self.assertEqual(suggestion[3]['due_date'], '2025-01-22')
    
    def test_suggest_schedule_quarterly(self):
        """Test generating a quarterly payment schedule"""
        suggestion = InvoicePaymentPlan.suggest_schedule(
            invoice_total=12000.00,
            start_date=date(2025, 1, 1),
            num_installments=4,
            frequency='quarterly'
        )
        
        self.assertEqual(len(suggestion), 4)
        self.assertEqual(suggestion[0]['due_date'], '2025-01-01')
        self.assertEqual(suggestion[1]['due_date'], '2025-04-01')
        self.assertEqual(suggestion[2]['due_date'], '2025-07-01')
        self.assertEqual(suggestion[3]['due_date'], '2025-10-01')
    
    def test_suggest_schedule_handles_rounding(self):
        """Test that rounding is handled correctly (last installment adjusts)"""
        # Amount that doesn't divide evenly
        suggestion = InvoicePaymentPlan.suggest_schedule(
            invoice_total=1000.00,
            start_date=date(2025, 1, 1),
            num_installments=3,
            frequency='monthly'
        )
        
        # 1000 / 3 = 333.33...
        self.assertEqual(suggestion[0]['amount'], 333.33)
        self.assertEqual(suggestion[1]['amount'], 333.33)
        # Last installment gets the remainder to hit exactly 1000
        self.assertEqual(suggestion[2]['amount'], 333.34)
        
        # Total should be exact
        total = sum(Decimal(str(inst['amount'])) for inst in suggestion)
        self.assertEqual(total, Decimal('1000.00'))
    
    def test_suggest_schedule_invalid_inputs(self):
        """Test that invalid inputs raise ValueError"""
        with self.assertRaises(ValueError):
            InvoicePaymentPlan.suggest_schedule(
                invoice_total=1000.00,
                start_date=date.today(),
                num_installments=0  # Invalid
            )
        
        with self.assertRaises(ValueError):
            InvoicePaymentPlan.suggest_schedule(
                invoice_total=-100.00,  # Invalid
                start_date=date.today(),
                num_installments=3
            )
        
        with self.assertRaises(ValueError):
            InvoicePaymentPlan.suggest_schedule(
                invoice_total=1000.00,
                start_date=date.today(),
                num_installments=3,
                frequency='invalid'  # Invalid frequency
            )
    
    def test_create_from_suggestion(self):
        """Test creating a payment plan from a suggestion"""
        invoice = self.create_ap_invoice(total=3000.00)
        
        suggestion = InvoicePaymentPlan.suggest_schedule(
            invoice_total=3000.00,
            start_date=date(2025, 1, 1),
            num_installments=3,
            frequency='monthly'
        )
        
        # Manual creation from suggestion
        total_amount = sum(Decimal(str(item['amount'])) for item in suggestion)
        plan = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=total_amount,
            description="3 monthly payments for vendor",
            status='pending'
        )
        
        for item in suggestion:
            PaymentPlanInstallment.objects.create(
                payment_plan=plan,
                installment_number=item['installment_number'],
                due_date=item['due_date'],
                amount=Decimal(str(item['amount'])),
                description=item.get('description', ''),
                status='pending',
                paid_amount=Decimal('0.00')
            )
        
        self.assertEqual(plan.total_amount, Decimal('3000.00'))
        self.assertEqual(plan.installments.count(), 3)
        self.assertEqual(plan.status, 'pending')
        self.assertEqual(plan.description, "3 monthly payments for vendor")
        
        # Verify installments were created correctly
        installments = list(plan.installments.all())
        self.assertEqual(installments[0].amount, Decimal('1000.00'))
        self.assertEqual(installments[1].amount, Decimal('1000.00'))
        self.assertEqual(installments[2].amount, Decimal('1000.00'))


class PaymentPlanCalculationTests(PaymentPlanTestCase):
    """Tests for payment plan calculation methods"""
    
    def setUp(self):
        super().setUp()
        
        # Create a payment plan with 3 installments
        invoice = self.create_ap_invoice(total=3000.00)
        self.plan = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=Decimal('3000.00')
        )
        
        for i in range(1, 4):
            PaymentPlanInstallment.objects.create(
                payment_plan=self.plan,
                installment_number=i,
                due_date=date.today() + relativedelta(months=i-1),
                amount=Decimal('1000.00')
            )
    
    def test_get_total_paid_no_payments(self):
        """Test total paid calculation when no payments made"""
        self.assertEqual(self.plan.get_total_paid(), Decimal('0.00'))
    
    def test_get_total_paid_with_payments(self):
        """Test total paid calculation with some payments"""
        installment = self.plan.installments.first()
        installment.paid_amount = Decimal('500.00')
        installment.save()
        
        self.assertEqual(self.plan.get_total_paid(), Decimal('500.00'))
    
    def test_get_remaining_balance(self):
        """Test remaining balance calculation"""
        self.assertEqual(self.plan.get_remaining_balance(), Decimal('3000.00'))
        
        # Make a payment
        installment = self.plan.installments.first()
        installment.paid_amount = Decimal('1000.00')
        installment.save()
        
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.get_remaining_balance(), Decimal('2000.00'))
    
    def test_is_fully_paid(self):
        """Test is_fully_paid check"""
        self.assertFalse(self.plan.is_fully_paid())
        
        # Pay all installments
        for installment in self.plan.installments.all():
            installment.paid_amount = installment.amount
            installment.save()
        
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.is_fully_paid())
    
    def test_has_overdue_installments_none_overdue(self):
        """Test checking for overdue installments when none are overdue"""
        # All installments are in the future
        self.assertFalse(self.plan.has_overdue_installments())
    
    def test_has_overdue_installments_with_overdue(self):
        """Test checking for overdue installments when some are overdue"""
        # Set first installment to past date and unpaid
        installment = self.plan.installments.first()
        installment.due_date = date.today() - timedelta(days=10)
        installment.save()
        
        self.assertTrue(self.plan.has_overdue_installments())
    
    def test_has_overdue_installments_paid_not_overdue(self):
        """Test that paid installments are not considered overdue"""
        # Set first installment to past date but fully paid
        installment = self.plan.installments.first()
        installment.due_date = date.today() - timedelta(days=10)
        installment.paid_amount = installment.amount
        installment.save()
        
        self.assertFalse(self.plan.has_overdue_installments())
    
    def test_get_overdue_installments(self):
        """Test getting list of overdue installments"""
        # Set two installments to past dates
        installments = list(self.plan.installments.all())
        installments[0].due_date = date.today() - timedelta(days=20)
        installments[0].save()
        installments[1].due_date = date.today() - timedelta(days=10)
        installments[1].save()
        
        overdue = list(self.plan.get_overdue_installments())
        self.assertEqual(len(overdue), 2)
        
        # Should be ordered by due_date (oldest first)
        self.assertEqual(overdue[0].installment_number, 1)
        self.assertEqual(overdue[1].installment_number, 2)


class PaymentProcessingTests(PaymentPlanTestCase):
    """Tests for payment processing (waterfall allocation)"""
    
    def setUp(self):
        super().setUp()
        
        # Create a payment plan with 3 installments of $1000 each
        invoice = self.create_ap_invoice(total=3000.00)
        self.plan = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=Decimal('3000.00')
        )
        
        for i in range(1, 4):
            PaymentPlanInstallment.objects.create(
                payment_plan=self.plan,
                installment_number=i,
                due_date=date.today() + relativedelta(months=i-1),
                amount=Decimal('1000.00')
            )
    
    def test_process_payment_exact_single_installment(self):
        """Test processing a payment that exactly pays one installment"""
        result = self.plan.process_payment(Decimal('1000.00'))
        
        self.assertEqual(result['payment_applied'], 1000.00)
        self.assertEqual(result['remaining_payment'], 0.00)
        self.assertEqual(len(result['updated_installments']), 1)
        
        # Check first installment was fully paid
        installment = self.plan.installments.get(installment_number=1)
        self.assertEqual(installment.paid_amount, Decimal('1000.00'))
        self.assertEqual(installment.status, 'paid')
    
    def test_process_payment_partial_installment(self):
        """Test processing a partial payment"""
        result = self.plan.process_payment(Decimal('500.00'))
        
        self.assertEqual(result['payment_applied'], 500.00)
        self.assertEqual(result['remaining_payment'], 0.00)
        self.assertEqual(len(result['updated_installments']), 1)
        
        # Check first installment was partially paid
        installment = self.plan.installments.get(installment_number=1)
        self.assertEqual(installment.paid_amount, Decimal('500.00'))
        self.assertEqual(installment.status, 'partial')
    
    def test_process_payment_multiple_installments(self):
        """Test processing a payment that covers multiple installments"""
        result = self.plan.process_payment(Decimal('2500.00'))
        
        self.assertEqual(result['payment_applied'], 2500.00)
        self.assertEqual(result['remaining_payment'], 0.00)
        self.assertEqual(len(result['updated_installments']), 3)
        
        # Check installments
        inst1 = self.plan.installments.get(installment_number=1)
        inst2 = self.plan.installments.get(installment_number=2)
        inst3 = self.plan.installments.get(installment_number=3)
        
        self.assertEqual(inst1.paid_amount, Decimal('1000.00'))
        self.assertEqual(inst1.status, 'paid')
        
        self.assertEqual(inst2.paid_amount, Decimal('1000.00'))
        self.assertEqual(inst2.status, 'paid')
        
        self.assertEqual(inst3.paid_amount, Decimal('500.00'))
        self.assertEqual(inst3.status, 'partial')
    
    def test_process_payment_full_payment(self):
        """Test processing a payment that pays entire plan"""
        result = self.plan.process_payment(Decimal('3000.00'))
        
        self.assertEqual(result['payment_applied'], 3000.00)
        self.assertEqual(result['remaining_payment'], 0.00)
        self.assertEqual(result['payment_plan_status'], 'paid')
        
        # All installments should be paid
        for installment in self.plan.installments.all():
            self.assertEqual(installment.paid_amount, Decimal('1000.00'))
            self.assertEqual(installment.status, 'paid')
    
    def test_process_payment_overpayment(self):
        """Test processing a payment larger than total (returns leftover)"""
        result = self.plan.process_payment(Decimal('3500.00'))
        
        self.assertEqual(result['payment_applied'], 3000.00)
        self.assertEqual(result['remaining_payment'], 500.00)  # Leftover
        self.assertEqual(result['payment_plan_status'], 'paid')
    
    def test_process_payment_waterfall_order(self):
        """Test that payments are applied in chronological order (oldest first)"""
        # Set different due dates to test ordering
        installments = list(self.plan.installments.all())
        installments[0].due_date = date(2025, 3, 1)
        installments[0].save()
        installments[1].due_date = date(2025, 1, 1)  # Oldest
        installments[1].save()
        installments[2].due_date = date(2025, 2, 1)
        installments[2].save()
        
        # Process partial payment
        result = self.plan.process_payment(Decimal('1500.00'))
        
        # Should pay installment #2 first (oldest), then partial on #3
        inst1 = self.plan.installments.get(installment_number=1)
        inst2 = self.plan.installments.get(installment_number=2)
        inst3 = self.plan.installments.get(installment_number=3)
        
        self.assertEqual(inst2.paid_amount, Decimal('1000.00'))  # Oldest - paid first
        self.assertEqual(inst3.paid_amount, Decimal('500.00'))   # Second oldest
        self.assertEqual(inst1.paid_amount, Decimal('0.00'))     # Newest - untouched
    
    def test_process_payment_incremental(self):
        """Test multiple incremental payments"""
        # First payment
        self.plan.process_payment(Decimal('800.00'))
        inst1 = self.plan.installments.get(installment_number=1)
        self.assertEqual(inst1.paid_amount, Decimal('800.00'))
        
        # Second payment
        self.plan.refresh_from_db()
        self.plan.process_payment(Decimal('700.00'))
        inst1.refresh_from_db()
        inst2 = self.plan.installments.get(installment_number=2)
        self.assertEqual(inst1.paid_amount, Decimal('1000.00'))  # Completed
        self.assertEqual(inst2.paid_amount, Decimal('500.00'))   # Partial
    
    def test_process_payment_invalid_amount(self):
        """Test that invalid payment amounts raise errors"""
        with self.assertRaises(ValidationError):
            self.plan.process_payment(Decimal('0.00'))
        
        with self.assertRaises(ValidationError):
            self.plan.process_payment(Decimal('-100.00'))


class PaymentPlanStatusTests(PaymentPlanTestCase):
    """Tests for payment plan status transitions"""
    
    def setUp(self):
        super().setUp()
        
        invoice = self.create_ap_invoice(total=3000.00)
        self.plan = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=Decimal('3000.00')
        )
        
        for i in range(1, 4):
            PaymentPlanInstallment.objects.create(
                payment_plan=self.plan,
                installment_number=i,
                due_date=date.today() + relativedelta(months=i-1),
                amount=Decimal('1000.00')
            )
    
    def test_initial_status_pending(self):
        """Test that new payment plans start with 'pending' status"""
        self.assertEqual(self.plan.status, 'pending')
    
    def test_update_status_to_partial(self):
        """Test status changes to 'partial' after first payment"""
        # Make a partial payment
        installment = self.plan.installments.first()
        installment.paid_amount = Decimal('500.00')
        installment.save()
        
        self.plan.update_status()
        self.assertEqual(self.plan.status, 'partial')
    
    def test_update_status_to_paid(self):
        """Test status changes to 'paid' when all installments paid"""
        # Pay all installments
        for installment in self.plan.installments.all():
            installment.paid_amount = installment.amount
            installment.save()
        
        self.plan.update_status()
        self.assertEqual(self.plan.status, 'paid')
    
    def test_update_status_to_overdue(self):
        """Test status changes to 'overdue' when installments are overdue"""
        # Set first installment to past and unpaid
        installment = self.plan.installments.first()
        installment.due_date = date.today() - timedelta(days=10)
        installment.save()
        
        self.plan.update_status()
        self.assertEqual(self.plan.status, 'overdue')
    
    def test_update_status_cancelled_not_changed(self):
        """Test that cancelled status is not changed by update_status()"""
        self.plan.status = 'cancelled'
        self.plan.save()
        
        # Try to update status
        self.plan.update_status()
        self.assertEqual(self.plan.status, 'cancelled')


class InstallmentTests(PaymentPlanTestCase):
    """Tests for individual installment functionality"""
    
    def setUp(self):
        super().setUp()
        
        invoice = self.create_ap_invoice(total=1000.00)
        self.plan = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=Decimal('1000.00')
        )
        
        self.installment = PaymentPlanInstallment.objects.create(
            payment_plan=self.plan,
            installment_number=1,
            due_date=date.today() + timedelta(days=30),
            amount=Decimal('1000.00')
        )
    
    def test_get_remaining_balance(self):
        """Test remaining balance calculation"""
        self.assertEqual(self.installment.get_remaining_balance(), Decimal('1000.00'))
        
        self.installment.paid_amount = Decimal('400.00')
        self.installment.save()
        
        self.assertEqual(self.installment.get_remaining_balance(), Decimal('600.00'))
    
    def test_is_fully_paid(self):
        """Test is_fully_paid check"""
        self.assertFalse(self.installment.is_fully_paid())
        
        self.installment.paid_amount = Decimal('1000.00')
        self.installment.save()
        
        self.assertTrue(self.installment.is_fully_paid())
    
    def test_is_overdue_future_date(self):
        """Test that future installments are not overdue"""
        self.installment.due_date = date.today() + timedelta(days=30)
        self.installment.save()
        
        self.assertFalse(self.installment.is_overdue())
    
    def test_is_overdue_past_date_unpaid(self):
        """Test that past unpaid installments are overdue"""
        self.installment.due_date = date.today() - timedelta(days=10)
        self.installment.save()
        
        self.assertTrue(self.installment.is_overdue())
    
    def test_is_overdue_past_date_paid(self):
        """Test that past paid installments are not overdue"""
        self.installment.due_date = date.today() - timedelta(days=10)
        self.installment.paid_amount = Decimal('1000.00')
        self.installment.save()
        
        self.assertFalse(self.installment.is_overdue())
    
    def test_update_status_paid(self):
        """Test status update to 'paid'"""
        self.installment.paid_amount = Decimal('1000.00')
        self.installment.save()
        
        self.installment.update_status()
        self.assertEqual(self.installment.status, 'paid')
    
    def test_update_status_partial(self):
        """Test status update to 'partial'"""
        self.installment.paid_amount = Decimal('500.00')
        self.installment.save()
        
        self.installment.update_status()
        self.assertEqual(self.installment.status, 'partial')
    
    def test_update_status_overdue(self):
        """Test status update to 'overdue'"""
        self.installment.due_date = date.today() - timedelta(days=10)
        self.installment.save()
        
        self.installment.update_status()
        self.assertEqual(self.installment.status, 'overdue')
    
    def test_update_status_pending(self):
        """Test status remains 'pending' when no payment"""
        self.installment.update_status()
        self.assertEqual(self.installment.status, 'pending')
    
    def test_validation_paid_exceeds_amount(self):
        """Test that paid_amount cannot exceed amount"""
        self.installment.paid_amount = Decimal('1500.00')
        
        with self.assertRaises(ValidationError):
            self.installment.save()
    
    def test_validation_negative_paid_amount(self):
        """Test that paid_amount cannot be negative"""
        self.installment.paid_amount = Decimal('-100.00')
        
        with self.assertRaises(ValidationError):
            self.installment.save()
    
    def test_validation_zero_amount(self):
        """Test that amount must be greater than zero"""
        with self.assertRaises(ValidationError):
            PaymentPlanInstallment.objects.create(
                payment_plan=self.plan,
                installment_number=2,
                due_date=date.today(),
                amount=Decimal('0.00')
            )
    
    def test_unique_installment_number_per_plan(self):
        """Test that installment numbers must be unique per payment plan"""
        # Try to create another installment with the same number
        with self.assertRaises(Exception):  # Will raise IntegrityError
            PaymentPlanInstallment.objects.create(
                payment_plan=self.plan,
                installment_number=1,  # Duplicate
                due_date=date.today(),
                amount=Decimal('1000.00')
            )


class PaymentPlanIntegrationTests(PaymentPlanTestCase):
    """Integration tests for complete payment plan workflows"""
    
    def test_complete_payment_plan_workflow(self):
        """Test a complete payment plan workflow from creation to completion"""
        # 1. Create invoice
        invoice = self.create_ap_invoice(total=5000.00)
        
        # 2. Generate payment schedule suggestion (use future dates)
        from django.utils import timezone
        future_date = timezone.now().date() + timedelta(days=30)
        
        suggestion = InvoicePaymentPlan.suggest_schedule(
            invoice_total=5000.00,
            start_date=future_date,
            num_installments=5,
            frequency='monthly'
        )
        
        # 3. Create payment plan from suggestion
        # 3. Create payment plan from suggestion manually
        total_amount = sum(Decimal(str(item['amount'])) for item in suggestion)
        plan = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=total_amount,
            description="5 monthly installments",
            status='pending'
        )
        
        for item in suggestion:
            PaymentPlanInstallment.objects.create(
                payment_plan=plan,
                installment_number=item['installment_number'],
                due_date=item['due_date'],
                amount=Decimal(str(item['amount'])),
                description=item.get('description', ''),
                status='pending',
                paid_amount=Decimal('0.00')
            )
        
        self.assertEqual(plan.status, 'pending')
        self.assertEqual(plan.installments.count(), 5)
        
        # 4. Make first payment (partial)
        result1 = plan.process_payment(Decimal('800.00'))
        self.assertEqual(result1['payment_applied'], 800.00)
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'partial')
        
        # 5. Make second payment (completes first installment and part of second)
        result2 = plan.process_payment(Decimal('700.00'))
        self.assertEqual(result2['payment_applied'], 700.00)
        
        # 6. Pay off remaining installments
        remaining = plan.get_remaining_balance()
        result3 = plan.process_payment(remaining)
        
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'paid')
        self.assertTrue(plan.is_fully_paid())
        self.assertEqual(plan.get_remaining_balance(), Decimal('0.00'))
    
    def test_multiple_payment_plans_per_invoice(self):
        """Test that an invoice can have multiple payment plans (if needed)"""
        invoice = self.create_ap_invoice(total=10000.00)
        
        # Create first payment plan
        plan1 = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=Decimal('5000.00'),
            description="First plan"
        )
        
        # Create second payment plan
        plan2 = InvoicePaymentPlan.objects.create(
            invoice=invoice.invoice,
            total_amount=Decimal('5000.00'),
            description="Second plan"
        )
        
        # Both should exist
        self.assertEqual(invoice.invoice.payment_plans.count(), 2)


class PaymentPlanAPITestCase(APITestCase):
    """Test suite for Payment Plan API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            name="US Dollar",
            code="USD",
            symbol="$",
            is_base_currency=True
        )
        self.country = Country.objects.create(
            name="United States",
            code="US"
        )
        self.supplier = Supplier.objects.create(
            name="Test Supplier",
            country=self.country
        )
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo="Test Entry",
            posted=False
        )
        
        self.ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('3000.00'),
            total=Decimal('3000.00'),
            gl_distributions=self.journal_entry
        )
        self.invoice = self.ap_invoice.invoice
        
        # Helper to create a plan
        self.create_plan_url = reverse(
            'finance:payments:invoice-payment-plans-list',
            kwargs={'invoice_pk': self.invoice.id}
        )

    def test_create_payment_plan(self):
        """Test creating a payment plan via API"""
        data = {
            'total_amount': '3000.00',
            'description': 'Test Plan',
            'installments': [
                {
                    'installment_number': 1,
                    'due_date': str(date.today() + timedelta(days=30)),
                    'amount': '1000.00'
                },
                {
                    'installment_number': 2,
                    'due_date': str(date.today() + timedelta(days=60)),
                    'amount': '1000.00'
                },
                {
                    'installment_number': 3,
                    'due_date': str(date.today() + timedelta(days=90)),
                    'amount': '1000.00'
                }
            ]
        }
        
        response = self.client.post(self.create_plan_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(InvoicePaymentPlan.objects.count(), 1)
        self.assertEqual(PaymentPlanInstallment.objects.count(), 3)
        
        plan_id = response.data['id']
        plan = InvoicePaymentPlan.objects.get(id=plan_id)
        self.assertEqual(plan.total_amount, Decimal('3000.00'))
        self.assertEqual(plan.status, 'pending')

    def test_create_payment_plan_validation_error(self):
        """Test validation: sum of installments must equal total"""
        data = {
            'total_amount': '3000.00',
            'installments': [
                {
                    'installment_number': 1,
                    'due_date': str(date.today()),
                    'amount': '1000.00'
                }
            ]
        }
        
        response = self.client.post(self.create_plan_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suggest_payment_plan(self):
        """Test suggestion endpoint"""
        url = reverse(
            'finance:payments:invoice-suggest-payment-plan',
            kwargs={'invoice_pk': self.invoice.id}
        )
        data = {
            'start_date': str(date.today()),
            'num_installments': 3,
            'frequency': 'monthly'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['suggested_installments']), 3)
        self.assertEqual(response.data['invoice_total'], '3000.00')

    def test_process_payment(self):
        """Test processing a payment"""
        # Create plan first
        plan = InvoicePaymentPlan.objects.create(
            invoice=self.invoice,
            total_amount=Decimal('3000.00')
        )
        PaymentPlanInstallment.objects.create(
            payment_plan=plan,
            installment_number=1,
            due_date=date.today(),
            amount=Decimal('1000.00')
        )
        
        url = reverse('finance:payments:payment-plan-process-payment', kwargs={'pk': plan.id})
        data = {'payment_amount': '500.00'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment_applied'], 500.0)
        
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'partial')
        self.assertEqual(plan.installments.first().paid_amount, Decimal('500.00'))

    def test_get_payment_plan_summary(self):
        """Test summary endpoint"""
        plan = InvoicePaymentPlan.objects.create(
            invoice=self.invoice,
            total_amount=Decimal('3000.00')
        )
        
        url = reverse('finance:payments:payment-plan-summary', kwargs={'pk': plan.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('3000.00'))
        self.assertEqual(Decimal(response.data['total_paid']), Decimal('0.00'))

    def test_cancel_payment_plan(self):
        """Test cancelling a plan"""
        plan = InvoicePaymentPlan.objects.create(
            invoice=self.invoice,
            total_amount=Decimal('3000.00')
        )
        
        url = reverse('finance:payments:payment-plan-cancel', kwargs={'pk': plan.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plan.refresh_from_db()
        self.assertEqual(plan.status, 'cancelled')

    def test_list_overdue_payment_plans(self):
        """Test listing overdue payment plans (Regression test for NameError)"""
        # Create a plan with an overdue installment
        plan = InvoicePaymentPlan.objects.create(
            invoice=self.invoice,
            total_amount=Decimal('3000.00'),
            description="Overdue Plan"
        )
        PaymentPlanInstallment.objects.create(
            payment_plan=plan,
            installment_number=1,
            due_date=date.today() - timedelta(days=5), # Past due
            amount=Decimal('1000.00'),
            paid_amount=Decimal('0.00')
        )
        
        url = reverse('finance:payments:payment-plans-overdue-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check standard response structure from auto_paginate
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['id'], plan.id)

    def test_overdue_installments(self):
        """Test overdue installments list"""
        plan = InvoicePaymentPlan.objects.create(
            invoice=self.invoice,
            total_amount=Decimal('3000.00')
        )
        # Past due installment
        PaymentPlanInstallment.objects.create(
            payment_plan=plan,
            installment_number=1,
            due_date=date.today() - timedelta(days=10),
            amount=Decimal('1000.00')
        )
        
        url = reverse('finance:payments:payment-plan-overdue-installments', kwargs={'pk': plan.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['overdue_installments']), 1)
