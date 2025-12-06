"""
Payment Models - Extensible Parent-Child Design
================================================

IMPORTANT DESIGN PATTERN:
========================
Payment is a MANAGED BASE CLASS that should NEVER be directly created, 
updated, or deleted. All operations MUST go through child payment classes
like StandardInvoicePayment.

This pattern allows adding new payment types in the future without 
modifying the base Payment class.

Usage Examples:
--------------
# CORRECT - Create a customer payment for invoices
payment = StandardInvoicePayment.objects.create(
    direction=StandardInvoicePayment.INCOMING,
    partner_type=StandardInvoicePayment.PARTNER_CUSTOMER,
    business_partner=customer.partner,
    amount=Decimal('1000.00'),
    currency=usd,
    date=date.today(),
)

# CORRECT - Use factory methods
payment = StandardInvoicePayment.create_customer_payment(
    customer=customer,
    amount=Decimal('1000.00'),
    currency=usd,
    date=date.today(),
)

# WRONG - Don't do this!
# payment = Payment.objects.create(...)  # This will raise an error!
"""
from django.db import models, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import BusinessPartner, Customer, Supplier
from Finance.Invoice.models import Genral_Invoice, AP_Invoice, AR_Invoice
from Finance.GL.models import JournalEntry


# ==============================================================================
# PAYMENT BASE CLASS (Managed - Do Not Create Directly)
# ==============================================================================

class PaymentManager(models.Manager):
    """
    Custom manager for Payment that prevents direct creation.
    All payments must be created through child classes (e.g., StandardInvoicePayment).
    """
    def create(self, **kwargs):
        raise PermissionDenied(
            "Cannot create Payment directly. "
            "Use StandardInvoicePayment.objects.create() or other payment type classes instead."
        )
    
    def bulk_create(self, objs, **kwargs):
        raise PermissionDenied(
            "Cannot bulk create Payment directly. "
            "Use child payment type classes instead."
        )


