"""
Invoice Models - Using Generic Base Pattern
Follows the same architecture as BusinessPartner with automatic field handling.

IMPORTANT DESIGN PATTERN:
========================
Invoice is a MANAGED BASE CLASS that should NEVER be directly created, 
updated, or deleted. All operations MUST go through child classes (AP_Invoice, AR_Invoice, etc.).

The magic: Child classes automatically inherit ALL Invoice fields as properties!
No need to manually define getters/setters - they're auto-generated!

Usage Examples:
--------------
# CORRECT - Create an AP invoice
ap_invoice = AP_Invoice.objects.create(
    # Invoice fields (auto-handled!)
    date=date.today(),
    currency=currency,
    subtotal=1000.00,
    total=1100.00,
    gl_distributions=journal_entry,
    # AP_Invoice fields
    supplier=supplier
)

# CORRECT - Update works automatically
ap_invoice.total = 1200.00
ap_invoice.save()  # Auto-updates Invoice!

# Add new field to Invoice? No changes needed in child classes!
"""

from django.db import models
from django.core.exceptions import ValidationError, PermissionDenied
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import Customer, Supplier
from Finance.GL.models import JournalEntry
from Finance.core.base_models import (
    ManagedParentModel,
    ManagedParentManager,
    ChildModelManagerMixin,
    ChildModelMixin
)



class Invoice(ManagedParentModel, models.Model):
    """
    General Invoice - MANAGED BASE CLASS (Interface-like)
    
    ⚠️ WARNING: Do NOT create, update, or delete Invoice instances directly!
    
    This model serves as a shared data container for AP_Invoice, AR_Invoice, and one_use_supplier.
    All operations should be performed through child classes, which will automatically 
    manage the associated Invoice instance.
    """
    
    # Payment status choices
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    PAYMENT_STATUSES = [
        (UNPAID, "Unpaid"),
        (PARTIALLY_PAID, "Partially Paid"),
        (PAID, "Paid"),
    ]
    
    # Approval status choices
    APPROVAL_STATUSES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    prefix_code = models.CharField(max_length=10, blank=True, null=True)
    # Core fields
    date = models.DateField()
    currency = models.ForeignKey(
        Currency, 
        on_delete=models.PROTECT, 
        related_name="invoices"
    )
    country = models.ForeignKey(
        Country, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        related_name="invoices", 
        help_text="Tax country for this invoice"
    )
    
    # Status fields
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUSES,
        default='DRAFT',
        help_text="Approval workflow status"
    )
    
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUSES, 
        default=UNPAID,
        help_text="Payment status of the invoice"
    )
    
    # Financial fields
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Invoice subtotal (before tax)"
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total tax amount"
    )
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Invoice total (subtotal + tax)"
    )
    gl_distributions = models.ForeignKey(
        JournalEntry, 
        on_delete=models.PROTECT, 
        null=False, 
        blank=False, 
        related_name="invoices", 
        help_text="GL Journal Entry for this invoice"
    )
    
    # Custom manager to prevent direct creation
    objects = ManagedParentManager()
    
    class Meta:
        db_table = 'invoice'
        verbose_name = 'General Invoice'
        verbose_name_plural = 'General Invoices'
    
    def __str__(self):
        return f"Invoice {self.id} - {self.date}"

class InvoiceItem(models.Model):
    """Invoice Line Item"""
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
   
    class Meta:
        db_table = 'invoice_item'  # NEW table name
    
    def __str__(self):
        return f"{self.invoice.id} - {self.description[:30]}"


# ==================== AP INVOICE ====================

class AP_InvoiceManager(ChildModelManagerMixin, models.Manager):
    """Manager for AP_Invoice - uses generic pattern!"""
    parent_model = Invoice
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-AP'
    }
    
    def active(self):
        """Get all active (not fully paid) AP invoices."""
        return self.exclude(invoice__payment_status='PAID')


class AP_Invoice(ChildModelMixin, models.Model):
    """
    Accounts Payable Invoice - represents invoices from suppliers.
    
    ALL Invoice fields are automatically available as properties!
    No need to manually define them - they're auto-generated!
    
    Usage:
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            total=1100.00,
            supplier=supplier
        )
        
        ap_invoice.total = 1200.00
        ap_invoice.save()
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    
    invoice = models.OneToOneField(
        Invoice, 
        on_delete=models.CASCADE, 
        primary_key=True,
        related_name="ap_invoice"
    )
    
    # AP-specific fields
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.PROTECT,
        related_name="ap_invoices"
    )
    
    # Custom manager
    objects = AP_InvoiceManager()
    
    class Meta:
        db_table = 'ap_invoice'
        verbose_name = 'AP Invoice'
        verbose_name_plural = 'AP Invoices'
    
    def __str__(self):
        return f"AP Invoice: {self.supplier.name} - ${self.invoice.total}"


# ==================== AR INVOICE ====================

class AR_InvoiceManager(ChildModelManagerMixin, models.Manager):
    """Manager for AR_Invoice - uses generic pattern!"""
    parent_model = Invoice
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-AR'
    }
    
    def active(self):
        """Get all active (not fully paid) AR invoices."""
        return self.exclude(invoice__payment_status='PAID')


class AR_Invoice(ChildModelMixin, models.Model):
    """
    Accounts Receivable Invoice - represents invoices to customers.
    
    ALL Invoice fields are automatically available as properties!
    
    Usage:
        ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            total=5500.00,
            customer=customer
        )
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    
    invoice = models.OneToOneField(
        Invoice, 
        on_delete=models.CASCADE, 
        primary_key=True,
        related_name="ar_invoice"
    )
    
    # AR-specific fields
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.PROTECT,
        related_name="ar_invoices"
    )
    
    # Custom manager
    objects = AR_InvoiceManager()
    
    class Meta:
        db_table = 'ar_invoice'
        verbose_name = 'AR Invoice'
        verbose_name_plural = 'AR Invoices'
    
    def __str__(self):
        return f"AR Invoice: {self.customer.name} - ${self.invoice.total}"


# ==================== ONE-TIME SUPPLIER ====================

class one_use_supplierManager(ChildModelManagerMixin, models.Manager):
    """Manager for one_use_supplier - uses generic pattern!"""
    parent_model = Invoice
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-OT'
    }


class one_use_supplier(ChildModelMixin, models.Model):
    """
    One-Time Supplier - for ad-hoc suppliers without master data.
    
    ALL Invoice fields are automatically available as properties!
    
    Usage:
        one_time = one_use_supplier.objects.create(
            date=date.today(),
            currency=currency,
            total=275.00,
            supplier_name="John's Plumbing",
            supplier_address="123 Main St"
        )
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE,
        related_name="one_use_suppliers"
    )
    
    # One-time supplier fields
    supplier_name = models.CharField(max_length=255)
    supplier_address = models.TextField(blank=True)
    supplier_email = models.EmailField(blank=True)
    supplier_phone = models.CharField(max_length=50, blank=True)
    supplier_tax_id = models.CharField(max_length=50, blank=True, help_text="Tax ID/VAT number")
    
    # Custom manager
    objects = one_use_supplierManager()
    
    class Meta:
        db_table = 'one_use_supplier'
        verbose_name = 'One-Time Supplier'
        verbose_name_plural = 'One-Time Suppliers'
    
    def __str__(self):
        return f"One-Time: {self.supplier_name} - ${self.invoice.total}"

