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
    supplier=supplier  # business_partner auto-set!
)

# CORRECT - Update works automatically
ap_invoice.total = 1200.00
ap_invoice.save()  # Auto-updates Invoice!

# Update supplier - business_partner auto-syncs!
ap_invoice.supplier = new_supplier
ap_invoice.save()  # business_partner updated automatically!
"""

from django.db import models
from django.core.exceptions import ValidationError
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import BusinessPartner, Customer, OneTime, Supplier
from Finance.GL.models import JournalEntry
from Finance.core.base_models import (
    ManagedParentModel,
    ManagedParentManager,
    ChildModelManagerMixin,
    ChildModelMixin
)


# ==================== INVOICE-SPECIFIC MIXINS ====================

class InvoiceChildManagerMixin(ChildModelManagerMixin):
    """
    Invoice-specific manager mixin that auto-sets business_partner.
    
    Extend this instead of ChildModelManagerMixin for Invoice child models.
    Set 'bp_source_field' to specify which field contains the business partner source
    (e.g., 'supplier', 'customer', 'one_time_supplier')
    """
    bp_source_field = None  # Must be set in child manager (e.g., 'supplier')
    
    def create(self, **kwargs):
        """Auto-set business_partner from the source field (supplier/customer/etc)"""
        if self.bp_source_field and self.bp_source_field in kwargs:
            if 'business_partner' not in kwargs:
                source_obj = kwargs[self.bp_source_field]
                kwargs['business_partner'] = source_obj.business_partner
        return super().create(**kwargs)


class InvoiceChildModelMixin(ChildModelMixin):
    """
    Invoice-specific child model mixin that auto-syncs business_partner.
    
    Extend this instead of ChildModelMixin for Invoice child models.
    Set 'bp_source_field' to specify which field contains the business partner source
    (e.g., 'supplier', 'customer', 'one_time_supplier')
    """
    bp_source_field = None  # Must be set in child model (e.g., 'supplier')
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Auto-sync business_partner with the source field"""
        if self.bp_source_field:
            source_field_id = f"{self.bp_source_field}_id"
            if getattr(self, source_field_id, None) and hasattr(self, 'invoice'):
                source_obj = getattr(self, self.bp_source_field)
                expected_bp = source_obj.business_partner
                # Auto-update business_partner to match source
                if self.invoice.business_partner_id != expected_bp.id:
                    self.invoice.business_partner = expected_bp
                    # Save the parent Invoice to persist the change
                    self.invoice._allow_direct_save = True
                    self.invoice.save()
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validation: Ensure business_partner matches source field"""
        super().clean()
        if self.bp_source_field:
            source_field_id = f"{self.bp_source_field}_id"
            if getattr(self, source_field_id, None) and hasattr(self, 'invoice'):
                source_obj = getattr(self, self.bp_source_field)
                if self.invoice.business_partner_id != source_obj.business_partner_id:
                    raise ValidationError({
                        self.bp_source_field: f'{self.bp_source_field.replace("_", " ").title()}\'s business partner must match invoice business partner.'
                    })


# ==================== INVOICE PARENT MODEL ====================

class Invoice(ManagedParentModel, models.Model):
    """
    General Invoice - MANAGED BASE CLASS (Interface-like)
    
    ⚠️ WARNING: Do NOT create, update, or delete Invoice instances directly!
    
    This model serves as a shared data container for AP_Invoice, AR_Invoice, and OneTimeSupplier.
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
    
    # Business Partner - Common field for all invoice types
    business_partner = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name="invoices",
        help_text="The business partner associated with this invoice (auto-set from child type)"
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
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Amount paid so far (cannot exceed total)"
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
    
    # ==================== PAYMENT HELPER FUNCTIONS ====================
    
    def is_paid(self):
        """
        Check if invoice is fully paid.
        
        Returns:
            bool: True if paid_amount equals total, False otherwise
        """
        if self.total is None:
            return False
        return self.paid_amount >= self.total
    
    def is_partially_paid(self):
        """
        Check if invoice has partial payment.
        
        Returns:
            bool: True if paid_amount > 0 but < total
        """
        if self.total is None:
            return False
        return 0 < self.paid_amount < self.total
    
    def remaining_amount(self):
        """
        Calculate remaining unpaid amount.
        
        Returns:
            Decimal: Total minus paid_amount
        """
        if self.total is None:
            return 0
        return self.total - self.paid_amount
    
    def can_pay(self, amount):
        """
        Validate if payment amount is acceptable.
        
        Args:
            amount (Decimal): Payment amount to validate
            
        Returns:
            tuple: (bool, str) - (is_valid, error_message)
        """
        if amount <= 0:
            return False, "Payment amount must be greater than zero"
        
        if self.total is None:
            return False, "Cannot pay invoice without total amount"
        
        if self.paid_amount + amount > self.total:
            return False, f"Payment amount exceeds remaining balance of {self.remaining_amount()}"
        
        return True, ""
    
    def pay(self, amount):
        """
        Add payment to the invoice.
        
        Args:
            amount (Decimal): Payment amount to add
            
        Raises:
            ValidationError: If payment amount is invalid or exceeds total
        """
        from decimal import Decimal
        
        # Validate amount
        can_pay, error_msg = self.can_pay(amount)
        if not can_pay:
            raise ValidationError(error_msg)
        
        # Add payment
        self.paid_amount += Decimal(str(amount))
        
        # Update payment status
        self.update_payment_status()
        
        # Save with bypass flag
        self._allow_direct_save = True
        self.save()
    
    def refund(self, amount):
        """
        Subtract refund from paid amount.
        
        Args:
            amount (Decimal): Refund amount to subtract
            
        Raises:
            ValidationError: If refund amount exceeds paid amount
        """
        from decimal import Decimal
        
        if amount <= 0:
            raise ValidationError("Refund amount must be greater than zero")
        
        if amount > self.paid_amount:
            raise ValidationError(f"Refund amount {amount} exceeds paid amount {self.paid_amount}")
        
        # Subtract refund
        self.paid_amount -= Decimal(str(amount))
        
        # Update payment status
        self.update_payment_status()
        
        # Save with bypass flag
        self._allow_direct_save = True
        self.save()
    
    def update_payment_status(self):
        """
        Auto-update payment_status field based on paid_amount.
        
        Sets status to:
        - PAID if fully paid
        - PARTIALLY_PAID if partially paid
        - UNPAID if nothing paid
        """
        if self.is_paid():
            self.payment_status = self.PAID
        elif self.is_partially_paid():
            self.payment_status = self.PARTIALLY_PAID
        else:
            self.payment_status = self.UNPAID
    
    def recalculate_paid_amount(self):
        """
        Recalculate paid_amount from all payment allocations.
        
        This method should be used to fix any inconsistencies between
        paid_amount and the sum of payment allocations.
        
        Returns:
            tuple: (old_amount, new_amount, was_changed)
        """
        from decimal import Decimal
        
        old_amount = self.paid_amount
        
        # Calculate from allocations
        total_allocated = self.payment_allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        
        # Update if different
        was_changed = old_amount != total_allocated
        if was_changed:
            self.paid_amount = total_allocated
            self.update_payment_status()
            self._allow_direct_save = True
            self.save(update_fields=['paid_amount', 'payment_status'])
        
        return (old_amount, total_allocated, was_changed)
    
    def get_payment_allocations_summary(self):
        """
        Get a summary of all payment allocations for this invoice.
        
        Returns:
            dict: Summary with total_allocated, allocation_count, and allocations list
        """
        from decimal import Decimal
        
        allocations = self.payment_allocations.select_related('payment').all()
        
        total = allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        
        return {
            'total_allocated': total,
            'allocation_count': allocations.count(),
            'allocations': [
                {
                    'payment_id': alloc.payment_id,
                    'payment_date': alloc.payment.date,
                    'amount': alloc.amount_allocated,
                    'created_at': alloc.created_at
                }
                for alloc in allocations
            ]
        }
    
    def validate_paid_amount(self):
        """
        Validate that paid_amount matches the sum of payment allocations.
        
        Returns:
            tuple: (is_valid, expected_amount, actual_amount, difference)
        """
        from decimal import Decimal
        
        expected = self.payment_allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        
        actual = self.paid_amount
        is_valid = expected == actual
        difference = actual - expected
        
        return (is_valid, expected, actual, difference)