class Payment(models.Model):
    """
    Payment - MANAGED BASE CLASS
    
    ⚠️ WARNING: Do NOT create, update, or delete Payment instances directly!
    
    This model serves as a shared data container for all payment types.
    All operations should be performed through child payment classes
    (e.g., StandardInvoicePayment), which will automatically manage 
    the associated Payment instance.
    
    Common Fields:
        payment_number: Auto-generated unique reference number
        date: Payment date
        amount: Payment amount
        currency: Payment currency
        exchange_rate: Exchange rate to base currency
        status: Workflow status (DRAFT → PENDING_APPROVAL → APPROVED → POSTED)
        is_posted: Whether payment is posted to GL
        gl_entry: Link to GL journal entry when posted
        memo: Notes/comments
    
    Relationships:
        - standard_invoice_payment: OneToOne to StandardInvoicePayment (if this is an invoice payment)
        - allocations: PaymentAllocation records linking to invoices
    """
    
    # Status choices (shared by all payment types)
    DRAFT = 'DRAFT'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    VOIDED = 'VOIDED'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (VOIDED, 'Voided'),
    ]
    
    # Core fields
    payment_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Auto-generated payment reference number"
    )
    date = models.DateField()
    
    # Amount fields
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Payment amount"
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Exchange rate to base currency at payment date"
    )
    
    # Status and workflow
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT
    )
    rejection_reason = models.TextField(null=True, blank=True)
    
    # Posting
    is_posted = models.BooleanField(default=False)
    posted_date = models.DateField(null=True, blank=True)
    gl_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Notes
    memo = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom manager to prevent direct creation
    objects = PaymentManager()
    
    class Meta:
        db_table = 'payment'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.payment_number} - {self.amount} {self.currency.code}"
    
    def save(self, *args, **kwargs):
        """
        Override save to prevent direct saves unless called from child class.
        """
        import inspect
        frame = inspect.currentframe()
        caller_locals = frame.f_back.f_locals
        
        # Allow save if it's being called from a child class or _allow_direct_save flag is set
        if not getattr(self, '_allow_direct_save', False):
            caller_self = caller_locals.get('self')
            if not isinstance(caller_self, (StandardInvoicePayment,)):
                raise PermissionDenied(
                    "Cannot save Payment directly. "
                    "Use StandardInvoicePayment or other child class save() method instead."
                )
        
        # Auto-generate payment number if not set
        if not self.payment_number:
            self._generate_payment_number()
        
        super().save(*args, **kwargs)
    
    def _generate_payment_number(self):
        """Generate a unique payment number. Can be overridden by child classes."""
        last = Payment.objects.order_by('-pk').first()
        next_num = (last.pk + 1) if last else 1
        self.payment_number = f"PAY-{next_num:06d}"
    
    def delete(self, *args, **kwargs):
        """
        Override delete to prevent direct deletion.
        """
        raise PermissionDenied(
            "Cannot delete Payment directly. "
            "Delete the associated payment type (e.g., StandardInvoicePayment) instead."
        )
    
    # ==================== PAYMENT TYPE DETECTION ====================
    
    def get_payment_type(self):
        """
        Get the type of payment.
        
        Returns:
            str: 'StandardInvoicePayment' or 'Unknown'
        """
        if hasattr(self, 'standard_invoice_payment') and self.standard_invoice_payment is not None:
            return 'StandardInvoicePayment'
        return 'Unknown'
    
    def get_child_payment(self):
        """
        Get the child payment instance.
        
        Returns:
            The child payment instance or None
        """
        if hasattr(self, 'standard_invoice_payment') and self.standard_invoice_payment is not None:
            return self.standard_invoice_payment
        return None
    
    # ==================== VALIDATION METHODS ====================
    
    def validate_amount(self):
        """Validate payment amount is positive."""
        if self.amount is None or self.amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero'})
    
    def validate_for_submission(self):
        """
        Validate payment is ready for submission.
        Child classes should override to add specific validation.
        """
        errors = {}
        
        if not self.amount or self.amount <= 0:
            errors['amount'] = 'Payment amount must be greater than zero'
        
        if not self.date:
            errors['date'] = 'Payment date is required'
        
        # Check if payment has allocations
        if not self.allocations.exists():
            errors['allocations'] = 'Payment must be allocated to at least one invoice'
        
        if errors:
            raise ValidationError(errors)
        
        return True
    
    def validate_for_posting(self):
        """Validate payment is ready to be posted."""
        if self.status != self.APPROVED:
            raise ValidationError('Payment must be approved before posting')
        
        if self.is_posted:
            raise ValidationError('Payment is already posted')
        
        self.validate_amount()
        return True
    
    # ==================== WORKFLOW METHODS ====================
    
    def can_submit(self):
        """Check if payment can be submitted for approval."""
        return self.status == self.DRAFT and not self.is_posted
    
    def submit_for_approval(self):
        """Submit payment for approval."""
        if not self.can_submit():
            raise ValidationError(f'Cannot submit payment with status: {self.status}')
        
        self.validate_for_submission()
        self.status = self.PENDING_APPROVAL
        self._allow_direct_save = True
        self.save(update_fields=['status', 'updated_at'])
        return True
    
    def can_approve(self):
        """Check if payment can be approved."""
        return self.status == self.PENDING_APPROVAL and not self.is_posted
    
    def approve(self, approved_by=None):
        """Approve the payment."""
        if not self.can_approve():
            raise ValidationError(f'Cannot approve payment with status: {self.status}')
        
        self.status = self.APPROVED
        self._allow_direct_save = True
        self.save(update_fields=['status', 'updated_at'])
        return True
    
    def can_reject(self):
        """Check if payment can be rejected."""
        return self.status == self.PENDING_APPROVAL and not self.is_posted
    
    def reject(self, reason):
        """Reject the payment."""
        if not self.can_reject():
            raise ValidationError(f'Cannot reject payment with status: {self.status}')
        
        if not reason:
            raise ValidationError('Rejection reason is required')
        
        self.status = self.REJECTED
        self.rejection_reason = reason
        self._allow_direct_save = True
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return True
    
    def revert_to_draft(self):
        """Revert rejected payment back to draft."""
        if self.status not in [self.REJECTED, self.PENDING_APPROVAL]:
            raise ValidationError('Can only revert rejected or pending payments')
        
        if self.is_posted:
            raise ValidationError('Cannot revert posted payment')
        
        self.status = self.DRAFT
        self.rejection_reason = None
        self._allow_direct_save = True
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return True
    
    # ==================== POSTING METHODS ====================
    
    def can_post(self):
        """Check if payment can be posted."""
        return self.status == self.APPROVED and not self.is_posted
    
    @transaction.atomic
    def post(self):
        """Post payment to GL and update invoice payment statuses."""
        self.validate_for_posting()
        
        # Create GL entries (child classes can override _create_gl_entries)
        gl_entry = self._create_gl_entries()
        if gl_entry:
            self.gl_entry = gl_entry
        
        # Update invoice payment statuses
        self._update_invoice_payment_statuses()
        
        self.is_posted = True
        self.posted_date = timezone.now().date()
        self._allow_direct_save = True
        self.save(update_fields=['is_posted', 'posted_date', 'gl_entry', 'updated_at'])
        return True
    
    def _create_gl_entries(self):
        """
        Create GL journal entries for payment posting.
        Child classes should override this to implement specific GL logic.
        """
        # TODO: Implement based on your GL structure
        return None
    
    def _update_invoice_payment_statuses(self):
        """Update payment status on all allocated invoices."""
        for allocation in self.allocations.all():
            if allocation.invoice:
                allocation.invoice.update_payment_status()
    
    def can_void(self):
        """Check if payment can be voided."""
        return self.is_posted and self.status == self.APPROVED
    
    @transaction.atomic
    def void(self, reason=None):
        """Void a posted payment."""
        if not self.can_void():
            raise ValidationError('Cannot void this payment')
        
        # Create reversing GL entries
        self._create_reversing_gl_entries()
        
        # Update invoice payment statuses
        self._update_invoice_payment_statuses()
        
        self.status = self.VOIDED
        self._allow_direct_save = True
        self.save(update_fields=['status', 'updated_at'])
        return True
    
    def _create_reversing_gl_entries(self):
        """
        Create reversing GL entries.
        Child classes should override this to implement specific GL logic.
        """
        # TODO: Implement based on your GL structure
        pass
    
    # ==================== ALLOCATION METHODS ====================
    
    def get_total_allocated(self):
        """Get total amount allocated to invoices."""
        result = self.allocations.aggregate(
            total=models.Sum('allocated_amount')
        )
        return result['total'] or Decimal('0.00')
    
    def get_unallocated_amount(self):
        """Get amount not yet allocated to invoices."""
        return self.amount - self.get_total_allocated()
    
    def is_fully_allocated(self):
        """Check if payment is fully allocated."""
        return self.get_unallocated_amount() <= Decimal('0.00')
    
    # ==================== CRUD METHODS ====================
    
    def can_modify(self):
        """Check if payment can be modified."""
        return not self.is_posted and self.status in [self.DRAFT, self.REJECTED]
    
    def can_delete(self):
        """Check if payment can be deleted."""
        return not self.is_posted and self.status == self.DRAFT
    
    # ==================== PROPERTIES ====================
    
    @property
    def amount_in_base_currency(self):
        """Get payment amount in base currency."""
        if self.currency.is_base_currency:
            return self.amount
        
        if self.exchange_rate:
            return self.amount * self.exchange_rate
        
        return None


