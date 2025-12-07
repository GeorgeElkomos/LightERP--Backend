"""
Tests for PaymentAllocation UPDATE edge cases

This test suite validates all the special cases when updating payment allocations:
- Increasing allocation amounts
- Decreasing allocation amounts
- Setting allocation to zero
- Concurrent modifications
- Validation during updates
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from datetime import date

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import Invoice, AP_Invoice
from Finance.BusinessPartner.models import BusinessPartner, Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry


class PaymentAllocationUpdateEdgeCasesTest(TestCase):
    """Test edge cases for PaymentAllocation updates"""
    
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
    
    def create_invoice(self, total=1000.00):
        """Helper to create an invoice"""
        return AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=total,
            total=total,
            gl_distributions=self.journal_entry
        )
    
    def create_payment(self):
        """Helper to create a payment"""
        return Payment.objects.create(
            date=date.today(),
            business_partner=self.supplier.business_partner,
            currency=self.currency,
            exchange_rate=Decimal('1.0000')
        )
    
    # ==================== UPDATE: INCREASE AMOUNT ====================
    
    def test_update_increase_amount(self):
        """Test increasing allocation amount (e.g., $300 → $700)"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        # Create initial allocation
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('300.00')
        )
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('300.00'))
        
        # Increase allocation
        allocation.amount_allocated = Decimal('700.00')
        allocation.save()
        
        # Check paid_amount increased by difference (700 - 300 = 400)
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('700.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PARTIALLY_PAID)
    
    def test_update_increase_to_full_payment(self):
        """Test increasing allocation to fully pay invoice"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # Increase to full payment
        allocation.amount_allocated = Decimal('1000.00')
        allocation.save()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('1000.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PAID)
        self.assertTrue(invoice.invoice.is_paid())
    
    def test_update_increase_exceeds_total_fails(self):
        """Test that increasing beyond invoice total fails"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # Try to increase beyond total
        allocation.amount_allocated = Decimal('1500.00')
        
        with self.assertRaises(ValidationError) as context:
            allocation.save()
        
        self.assertIn('amount_allocated', str(context.exception))
        
        # Verify paid_amount didn't change
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
    
    # ==================== UPDATE: DECREASE AMOUNT ====================
    
    def test_update_decrease_amount(self):
        """Test decreasing allocation amount (e.g., $700 → $300)"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        # Create allocation
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('700.00')
        )
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('700.00'))
        
        # Decrease allocation
        allocation.amount_allocated = Decimal('300.00')
        allocation.save()
        
        # Check paid_amount decreased by difference (700 - 300 = 400)
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('300.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PARTIALLY_PAID)
    
    def test_update_decrease_from_paid_to_partial(self):
        """Test decreasing from fully paid to partially paid"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        # Create full payment
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('1000.00')
        )
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.payment_status, Invoice.PAID)
        
        # Decrease to partial payment
        allocation.amount_allocated = Decimal('600.00')
        allocation.save()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('600.00'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PARTIALLY_PAID)
        self.assertFalse(invoice.invoice.is_paid())
    
    def test_update_decrease_to_near_zero(self):
        """Test decreasing to very small amount"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # Decrease to minimal amount
        allocation.amount_allocated = Decimal('0.01')
        allocation.save()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('0.01'))
        self.assertEqual(invoice.invoice.payment_status, Invoice.PARTIALLY_PAID)
    
    def test_update_decrease_to_zero_fails(self):
        """Test that decreasing to zero or negative fails validation"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # Try to set to zero
        allocation.amount_allocated = Decimal('0.00')
        
        with self.assertRaises(ValidationError) as context:
            allocation.save()
        
        self.assertIn('amount_allocated', str(context.exception))
        
        # Verify paid_amount didn't change
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
    
    def test_update_decrease_to_negative_fails(self):
        """Test that setting negative amount fails"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # Try to set to negative
        allocation.amount_allocated = Decimal('-100.00')
        
        with self.assertRaises(ValidationError):
            allocation.save()
        
        # Verify paid_amount didn't change
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
    
    # ==================== UPDATE: WITH MULTIPLE ALLOCATIONS ====================
    
    def test_update_with_multiple_allocations(self):
        """Test updating one allocation when multiple exist"""
        invoice = self.create_invoice(total=1000.00)
        payment1 = self.create_payment()
        payment2 = self.create_payment()
        
        # Create two allocations
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
        
        # Update first allocation
        alloc1.amount_allocated = Decimal('500.00')
        alloc1.save()
        
        # Check total is correct
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('900.00'))
    
    def test_update_exceeds_remaining_with_other_allocations(self):
        """Test that update fails if it would exceed remaining balance"""
        invoice = self.create_invoice(total=1000.00)
        payment1 = self.create_payment()
        payment2 = self.create_payment()
        
        # First allocation takes 600
        alloc1 = PaymentAllocation.objects.create(
            payment=payment1,
            invoice=invoice.invoice,
            amount_allocated=Decimal('600.00')
        )
        
        # Second allocation takes 200
        alloc2 = PaymentAllocation.objects.create(
            payment=payment2,
            invoice=invoice.invoice,
            amount_allocated=Decimal('200.00')
        )
        
        # Try to update second allocation to 500 (would total 1100)
        alloc2.amount_allocated = Decimal('500.00')
        
        with self.assertRaises(ValidationError) as context:
            alloc2.save()
        
        self.assertIn('remaining balance', str(context.exception).lower())
        
        # Verify nothing changed
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('800.00'))
    
    # ==================== UPDATE: SMALL CHANGES ====================
    
    def test_update_small_increase(self):
        """Test small increase in allocation"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # Small increase
        allocation.amount_allocated = Decimal('500.50')
        allocation.save()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.50'))
    
    def test_update_small_decrease(self):
        """Test small decrease in allocation"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # Small decrease
        allocation.amount_allocated = Decimal('499.50')
        allocation.save()
        
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('499.50'))
    
    def test_update_no_change(self):
        """Test updating with same amount (no actual change)"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        # "Update" with same value
        allocation.amount_allocated = Decimal('500.00')
        allocation.save()
        
        # Should still be correct
        invoice.invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
    
    # ==================== UPDATE: TRANSACTION ROLLBACK ====================
    
    def test_update_rollback_on_error(self):
        """Test that failed update doesn't change paid_amount"""
        invoice = self.create_invoice(total=1000.00)
        payment = self.create_payment()
        
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        try:
            with transaction.atomic():
                # Try invalid update
                allocation.amount_allocated = Decimal('1500.00')
                allocation.save()
        except ValidationError:
            pass
        
        # Refresh and verify nothing changed
        invoice.invoice.refresh_from_db()
        allocation.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
        self.assertEqual(allocation.amount_allocated, Decimal('500.00'))
