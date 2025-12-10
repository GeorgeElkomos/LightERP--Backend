"""
Invoice Parent Model - MANAGED BASE CLASS

This is the core Invoice model that serves as a shared data container
for AP_Invoice, AR_Invoice, and OneTimeSupplier.

⚠️ WARNING: Do NOT create, update, or delete Invoice instances directly!
All operations should be performed through child classes.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import BusinessPartner
from Finance.GL.models import JournalEntry
from Finance.core.base_models import ManagedParentModel, ManagedParentManager
from core.approval.mixins import ApprovableMixin, ApprovableInterface


class Invoice(ApprovableMixin, ApprovableInterface, ManagedParentModel, models.Model):
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
    
    # Approval status choices - Define as constants for easy reference
    DRAFT = 'DRAFT'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    
    APPROVAL_STATUSES = [
        (DRAFT, 'Draft'),
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
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
        default=DRAFT,
        help_text="Approval workflow status"
    )
    
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUSES, 
        default=UNPAID,
        help_text="Payment status of the invoice"
    )
    
    # Approval tracking fields
    submitted_for_approval_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When invoice was submitted for approval"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When invoice was approved"
    )
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When invoice was rejected"
    )
    rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text="Reason for rejection"
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
    
    # ==================== APPROVAL WORKFLOW HELPER METHODS ====================
    
    def _get_child(self):
        """Get the child invoice instance dynamically.
        
        This automatically discovers ANY child model with a OneToOneField to Invoice.
        No need to modify this method when adding new invoice types!
        
        Returns:
            Child instance (AP_Invoice, AR_Invoice, etc.) or None
        """
        # Get all OneToOne related objects dynamically
        for related_object in self._meta.related_objects:
            # Check if it's a OneToOneField (not ForeignKey)
            if related_object.one_to_one:
                # Get the accessor name (e.g., 'ap_invoice', 'ar_invoice')
                accessor_name = related_object.get_accessor_name()
                # Check if this instance has that child
                if hasattr(self, accessor_name):
                    try:
                        return getattr(self, accessor_name)
                    except related_object.related_model.DoesNotExist:
                        # Child doesn't exist for this invoice
                        continue
        return None
    
    def _call_child_hook(self, method_name, *args, **kwargs):
        """Call child-specific hook method if it exists.
        
        This is the core of the callback pattern. Parent methods call this
        to delegate to child-specific implementations.
        
        Args:
            method_name: Name of the child method to call (e.g., 'on_stage_approved_child')
            *args: Positional arguments to pass to child method
            **kwargs: Keyword arguments to pass to child method
        
        Example:
            self._call_child_hook('on_stage_approved_child', stage_instance)
        """
        child = self._get_child()
        if child and hasattr(child, method_name):
            method = getattr(child, method_name)
            if callable(method):
                method(*args, **kwargs)
    
    # ==================== APPROVAL INTERFACE IMPLEMENTATION ====================
    
    def on_approval_started(self, workflow_instance):
        """Called when approval workflow starts.
        
        Parent logic: Update status and timestamp.
        Then delegates to child for type-specific logic.
        """
        # PARENT LOGIC (common to all invoice types)
        self.approval_status = Invoice.PENDING_APPROVAL
        self.submitted_for_approval_at = timezone.now()
        self._allow_direct_save = True
        self.save(update_fields=['approval_status', 'submitted_for_approval_at'])
        
        # DELEGATE TO CHILD (if child has custom logic)
        self._call_child_hook('on_approval_started_child', workflow_instance)
    
    def on_stage_approved(self, stage_instance):
        """Called when a stage is approved.
        
        Parent logic: Log the stage completion.
        Then delegates to child for type-specific logic.
        """
        # PARENT LOGIC
        stage_name = stage_instance.stage_template.name
        
        # DELEGATE TO CHILD
        self._call_child_hook('on_stage_approved_child', stage_instance)
    
    def on_fully_approved(self, workflow_instance):
        """Called when all stages are approved.
        
        Parent logic: Update status and timestamp.
        Then delegates to child for type-specific business logic.
        """
        # PARENT LOGIC
        self.approval_status = Invoice.APPROVED
        self.approved_at = timezone.now()
        self._allow_direct_save = True
        self.save(update_fields=['approval_status', 'approved_at'])
        
        # DELEGATE TO CHILD
        self._call_child_hook('on_fully_approved_child', workflow_instance)
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        """Called when workflow is rejected.
        
        Parent logic: Update status, timestamp, and capture rejection reason.
        Then delegates to child for type-specific logic.
        """
        # PARENT LOGIC
        self.approval_status = Invoice.REJECTED
        self.rejected_at = timezone.now()
        
        # Get rejection reason from last action
        if stage_instance:
            from core.approval.models import ApprovalAction
            last_action = stage_instance.actions.filter(
                action=ApprovalAction.ACTION_REJECT
            ).order_by('-created_at').first()
            if last_action and last_action.comment:
                self.rejection_reason = last_action.comment
        
        self._allow_direct_save = True
        self.save(update_fields=['approval_status', 'rejected_at', 'rejection_reason'])
        
        # DELEGATE TO CHILD
        self._call_child_hook('on_rejected_child', workflow_instance, stage_instance)
    
    def on_cancelled(self, workflow_instance, reason=None):
        """Called when workflow is cancelled.
        
        Parent logic: Reset to draft state.
        Then delegates to child for type-specific logic.
        """
        # PARENT LOGIC
        self.approval_status = Invoice.DRAFT
        self.submitted_for_approval_at = None
        self.approved_at = None
        self.rejected_at = None
        self.rejection_reason = reason or ''
        self._allow_direct_save = True
        self.save(update_fields=[
            'approval_status',
            'submitted_for_approval_at',
            'approved_at',
            'rejected_at',
            'rejection_reason'
        ])
        
        # DELEGATE TO CHILD
        self._call_child_hook('on_cancelled_child', workflow_instance, reason)
    
    # ==================== APPROVAL CONVENIENCE METHODS ====================
    
    def validate_for_submission(self):
        """Validate if invoice can be submitted for approval.
        
        Raises:
            ValidationError: If invoice cannot be submitted
        """
        if self.approval_status not in [Invoice.DRAFT]:
            raise ValidationError(
                f"Cannot submit invoice with status '{self.approval_status}'. "
                "Only DRAFT or REJECTED invoices can be submitted."
            )
        
        # Calculate subtotal from all invoice items
        from decimal import Decimal
        subtotal = Decimal('0')
        for item in self.items.all():
            item_total = item.quantity * item.unit_price
            subtotal += item_total
        
        # Assign calculated subtotal
        self.subtotal = subtotal
        
        # Calculate tax amount (if tax_amount is not already set)
        if self.tax_amount is None:
            self.tax_amount = Decimal('0')
        
        # Calculate total (subtotal + tax)
        self.total = self.subtotal + self.tax_amount
        
        if not self.gl_distributions.is_balanced() or self.gl_distributions.get_total_debit() != self.total:
            raise ValidationError(
                "GL Distributions must be balanced and match the invoice total."
            )
        
        # Save the calculated values
        self._allow_direct_save = True
        self.save(update_fields=['subtotal', 'tax_amount', 'total'])
    
    def submit_for_approval(self):
        """Submit invoice for approval workflow.
        
        Returns:
            ApprovalWorkflowInstance
            
        Raises:
            ValueError: If invoice cannot be submitted
        """
        from core.approval.managers import ApprovalManager
        
        self.validate_for_submission()
        
        return ApprovalManager.start_workflow(self)
    
    def approve_by_user(self, user, comment=None):
        """Approve invoice (by user).
        
        Args:
            user: User performing the approval
            comment: Optional approval comment
            
        Returns:
            ApprovalWorkflowInstance
        """
        from core.approval.managers import ApprovalManager
        return ApprovalManager.process_action(
            self, user, 'approve', comment=comment
        )
    
    def reject_by_user(self, user, comment=None):
        """Reject invoice (by user).
        
        Args:
            user: User performing the rejection
            comment: Optional rejection reason
            
        Returns:
            ApprovalWorkflowInstance
        """
        from core.approval.managers import ApprovalManager
        return ApprovalManager.process_action(
            self, user, 'reject', comment=comment
        )
    
    def can_be_approved_by(self, user):
        """Check if user can approve this invoice.
        
        Args:
            user: User to check
            
        Returns:
            bool: True if user can approve
        """
        if not self.has_pending_approval():
            return False
        
        current_approvers = self.get_current_approvers()
        return user in current_approvers

    def can_post_tp_gl(self):
        """Check if the invoice can post third-party GL entries.
        
        Returns:
            bool: True if invoice is approved and fully paid
        """
        return self.approval_status == Invoice.APPROVED
    
    def post_to_gl(self):
        """Post the invoice to the GL system.
        
        Raises:
            ValueError: If invoice cannot post to GL
        """
        if not self.can_post_tp_gl():
            raise ValueError("Invoice must be approved to post to GL.")
        
        self.gl_distributions.post()
        
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