# ==============================================================================
# STANDARD INVOICE PAYMENT (Child Class for AP/AR Invoice Payments)
# ==============================================================================

class StandardInvoicePaymentManager(models.Manager):
    """
    Custom manager for StandardInvoicePayment with automatic Payment creation.
    """
    def create(self, **kwargs):
        """
        Create a new StandardInvoicePayment along with its parent Payment.
        
        Automatically extracts Payment fields and creates both objects.
        """
        # Extract Payment fields
        payment_fields = {
            'date': kwargs.pop('date'),
            'amount': kwargs.pop('amount'),
            'currency': kwargs.pop('currency'),
            'exchange_rate': kwargs.pop('exchange_rate', None),
            'status': kwargs.pop('status', Payment.DRAFT),
            'memo': kwargs.pop('memo', ''),
        }
        
        # Create Payment (with permission)
        payment = Payment(**payment_fields)
        payment._allow_direct_save = True
        
        # Generate appropriate payment number based on direction
        direction = kwargs.get('direction', StandardInvoicePayment.INCOMING)
        prefix = 'RCP' if direction == StandardInvoicePayment.INCOMING else 'PMT'
        last = Payment.objects.order_by('-pk').first()
        next_num = (last.pk + 1) if last else 1
        payment.payment_number = f"{prefix}-{next_num:06d}"
        
        payment.save()
        
        # Create StandardInvoicePayment with remaining fields
        kwargs['payment'] = payment
        std_payment = super().create(**kwargs)
        
        return std_payment
    
    def active(self):
        """Get all active (non-voided) payments."""
        return self.filter(payment__status__in=[
            Payment.DRAFT, 
            Payment.PENDING_APPROVAL, 
            Payment.APPROVED
        ])
    
    def incoming(self):
        """Get all incoming (customer) payments."""
        return self.filter(direction=StandardInvoicePayment.INCOMING)
    
    def outgoing(self):
        """Get all outgoing (supplier) payments."""
        return self.filter(direction=StandardInvoicePayment.OUTGOING)


