"""
Model Tests for Invoice DRY Architecture

Tests verify:
- Property proxies work correctly
- Manager's create() method extracts fields properly
- Updates propagate from child to parent
- Deletion handles Invoice cleanup
- Invoice protection mechanisms work
"""

from django.test import TestCase
from django.core.exceptions import PermissionDenied, ValidationError
from datetime import date
from decimal import Decimal

from Finance.Invoice.models import Invoice, AP_Invoice, AR_Invoice, one_use_supplier
from Finance.BusinessPartner.models import Customer, Supplier
from Finance.core.models import Country, Currency
from Finance.GL.models import JournalEntry


class InvoiceModelTests(TestCase):
    """Test the DRY architecture at model level"""
    
    def setUp(self):
        """Set up test data"""
        # Create countries
        self.country_us = Country.objects.create(code='US', name='United States')
        self.country_uk = Country.objects.create(code='UK', name='United Kingdom')
        
        # Create currency
        self.currency_usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        self.currency_gbp = Currency.objects.create(
            code='GBP',
            name='British Pound',
            symbol='£'
        )
        
        # Create customer
        self.customer = Customer.objects.create(
            name="Acme Corp",
            email="contact@acme.com",
            country=self.country_us
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            name="Tech Supplies Inc",
            email="sales@techsupplies.com",
            country=self.country_uk
        )
        
        # Create journal entry
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            memo='Test Journal Entry'
        )
    
    def test_cannot_create_invoice_directly(self):
        """Verify Invoice.objects.create() raises PermissionDenied"""
        with self.assertRaises(PermissionDenied) as context:
            Invoice.objects.create(
                date=date.today(),
                currency=self.currency_usd,
                total=Decimal('1000.00'),
                gl_distributions=self.journal_entry
            )
        
        self.assertIn("Cannot create Invoice directly", str(context.exception))
    
    def test_ap_invoice_create_with_manager(self):
        """Create AP invoice using AP_Invoice.objects.create()"""
        ap_invoice = AP_Invoice.objects.create(
            # Invoice fields
            date=date.today(),
            currency=self.currency_usd,
            country=self.country_us,
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('100.00'),
            total=Decimal('1100.00'),
            gl_distributions=self.journal_entry,
            approval_status='DRAFT',
            payment_status='UNPAID',
            # AP-specific field
            supplier=self.supplier
        )
        
        # Verify AP_Invoice created
        self.assertIsNotNone(ap_invoice.invoice_id)
        self.assertEqual(ap_invoice.supplier, self.supplier)
        
        # Verify Invoice created
        self.assertIsNotNone(ap_invoice.invoice)
        self.assertIsNotNone(ap_invoice.invoice.id)
        
        # Verify all fields set correctly
        self.assertEqual(ap_invoice.invoice.date, date.today())
        self.assertEqual(ap_invoice.invoice.currency, self.currency_usd)
        self.assertEqual(ap_invoice.invoice.country, self.country_us)
        self.assertEqual(ap_invoice.invoice.subtotal, Decimal('1000.00'))
        self.assertEqual(ap_invoice.invoice.tax_amount, Decimal('100.00'))
        self.assertEqual(ap_invoice.invoice.total, Decimal('1100.00'))
        self.assertEqual(ap_invoice.invoice.gl_distributions, self.journal_entry)
        self.assertEqual(ap_invoice.invoice.approval_status, 'DRAFT')
        self.assertEqual(ap_invoice.invoice.payment_status, 'UNPAID')
    
    def test_ar_invoice_create_with_manager(self):
        """Create AR invoice using AR_Invoice.objects.create()"""
        ar_invoice = AR_Invoice.objects.create(
            # Invoice fields
            date=date.today(),
            currency=self.currency_gbp,
            country=self.country_uk,
            subtotal=Decimal('5000.00'),
            tax_amount=Decimal('500.00'),
            total=Decimal('5500.00'),
            gl_distributions=self.journal_entry,
            # AR-specific field
            customer=self.customer
        )
        
        # Verify AR_Invoice created
        self.assertIsNotNone(ar_invoice.invoice_id)
        self.assertEqual(ar_invoice.customer, self.customer)
        
        # Verify Invoice created
        self.assertIsNotNone(ar_invoice.invoice)
        self.assertEqual(ar_invoice.invoice.currency, self.currency_gbp)
        self.assertEqual(ar_invoice.invoice.total, Decimal('5500.00'))
    
    def test_one_use_supplier_create_with_manager(self):
        """Create one-time supplier using one_use_supplier.objects.create()"""
        one_time = one_use_supplier.objects.create(
            # Invoice fields
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('275.00'),
            gl_distributions=self.journal_entry,
            # One-time supplier fields
            supplier_name="John's Plumbing",
            supplier_address="123 Main St",
            supplier_email="john@plumbing.com",
            supplier_phone="+1-555-7777",
            supplier_tax_id="TAX123"
        )
        
        # Verify one_use_supplier created
        self.assertIsNotNone(one_time.id)
        self.assertEqual(one_time.supplier_name, "John's Plumbing")
        self.assertEqual(one_time.supplier_address, "123 Main St")
        self.assertEqual(one_time.supplier_email, "john@plumbing.com")
        self.assertEqual(one_time.supplier_phone, "+1-555-7777")
        self.assertEqual(one_time.supplier_tax_id, "TAX123")
        
        # Verify Invoice created
        self.assertIsNotNone(one_time.invoice)
        self.assertEqual(one_time.invoice.total, Decimal('275.00'))
    
    def test_property_proxies_read(self):
        """Access Invoice fields through AP_Invoice properties"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            subtotal=Decimal('2000.00'),
            tax_amount=Decimal('200.00'),
            total=Decimal('2200.00'),
            gl_distributions=self.journal_entry,
            approval_status='APPROVED',
            payment_status='PARTIALLY_PAID',
            supplier=self.supplier
        )
        
        # Access through properties (should work via proxies)
        self.assertEqual(ap_invoice.date, date.today())
        self.assertEqual(ap_invoice.currency, self.currency_usd)
        self.assertEqual(ap_invoice.subtotal, Decimal('2000.00'))
        self.assertEqual(ap_invoice.tax_amount, Decimal('200.00'))
        self.assertEqual(ap_invoice.total, Decimal('2200.00'))
        self.assertEqual(ap_invoice.approval_status, 'APPROVED')
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
        
        # Verify they match Invoice fields
        self.assertEqual(ap_invoice.date, ap_invoice.invoice.date)
        self.assertEqual(ap_invoice.total, ap_invoice.invoice.total)
        self.assertEqual(ap_invoice.approval_status, ap_invoice.invoice.approval_status)
    
    def test_property_proxies_write(self):
        """Update Invoice fields through AP_Invoice properties"""
        ap_invoice = AP_Invoice.objects.create(
            date=date(2024, 1, 1),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        # Update through properties
        new_date = date(2024, 12, 31)
        ap_invoice.date = new_date
        ap_invoice.currency = self.currency_gbp
        ap_invoice.subtotal = Decimal('3000.00')
        ap_invoice.tax_amount = Decimal('300.00')
        ap_invoice.total = Decimal('3300.00')
        ap_invoice.approval_status = 'APPROVED'
        ap_invoice.payment_status = 'PAID'
        ap_invoice.save()
        
        # Refresh from database
        ap_invoice.refresh_from_db()
        
        # Verify updates persisted
        self.assertEqual(ap_invoice.date, new_date)
        self.assertEqual(ap_invoice.currency, self.currency_gbp)
        self.assertEqual(ap_invoice.subtotal, Decimal('3000.00'))
        self.assertEqual(ap_invoice.tax_amount, Decimal('300.00'))
        self.assertEqual(ap_invoice.total, Decimal('3300.00'))
        self.assertEqual(ap_invoice.approval_status, 'APPROVED')
        self.assertEqual(ap_invoice.payment_status, 'PAID')
        
        # Verify Invoice was updated
        self.assertEqual(ap_invoice.invoice.total, Decimal('3300.00'))
        self.assertEqual(ap_invoice.invoice.approval_status, 'APPROVED')
        self.assertEqual(ap_invoice.invoice.payment_status, 'PAID')
    
    def test_ap_invoice_update(self):
        """Update multiple fields (Invoice + AP-specific)"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1500.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        # Create another supplier
        new_supplier = Supplier.objects.create(
            name="New Supplier",
            email="new@supplier.com"
        )
        
        # Update both Invoice and AP_Invoice fields
        ap_invoice.total = Decimal('2500.00')
        ap_invoice.payment_status = 'PARTIALLY_PAID'
        ap_invoice.supplier = new_supplier
        ap_invoice.save()
        
        # Refresh and verify
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.total, Decimal('2500.00'))
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
        self.assertEqual(ap_invoice.supplier, new_supplier)
    
    def test_ar_invoice_update(self):
        """Update multiple fields (Invoice + AR-specific)"""
        ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('7000.00'),
            gl_distributions=self.journal_entry,
            customer=self.customer
        )
        
        # Create another customer
        new_customer = Customer.objects.create(
            name="New Customer",
            email="new@customer.com"
        )
        
        # Update both types of fields
        ar_invoice.total = Decimal('8000.00')
        ar_invoice.approval_status = 'APPROVED'
        ar_invoice.customer = new_customer
        ar_invoice.save()
        
        # Refresh and verify
        ar_invoice.refresh_from_db()
        self.assertEqual(ar_invoice.total, Decimal('8000.00'))
        self.assertEqual(ar_invoice.approval_status, 'APPROVED')
        self.assertEqual(ar_invoice.customer, new_customer)
    
    def test_ap_invoice_delete(self):
        """Delete AP invoice and verify Invoice is also deleted"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('999.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        invoice_id = ap_invoice.invoice.id
        ap_invoice_id = ap_invoice.invoice_id
        
        # Delete AP invoice
        ap_invoice.delete()
        
        # Verify AP invoice deleted
        self.assertFalse(AP_Invoice.objects.filter(invoice_id=ap_invoice_id).exists())
        
        # Verify Invoice also deleted
        self.assertFalse(Invoice.objects.filter(id=invoice_id).exists())
    
    def test_ar_invoice_delete(self):
        """Delete AR invoice and verify Invoice is also deleted"""
        ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('4444.00'),
            gl_distributions=self.journal_entry,
            customer=self.customer
        )
        
        invoice_id = ar_invoice.invoice.id
        ar_invoice_id = ar_invoice.invoice_id
        
        # Delete AR invoice
        ar_invoice.delete()
        
        # Verify AR invoice deleted
        self.assertFalse(AR_Invoice.objects.filter(invoice_id=ar_invoice_id).exists())
        
        # Verify Invoice also deleted
        self.assertFalse(Invoice.objects.filter(id=invoice_id).exists())
    
    def test_one_use_supplier_delete(self):
        """Delete one-time supplier and verify Invoice handling"""
        one_time = one_use_supplier.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('150.00'),
            gl_distributions=self.journal_entry,
            supplier_name="Temp Supplier"
        )
        
        invoice_id = one_time.invoice.id
        one_time_id = one_time.id
        
        # Delete one-time supplier
        one_time.delete()
        
        # Verify one_use_supplier deleted
        self.assertFalse(one_use_supplier.objects.filter(id=one_time_id).exists())
        
        # Note: one_use_supplier uses ForeignKey, not OneToOneField
        # So Invoice might still exist if there are other one_use_supplier records
        # This test just verifies the deletion doesn't error
    
    def test_cannot_save_invoice_directly(self):
        """Get Invoice and try to save it directly"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('500.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        invoice = ap_invoice.invoice
        invoice.total = Decimal('600.00')
        
        # Try to save directly - should raise PermissionDenied
        with self.assertRaises(PermissionDenied) as context:
            invoice.save()
        
        self.assertIn("Cannot save Invoice directly", str(context.exception))
    
    def test_cannot_delete_invoice_directly(self):
        """Get Invoice and try to delete it directly"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('500.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        invoice = ap_invoice.invoice
        
        # Try to delete directly - should raise PermissionDenied
        with self.assertRaises(PermissionDenied) as context:
            invoice.delete()
        
        self.assertIn("Cannot delete Invoice directly", str(context.exception))
    
    def test_ap_invoice_manager_active_method(self):
        """Test AP_Invoice.objects.active() method"""
        # Create invoices with different payment statuses
        unpaid = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier,
            payment_status='UNPAID'
        )
        
        partially_paid = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('2000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier,
            payment_status='PARTIALLY_PAID'
        )
        
        paid = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('3000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier,
            payment_status='PAID'
        )
        
        # Get active invoices (not fully paid)
        active_invoices = AP_Invoice.objects.active()
        
        # Verify only unpaid and partially paid returned
        self.assertEqual(active_invoices.count(), 2)
        self.assertIn(unpaid, active_invoices)
        self.assertIn(partially_paid, active_invoices)
        self.assertNotIn(paid, active_invoices)
    
    def test_ar_invoice_manager_active_method(self):
        """Test AR_Invoice.objects.active() method"""
        # Create invoices with different payment statuses
        unpaid = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('5000.00'),
            gl_distributions=self.journal_entry,
            customer=self.customer,
            payment_status='UNPAID'
        )
        
        partially_paid = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('6000.00'),
            gl_distributions=self.journal_entry,
            customer=self.customer,
            payment_status='PARTIALLY_PAID'
        )
        
        paid = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('7000.00'),
            gl_distributions=self.journal_entry,
            customer=self.customer,
            payment_status='PAID'
        )
        
        # Get active invoices (not fully paid)
        active_invoices = AR_Invoice.objects.active()
        
        # Verify only unpaid and partially paid returned
        self.assertEqual(active_invoices.count(), 2)
        self.assertIn(unpaid, active_invoices)
        self.assertIn(partially_paid, active_invoices)
        self.assertNotIn(paid, active_invoices)
    
    def test_default_values_on_create(self):
        """Test that default values are set correctly"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
            # Not specifying approval_status or payment_status
        )
        
        # Verify defaults were set
        self.assertEqual(ap_invoice.approval_status, 'DRAFT')
        self.assertEqual(ap_invoice.payment_status, 'UNPAID')
    
    def test_multiple_invoice_types_for_same_currency(self):
        """Test creating multiple invoice types with the same currency"""
        # Create AP invoice
        ap = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        # Create AR invoice with same currency
        ar = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('2000.00'),
            gl_distributions=self.journal_entry,
            customer=self.customer
        )
        
        # Create one-time supplier with same currency
        one_time = one_use_supplier.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('300.00'),
            gl_distributions=self.journal_entry,
            supplier_name="One Time"
        )
        
        # Verify all created successfully
        self.assertEqual(ap.currency, self.currency_usd)
        self.assertEqual(ar.currency, self.currency_usd)
        self.assertEqual(one_time.currency, self.currency_usd)
    
    def test_invoice_status_transitions(self):
        """Test transitioning invoice through different statuses"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        # Initial status
        self.assertEqual(ap_invoice.approval_status, 'DRAFT')
        self.assertEqual(ap_invoice.payment_status, 'UNPAID')
        
        # Move to pending approval
        ap_invoice.approval_status = 'PENDING_APPROVAL'
        ap_invoice.save()
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.approval_status, 'PENDING_APPROVAL')
        
        # Approve
        ap_invoice.approval_status = 'APPROVED'
        ap_invoice.save()
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.approval_status, 'APPROVED')
        
        # Partial payment
        ap_invoice.payment_status = 'PARTIALLY_PAID'
        ap_invoice.save()
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
        
        # Full payment
        ap_invoice.payment_status = 'PAID'
        ap_invoice.save()
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PAID')
    
    def test_invoice_with_country(self):
        """Test creating invoice with country for tax purposes"""
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            country=self.country_us,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        # Verify country is set
        self.assertEqual(ap_invoice.country, self.country_us)
        self.assertEqual(ap_invoice.invoice.country, self.country_us)
