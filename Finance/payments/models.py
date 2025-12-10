from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from Finance.core.models import Currency
from Finance.BusinessPartner.models import BusinessPartner
from Finance.Invoice.models import Invoice
from Finance.GL.models import JournalEntry
from core.approval.mixins import ApprovableMixin, ApprovableInterface

class Payment(ApprovableMixin, ApprovableInterface, models.Model):
    
    # Status choices (shared by all payment types)
    DRAFT = 'DRAFT'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]
    
    date = models.DateField()
    
    business_partner = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='payments'
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
    approval_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
        help_text="Approval workflow status"
    )
    
    # Approval tracking fields
    submitted_for_approval_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was submitted for approval"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was approved"
    )
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was rejected"
    )
    rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text="Reason for rejection"
    )
    
    gl_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        db_table = 'payment'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"Payment {self.id} - {self.business_partner} - {self.date}"
    
    # ==================== PAYMENT ALLOCATION HELPER METHODS ====================
    
    def get_total_allocated(self):
        """
        Calculate total amount allocated from this payment to invoices.
        
        Returns:
            Decimal: Sum of all allocation amounts
        """
        total = self.allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        return total
    
    def get_allocated_invoices(self):
        """
        Get all invoices that have allocations from this payment.
        
        Returns:
            QuerySet: Invoice objects with allocations
        """
        return Invoice.objects.filter(
            payment_allocations__payment=self
        ).distinct()
    
    def can_allocate_to_invoice(self, invoice, amount):
        """
        Check if this payment can allocate a specific amount to an invoice.
        
        Args:
            invoice (Invoice): The invoice to allocate to
            amount (Decimal): The amount to allocate
            
        Returns:
            tuple: (bool, str) - (is_valid, error_message)
        """
        # Check currency match
        if self.currency_id != invoice.currency_id:
            return False, f"Currency mismatch: Payment is in {self.currency}, Invoice is in {invoice.currency}"
        
        # Check business partner match
        if self.business_partner_id != invoice.business_partner_id:
            return False, "Business partner mismatch between payment and invoice"
        
        # Check if invoice can accept this payment
        can_pay, error_msg = invoice.can_pay(amount)
        if not can_pay:
            return False, error_msg
        
        return True, ""
    
    @transaction.atomic
    def allocate_to_invoice(self, invoice, amount):
        """
        Create a payment allocation to an invoice.
        
        Args:
            invoice (Invoice): The invoice to allocate payment to
            amount (Decimal): The amount to allocate
            
        Returns:
            PaymentAllocation: The created allocation
            
        Raises:
            ValidationError: If allocation is invalid
        """
        # Validate
        can_allocate, error_msg = self.can_allocate_to_invoice(invoice, amount)
        if not can_allocate:
            raise ValidationError(error_msg)
        
        # Check if allocation already exists
        existing_allocation = self.allocations.filter(invoice=invoice).first()
        if existing_allocation:
            # Update existing allocation
            existing_allocation.amount_allocated += Decimal(str(amount))
            existing_allocation.save()
            return existing_allocation
        else:
            # Create new allocation
            allocation = PaymentAllocation.objects.create(
                payment=self,
                invoice=invoice,
                amount_allocated=amount
            )
            return allocation
    
    @transaction.atomic
    def remove_allocation(self, invoice):
        """
        Remove payment allocation from an invoice.
        
        Args:
            invoice (Invoice): The invoice to remove allocation from
            
        Returns:
            bool: True if allocation was removed, False if no allocation existed
        """
        try:
            allocation = self.allocations.get(invoice=invoice)
            allocation.delete()
            return True
        except PaymentAllocation.DoesNotExist:
            return False
    
    @transaction.atomic
    def clear_all_allocations(self):
        """
        Remove all payment allocations.
        This will decrease paid_amount on all related invoices.
        
        NOTE: We must delete allocations individually to trigger the custom
        delete() method which updates invoice.paid_amount. Bulk delete bypasses this.
        
        Returns:
            int: Number of allocations deleted
        """
        allocations = list(self.allocations.all())  # Convert to list to avoid query issues
        count = len(allocations)
        
        # Delete each allocation individually to trigger custom delete() logic
        for allocation in allocations:
            allocation.delete()
        
        return count
    
    # ==================== APPROVAL WORKFLOW INTERFACE IMPLEMENTATION ====================
    
    def on_approval_started(self, workflow_instance):
        """Called when approval workflow starts.
        
        Updates status and timestamp when payment is submitted for approval.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
        """
        self.approval_status = Payment.PENDING_APPROVAL
        self.submitted_for_approval_at = timezone.now()
        self.save(update_fields=['approval_status', 'submitted_for_approval_at'])
    
    def on_stage_approved(self, stage_instance):
        """Called when a stage is approved.
        
        Logs the stage completion. Override in subclasses for custom logic.
        
        Args:
            stage_instance: ApprovalWorkflowStageInstance object
        """
        stage_name = stage_instance.stage_template.name
        # Optional: Add logging or notifications here
        pass
    
    def on_fully_approved(self, workflow_instance):
        """Called when all stages are approved.
        
        Updates status, timestamp, and posts GL entries if configured.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
        """
        self.approval_status = Payment.APPROVED
        self.approved_at = timezone.now()
        self.save(update_fields=['approval_status', 'approved_at'])
        
        # Post to GL if gl_entry exists
        if self.gl_entry:
            try:
                self.gl_entry.post()
            except Exception as e:
                # Log error but don't fail the approval
                # You may want to handle this differently
                pass
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        """Called when workflow is rejected.
        
        Updates status, timestamp, and captures rejection reason.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            stage_instance: ApprovalWorkflowStageInstance where rejection occurred (optional)
        """
        self.approval_status = Payment.REJECTED
        self.rejected_at = timezone.now()
        
        # Get rejection reason from last action
        if stage_instance:
            from core.approval.models import ApprovalAction
            last_action = stage_instance.actions.filter(
                action=ApprovalAction.ACTION_REJECT
            ).order_by('-created_at').first()
            if last_action and last_action.comment:
                self.rejection_reason = last_action.comment
        
        self.save(update_fields=['approval_status', 'rejected_at', 'rejection_reason'])
    
    def on_cancelled(self, workflow_instance, reason=None):
        """Called when workflow is cancelled.
        
        Resets to draft state and clears approval timestamps.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            reason: String describing why it was cancelled
        """
        self.approval_status = Payment.DRAFT
        self.submitted_for_approval_at = None
        self.approved_at = None
        self.rejected_at = None
        self.rejection_reason = reason or ''
        self.save(update_fields=[
            'approval_status',
            'submitted_for_approval_at',
            'approved_at',
            'rejected_at',
            'rejection_reason'
        ])
    
    # ==================== APPROVAL CONVENIENCE METHODS ====================
    
    def validate_for_submission(self):
        """Validate if payment can be submitted for approval.
        
        Raises:
            ValidationError: If payment cannot be submitted
        """
        if self.approval_status not in [Payment.DRAFT, Payment.REJECTED]:
            raise ValidationError(
                f"Cannot submit payment with status '{self.approval_status}'. "
                "Only DRAFT or REJECTED payments can be submitted."
            )
        
        # Validate that payment has at least one allocation
        if not self.allocations.exists():
            raise ValidationError(
                "Payment must have at least one invoice allocation before submission."
            )
        
        # Validate GL entry if exists
        if self.gl_entry and not self.gl_entry.is_balanced():
            raise ValidationError(
                "GL entry must be balanced before submission."
            )
    
    def submit_for_approval(self):
        """Submit payment for approval workflow.
        
        Returns:
            ApprovalWorkflowInstance
            
        Raises:
            ValidationError: If payment cannot be submitted
        """
        from core.approval.managers import ApprovalManager
        
        self.validate_for_submission()
        
        return ApprovalManager.start_workflow(self)
    
    def approve_by_user(self, user, comment=None):
        """Approve payment (by user).
        
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
        """Reject payment (by user).
        
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
        """Check if user can approve this payment.
        
        Args:
            user: User to check
            
        Returns:
            bool: True if user can approve
        """
        if not self.has_pending_approval():
            return False
        
        current_approvers = self.get_current_approvers()
        return user in current_approvers
    
    def can_post_to_gl(self):
        """Check if the payment can post GL entries.
        
        Returns:
            bool: True if payment is approved and has GL entry
        """
        return self.approval_status == Payment.APPROVED and self.gl_entry is not None
    
    def post_to_gl(self):
        """Post the payment to the GL system.
        
        Raises:
            ValueError: If payment cannot post to GL
        """
        if not self.can_post_to_gl():
            raise ValueError("Payment must be approved and have a GL entry to post to GL.")
        
        self.gl_entry.post()