class InvoiceItem(models.Model):
    """Invoice Line Item"""
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
   
    class Meta:
        db_table = 'invoice_item'
    
    def __str__(self):
        return f"{self.invoice.id} - {self.description[:30]}"


# ==================== AP INVOICE ====================

class AP_InvoiceManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for AP_Invoice - uses Invoice-specific pattern!"""
    parent_model = Invoice
    bp_source_field = 'supplier'  # ← Auto-extracts business_partner from supplier
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-AP'
    }
    
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
            supplier=supplier  # business_partner auto-set!
        )
        
        # Update supplier - business_partner auto-syncs
        ap_invoice.supplier = new_supplier
        ap_invoice.save()
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    bp_source_field = 'supplier'  # ← Auto-syncs business_partner from supplier
    
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
    """Manager for AR_Invoice - uses Invoice-specific pattern!"""
    parent_model = Invoice
    bp_source_field = 'customer'  # ← Auto-extracts business_partner from customer
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-AR'
    }
    
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
            customer=customer  # business_partner auto-set!
        )
        
        # Update customer - business_partner auto-syncs
        ar_invoice.customer = new_customer
        ar_invoice.save()
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    bp_source_field = 'customer'  # ← Auto-syncs business_partner from customer
    
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

class OneTimeSupplierManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for OneTimeSupplier - uses Invoice-specific pattern!"""
    parent_model = Invoice
    bp_source_field = 'one_time_supplier'  # ← Auto-extracts business_partner from one_time_supplier
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-OT'
    }


class OneTimeSupplier(InvoiceChildModelMixin, models.Model):
    """
    One-Time Supplier - for ad-hoc suppliers without master data.
    
    ALL Invoice fields are automatically available as properties!
    
    Usage:
        one_time = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            total=275.00,
            one_time_supplier=one_time_supplier_instance
        )
        
        # Update one_time_supplier - business_partner auto-syncs
        one_time.one_time_supplier = new_one_time
        one_time.save()
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    bp_source_field = 'one_time_supplier'  # ← Auto-syncs business_partner from one_time_supplier
    
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE,
        related_name="OneTimeSuppliers"
    )
    
    # One-time supplier specific field
    one_time_supplier = models.ForeignKey(
        OneTime, 
        on_delete=models.PROTECT,
        related_name="one_time_suppliers_invoices"
    )
    
    # Custom manager
    objects = OneTimeSupplierManager()
    
    class Meta:
        db_table = 'OneTimeSupplier'
        verbose_name = 'One-Time Supplier'
        verbose_name_plural = 'One-Time Suppliers'
    
    def __str__(self):
        return f"One-Time: {self.one_time_supplier.name} - ${self.invoice.total}"