class StandardInvoicePayment(models.Model):
    """
    Standard Invoice Payment - for paying AP and AR invoices.
    
    This class automatically manages the associated Payment instance.
    All Payment fields are accessible as properties on this class.
    
    Usage:
        # Create a customer payment
        payment = StandardInvoicePayment.objects.create(
            direction=StandardInvoicePayment.INCOMING,
            partner_type=StandardInvoicePayment.PARTNER_CUSTOMER,
            business_partner=customer.partner,
            amount=Decimal('1000.00'),
            currency=usd,
            date=date.today(),
        )
        
        # Or use factory methods
        payment = StandardInvoicePayment.create_customer_payment(
            customer=customer,
            amount=Decimal('1000.00'),
            currency=usd,
            date=date.today(),
        )
        
        # Access Payment fields via properties
        print(payment.payment_number)  # Proxied from payment
        print(payment.status)  # Proxied from payment
        
        # Allocate to invoices
        payment.allocate_to_invoice(invoice, amount=Decimal('500.00'))
    """
    
    # Payment direction
    INCOMING = 'IN'   # Customer payment (AR)
    OUTGOING = 'OUT'  # Supplier payment (AP)
    DIRECTION_CHOICES = [
        (INCOMING, 'Incoming (Receipt)'),
        (OUTGOING, 'Outgoing (Disbursement)'),
    ]
    
    # Partner types
    PARTNER_CUSTOMER = 'CUSTOMER'
    PARTNER_SUPPLIER = 'SUPPLIER'
    PARTNER_OTHER = 'OTHER'
    PARTNER_TYPE_CHOICES = [
        (PARTNER_CUSTOMER, 'Customer'),
        (PARTNER_SUPPLIER, 'Supplier'),
        (PARTNER_OTHER, 'Other'),
    ]
    
    # Link to parent Payment
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name='standard_invoice_payment'
    )
    
    # Direction and partner info
    
    partner_type = models.CharField(
        max_length=10,
        choices=PARTNER_TYPE_CHOICES,
        help_text="Type of business partner"
    )
    business_partner = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='standard_invoice_payments',
        help_text="The business partner (customer/supplier) for this payment"
    )
    
    # Reference number (check number, wire transfer ID, etc.)
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="External reference (check number, wire transfer ID, etc.)"
    )
    
    # Custom manager
    objects = StandardInvoicePaymentManager()
    
    class Meta:
        db_table = 'standard_invoice_payment'
        verbose_name = 'Standard Invoice Payment'
        verbose_name_plural = 'Standard Invoice Payments'
    
    def __str__(self):
        partner_name = self.business_partner.name if self.business_partner else 'N/A'
        return f"{self.payment.payment_number} - {partner_name} - {self.payment.amount} {self.payment.currency.code}"
    
    def save(self, *args, **kwargs):
        """
        Override save to handle Payment updates.
        """
        if not self.payment_id:
            raise ValidationError(
                "Use StandardInvoicePayment.objects.create() instead of StandardInvoicePayment() constructor. "
                "This ensures proper Payment creation."
            )
        
        # Update Payment if any of its fields were set on this instance
        payment_fields = ['date', 'amount', 'currency', 'exchange_rate', 'memo']
        payment_updated = False
        
        for field in payment_fields:
            if hasattr(self, f'_{field}_temp'):
                setattr(self.payment, field, getattr(self, f'_{field}_temp'))
                delattr(self, f'_{field}_temp')
                payment_updated = True
        
        if payment_updated:
            self.payment._allow_direct_save = True
            self.payment.save()
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate payment consistency."""
        super().clean()
        
        # Validate direction matches partner type
        if self.partner_type == self.PARTNER_CUSTOMER and self.direction != self.INCOMING:
            raise ValidationError('Customer payments must be incoming (receipts)')
        if self.partner_type == self.PARTNER_SUPPLIER and self.direction != self.OUTGOING:
            raise ValidationError('Supplier payments must be outgoing (disbursements)')
    
    def delete(self, *args, **kwargs):
        """
        Override delete to also delete the associated Payment.
        """
        payment = self.payment
        super().delete(*args, **kwargs)
        
        # Delete parent Payment
        payment._allow_direct_save = True
        super(Payment, payment).delete(*args, **kwargs)
    
    # ==================== PROPERTY PROXIES FOR PAYMENT FIELDS ====================
    
    @property
    def payment_number(self):
        return self.payment.payment_number
    
    @property
    def date(self):
        return self.payment.date
    
    @date.setter
    def date(self, value):
        self._date_temp = value
        if self.payment_id:
            self.payment.date = value
    
    @property
    def amount(self):
        return self.payment.amount
    
    @amount.setter
    def amount(self, value):
        self._amount_temp = value
        if self.payment_id:
            self.payment.amount = value
    
    @property
    def currency(self):
        return self.payment.currency
    
    @currency.setter
    def currency(self, value):
        self._currency_temp = value
        if self.payment_id:
            self.payment.currency = value
    
    @property
    def exchange_rate(self):
        return self.payment.exchange_rate
    
    @exchange_rate.setter
    def exchange_rate(self, value):
        self._exchange_rate_temp = value
        if self.payment_id:
            self.payment.exchange_rate = value
    
    @property
    def status(self):
        return self.payment.status
    
    @property
    def rejection_reason(self):
        return self.payment.rejection_reason
    
    @property
    def is_posted(self):
        return self.payment.is_posted
    
    @property
    def posted_date(self):
        return self.payment.posted_date
    
    @property
    def gl_entry(self):
        return self.payment.gl_entry
    
    @property
    def memo(self):
        return self.payment.memo
    
    @memo.setter
    def memo(self, value):
        self._memo_temp = value
        if self.payment_id:
            self.payment.memo = value
    
    @property
    def created_at(self):
        return self.payment.created_at
    
    @property
    def updated_at(self):
        return self.payment.updated_at
    
    @property
    def allocations(self):
        """Get payment allocations from parent Payment."""
        return self.payment.allocations
    
    @property
    def amount_in_base_currency(self):
        return self.payment.amount_in_base_currency
    
    # ==================== CONVENIENCE PROPERTIES ====================
    
    @property
    def is_incoming(self):
        return self.direction == self.INCOMING
    
    @property
    def is_outgoing(self):
        return self.direction == self.OUTGOING
    
    @property
    def is_customer_payment(self):
        return self.partner_type == self.PARTNER_CUSTOMER
    
    @property
    def is_supplier_payment(self):
        return self.partner_type == self.PARTNER_SUPPLIER
    
    # ==================== WORKFLOW METHOD PROXIES ====================
    
    def can_submit(self):
        return self.payment.can_submit()
    
    def submit_for_approval(self):
        return self.payment.submit_for_approval()
    
    def can_approve(self):
        return self.payment.can_approve()
    
    def approve(self, approved_by=None):
        return self.payment.approve(approved_by)
    
    def can_reject(self):
        return self.payment.can_reject()
    
    def reject(self, reason):
        return self.payment.reject(reason)
    
    def revert_to_draft(self):
        return self.payment.revert_to_draft()
    
    def can_post(self):
        return self.payment.can_post()
    
    def post(self):
        return self.payment.post()
    
    def can_void(self):
        return self.payment.can_void()
    
    def void(self, reason=None):
        return self.payment.void(reason)
    
    # ==================== ALLOCATION METHODS ====================
    
    def get_total_allocated(self):
        return self.payment.get_total_allocated()
    
    def get_unallocated_amount(self):
        return self.payment.get_unallocated_amount()
    
    def is_fully_allocated(self):
        return self.payment.is_fully_allocated()
    
    def allocate_to_invoice(self, invoice, amount, discount_amount=None, write_off_amount=None):
        """
        Allocate this payment to an invoice.
        
        Args:
            invoice: Genral_Invoice (or AR_Invoice/AP_Invoice)
            amount: Decimal - Amount to allocate
            discount_amount: Decimal (optional) - Early payment discount
            write_off_amount: Decimal (optional) - Write-off amount
        Returns:
            PaymentAllocation: Created allocation
        """
        # Handle AR/AP invoice types - get base Genral_Invoice
        if hasattr(invoice, 'invoice'):
            # It's an AP_Invoice or AR_Invoice
            general_invoice = invoice.invoice
        else:
            general_invoice = invoice
        
        return PaymentAllocation.objects.create(
            payment=self.payment,
            invoice=general_invoice,
            allocated_amount=Decimal(str(amount)),
            discount_amount=Decimal(str(discount_amount)) if discount_amount else None,
            write_off_amount=Decimal(str(write_off_amount)) if write_off_amount else None
        )
    
    # ==================== CRUD METHODS ====================
    
    def can_modify(self):
        return self.payment.can_modify()
    
    def can_delete(self):
        return self.payment.can_delete()
    
    @transaction.atomic
    def safe_delete(self):
        """Safely delete payment and its allocations."""
        if not self.can_delete():
            raise ValidationError('Cannot delete this payment. Must be draft and not posted.')
        
        self.payment.allocations.all().delete()
        self.delete()
        return True
    
    # ==================== FACTORY METHODS ====================
    
    @classmethod
    @transaction.atomic
    def create_customer_payment(cls, customer, amount, currency, date, **kwargs):
        """
        Factory method to create a customer (incoming) payment.
        
        Args:
            customer: Customer - The customer making payment
            amount: Decimal - Payment amount
            currency: Currency - Payment currency
            date: date - Payment date
            **kwargs: Additional payment fields (reference_number, memo, exchange_rate)
        Returns:
            StandardInvoicePayment: Created payment
        """
        # Get the business partner from customer
        business_partner = customer.partner
        
        return cls.objects.create(
            direction=cls.INCOMING,
            partner_type=cls.PARTNER_CUSTOMER,
            business_partner=business_partner,
            amount=Decimal(str(amount)),
            currency=currency,
            date=date,
            **kwargs
        )
    
    @classmethod
    @transaction.atomic
    def create_supplier_payment(cls, supplier, amount, currency, date, **kwargs):
        """
        Factory method to create a supplier (outgoing) payment.
        
        Args:
            supplier: Supplier - The supplier receiving payment
            amount: Decimal - Payment amount
            currency: Currency - Payment currency
            date: date - Payment date
            **kwargs: Additional payment fields (reference_number, memo, exchange_rate)
        Returns:
            StandardInvoicePayment: Created payment
        """
        # Get the business partner from supplier
        business_partner = supplier.partner
        
        return cls.objects.create(
            direction=cls.OUTGOING,
            partner_type=cls.PARTNER_SUPPLIER,
            business_partner=business_partner,
            amount=Decimal(str(amount)),
            currency=currency,
            date=date,
            **kwargs
        )


# ==============================================================================
# PAYMENT ALLOCATION
# ==============================================================================

class PaymentAllocation(models.Model):
    """
    Allocation of a payment to one or more invoices.
    A single payment can be split across multiple invoices.
    Supports partial payments, discounts, and write-offs.
    """
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    invoice = models.ForeignKey(
        Genral_Invoice,
        on_delete=models.PROTECT,
        related_name='payment_allocations'
    )
    
    # Allocation amounts
    allocated_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Amount allocated to this invoice from the payment"
    )
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Early payment discount amount"
    )
    write_off_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Write-off amount (small balance write-off)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_allocation'
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'
        unique_together = ['payment', 'invoice']
    
    def __str__(self):
        return f"{self.payment.payment_number} → Invoice #{self.invoice.invoice_number}: {self.allocated_amount}"
    
    @property
    def total_settlement(self):
        """Total amount settling the invoice (allocated + discount + write-off)."""
        total = self.allocated_amount
        if self.discount_amount:
            total += self.discount_amount
        if self.write_off_amount:
            total += self.write_off_amount
        return total
    
    def _get_payment_direction(self):
        """
        Get the payment direction from the child payment type.
        Returns None if payment type doesn't have direction.
        """
        if hasattr(self.payment, 'standard_invoice_payment') and self.payment.standard_invoice_payment:
            return self.payment.standard_invoice_payment.direction
        return None
    
    def clean(self):
        """Validate the allocation."""
        super().clean()
        
        if self.allocated_amount is None or self.allocated_amount <= 0:
            raise ValidationError({'allocated_amount': 'Allocation amount must be greater than zero'})
        
        # Check payment direction matches invoice type (for StandardInvoicePayment)
        if self.payment and self.invoice:
            direction = self._get_payment_direction()
            
            if direction is not None:
                if direction == StandardInvoicePayment.INCOMING:
                    # Incoming payment should be for AR invoices
                    if not hasattr(self.invoice, 'ar_invoice'):
                        raise ValidationError(
                            'Incoming payments can only be allocated to AR invoices'
                        )
                else:
                    # Outgoing payment should be for AP invoices
                    if not hasattr(self.invoice, 'ap_invoice'):
                        raise ValidationError(
                            'Outgoing payments can only be allocated to AP invoices'
                        )
        
        # Check allocation doesn't exceed invoice balance
        if self.invoice:
            balance = self.invoice.get_balance_due()
            # Exclude current allocation if updating
            if self.pk:
                current = PaymentAllocation.objects.get(pk=self.pk)
                balance += current.total_settlement
            
            if self.total_settlement > balance:
                raise ValidationError({
                    'allocated_amount': f'Total settlement ({self.total_settlement}) exceeds invoice balance ({balance})'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
