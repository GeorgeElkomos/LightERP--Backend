"""
AR Invoice Model - Accounts Receivable

Represents invoices to customers that the company expects to receive payment for.
"""

from django.db import models
from Finance.BusinessPartner.models import Customer
from .parent_model import Invoice
from .mixins import InvoiceChildManagerMixin, InvoiceChildModelMixin


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
    
    # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    # These methods are OPTIONAL - implement only what you need for AR-specific logic!
    # They are called AFTER the parent Invoice methods execute.
    # AR invoices typically have DIFFERENT logic than AP invoices!
    
    def on_approval_started_child(self, workflow_instance):
        """AR-specific logic when approval starts.
        
        Called AFTER parent's on_approval_started().
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            
        TODO: Implement AR-specific logic here, such as:
        - Notify sales team
        - Update sales order status
        - Create audit log entry
        - etc.
        """
        pass
        # Example implementation:
        # self.notify_sales_team_submission()
        # print(f"AR Invoice for {self.customer.name} submitted for approval")
    
    def on_stage_approved_child(self, stage_instance):
        """AR-specific logic when a stage is approved.
        
        Called AFTER parent's on_stage_approved().
        
        Args:
            stage_instance: ApprovalWorkflowStageInstance object
            
        TODO: Implement stage-specific logic here.
        """
        pass
        # Example implementation:
        # stage_name = stage_instance.stage_template.name
        # if stage_name == 'Credit Check':
        #     self.mark_credit_approved()
        # elif stage_name == 'Sales Manager Review':
        #     self.prepare_for_customer_delivery()
    
    def on_fully_approved_child(self, workflow_instance):
        """AR-specific logic when ALL stages are approved.
        
        Called AFTER parent's on_fully_approved().
        This is where you execute your main AR business logic!
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            
        TODO: Implement your main AR business logic here, such as:
        - Send invoice to customer (not supplier!)
        - Record accounts receivable (not payable!)
        - Update sales order
        - Create receivable record
        - Send confirmation email to customer
        - etc.
        """
        pass
        # Example implementation:
        # self.send_invoice_to_customer()
        # self.record_accounts_receivable()
        # if hasattr(self, 'sales_order'):
        #     self.sales_order.mark_invoice_approved()
        # self.notify_customer_invoice_sent()
    
    def on_rejected_child(self, workflow_instance, stage_instance=None):
        """AR-specific logic when workflow is rejected.
        
        Called AFTER parent's on_rejected().
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            stage_instance: ApprovalWorkflowStageInstance where rejection occurred (optional)
            
        TODO: Implement rejection handling here, such as:
        - Notify sales team about rejection
        - Update customer record if needed
        - etc.
        """
        pass
        # Example implementation:
        # self.notify_sales_team_rejection()
        # self.revert_sales_order_status()
    
    def on_cancelled_child(self, workflow_instance, reason=None):
        """AR-specific logic when workflow is cancelled.
        
        Called AFTER parent's on_cancelled().
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            reason: String describing why it was cancelled
            
        TODO: Implement cancellation handling here.
        """
        pass
        # Example implementation:
        # self.notify_sales_team_cancellation(reason)
    
    # ==================== APPROVAL CONVENIENCE METHODS ====================
    
    def submit_for_approval(self):
        """Submit AR invoice for approval.
        
        Convenience method that delegates to parent Invoice.
        
        Returns:
            ApprovalWorkflowInstance
        """
        return self.invoice.submit_for_approval()
    
    def approve(self, user, comment=None):
        """Approve this AR invoice.
        
        Convenience method that delegates to parent Invoice.
        
        Args:
            user: User performing the approval
            comment: Optional approval comment
            
        Returns:
            ApprovalWorkflowInstance
        """
        return self.invoice.approve_by_user(user, comment)
    
    def reject(self, user, comment=None):
        """Reject this AR invoice.
        
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
        """Check if user can approve this AR invoice.
        
        Args:
            user: User to check
            
        Returns:
            bool: True if user can approve
        """
        return self.invoice.can_be_approved_by(user)

