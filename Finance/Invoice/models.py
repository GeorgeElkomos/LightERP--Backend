"""
Invoice Models - Child-Driven Pattern with DRY Principle
Follows the same architecture as BusinessPartner but with automatic field handling.

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


class InvoiceManager(models.Manager):
    """
    Custom manager for Invoice that prevents direct creation.
    """
    def create(self, **kwargs):
        raise PermissionDenied(
            "Cannot create Invoice directly. "
            "Use AP_Invoice.objects.create(), AR_Invoice.objects.create(), or "
            "one_use_supplier.objects.create() instead."
        )
    
    def bulk_create(self, objs, **kwargs):
        raise PermissionDenied(
            "Cannot bulk create Invoice directly. "
            "Use AP_Invoice, AR_Invoice, or one_use_supplier models instead."
        )


class Invoice(models.Model):
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
    objects = InvoiceManager()
    
    class Meta:
        db_table = 'invoice'
        verbose_name = 'General Invoice'
        verbose_name_plural = 'General Invoices'
    
    def __str__(self):
        return f"Invoice {self.id} - {self.date}"
    
    def save(self, *args, **kwargs):
        """Override save to prevent direct saves unless called from child class."""
        
        if not getattr(self, '_allow_direct_save', False):
            raise PermissionDenied(
                "Cannot save Invoice directly. "
                "Use child class save() method instead."
            )
        
        # Reset flag after use
        self._allow_direct_save = False
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to prevent direct deletion."""
        raise PermissionDenied(
            "Cannot delete Invoice directly. "
            "Delete the associated child invoice instead."
        )
    
    @classmethod
    def get_field_names(cls):
        """
        Get all field names from Invoice.
        This is used by child classes to auto-generate properties.
        """
        return [field.name for field in cls._meta.get_fields() 
                if not field.many_to_many and not field.one_to_many 
                and field.name != 'id']


# ==================== BASE MANAGER MIXIN ====================

class InvoiceChildManagerMixin:
    """
    Mixin for child invoice managers.
    Automatically extracts Invoice fields from kwargs.
    """
    
    def create(self, **kwargs):
        """
        Create a new child invoice along with its Invoice.
        Automatically extracts Invoice fields - NO MANUAL LISTING NEEDED!
        """
        # Get all Invoice field names dynamically
        invoice_field_names = Invoice.get_field_names()
        
        # Extract Invoice fields from kwargs
        invoice_fields = {}
        for field_name in invoice_field_names:
            if field_name in kwargs:
                invoice_fields[field_name] = kwargs.pop(field_name)
        
        # Set defaults for required fields if not provided
        if 'approval_status' not in invoice_fields:
            invoice_fields['approval_status'] = 'DRAFT'
        if 'payment_status' not in invoice_fields:
            invoice_fields['payment_status'] = 'UNPAID'
        
        # Create Invoice (with permission)
        invoice = Invoice(**invoice_fields)
        invoice._allow_direct_save = True
        invoice.save()
        
        # Create child invoice with remaining fields
        kwargs['invoice'] = invoice
        child_invoice = super().create(**kwargs)
        
        return child_invoice


# ==================== BASE MODEL MIXIN ====================

class InvoiceChildModelMixin:
    """
    Mixin for child invoice models.
    Automatically creates property proxies for ALL Invoice fields.
    """
    
    def save(self, *args, **kwargs):
        """
        Override save to handle Invoice updates automatically.
        """
        # If invoice doesn't exist yet, raise error
        if not self.invoice_id:
            raise ValidationError(
                f"Use {self.__class__.__name__}.objects.create() instead of "
                f"{self.__class__.__name__}() constructor. "
                "This ensures proper Invoice creation."
            )
        
        # Get all Invoice field names dynamically
        invoice_field_names = Invoice.get_field_names()
        
        # Update Invoice if any of its fields were set
        invoice_updated = False
        
        for field_name in invoice_field_names:
            temp_attr = f'_{field_name}_temp'
            if hasattr(self, temp_attr):
                setattr(self.invoice, field_name, getattr(self, temp_attr))
                delattr(self, temp_attr)
                invoice_updated = True
        
        if invoice_updated:
            self.invoice._allow_direct_save = True
            self.invoice.save()
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to also delete the associated Invoice.
        """
        invoice = self.invoice

        # Delete the child first
        super().delete(*args, **kwargs)
        
        try:
            invoice.refresh_from_db()

            # Get all OneToOne reverse relations (children)
            has_children = False
            for related_object in invoice._meta.related_objects:
                if related_object.one_to_one:
                    # Check if this child still exists
                    if hasattr(invoice, related_object.get_accessor_name()):
                        has_children = True
                        break
             # If no children left, delete the BusinessPartner
            if not has_children:
                invoice._allow_direct_save = True
                super(Invoice, invoice).delete(*args, **kwargs)
        except Invoice.DoesNotExist:
            # Already deleted, nothing to do
            pass
    
    def __init__(self, *args, **kwargs):
        """
        Override __init__ to dynamically create property proxies.
        """
        super().__init__(*args, **kwargs)
        
        # Dynamically create property proxies for all Invoice fields
        if not hasattr(self.__class__, '_properties_created'):
            self.__class__._create_invoice_properties()
            self.__class__._properties_created = True
    
    @classmethod
    def _create_invoice_properties(cls):
        """
        Dynamically create property proxies for all Invoice fields.
        This runs once per class and creates properties for ALL fields automatically!
        """
        invoice_field_names = Invoice.get_field_names()
        
        for field_name in invoice_field_names:
            # Skip if property already exists
            if hasattr(cls, field_name):
                continue
            
            # Create getter and setter functions
            def make_property(fname):
                def getter(self):
                    return getattr(self.invoice, fname)
                
                def setter(self, value):
                    setattr(self, f'_{fname}_temp', value)
                    if self.invoice_id:
                        setattr(self.invoice, fname, value)
                
                return property(getter, setter)
            
            # Add property to class
            setattr(cls, field_name, make_property(field_name))


# ==================== AP INVOICE ====================

class AP_InvoiceManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for AP_Invoice - inherits all auto-magic from mixin!"""
    
    def active(self):
        """Get all active (not fully paid) AP invoices."""
        return self.exclude(invoice__payment_status='PAID')


class AP_Invoice(InvoiceChildModelMixin, models.Model):
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

class AR_InvoiceManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for AR_Invoice - inherits all auto-magic from mixin!"""
    
    def active(self):
        """Get all active (not fully paid) AR invoices."""
        return self.exclude(invoice__payment_status='PAID')


class AR_Invoice(InvoiceChildModelMixin, models.Model):
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

class one_use_supplierManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for one_use_supplier - inherits all auto-magic from mixin!"""
    pass


class one_use_supplier(InvoiceChildModelMixin, models.Model):
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
