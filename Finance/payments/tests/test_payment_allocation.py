"""
Tests for Payment Allocation Management System

This test suite validates the synchronization between Payment, PaymentAllocation, 
and Invoice.paid_amount fields.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from datetime import date

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import Invoice, AP_Invoice, AR_Invoice
from Finance.BusinessPartner.models import BusinessPartner, Customer, Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry


class PaymentAllocationTestCase(TestCase):
    """Test case for Payment Allocation functionality"""
    
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
    
    def create_ap_invoice(self, total=1000.00):
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
    
    def create_ar_invoice(self, total=1000.00):
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
    
    def create_payment(self, business_partner):
        """Helper to create a payment"""
        return Payment.objects.create(
            date=date.today(),
            business_partner=business_partner,
            currency=self.currency,
            exchange_rate=1.0000
        )
    
    # ==================== CREATION TESTS ====================
    
    def test_create_allocation_updates_paid_amount(self):
        """Test that creating an allocation updates invoice paid_amount"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        # Initially unpaid
        self.assertEqual(invoice.invoice.paid_amount, Decimal('0'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.UNPAID)
        
        # Create allocation
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('300.00')
        )
        
        # Refresh invoice
        invoice.invoice.refresh_from_db()
        
        # Check paid_amount updated
        self.assertEqual(invoice.invoice.paid_amount, Decimal('300.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PARTIALLY_PAID)
    
    def test_create_full_payment_allocation(self):
        """Test full payment allocation"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        # Create full payment allocation
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('1000.00')
        )
        
        # Refresh invoice
        invoice.invoice.refresh_from_db()
        
        # Check fully paid
        self.assertEqual(invoice.invoice.paid_amount, Decimal('1000.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PAID)
        self.assertTrue(invoice.invoice.is_paid())
    
    def test_create_multiple_allocations(self):
        """Test multiple partial allocations"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment1 = self.create_payment(self.supplier.business_partner)
        payment2 = self.create_payment(self.supplier.business_partner)
        
        # Create first allocation
        PaymentAllocation.objects.create(
            payment=payment1,
            invoice=invoice.invoice,
            amount_allocated=Decimal('400.00')
        )
        
        # Refresh and check
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('400.00'))
        
        # Create second allocation
        PaymentAllocation.objects.create(
            payment=payment2,
            invoice=invoice.invoice,
            amount_allocated=Decimal('600.00')
        )
        
        # Refresh and check fully paid
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('1000.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PAID)
    
    # ==================== UPDATE TESTS ====================
    
    def test_update_allocation_updates_paid_amount(self):
        """Test that updating allocation amount updates paid_amount"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        # Create allocation
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('300.00')
        )
        
        # Update allocation
        allocation.amount_allocated = Decimal('500.00')
        allocation.save()
        
        # Refresh and check
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
    
    def test_increase_allocation_amount(self):
        """Test increasing allocation amount"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('200.00')
        )
        
        # Increase
        allocation.amount_allocated = Decimal('800.00')
        allocation.save()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('800.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PARTIALLY_PAID)
    
    def test_decrease_allocation_amount(self):
        """Test decreasing allocation amount"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('800.00')
        )
        
        # Decrease
        allocation.amount_allocated = Decimal('300.00')
        allocation.save()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('300.00'))
    
    # ==================== DELETE TESTS ====================
    
    def test_delete_allocation_updates_paid_amount(self):
        """Test that deleting allocation decreases paid_amount"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
        
        # Delete allocation
        allocation.delete()
        
        # Refresh and check
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('0'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.UNPAID)
    
    def test_delete_one_of_multiple_allocations(self):
        """Test deleting one allocation when multiple exist"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment1 = self.create_payment(self.supplier.business_partner)
        payment2 = self.create_payment(self.supplier.business_partner)
        
        alloc1 = PaymentAllocation.objects.create(
            payment=payment1,
            invoice=invoice.invoice,
            amount_allocated=Decimal('300.00')
        )
        
        alloc2 = PaymentAllocation.objects.create(
            payment=payment2,
            invoice=invoice.invoice,
            amount_allocated=Decimal('400.00')
        )
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('700.00'))
        
        # Delete first allocation
        alloc1.delete()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('400.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PARTIALLY_PAID)
    
    # ==================== VALIDATION TESTS ====================
    
    def test_allocation_amount_must_be_positive(self):
        """Test that allocation amount must be positive"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        with self.assertRaises(ValidationError) as context:
            allocation = PaymentAllocation(
                payment=payment,
                invoice=invoice.invoice,
                amount_allocated=Decimal('-100.00')
            )
            allocation.full_clean()
        
        self.assertIn('amount_allocated', str(context.exception))
    
    def test_allocation_cannot_exceed_invoice_total(self):
        """Test that allocation cannot exceed remaining invoice balance"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        with self.assertRaises(ValidationError) as context:
            allocation = PaymentAllocation(
                payment=payment,
                invoice=invoice.invoice,
                amount_allocated=Decimal('1500.00')
            )
            allocation.full_clean()
        
        self.assertIn('amount_allocated', str(context.exception))
    
    def test_total_allocations_cannot_exceed_invoice_total(self):
        """Test that total allocations cannot exceed invoice total"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment1 = self.create_payment(self.supplier.business_partner)
        payment2 = self.create_payment(self.supplier.business_partner)
        
        # First allocation
        PaymentAllocation.objects.create(
            payment=payment1,
            invoice=invoice.invoice,
            amount_allocated=Decimal('700.00')
        )
        
        # Second allocation should fail
        with self.assertRaises(ValidationError) as context:
            allocation = PaymentAllocation(
                payment=payment2,
                invoice=invoice.invoice,
                amount_allocated=Decimal('500.00')
            )
            allocation.full_clean()
        
        self.assertIn('amount_allocated', str(context.exception))
    
    def test_currency_mismatch_validation(self):
        """Test that payment and invoice currencies must match"""
        # Create different currency
        eur_currency = Currency.objects.create(
            name="Euro",
            code="EUR",
            symbol="€",
            is_base_currency=False
        )
        
        invoice = self.create_ap_invoice(total=1000.00)
        payment = Payment.objects.create(
            date=date.today(),
            business_partner=self.supplier.business_partner,
            currency=eur_currency,
            exchange_rate=1.0000
        )
        
        with self.assertRaises(ValidationError) as context:
            allocation = PaymentAllocation(
                payment=payment,
                invoice=invoice.invoice,
                amount_allocated=Decimal('500.00')
            )
            allocation.full_clean()
        
        self.assertIn('currency', str(context.exception).lower())
    
    def test_business_partner_mismatch_validation(self):
        """Test that payment and invoice business partners must match"""
        invoice = self.create_ap_invoice(total=1000.00)
        
        # Create different supplier (different business partner)
        other_supplier = Supplier.objects.create(
            name="Other Supplier",
            country=self.country
        )
        payment = self.create_payment(other_supplier.business_partner)
        
        with self.assertRaises(ValidationError) as context:
            allocation = PaymentAllocation(
                payment=payment,
                invoice=invoice.invoice,
                amount_allocated=Decimal('500.00')
            )
            allocation.full_clean()
        
        self.assertIn('business partner', str(context.exception).lower())
    
    # ==================== HELPER METHODS TESTS ====================
    
    def test_payment_get_total_allocated(self):
        """Test Payment.get_total_allocated() method"""
        invoice1 = self.create_ap_invoice(total=1000.00)
        invoice2 = self.create_ap_invoice(total=800.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice1.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice2.invoice,
            amount_allocated=Decimal('300.00')
        )
        
        total = payment.get_total_allocated()
        self.assertEqual(total, Decimal('800.00'))
    
    def test_payment_allocate_to_invoice(self):
        """Test Payment.allocate_to_invoice() helper method"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        allocation = payment.allocate_to_invoice(invoice.invoice, Decimal('400.00'))
        
        self.assertIsNotNone(allocation)
        self.assertEqual(allocation.amount_allocated, Decimal('400.00'))
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('400.00'))
    
    def test_payment_remove_allocation(self):
        """Test Payment.remove_allocation() helper method"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        payment.allocate_to_invoice(invoice.invoice, Decimal('400.00'))
        
        result = payment.remove_allocation(invoice.invoice)
        
        self.assertTrue(result)
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('0'))
    
    def test_payment_clear_all_allocations(self):
        """Test Payment.clear_all_allocations() helper method"""
        invoice1 = self.create_ap_invoice(total=1000.00)
        invoice2 = self.create_ap_invoice(total=800.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        payment.allocate_to_invoice(invoice1.invoice, Decimal('500.00'))
        payment.allocate_to_invoice(invoice2.invoice, Decimal('300.00'))
        
        count = payment.clear_all_allocations()
        
        self.assertEqual(count, 2)
        
        invoice1.invoice.refresh_from_db()
        invoice2.invoice.refresh_from_db()
        
        self.assertEqual(invoice1.invoice.paid_amount, Decimal('0'))
        self.assertEqual(invoice2.invoice.paid_amount, Decimal('0'))
    
    def test_invoice_recalculate_paid_amount(self):
        """Test Invoice.recalculate_paid_amount() method"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('600.00')
        )
        
        # Manually corrupt paid_amount
        invoice.invoice.paid_amount = Decimal('999.99')
        invoice.invoice._allow_direct_save = True
        invoice.invoice.save()
        
        # Recalculate
        old, new, changed = invoice.invoice.recalculate_paid_amount()
        
        self.assertTrue(changed)
        self.assertEqual(old, Decimal('999.99'))
        self.assertEqual(new, Decimal('600.00'))
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('600.00'))
    
    def test_invoice_validate_paid_amount(self):
        """Test Invoice.validate_paid_amount() method"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('600.00')
        )
        
        is_valid, expected, actual, diff = invoice.invoice.validate_paid_amount()
        
        self.assertTrue(is_valid)
        self.assertEqual(expected, Decimal('600.00'))
        self.assertEqual(actual, Decimal('600.00'))
        self.assertEqual(diff, Decimal('0'))
    
    def test_invoice_get_payment_allocations_summary(self):
        """Test Invoice.get_payment_allocations_summary() method"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment1 = self.create_payment(self.supplier.business_partner)
        payment2 = self.create_payment(self.supplier.business_partner)
        
        PaymentAllocation.objects.create(
            payment=payment1,
            invoice=invoice.invoice,
            amount_allocated=Decimal('400.00')
        )
        
        PaymentAllocation.objects.create(
            payment=payment2,
            invoice=invoice.invoice,
            amount_allocated=Decimal('300.00')
        )
        
        summary = invoice.invoice.get_payment_allocations_summary()
        
        self.assertEqual(summary['total_allocated'], Decimal('700.00'))
        self.assertEqual(summary['allocation_count'], 2)
        self.assertEqual(len(summary['allocations']), 2)
    
    # ==================== TRANSACTION TESTS ====================
    
    def test_allocation_rollback_on_error(self):
        """Test that failed allocation doesn't update paid_amount"""
        invoice = self.create_ap_invoice(total=1000.00)
        payment = self.create_payment(self.supplier.business_partner)
        
        try:
            with transaction.atomic():
                # Create valid allocation
                PaymentAllocation.objects.create(
                    payment=payment,
                    invoice=invoice.invoice,
                    amount_allocated=Decimal('500.00')
                )
                
                # Force an error
                raise Exception("Simulated error")
        except Exception:
            pass
        
        # Check that paid_amount wasn't updated
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('0'))
    
    # ==================== AR INVOICE TESTS ====================
    
    def test_ar_invoice_payment_allocation(self):
        """Test payment allocation for AR invoices (customer payments)"""
        ar_invoice = self.create_ar_invoice(total=2000.00)
        payment = self.create_payment(self.customer.business_partner)
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=ar_invoice.invoice,
            amount_allocated=Decimal('2000.00')
        )
        
        ar_invoice.invoice.refresh_from_db()
        self.assertEqual(ar_invoice.invoice.paid_amount, Decimal('2000.00'))
        self.assertEqual(ar_invoice.invoice.payment_status, Invoice.PAID)

