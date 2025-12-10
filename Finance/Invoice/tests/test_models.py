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

from Finance.Invoice.models import Invoice, AP_Invoice, AR_Invoice, OneTimeSupplier, InvoiceItem
from Finance.BusinessPartner.models import Customer, OneTime, Supplier
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
    
    def test_OneTimeSupplier_create_with_manager(self):
        """Create one-time supplier using OneTimeSupplier.objects.create()"""
        # Create a OneTime supplier first
        from Finance.BusinessPartner.models import OneTime
        one_time_supplier_instance = OneTime.objects.create(
            name="John's Plumbing",
            email="john@plumbing.com",
            phone="+1-555-7777",
            tax_id="TAX123"
        )
        
        one_time = OneTimeSupplier.objects.create(
            # Invoice fields
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('275.00'),
            gl_distributions=self.journal_entry,
            # One-time supplier field
            one_time_supplier=one_time_supplier_instance
        )
        
        # Verify OneTimeSupplier created
        self.assertIsNotNone(one_time.id)
        self.assertEqual(one_time.one_time_supplier.name, "John's Plumbing")
        self.assertEqual(one_time.one_time_supplier.email, "john@plumbing.com")
        self.assertEqual(one_time.one_time_supplier.phone, "+1-555-7777")
        self.assertEqual(one_time.one_time_supplier.tax_id, "TAX123")
        
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
        self.assertEqual(ap_invoice.payment_status, 'PAID')
        
        # Verify Invoice was updated
        self.assertEqual(ap_invoice.invoice.total, Decimal('3300.00'))
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
        ar_invoice.customer = new_customer
        ar_invoice.save()
        
        # Refresh and verify
        ar_invoice.refresh_from_db()
        self.assertEqual(ar_invoice.total, Decimal('8000.00'))
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
    
    def test_OneTimeSupplier_delete(self):
        """Delete one-time supplier and verify Invoice handling"""
        # Create a OneTime supplier first
        from Finance.BusinessPartner.models import OneTime
        one_time_supplier_instance = OneTime.objects.create(name="Temp Supplier")
        
        one_time = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('150.00'),
            gl_distributions=self.journal_entry,
            one_time_supplier=one_time_supplier_instance
        )
        
        invoice_id = one_time.invoice.id
        one_time_id = one_time.id
        
        # Delete one-time supplier
        one_time.delete()
        
        # Verify OneTimeSupplier deleted
        self.assertFalse(OneTimeSupplier.objects.filter(id=one_time_id).exists())
        
        # Note: OneTimeSupplier uses ForeignKey, not OneToOneField
        # So Invoice might still exist if there are other OneTimeSupplier records
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
        # Create OneTime supplier for one-time invoice
        from Finance.BusinessPartner.models import OneTime
        one_time_supplier_instance = OneTime.objects.create(name="One Time Supplier")
        
        one_time_1 = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('200.00'),
            gl_distributions=self.journal_entry,
            one_time_supplier=one_time_supplier_instance
        )
        
        # Verify all created successfully
        self.assertEqual(ap.currency, self.currency_usd)
        self.assertEqual(ar.currency, self.currency_usd)
        self.assertEqual(one_time_1.currency, self.currency_usd)
    
    def test_invoice_status_transitions(self):
        """Test transitioning invoice through different statuses using approval workflow"""
        from Finance.Invoice.tests.test_helpers import create_simple_approval_template_for_invoice, get_or_create_test_user
        from Finance.GL.models import JournalLine, XX_SegmentType, XX_Segment, XX_Segment_combination
        from decimal import Decimal
        
        # Set up approval workflow
        create_simple_approval_template_for_invoice()
        user = get_or_create_test_user('test_user@example.com')
        
        # Create balanced journal entry
        journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            memo='Test Journal Entry'
        )
        
        # Create segments for balanced journal
        segment_type_1 = XX_SegmentType.objects.create(segment_name='Company', description='Company')
        segment_type_2 = XX_SegmentType.objects.create(segment_name='Account', description='Account')
        segment_100 = XX_Segment.objects.create(segment_type=segment_type_1, code='100', alias='Co 100', node_type='detail')
        segment_6100 = XX_Segment.objects.create(segment_type=segment_type_2, code='6100', alias='Expense', node_type='detail')
        segment_2100 = XX_Segment.objects.create(segment_type=segment_type_2, code='2100', alias='AP', node_type='detail')
        
        combination_dr_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, '100'),
            (segment_type_2.id, '6100')
        ])
        combination_cr_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, '100'),
            (segment_type_2.id, '2100')
        ])
        
        combination_dr = XX_Segment_combination.objects.get(id=combination_dr_id)
        combination_cr = XX_Segment_combination.objects.get(id=combination_cr_id)
        
        JournalLine.objects.create(entry=journal_entry, type='DEBIT',
                                   segment_combination=combination_dr, amount=Decimal('1000.00'))
        JournalLine.objects.create(entry=journal_entry, type='CREDIT',
                                   segment_combination=combination_cr, amount=Decimal('1000.00'))
        
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            subtotal=Decimal('1000.00'),
            gl_distributions=journal_entry,
            supplier=self.supplier
        )
        
        # Create invoice items to pass validation
        InvoiceItem.objects.create(
            invoice=ap_invoice.invoice,
            name='Test Item',
            description='Test Description',
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00')
        )
        
        # Initial status
        self.assertEqual(ap_invoice.approval_status, 'DRAFT')
        self.assertEqual(ap_invoice.payment_status, 'UNPAID')
        
        # Submit for approval (moves to PENDING_APPROVAL)
        ap_invoice.submit_for_approval()
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.approval_status, 'PENDING_APPROVAL')
        
        # Approve (moves to APPROVED)
        ap_invoice.approve(user, comment='Approved for testing')
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.approval_status, 'APPROVED')
        
        # Partial payment
        ap_invoice.invoice.payment_status = 'PARTIALLY_PAID'
        ap_invoice.invoice._allow_direct_save = True
        ap_invoice.invoice.save()
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
        
        # Full payment
        ap_invoice.invoice.payment_status = 'PAID'
        ap_invoice.invoice._allow_direct_save = True
        ap_invoice.invoice.save()
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


