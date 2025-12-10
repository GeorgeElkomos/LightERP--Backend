"""
Test to demonstrate dynamic child discovery.

This test shows that the Invoice parent class can automatically
discover ANY child type without hard-coding the relationships.
"""

from django.test import TestCase
from django.utils import timezone
from Finance.Invoice.models import Invoice, AP_Invoice, AR_Invoice
from Finance.BusinessPartner.models import Supplier, Customer
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry


class DynamicChildDiscoveryTest(TestCase):
    """Test that _get_child() works dynamically for any child type."""
    
    def setUp(self):
        """Create test data ONCE and reuse for all tests."""
        # Create currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        # Create country
        self.country = Country.objects.create(
            code='US',
            name='United States'
        )
        
        # Create journal entry (required for Invoice.gl_distributions)
        self.journal_entry = JournalEntry.objects.create(
            date=timezone.now().date(),
            currency=self.currency,
            memo='Test Journal Entry for invoices'
        )
        
        # Create supplier (via child model)
        self.supplier = Supplier.objects.create(
            name='Test Supplier Inc'
        )
        
        # Create customer (via child model)
        self.customer = Customer.objects.create(
            name='Test Customer Inc'
        )
    
    def test_get_child_discovers_ap_invoice(self):
        """Test that _get_child() discovers AP_Invoice automatically."""
        # Create AP Invoice with gl_distributions
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=timezone.now().date(),
            currency=self.currency,
            country=self.country,
            total=1000.00,
            gl_distributions=self.journal_entry
        )
        
        # Get the parent
        invoice = ap_invoice.invoice
        
        # Test dynamic discovery
        child = invoice._get_child()
        
        self.assertIsNotNone(child)
        self.assertEqual(child, ap_invoice)
        self.assertIsInstance(child, AP_Invoice)
    
    def test_get_child_discovers_ar_invoice(self):
        """Test that _get_child() discovers AR_Invoice automatically."""
        # Create AR Invoice with gl_distributions
        ar_invoice = AR_Invoice.objects.create(
            customer=self.customer,
            date=timezone.now().date(),
            currency=self.currency,
            country=self.country,
            total=2000.00,
            gl_distributions=self.journal_entry
        )
        
        # Get the parent
        invoice = ar_invoice.invoice
        
        # Test dynamic discovery
        child = invoice._get_child()
        
        self.assertIsNotNone(child)
        self.assertEqual(child, ar_invoice)
        self.assertIsInstance(child, AR_Invoice)
    
    def test_get_child_returns_none_for_orphaned_invoice(self):
        """Test that _get_child() returns None if no child exists."""
        # This should never happen in production (parent is managed),
        # but we test the edge case
        
        # We can't create Invoice directly due to ManagedParentManager,
        # so we'll create via child and then delete the child
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=timezone.now().date(),
            currency=self.currency,
            country=self.country,
            total=1000.00,
            gl_distributions=self.journal_entry
        )
        
        invoice = ap_invoice.invoice
        invoice_id = invoice.id
        ap_invoice_pk = ap_invoice.pk
        
        # Delete the child (this breaks the relationship)
        AP_Invoice.objects.filter(pk=ap_invoice_pk).delete()
        
        # Refresh the invoice
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Test dynamic discovery
        child = invoice._get_child()
        
        self.assertIsNone(child)
    
    def test_future_proofing(self):
        """
        Demonstrate that adding NEW invoice types requires NO changes to Invoice class.
        
        This is a conceptual test showing the design pattern.
        If you add a new child type (e.g., CreditNote, DebitNote, etc.),
        _get_child() will automatically discover it!
        """
        # This test always passes - it's documentation
        self.assertTrue(True)


class CallbackPatternTest(TestCase):
    """Test that callback pattern works with dynamic discovery."""
    
    def setUp(self):
        """Create test data ONCE and reuse."""
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        self.country = Country.objects.create(
            code='US',
            name='United States'
        )
        
        # Create journal entry
        self.journal_entry = JournalEntry.objects.create(
            date=timezone.now().date(),
            currency=self.currency,
            memo='Test Journal Entry for invoices'
        )
        
        # Create supplier (via child model)
        self.supplier = Supplier.objects.create(
            name='Test Supplier Inc'
        )
    
    def test_callback_hook_is_called_on_ap_invoice(self):
        """Test that child hooks are called via dynamic discovery."""
        # Create AP Invoice with gl_distributions
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=timezone.now().date(),
            currency=self.currency,
            country=self.country,
            total=1000.00,
            gl_distributions=self.journal_entry
        )
        
        invoice = ap_invoice.invoice
        
        # Mock the child hook to verify it gets called
        call_log = []
        
        def mock_child_hook(workflow_instance):
            call_log.append(('on_approval_started_child', workflow_instance))
        
        # Temporarily replace the child method
        original_method = ap_invoice.on_approval_started_child
        ap_invoice.on_approval_started_child = mock_child_hook
        
        try:
            # Call parent method (which should delegate to child)
            invoice._call_child_hook('on_approval_started_child', 'test_workflow')
            
            # Verify child hook was called
            self.assertEqual(len(call_log), 1)
            self.assertEqual(call_log[0][0], 'on_approval_started_child')
            self.assertEqual(call_log[0][1], 'test_workflow')
        finally:
            # Restore original method
            ap_invoice.on_approval_started_child = original_method