class PaymentAllocation(models.Model):
    """
    PaymentAllocation - Links Payments to Invoices
    
    This model records how payments are allocated to specific invoices.
    Each allocation links one Payment to one Invoice with a specified amount.
    
    IMPORTANT: This model automatically syncs the Invoice.paid_amount field!
    - When an allocation is created, it increases Invoice.paid_amount
    - When an allocation is updated, it adjusts Invoice.paid_amount
    - When an allocation is deleted, it decreases Invoice.paid_amount
    """
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payment_allocations'
    )
    
    amount_allocated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Amount of the payment allocated to this invoice"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_allocation'
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'
        unique_together = ('payment', 'invoice')
    
    def __str__(self):
        return f"Payment {self.payment_id} → Invoice {self.invoice_id}: {self.amount_allocated}"
    
    def clean(self):
        """
        Validate the payment allocation before saving.
        
        Uses Invoice helper methods for validation:
        - invoice.can_pay() for amount validation
        - Validates currency and business partner match
        
        Handles both CREATE and UPDATE scenarios correctly.
        """
        super().clean()
        
        # Validate currency compatibility
        if self.payment and self.invoice:
            if self.payment.currency_id != self.invoice.currency_id:
                raise ValidationError({
                    'amount_allocated': f'Payment currency ({self.payment.currency}) does not match invoice currency ({self.invoice.currency}).'
                })
        
        # Validate business partner compatibility
        if self.payment and self.invoice:
            if self.payment.business_partner_id != self.invoice.business_partner_id:
                raise ValidationError({
                    'invoice': 'Payment business partner must match invoice business partner.'
                })
        
        # Validate the allocation amount
        if self.invoice and self.amount_allocated is not None:
            # For updates, we need to check if the NEW amount is valid
            # by temporarily removing the old amount from paid_amount
            if self.pk:
                try:
                    old_allocation = PaymentAllocation.objects.get(pk=self.pk)
                    old_amount = old_allocation.amount_allocated
                    
                    # Calculate what the paid_amount would be without this allocation
                    temp_paid = self.invoice.paid_amount - old_amount
                    
                    # Now check if we can "pay" the new amount
                    remaining = self.invoice.total - temp_paid
                    if self.amount_allocated > remaining:
                        raise ValidationError({
                            'amount_allocated': f'Allocation amount {self.amount_allocated} exceeds invoice remaining balance of {remaining}.'
                        })
                    
                    # Also validate it's positive
                    if self.amount_allocated <= 0:
                        raise ValidationError({
                            'amount_allocated': 'Allocation amount must be greater than zero.'
                        })
                        
                except PaymentAllocation.DoesNotExist:
                    # Allocation was deleted, treat as new creation
                    can_pay, error_msg = self.invoice.can_pay(self.amount_allocated)
                    if not can_pay:
                        raise ValidationError({
                            'amount_allocated': error_msg
                        })
            else:
                # For new allocations, use the invoice's can_pay() helper method
                can_pay, error_msg = self.invoice.can_pay(self.amount_allocated)
                if not can_pay:
                    raise ValidationError({
                        'amount_allocated': error_msg
                    })
    
    def get_payment_total_allocated(self):
        """
        Calculate total amount allocated from this payment (excluding current allocation if updating).
        
        Returns:
            Decimal: Total allocated amount
        """
        allocations = PaymentAllocation.objects.filter(
            payment=self.payment
        ).exclude(pk=self.pk if self.pk else None)
        
        total = allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        
        return total
    
    def get_invoice_total_allocated(self):
        """
        Calculate total amount allocated to this invoice (excluding current allocation if updating).
        
        Returns:
            Decimal: Total allocated amount
        """
        allocations = PaymentAllocation.objects.filter(
            invoice=self.invoice
        ).exclude(pk=self.pk if self.pk else None)
        
        total = allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        
        return total
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Save the allocation and update the invoice paid_amount.
        Uses database transaction to ensure data consistency.
        
        Handles three scenarios:
        1. CREATE: New allocation - adds to paid_amount
        2. UPDATE (increase): Allocation increased - adds difference
        3. UPDATE (decrease): Allocation decreased - subtracts difference
        """
        # Run validation
        self.full_clean()
        
        # Determine if this is an update by checking if pk exists AND record exists in DB
        is_update = False
        old_amount = Decimal('0')
        
        if self.pk is not None:
            try:
                old_allocation = PaymentAllocation.objects.get(pk=self.pk)
                old_amount = old_allocation.amount_allocated
                is_update = True
            except PaymentAllocation.DoesNotExist:
                is_update = False
        
        # Save the allocation first
        super().save(*args, **kwargs)
        
        # Update invoice paid_amount using the helper method
        if is_update:
            # Calculate the difference (can be positive or negative)
            amount_diff = self.amount_allocated - old_amount
            if amount_diff != 0:  # Only update if there's actually a change
                self._update_invoice_paid_amount(amount_diff)
        else:
            # New allocation - add the full amount
            self._update_invoice_paid_amount(self.amount_allocated)
    
    def _update_invoice_paid_amount(self, amount_change):
        """
        Update the invoice paid_amount by the specified amount.
        Uses Invoice.pay() or Invoice.refund() helper methods.
        
        Args:
            amount_change (Decimal): Amount to add to paid_amount (can be positive or negative)
            
        Raises:
            ValidationError: If the update would violate invoice constraints
        """
        # Skip if no change
        if amount_change == 0:
            return
        
        # Refresh invoice from database to avoid stale data
        self.invoice.refresh_from_db()
        
        # Use the appropriate Invoice helper method
        if amount_change > 0:
            # Increasing allocation: Use pay() for positive amounts
            self.invoice.pay(amount_change)
        else:
            # Decreasing allocation: Use refund() for negative amounts
            # refund() expects positive values, so we pass the absolute value
            self.invoice.refund(abs(amount_change))
    
    @transaction.atomic
    def delete(self, *args, **kwargs):
        """
        Delete the allocation and update the invoice paid_amount.
        Uses Invoice.refund() helper method to reverse the payment.
        Uses database transaction to ensure data consistency.
        """
        # Store amount before deletion
        amount_to_reverse = self.amount_allocated
        invoice = self.invoice
        
        # Delete the allocation
        super().delete(*args, **kwargs)
        
        # Reverse the payment using refund()
        invoice.refresh_from_db()
        invoice.refund(amount_to_reverse)