class BusinessPartnerIntegrationTests(TestCase):
    """Test business_partner field integration and auto-sync"""
    
    def setUp(self):
        """Set up test data"""
        # Create countries
        self.country_us = Country.objects.create(code='US', name='United States')
        
        # Create currency
        self.currency_usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
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
            country=self.country_us
        )
        
        # Create one-time supplier
        self.one_time = OneTime.objects.create(
            name="Quick Fix Plumbing",
            email="john@plumbing.com",
            country=self.country_us
        )
        
        # Create journal entry
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency_usd,
            memo='Test Journal Entry'
        )
    
    def test_ap_invoice_business_partner_auto_set_on_create(self):
        """Verify business_partner is auto-set from supplier on creation"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        # Verify business_partner was auto-set
        self.assertEqual(
            ap_invoice.invoice.business_partner,
            self.supplier.business_partner
        )
        self.assertEqual(
            ap_invoice.invoice.business_partner_id,
            self.supplier.business_partner_id
        )
    
    def test_ar_invoice_business_partner_auto_set_on_create(self):
        """Verify business_partner is auto-set from customer on creation"""
        ar_invoice = AR_Invoice.objects.create(
            customer=self.customer,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('5000.00'),
            gl_distributions=self.journal_entry
        )
        
        # Verify business_partner was auto-set
        self.assertEqual(
            ar_invoice.invoice.business_partner,
            self.customer.business_partner
        )
        self.assertEqual(
            ar_invoice.invoice.business_partner_id,
            self.customer.business_partner_id
        )
    
    def test_one_time_supplier_business_partner_auto_set_on_create(self):
        """Verify business_partner is auto-set from one_time_supplier on creation"""
        one_time_invoice = OneTimeSupplier.objects.create(
            one_time_supplier=self.one_time,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('275.00'),
            gl_distributions=self.journal_entry
        )
        
        # Verify business_partner was auto-set
        self.assertEqual(
            one_time_invoice.invoice.business_partner,
            self.one_time.business_partner
        )
        self.assertEqual(
            one_time_invoice.invoice.business_partner_id,
            self.one_time.business_partner_id
        )
    
    def test_ap_invoice_business_partner_syncs_on_supplier_change(self):
        """Verify business_partner auto-syncs when supplier changes"""
        # Create initial invoice
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        original_bp = ap_invoice.invoice.business_partner
        
        # Create new supplier
        new_supplier = Supplier.objects.create(
            name="New Supplier Corp",
            email="new@supplier.com"
        )
        
        # Change supplier
        ap_invoice.supplier = new_supplier
        ap_invoice.save()
        
        # Refresh from database
        ap_invoice.refresh_from_db()
        
        # Verify business_partner was auto-synced
        self.assertNotEqual(ap_invoice.invoice.business_partner, original_bp)
        self.assertEqual(
            ap_invoice.invoice.business_partner,
            new_supplier.business_partner
        )
    
    def test_ar_invoice_business_partner_syncs_on_customer_change(self):
        """Verify business_partner auto-syncs when customer changes"""
        # Create initial invoice
        ar_invoice = AR_Invoice.objects.create(
            customer=self.customer,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('5000.00'),
            gl_distributions=self.journal_entry
        )
        
        original_bp = ar_invoice.invoice.business_partner
        
        # Create new customer
        new_customer = Customer.objects.create(
            name="New Customer Inc",
            email="new@customer.com"
        )
        
        # Change customer
        ar_invoice.customer = new_customer
        ar_invoice.save()
        
        # Refresh from database
        ar_invoice.refresh_from_db()
        
        # Verify business_partner was auto-synced
        self.assertNotEqual(ar_invoice.invoice.business_partner, original_bp)
        self.assertEqual(
            ar_invoice.invoice.business_partner,
            new_customer.business_partner
        )
    
    def test_one_time_supplier_business_partner_syncs_on_change(self):
        """Verify business_partner auto-syncs when one_time_supplier changes"""
        # Create initial invoice
        one_time_invoice = OneTimeSupplier.objects.create(
            one_time_supplier=self.one_time,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('275.00'),
            gl_distributions=self.journal_entry
        )
        
        original_bp = one_time_invoice.invoice.business_partner
        
        # Create new one-time supplier
        new_one_time = OneTime.objects.create(
            name="Emergency Repairs",
            email="emergency@repairs.com"
        )
        
        # Change one_time_supplier
        one_time_invoice.one_time_supplier = new_one_time
        one_time_invoice.save()
        
        # Refresh from database
        one_time_invoice.refresh_from_db()
        
        # Verify business_partner was auto-synced
        self.assertNotEqual(one_time_invoice.invoice.business_partner, original_bp)
        self.assertEqual(
            one_time_invoice.invoice.business_partner,
            new_one_time.business_partner
        )
    
    def test_ap_invoice_business_partner_accessible_via_property(self):
        """Verify business_partner is accessible as a property on AP_Invoice"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        # Access via property (should proxy from invoice.business_partner)
        self.assertEqual(
            ap_invoice.business_partner,
            self.supplier.business_partner
        )
    
    def test_ar_invoice_business_partner_accessible_via_property(self):
        """Verify business_partner is accessible as a property on AR_Invoice"""
        ar_invoice = AR_Invoice.objects.create(
            customer=self.customer,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('5000.00'),
            gl_distributions=self.journal_entry
        )
        
        # Access via property (should proxy from invoice.business_partner)
        self.assertEqual(
            ar_invoice.business_partner,
            self.customer.business_partner
        )
    
    def test_business_partner_consistency_across_multiple_updates(self):
        """Test business_partner stays consistent across multiple field updates"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency_usd,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        # Update other fields multiple times
        ap_invoice.total = Decimal('1500.00')
        ap_invoice.save()
        ap_invoice.refresh_from_db()
        
        ap_invoice.payment_status = 'PARTIALLY_PAID'
        ap_invoice.save()
        ap_invoice.refresh_from_db()
        
        # business_partner should still match supplier
        self.assertEqual(
            ap_invoice.invoice.business_partner,
            self.supplier.business_partner
        )


class InvoicePaymentTests(TestCase):
    """Test payment functionality: paid_amount field and helper functions"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        self.supplier = Supplier.objects.create(
            name="Test Supplier",
            email="supplier@test.com"
        )
        
        self.customer = Customer.objects.create(
            name="Test Customer",
            email="customer@test.com"
        )
        
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Entry'
        )
    
    def test_paid_amount_defaults_to_zero(self):
        """Test that paid_amount defaults to 0 on creation"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        self.assertEqual(ap_invoice.paid_amount, Decimal('0'))
        self.assertEqual(ap_invoice.payment_status, 'UNPAID')
    
    def test_is_paid_returns_false_for_unpaid_invoice(self):
        """Test is_paid() returns False for unpaid invoice"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        self.assertFalse(ap_invoice.invoice.is_paid())
    
    def test_is_paid_returns_true_for_fully_paid_invoice(self):
        """Test is_paid() returns True when paid_amount equals total"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.refresh_from_db()
        
        self.assertTrue(ap_invoice.invoice.is_paid())
        self.assertEqual(ap_invoice.payment_status, 'PAID')
    
    def test_is_partially_paid_returns_false_for_unpaid(self):
        """Test is_partially_paid() returns False for unpaid invoice"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        self.assertFalse(ap_invoice.invoice.is_partially_paid())
    
    def test_is_partially_paid_returns_true_for_partial_payment(self):
        """Test is_partially_paid() returns True for partial payment"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('400.00'))
        ap_invoice.refresh_from_db()
        
        self.assertTrue(ap_invoice.invoice.is_partially_paid())
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
    
    def test_is_partially_paid_returns_false_for_fully_paid(self):
        """Test is_partially_paid() returns False when fully paid"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.refresh_from_db()
        
        self.assertFalse(ap_invoice.invoice.is_partially_paid())
    
    def test_remaining_amount_for_unpaid_invoice(self):
        """Test remaining_amount() returns total for unpaid invoice"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        self.assertEqual(ap_invoice.invoice.remaining_amount(), Decimal('1000.00'))
    
    def test_remaining_amount_for_partially_paid_invoice(self):
        """Test remaining_amount() calculates correctly for partial payment"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('350.00'))
        ap_invoice.refresh_from_db()
        
        self.assertEqual(ap_invoice.invoice.remaining_amount(), Decimal('650.00'))
    
    def test_remaining_amount_for_fully_paid_invoice(self):
        """Test remaining_amount() returns 0 for fully paid invoice"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.refresh_from_db()
        
        self.assertEqual(ap_invoice.invoice.remaining_amount(), Decimal('0'))
    
    def test_pay_adds_to_paid_amount(self):
        """Test pay() adds amount to paid_amount"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('400.00'))
        ap_invoice.refresh_from_db()
        
        self.assertEqual(ap_invoice.paid_amount, Decimal('400.00'))
    
    def test_pay_multiple_times(self):
        """Test multiple payments accumulate correctly"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('200.00'))
        ap_invoice.invoice.pay(Decimal('300.00'))
        ap_invoice.invoice.pay(Decimal('100.00'))
        ap_invoice.refresh_from_db()
        
        self.assertEqual(ap_invoice.paid_amount, Decimal('600.00'))
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
    
    def test_pay_updates_payment_status_to_paid(self):
        """Test pay() auto-updates payment_status to PAID when fully paid"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.refresh_from_db()
        
        self.assertEqual(ap_invoice.payment_status, 'PAID')
    
    def test_pay_rejects_negative_amount(self):
        """Test pay() raises error for negative amount"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        with self.assertRaises(ValidationError) as context:
            ap_invoice.invoice.pay(Decimal('-100.00'))
        
        self.assertIn('greater than zero', str(context.exception))
    
    def test_pay_rejects_zero_amount(self):
        """Test pay() raises error for zero amount"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        with self.assertRaises(ValidationError) as context:
            ap_invoice.invoice.pay(Decimal('0'))
        
        self.assertIn('greater than zero', str(context.exception))
    
    def test_pay_rejects_overpayment(self):
        """Test pay() raises error when payment exceeds remaining balance"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        with self.assertRaises(ValidationError) as context:
            ap_invoice.invoice.pay(Decimal('1500.00'))
        
        self.assertIn('exceeds remaining balance', str(context.exception))
    
    def test_pay_rejects_overpayment_on_partially_paid(self):
        """Test pay() prevents overpayment on partially paid invoice"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('700.00'))
        
        with self.assertRaises(ValidationError) as context:
            ap_invoice.invoice.pay(Decimal('400.00'))
        
        self.assertIn('exceeds remaining balance', str(context.exception))
    
    def test_refund_subtracts_from_paid_amount(self):
        """Test refund() subtracts amount from paid_amount"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.invoice.refund(Decimal('200.00'))
        ap_invoice.refresh_from_db()
        
        self.assertEqual(ap_invoice.paid_amount, Decimal('800.00'))
    
    def test_refund_updates_payment_status(self):
        """Test refund() updates payment_status correctly"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PAID')
        
        ap_invoice.invoice.refund(Decimal('300.00'))
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
    
    def test_refund_full_amount_sets_unpaid(self):
        """Test refunding full amount sets status to UNPAID"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('500.00'))
        ap_invoice.invoice.refund(Decimal('500.00'))
        ap_invoice.refresh_from_db()
        
        self.assertEqual(ap_invoice.paid_amount, Decimal('0'))
        self.assertEqual(ap_invoice.payment_status, 'UNPAID')
    
    def test_refund_rejects_negative_amount(self):
        """Test refund() raises error for negative amount"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('500.00'))
        
        with self.assertRaises(ValidationError) as context:
            ap_invoice.invoice.refund(Decimal('-100.00'))
        
        self.assertIn('greater than zero', str(context.exception))
    
    def test_refund_rejects_amount_exceeding_paid_amount(self):
        """Test refund() raises error when refund exceeds paid_amount"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('400.00'))
        
        with self.assertRaises(ValidationError) as context:
            ap_invoice.invoice.refund(Decimal('500.00'))
        
        self.assertIn('exceeds paid amount', str(context.exception))
    
    def test_can_pay_validates_positive_amount(self):
        """Test can_pay() validates amount is positive"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        is_valid, error = ap_invoice.invoice.can_pay(Decimal('-50.00'))
        self.assertFalse(is_valid)
        self.assertIn('greater than zero', error)
    
    def test_can_pay_validates_total_exists(self):
        """Test can_pay() validates total is set"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            gl_distributions=self.journal_entry
        )
        
        is_valid, error = ap_invoice.invoice.can_pay(Decimal('100.00'))
        self.assertFalse(is_valid)
        self.assertIn('without total amount', error)
    
    def test_can_pay_validates_no_overpayment(self):
        """Test can_pay() prevents overpayment"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        is_valid, error = ap_invoice.invoice.can_pay(Decimal('1500.00'))
        self.assertFalse(is_valid)
        self.assertIn('exceeds remaining balance', error)
    
    def test_can_pay_accepts_valid_amount(self):
        """Test can_pay() accepts valid payment"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        is_valid, error = ap_invoice.invoice.can_pay(Decimal('500.00'))
        self.assertTrue(is_valid)
        self.assertEqual(error, '')
    
    def test_update_payment_status_sets_unpaid(self):
        """Test update_payment_status() sets UNPAID when paid_amount is 0"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.update_payment_status()
        self.assertEqual(ap_invoice.invoice.payment_status, 'UNPAID')
    
    def test_update_payment_status_sets_partially_paid(self):
        """Test update_payment_status() sets PARTIALLY_PAID correctly"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('600.00'))
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
    
    def test_update_payment_status_sets_paid(self):
        """Test update_payment_status() sets PAID when fully paid"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PAID')
    
    def test_payment_workflow_ar_invoice(self):
        """Test complete payment workflow on AR_Invoice - child can call parent methods directly"""
        ar_invoice = AR_Invoice.objects.create(
            customer=self.customer,
            date=date.today(),
            currency=self.currency,
            total=Decimal('5000.00'),
            gl_distributions=self.journal_entry
        )
        
        # TEST: Child should be able to call parent methods directly!
        # No need for ar_invoice.invoice.is_paid() - just ar_invoice.is_paid()
        self.assertFalse(ar_invoice.is_paid())  # Direct call!
        self.assertEqual(ar_invoice.remaining_amount(), Decimal('5000.00'))  # Direct call!
        
        # First payment
        ar_invoice.pay(Decimal('2000.00'))  # Direct call!
        ar_invoice.refresh_from_db()
        self.assertTrue(ar_invoice.is_partially_paid())  # Direct call!
        self.assertEqual(ar_invoice.remaining_amount(), Decimal('3000.00'))  # Direct call!
        
        # Second payment
        ar_invoice.pay(Decimal('3000.00'))  # Direct call!
        ar_invoice.refresh_from_db()
        self.assertTrue(ar_invoice.is_paid())  # Direct call!
        self.assertEqual(ar_invoice.remaining_amount(), Decimal('0'))  # Direct call!
        self.assertEqual(ar_invoice.payment_status, 'PAID')
    
    def test_payment_workflow_with_refund(self):
        """Test payment and refund workflow"""
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry
        )
        
        # Pay full amount
        ap_invoice.invoice.pay(Decimal('1000.00'))
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PAID')
        
        # Partial refund
        ap_invoice.invoice.refund(Decimal('250.00'))
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.paid_amount, Decimal('750.00'))
        self.assertEqual(ap_invoice.payment_status, 'PARTIALLY_PAID')
        
        # Pay remaining
        ap_invoice.invoice.pay(Decimal('250.00'))
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.payment_status, 'PAID')
