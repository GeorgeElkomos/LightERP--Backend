"""
AP Invoice Model - Accounts Payable

Represents invoices from suppliers that the company needs to pay.
"""

from django.db import models
from Finance.BusinessPartner.models import Supplier
from .parent_model import Invoice
from .mixins import InvoiceChildManagerMixin, InvoiceChildModelMixin


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
    
    # Optional link to Goods Receipt (for invoices created from receiving)
    goods_receipt = models.ForeignKey(
        'receiving.GoodsReceipt',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ap_invoices',
        help_text="Goods Receipt that this invoice was created from (if applicable)"
    )
    
    # Custom manager
    objects = AP_InvoiceManager()
    
    class Meta:
        db_table = 'ap_invoice'
        verbose_name = 'AP Invoice'
        verbose_name_plural = 'AP Invoices'
    
    def __str__(self):
        return f"AP Invoice: {self.supplier.name} - ${self.invoice.total}"
    
    # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    # These methods are OPTIONAL - implement only what you need for AP-specific logic!
    # They are called AFTER the parent Invoice methods execute.
    
    def on_approval_started_child(self, workflow_instance):
        """AP-specific logic when approval starts.
        
        Called AFTER parent's on_approval_started().
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            
        TODO: Implement AP-specific logic here, such as:
        - Send notification to supplier
        - Create audit log entry
        - Update related purchase order status
        - etc.
        """
        pass
        # Example implementation:
        # self.notify_supplier_submission()
        # print(f"AP Invoice from {self.supplier.name} submitted for approval")
    
    def on_stage_approved_child(self, stage_instance):
        """AP-specific logic when a stage is approved.
        
        Called AFTER parent's on_stage_approved().
        You can have different logic for different stages!
        
        Args:
            stage_instance: ApprovalWorkflowStageInstance object
            
        TODO: Implement stage-specific logic here, such as:
        - Different actions based on which stage was approved
        - Send notifications at specific stages
        - Prepare for payment processing
        - etc.
        """
        pass
        # Example implementation:
        # stage_name = stage_instance.stage_template.name
        # if stage_name == 'Accountant Review':
        #     self.mark_documents_verified()
        # elif stage_name == 'Finance Manager Review':
        #     self.prepare_for_payment()
        # elif stage_name == 'CFO Final Approval':
        #     self.mark_ready_for_payment()
    
    def on_fully_approved_child(self, workflow_instance):
        """AP-specific logic when ALL stages are approved.
        
        Called AFTER parent's on_fully_approved().
        This is where you execute your main AP business logic!
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            
        TODO: Implement your main AP business logic here, such as:
        - Schedule payment
        - Notify supplier of approval
        - Update related purchase order
        - Create payment record
        - Integrate with payment system
        - etc.
        """
        pass
        # Example implementation:
        # self.schedule_payment()
        # self.notify_supplier_approval()
        # if hasattr(self, 'purchase_order') and self.purchase_order:
        #     self.purchase_order.mark_invoice_approved()
        # self.create_payment_record()
    
    def on_rejected_child(self, workflow_instance, stage_instance=None):
        """AP-specific logic when workflow is rejected.
        
        Called AFTER parent's on_rejected().
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            stage_instance: ApprovalWorkflowStageInstance where rejection occurred (optional)
            
        TODO: Implement rejection handling here, such as:
        - Notify supplier about rejection
        - Cancel any preliminary actions
        - Update related records
        - etc.
        """
        pass
        # Example implementation:
        # rejection_reason = self.invoice.rejection_reason or "No reason provided"
        # self.notify_supplier_rejection(rejection_reason)
        # self.cancel_preliminary_payments()
    
    def on_cancelled_child(self, workflow_instance, reason=None):
        """AP-specific logic when workflow is cancelled.
        
        Called AFTER parent's on_cancelled().
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            reason: String describing why it was cancelled
            
        TODO: Implement cancellation handling here, such as:
        - Notify supplier about cancellation
        - Rollback any changes
        - etc.
        """
        pass
        # Example implementation:
        # self.notify_supplier_cancellation(reason)
    
    # ==================== APPROVAL CONVENIENCE METHODS ====================
    
    def submit_for_approval(self):
        """Submit AP invoice for approval.
        
        Convenience method that delegates to parent Invoice.
        
        Returns:
            ApprovalWorkflowInstance
        """
        return self.invoice.submit_for_approval()
    
    def approve(self, user, comment=None):
        """Approve this AP invoice.
        
        Convenience method that delegates to parent Invoice.
        
        Args:
            user: User performing the approval
            comment: Optional approval comment
            
        Returns:
            ApprovalWorkflowInstance
        """
        return self.invoice.approve_by_user(user, comment)
    
    def reject(self, user, comment=None):
        """Reject this AP invoice.
        
        Convenience method that delegates to parent Invoice.
        
        Args:
            user: User performing the rejection
            comment: Optional rejection reason
            
        Returns:
            ApprovalWorkflowInstance
        """
        return self.invoice.reject_by_user(user, comment)
    
    @property
    def approval_status(self):
        """Get approval status from parent Invoice."""
        return self.invoice.approval_status
    
    @property
    def has_pending_approval(self):
        """Check if invoice has pending approval."""
        return self.invoice.has_pending_approval()
    
    @property
    def current_approvers(self):
        """Get users who can currently approve."""
        return self.invoice.get_current_approvers()
    
    @property
    def approval_history(self):
        """Get approval history."""
        return self.invoice.get_approval_history()
    
    def can_be_approved_by(self, user):
        """Check if user can approve this AP invoice.
        
        Args:
            user: User to check
            
        Returns:
            bool: True if user can approve
        """
        return self.invoice.can_be_approved_by(user)

