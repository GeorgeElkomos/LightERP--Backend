"""Example implementations of the approval system.

These examples show how to integrate the approval workflow
with different types of models in your Django project.

ARCHITECTURE NOTES:
===================

1. ON-DEMAND STAGE CREATION:
   - Workflow stages are created only when needed as the workflow progresses
   - When workflow starts, only the first stage is created and activated
   - Subsequent stages are created when the previous stage completes
   - If workflow is rejected at stage 2, stages 3+ are never created
   - This prevents database pollution with unused stage instances

2. GENERIC WORKFLOW SYSTEM:
   - Uses Django's ContentType framework to work with ANY model
   - No user_level filtering - all eligible users are assigned to stages
   - You can add custom filtering in ApprovalWorkflowStageTemplate.required_role

3. REQUIRED INTERFACE:
   - Models must inherit from ApprovableMixin and implement ApprovableInterface
   - Must implement 5 required methods:
     * on_approval_started(workflow_instance)
     * on_stage_approved(stage_instance)
     * on_fully_approved(workflow_instance)
     * on_rejected(workflow_instance, stage_instance=None)
     * on_cancelled(workflow_instance, reason=None)

4. DECISION POLICIES:
   - ALL: All assigned users must approve
   - ANY: Any one assigned user can approve
   - QUORUM: Specific number of approvals required

5. WORKFLOW MANAGEMENT:
   - Use ApprovalManager for all workflow operations
   - Supports delegation, cancellation, restart
   - Full audit trail via ApprovalAction model
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from core.approval.mixins import ApprovableMixin, ApprovableInterface
from core.approval.managers import ApprovalManager
from core.job_roles.models import JobRole


# ============================================================================
# EXAMPLE 1: Budget Transfer Model (Your original use case)
# ============================================================================

class BudgetTransfer(ApprovableMixin, ApprovableInterface, models.Model):
    """Example: Budget transfer that requires approval."""
    
    TRANSFER_TYPE_CHOICES = [
        ("FAR", "From Activity to Reserve"),
        ("AFR", "Activity to Fund Reserve"),
        ("FAD", "Fund Activity Distribution"),
        ("GEN", "General Transfer"),
    ]
    
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    
    transfer_number = models.CharField(max_length=50, unique=True)
    transfer_type = models.CharField(max_length=10, choices=TRANSFER_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_transfers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "budget_transfer"
    
    def __str__(self):
        return f"{self.transfer_number} - {self.get_transfer_type_display()}"
    
    # ----------------------
    # ApprovableInterface Implementation (REQUIRED)
    # ----------------------
    
    def on_approval_started(self, workflow_instance):
        """Called when approval workflow starts."""
        self.status = "pending_approval"
        self.save(update_fields=["status"])
        
        # Optional: Send notification to approvers
        print(f"Approval workflow started for {self.transfer_number}")
    
    def on_stage_approved(self, stage_instance):
        """Called when a stage is approved."""
        stage_name = stage_instance.stage_template.name
        print(f"Stage '{stage_name}' approved for transfer {self.transfer_number}")
        
        # Optional: Log to audit trail, send notifications, etc.
    
    def on_fully_approved(self, workflow_instance):
        """Called when all stages are approved."""
        self.status = "approved"
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_at"])
        
        # Execute business logic
        self.execute_transfer()
        
        print(f"Transfer {self.transfer_number} fully approved and executed!")
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        """Called when workflow is rejected."""
        self.status = "rejected"
        self.rejected_at = timezone.now()
        self.save(update_fields=["status", "rejected_at"])
        
        stage_name = stage_instance.stage_template.name if stage_instance else "Unknown"
        print(f"Transfer {self.transfer_number} rejected at stage '{stage_name}'")
        
        # Optional: Notify requester, rollback changes
    
    def on_cancelled(self, workflow_instance, reason=None):
        """Called when workflow is cancelled."""
        self.status = "cancelled"
        self.save(update_fields=["status"])
        
        print(f"Transfer {self.transfer_number} cancelled. Reason: {reason}")
    
    # Business logic
    def execute_transfer(self):
        """Execute the actual budget transfer."""
        # Implement your transfer logic here
        # e.g., update budget balances, create transactions, etc.
        pass
    
    # Convenience methods
    def submit_for_approval(self):
        """Submit this transfer for approval."""
        return ApprovalManager.start_workflow(self)
    
    def approve(self, user, comment=None):
        """Approve this transfer (by user)."""
        return ApprovalManager.process_action(
            self, user, "approve", comment=comment
        )
    
    def reject(self, user, comment=None):
        """Reject this transfer (by user)."""
        return ApprovalManager.process_action(
            self, user, "reject", comment=comment
        )


# ============================================================================
# EXAMPLE 2: Purchase Order Model
# ============================================================================

class PurchaseOrder(ApprovableMixin, ApprovableInterface, models.Model):
    """Example: Purchase order requiring approval based on amount."""
    
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]
    
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.CharField(max_length=200)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_pos"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "purchase_order"
    
    def __str__(self):
        return f"PO-{self.po_number}"
    
    # ----------------------
    # ApprovableInterface Implementation (REQUIRED)
    # ----------------------
    
    def on_approval_started(self, workflow_instance):
        self.status = "pending_approval"
        self.save(update_fields=["status"])
    
    def on_stage_approved(self, stage_instance):
        print(f"PO {self.po_number}: Stage {stage_instance.stage_template.name} approved")
    
    def on_fully_approved(self, workflow_instance):
        self.status = "approved"
        self.save(update_fields=["status"])
        
        # Send PO to supplier
        self.send_to_supplier()
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        self.status = "rejected"
        self.save(update_fields=["status"])
        
        # Notify requester
        print(f"PO {self.po_number} rejected")
    
    def on_cancelled(self, workflow_instance, reason=None):
        self.status = "draft"
        self.save(update_fields=["status"])
    
    def send_to_supplier(self):
        """Send approved PO to supplier."""
        # Implement email/API logic
        pass


# ============================================================================
# EXAMPLE 3: Expense Report Model
# ============================================================================

class ExpenseReport(ApprovableMixin, ApprovableInterface, models.Model):
    """Example: Employee expense report."""
    
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("paid", "Paid"),
    ]
    
    report_number = models.CharField(max_length=50, unique=True)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expense_reports"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "expense_report"
    
    def __str__(self):
        return f"Expense Report {self.report_number}"
    
    # ----------------------
    # ApprovableInterface Implementation (REQUIRED)
    # ----------------------
    
    def on_approval_started(self, workflow_instance):
        self.status = "submitted"
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at"])
        
        # Notify manager
        print(f"Expense report {self.report_number} submitted for approval")
    
    def on_stage_approved(self, stage_instance):
        pass  # Optional logging
    
    def on_fully_approved(self, workflow_instance):
        self.status = "approved"
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_at"])
        
        # Trigger payment process
        self.create_payment()
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        self.status = "rejected"
        self.save(update_fields=["status"])
        
        # Notify employee
        print(f"Expense report {self.report_number} rejected")
    
    def on_cancelled(self, workflow_instance, reason=None):
        self.status = "draft"
        self.submitted_at = None
        self.save(update_fields=["status", "submitted_at"])
    
    def create_payment(self):
        """Create payment record for approved expenses."""
        # Create payment in accounting system
        pass


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_usage():
    """Examples of how to use the approval system.
    
    Note: The approval system uses on-demand stage creation.
    Stages are created only when needed as the workflow progresses.
    If a workflow is rejected at stage 2, stages 3+ are never created.
    """
    
    # ------------------------------
    # 1. Starting a workflow
    # ------------------------------
    
    # Create a budget transfer
    transfer = BudgetTransfer.objects.create(
        transfer_number="BT-2024-001",
        transfer_type="FAR",
        amount=50000,
        description="Budget reallocation",
        created_by=some_user,
    )
    
    # Start approval workflow
    workflow = ApprovalManager.start_workflow(transfer)
    print(f"Workflow started: {workflow}")
    
    # Or use convenience method
    transfer.submit_for_approval()
    
    # ------------------------------
    # 2. User approving/rejecting
    # ------------------------------
    
    # User approves
    ApprovalManager.process_action(
        transfer,
        user=approver_user,
        action="approve",
        comment="Looks good to me"
    )
    
    # Or use convenience method
    transfer.approve(approver_user, comment="Approved")
    
    # User rejects
    ApprovalManager.process_action(
        transfer,
        user=approver_user,
        action="reject",
        comment="Insufficient justification"
    )
    
    # ------------------------------
    # 3. Delegation
    # ------------------------------
    
    ApprovalManager.process_action(
        transfer,
        user=original_approver,
        action="delegate",
        comment="I'm on vacation",
        target_user=backup_approver
    )
    
    # ------------------------------
    # 4. Getting user's pending approvals
    # ------------------------------
    
    pending_workflows = ApprovalManager.get_user_pending_approvals(user)
    
    for workflow in pending_workflows:
        obj = workflow.content_object  # The actual object (BudgetTransfer, etc.)
        print(f"Pending: {obj}")
    
    # ------------------------------
    # 5. Checking workflow status
    # ------------------------------
    
    is_finished, status = ApprovalManager.is_workflow_finished(transfer)
    print(f"Finished: {is_finished}, Status: {status}")
    
    # Or use mixin methods
    current_workflow = transfer.get_current_workflow()  # or get_active_workflow()
    current_status = transfer.get_workflow_status()
    has_pending = transfer.has_pending_workflow()  # or has_pending_approval()
    current_approvers = transfer.get_current_approvers()
    approval_history = transfer.get_approval_history()  # Returns ApprovalAction queryset
    
    # ------------------------------
    # 6. Cancelling a workflow
    # ------------------------------
    
    ApprovalManager.cancel_workflow(
        transfer,
        reason="Duplicate request"
    )
    
    # ------------------------------
    # 7. Restarting a workflow
    # ------------------------------
    
    new_workflow = ApprovalManager.restart_workflow(transfer)


# ============================================================================
# WORKFLOW TEMPLATE SETUP EXAMPLES
# ============================================================================

def create_budget_transfer_workflow_template():
    """Example: Create a multi-stage workflow template for budget transfers.
    
    This shows how to set up a 3-stage approval workflow:
    - Stage 1: Supervisor (ANY policy - any supervisor can approve)
    - Stage 2: Managers (ALL policy - all managers must approve)
    - Stage 3: CFO (ANY policy - CFO approves)
    
    Note: Stages are created on-demand as workflow progresses.
    """
    from django.contrib.contenttypes.models import ContentType
    from core.approval.models import (
        ApprovalWorkflowTemplate,
        ApprovalWorkflowStageTemplate
    )
    
    # Get content type for BudgetTransfer model
    ct = ContentType.objects.get_for_model(BudgetTransfer)
    
    # Create workflow template
    template = ApprovalWorkflowTemplate.objects.create(
        code='BUDGET_TRANSFER_APPROVAL',
        name='Budget Transfer Approval Workflow',
        description='Multi-stage approval for budget transfers',
        content_type=ct,
        is_active=True,
        version=1
    )
    
    # Get or create job roles
    supervisor_role, _ = JobRole.objects.get_or_create(name='supervisor')
    manager_role, _ = JobRole.objects.get_or_create(name='manager')
    cfo_role, _ = JobRole.objects.get_or_create(name='cfo')
    
    # Stage 1: Supervisor Review (ANY policy)
    ApprovalWorkflowStageTemplate.objects.create(
        workflow_template=template,
        order_index=1,
        name='Supervisor Review',
        decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
        required_role=supervisor_role,  # ForeignKey to JobRole
        quorum_count=None,
        allow_reject=True,
        allow_delegate=True,
        sla_hours=24
    )
    
    # Stage 2: Manager Review (ALL policy)
    ApprovalWorkflowStageTemplate.objects.create(
        workflow_template=template,
        order_index=2,
        name='Manager Review',
        decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
        required_role=manager_role,
        quorum_count=None,
        allow_reject=True,
        allow_delegate=False,
        sla_hours=48
    )
    
    # Stage 3: CFO Approval (ANY policy)
    ApprovalWorkflowStageTemplate.objects.create(
        workflow_template=template,
        order_index=3,
        name='CFO Final Approval',
        decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
        required_role=cfo_role,
        quorum_count=None,
        allow_reject=True,
        allow_delegate=False,
        sla_hours=72
    )
    
    print(f"Created workflow template: {template}")
    return template


def create_purchase_order_workflow_template():
    """Example: Create workflow with QUORUM policy for purchase orders.
    
    This shows a 2-stage workflow:
    - Stage 1: Department Heads (QUORUM - 2 out of N must approve)
    - Stage 2: Finance Director (ANY - single approval)
    """
    from django.contrib.contenttypes.models import ContentType
    from core.approval.models import (
        ApprovalWorkflowTemplate,
        ApprovalWorkflowStageTemplate
    )
    
    ct = ContentType.objects.get_for_model(PurchaseOrder)
    
    template = ApprovalWorkflowTemplate.objects.create(
        code='PO_APPROVAL',
        name='Purchase Order Approval',
        content_type=ct,
        is_active=True,
        version=1
    )
    
    # Get or create job roles
    dept_head_role, _ = JobRole.objects.get_or_create(name='department_head')
    finance_director_role, _ = JobRole.objects.get_or_create(name='finance_director')
    
    # Stage 1: Department Heads (QUORUM policy)
    ApprovalWorkflowStageTemplate.objects.create(
        workflow_template=template,
        order_index=1,
        name='Department Head Review',
        decision_policy=ApprovalWorkflowStageTemplate.POLICY_QUORUM,
        required_role=dept_head_role,
        quorum_count=2,  # Need 2 approvals out of all department heads
        allow_reject=True,
        allow_delegate=True
    )
    
    # Stage 2: Finance Director (ANY policy)
    ApprovalWorkflowStageTemplate.objects.create(
        workflow_template=template,
        order_index=2,
        name='Finance Director Approval',
        decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
        required_role=finance_director_role,
        quorum_count=None,
        allow_reject=True,
        allow_delegate=False
    )
    
    return template


def create_simple_workflow_template():
    """Example: Simple single-stage approval workflow.
    
    Use this for simple approvals that only need one person to approve.
    """
    from django.contrib.contenttypes.models import ContentType
    from core.approval.models import (
        ApprovalWorkflowTemplate,
        ApprovalWorkflowStageTemplate
    )
    
    ct = ContentType.objects.get_for_model(ExpenseReport)
    
    template = ApprovalWorkflowTemplate.objects.create(
        code='EXPENSE_SIMPLE',
        name='Simple Expense Approval',
        content_type=ct,
        is_active=True,
        version=1
    )
    
    # Get or create manager job role
    manager_role, _ = JobRole.objects.get_or_create(name='manager')
    
    # Single stage: Manager approval
    ApprovalWorkflowStageTemplate.objects.create(
        workflow_template=template,
        order_index=1,
        name='Manager Approval',
        decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
        required_role=manager_role,
        allow_reject=True,
        allow_delegate=True
    )
    
    return template


# ============================================================================
# ADVANCED USAGE EXAMPLES
# ============================================================================

def example_workflow_monitoring():
    """Example: Monitor workflow progress and get detailed information."""
    
    # Get a transfer object
    transfer = BudgetTransfer.objects.get(transfer_number='BT-2024-001')
    
    # Check if workflow exists and is active
    workflow = transfer.get_current_workflow()
    if workflow:
        print(f"Workflow Status: {workflow.status}")
        print(f"Current Stage: {workflow.current_stage_template}")
        print(f"Completed Stages: {workflow.completed_stage_count}")
        
        # Get active stage instances
        active_stages = workflow.stage_instances.filter(status='active')
        for stage in active_stages:
            print(f"Active Stage: {stage.stage_template.name}")
            
            # Get pending assignments for this stage
            pending = stage.assignments.filter(status='pending')
            print(f"  Pending approvers: {pending.count()}")
            for assignment in pending:
                print(f"    - {assignment.user.email}")
        
        # Get approval history
        history = transfer.get_approval_history()
        for action in history:
            print(f"{action.created_at}: {action.user} - {action.action}")
            if action.comment:
                print(f"  Comment: {action.comment}")
    
    # Check who can currently approve
    approvers = transfer.get_current_approvers()
    print(f"Current approvers: {list(approvers.values_list('email', flat=True))}")


def example_delegation_management():
    """Example: Managing approval delegations."""
    from core.approval.models import ApprovalDelegation
    from django.utils import timezone
    from datetime import timedelta
    
    # Create a permanent delegation
    delegation = ApprovalDelegation.objects.create(
        from_user=user_on_vacation,
        to_user=backup_user,
        reason="Annual leave",
        active=True
    )
    
    # Create a time-limited delegation
    delegation = ApprovalDelegation.objects.create(
        from_user=manager,
        to_user=deputy_manager,
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=7)).date(),
        reason="Business trip",
        active=True
    )
    
    # Check if delegation is currently active
    if delegation.is_active:
        print(f"Delegation active: {delegation.from_user} -> {delegation.to_user}")
    
    # Deactivate delegation
    delegation.deactivate()


def example_error_handling():
    """Example: Proper error handling when using the approval system."""
    
    transfer = BudgetTransfer.objects.get(transfer_number='BT-2024-001')
    
    # Starting a workflow
    try:
        workflow = ApprovalManager.start_workflow(transfer)
        print(f"Workflow started successfully: {workflow.id}")
    except ValueError as e:
        # Workflow already in progress
        print(f"Error: {e}")
    
    # Processing an action
    try:
        ApprovalManager.process_action(
            transfer,
            user=some_user,
            action='approve',
            comment='Approved'
        )
    except ValueError as e:
        # User doesn't have permission, workflow not found, etc.
        print(f"Cannot approve: {e}")
    
    # Checking workflow state
    is_finished, status = ApprovalManager.is_workflow_finished(transfer)
    if is_finished:
        print(f"Workflow finished with status: {status}")
    else:
        print("Workflow still in progress")


