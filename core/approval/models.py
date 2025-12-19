"""Dynamic approval workflow models.

Generic approval system that can be attached to any Django model.
Uses GenericForeignKey to link workflows to any content type.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings

# Import UserLevel model
from .mixins import ApprovableMixin
from core.job_roles.models import JobRole


class ApprovalWorkflowTemplate(models.Model):
    """Defines a reusable workflow template.
    
    Can be used for any model type via content_type field.
    Templates are versioned and can be activated/deactivated.
    """
    
    code = models.CharField(
        max_length=60, 
        unique=True,
        help_text="Unique identifier for this template"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    
    # Generic: works with any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The model type this template applies to (e.g., BudgetTransfer, Invoice, etc.)"
    )
    
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "approval_workflow_template"
        ordering = ["content_type", "-version", "code"]
        indexes = [
            models.Index(fields=["content_type", "is_active"]),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version} for {self.content_type.model} ({'active' if self.is_active else 'inactive'})"


class ApprovalWorkflowStageTemplate(models.Model):
    """Stage template belonging to a workflow template."""
    
    POLICY_ALL = "ALL"
    POLICY_ANY = "ANY"
    POLICY_QUORUM = "QUORUM"
    DECISION_POLICY_CHOICES = [
        (POLICY_ALL, "All must approve"),
        (POLICY_ANY, "Any one can approve"),
        (POLICY_QUORUM, "Quorum of approvals"),
    ]
    
    workflow_template = models.ForeignKey(
        ApprovalWorkflowTemplate,
        related_name="stages",
        on_delete=models.CASCADE
    )
    order_index = models.PositiveIntegerField(help_text="1-based ordering of stages")
    name = models.CharField(max_length=120)
    
    decision_policy = models.CharField(
        max_length=10,
        choices=DECISION_POLICY_CHOICES,
        default=POLICY_ALL
    )
    quorum_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Required number of approvals for QUORUM policy"
    )
    
    # User filtering
    # Note: required_user_level removed - tests will assign all active users
    # You can extend this by adding your own filtering logic
    required_role = models.ForeignKey(
        JobRole,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Optional job role filter - only users with this job role can approve"
    )
    
    # Additional dynamic filtering (JSON string for future use)
    dynamic_filter_json = models.TextField(
        null=True,
        blank=True,
        help_text="JSON string for complex filtering logic"
    )
    
    # Policies
    allow_reject = models.BooleanField(default=True)
    allow_delegate = models.BooleanField(default=False)
    
    # SLA
    sla_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Hours before SLA breach"
    )
    
    # Future: parallel execution
    parallel_group = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Stages in same group run in parallel"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "approval_workflow_stage_template"
        ordering = ["workflow_template", "order_index"]
        unique_together = ("workflow_template", "order_index")
    
    def __str__(self):
        return f"{self.workflow_template.code}#{self.order_index} {self.name}"


class ApprovalWorkflowInstance(models.Model):
    """Runtime instance of a workflow for any model object.
    
    Uses GenericForeignKey to link to any Django model.
    """
    
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    
    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    
    template = models.ForeignKey(
        ApprovalWorkflowTemplate,
        on_delete=models.PROTECT,
        related_name="instances"
    )
    current_stage_template = models.ForeignKey(
        ApprovalWorkflowStageTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="active_instances"
    )
    
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    completed_stage_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = "approval_workflow_instance"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status", "current_stage_template"]),
        ]
    
    def __str__(self):
        obj_repr = str(self.content_object) if self.content_object else f"{self.content_type.model} #{self.object_id}"
        return f"Workflow for {obj_repr} ({self.status})"


class ApprovalWorkflowStageInstance(models.Model):
    """Concrete runtime stage tied to its template and parent instance."""
    
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_SKIPPED = "skipped"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    
    workflow_instance = models.ForeignKey(
        ApprovalWorkflowInstance,
        related_name="stage_instances",
        on_delete=models.CASCADE
    )
    stage_template = models.ForeignKey(
        ApprovalWorkflowStageTemplate,
        related_name="stage_instances",
        on_delete=models.PROTECT
    )
    
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "approval_workflow_stage_instance"
        ordering = ["workflow_instance", "stage_template__order_index"]
        indexes = [
            models.Index(fields=["workflow_instance", "status"]),
        ]
    
    def __str__(self):
        return f"Stage {self.stage_template.name} for {self.workflow_instance}"
    
    @property
    def is_terminal(self):
        return self.status in {
            self.STATUS_COMPLETED,
            self.STATUS_SKIPPED,
            self.STATUS_CANCELLED
        }


class ApprovalAssignment(models.Model):
    """Materialized eligible approvers for a given stage instance."""
    
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_DELEGATED = "delegated"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_DELEGATED, "Delegated"),
    ]
    
    stage_instance = models.ForeignKey(
        ApprovalWorkflowStageInstance,
        related_name="assignments",
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approval_assignments",
        on_delete=models.CASCADE
    )
    
    # Snapshot of user info at assignment time
    role_snapshot = models.CharField(max_length=50, null=True, blank=True)
    level_snapshot = models.CharField(max_length=50, null=True, blank=True)
    
    is_mandatory = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "approval_assignment"
        unique_together = ("stage_instance", "user")
        indexes = [
            models.Index(fields=["user", "status"]),
        ]
    
    def __str__(self):
        return f"Assignment: {self.user} -> {self.stage_instance} ({self.status})"


class ApprovalAction(models.Model):
    """Audit log of user actions within a stage instance."""
    
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_DELEGATE = "delegate"
    ACTION_COMMENT = "comment"
    ACTION_CHOICES = [
        (ACTION_APPROVE, "Approve"),
        (ACTION_REJECT, "Reject"),
        (ACTION_DELEGATE, "Delegate"),
        (ACTION_COMMENT, "Comment"),
    ]
    
    stage_instance = models.ForeignKey(
        ApprovalWorkflowStageInstance,
        related_name="actions",
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approval_actions",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Null for system actions"
    )
    assignment = models.ForeignKey(
        ApprovalAssignment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actions"
    )
    
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    triggers_stage_completion = models.BooleanField(default=False)
    
    class Meta:
        db_table = "approval_action"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["stage_instance", "action"]),
            models.Index(fields=["user", "created_at"]),
        ]
    
    def __str__(self):
        user_str = self.user if self.user else "SYSTEM"
        return f"{self.action} by {user_str} on {self.stage_instance}"


class ApprovalDelegation(models.Model):
    """Delegation record when user delegates approval to another user."""
    
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="delegations_given",
        on_delete=models.CASCADE
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="delegations_received",
        on_delete=models.CASCADE
    )
    stage_instance = models.ForeignKey(
        ApprovalWorkflowStageInstance,
        related_name="delegations",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True, default='')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "approval_delegation"
        indexes = [
            models.Index(fields=["active", "to_user"]),
        ]
    
    def __str__(self):
        return f"Delegation: {self.from_user} -> {self.to_user} ({'active' if self.active else 'inactive'})"
    
    @property
    def is_active(self):
        """Check if delegation is currently active based on dates and active flag."""
        if not self.active:
            return False
        
        if self.start_date or self.end_date:
            from django.utils import timezone
            today = timezone.now().date()
            
            if self.start_date and today < self.start_date:
                return False  # Not started yet
            
            if self.end_date and today > self.end_date:
                return False  # Already ended
        
        return True
    
    def deactivate(self):
        """Deactivate this delegation."""
        if self.active:
            self.active = False
            self.deactivated_at = timezone.now()
            self.save(update_fields=["active", "deactivated_at"])


# =================================
# TEST MODELS FOR APPROVAL TESTING
# =================================

class TestInvoice(ApprovableMixin, models.Model):
    """Test invoice model for approval workflow testing."""
    
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    vendor_name = models.CharField(max_length=200)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    
    # Tracking fields
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Audit trail
    approval_started_count = models.IntegerField(default=0)
    stage_approved_count = models.IntegerField(default=0)
    fully_approved_called = models.BooleanField(default=False)
    rejected_called = models.BooleanField(default=False)
    cancelled_called = models.BooleanField(default=False)
    last_stage_approved = models.CharField(max_length=200, null=True, blank=True)
    
    class Meta:
        app_label = 'approval'
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"
    
    # ApprovableInterface Implementation
    def on_approval_started(self, workflow_instance):
        """Called when approval workflow starts."""
        self.status = self.STATUS_PENDING
        self.approval_started_count += 1
        self.save(update_fields=['status', 'approval_started_count'])
    
    def on_stage_approved(self, stage_instance):
        """Called when a stage is approved."""
        self.stage_approved_count += 1
        self.last_stage_approved = stage_instance.stage_template.name
        self.save(update_fields=['stage_approved_count', 'last_stage_approved'])
    
    def on_fully_approved(self, workflow_instance):
        """Called when all stages are approved."""
        self.status = self.STATUS_APPROVED
        self.approved_at = timezone.now()
        self.fully_approved_called = True
        self.save(update_fields=['status', 'approved_at', 'fully_approved_called'])
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        """Called when workflow is rejected."""
        self.status = self.STATUS_REJECTED
        self.rejected_at = timezone.now()
        self.rejected_called = True
        self.save(update_fields=['status', 'rejected_at', 'rejected_called'])
    
    def on_cancelled(self, workflow_instance, reason=None):
        """Called when workflow is cancelled."""
        self.status = self.STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        self.cancelled_called = True
        self.save(update_fields=['status', 'cancelled_at', 'cancelled_called'])


class TestPurchaseOrder(ApprovableMixin, models.Model):
    """Test purchase order model for approval workflow testing."""
    
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]
    
    po_number = models.CharField(max_length=50, unique=True)
    supplier_name = models.CharField(max_length=200)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'approval'
    
    def __str__(self):
        return f"PO {self.po_number}"
    
    # ApprovableInterface Implementation
    def on_approval_started(self, workflow_instance):
        self.status = self.STATUS_PENDING
        self.save(update_fields=['status'])
    
    def on_stage_approved(self, stage_instance):
        pass  # No special action
    
    def on_fully_approved(self, workflow_instance):
        self.status = self.STATUS_APPROVED
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_at'])
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        self.status = self.STATUS_REJECTED
        self.save(update_fields=['status'])
    
    def on_cancelled(self, workflow_instance, reason=None):
        self.status = self.STATUS_DRAFT
        self.save(update_fields=['status'])

