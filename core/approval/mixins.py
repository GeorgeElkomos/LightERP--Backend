"""Mixins for models that require approval workflows.

Use ApprovableMixin to add approval functionality to any Django model.
Implement the required methods to define custom behavior.
"""

from abc import ABCMeta
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.base import ModelBase


# Combined metaclass to resolve ABC and Django Model conflict
class ApprovableMetaclass(ABCMeta, ModelBase):
    """Metaclass that combines ABC and Django Model metaclasses."""
    pass


class ApprovableInterface(metaclass=ApprovableMetaclass):
    """Abstract interface defining required methods for approvable models.
    
    Any model using the approval system MUST implement these methods
    to define custom behavior at each workflow stage.
    """
    
    def on_approval_started(self, workflow_instance):
        """Called when the approval workflow is started.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            
        Example:
            def on_approval_started(self, workflow_instance):
                self.status = 'pending_approval'
                self.save(update_fields=['status'])
                # Send notification, log, etc.
        """
        raise NotImplementedError("Subclasses must implement on_approval_started()")
    
    def on_stage_approved(self, stage_instance):
        """Called when a stage is approved (before moving to next stage).
        
        Args:
            stage_instance: ApprovalWorkflowStageInstance object
            
        Example:
            def on_stage_approved(self, stage_instance):
                # Log stage completion
                print(f"Stage {stage_instance.stage_template.name} approved")
        """
        raise NotImplementedError("Subclasses must implement on_stage_approved()")
    
    def on_fully_approved(self, workflow_instance):
        """Called when ALL stages are approved.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            
        Example:
            def on_fully_approved(self, workflow_instance):
                self.status = 'approved'
                self.approved_at = timezone.now()
                self.save(update_fields=['status', 'approved_at'])
                # Execute business logic (transfer funds, update inventory, etc.)
        """
        raise NotImplementedError("Subclasses must implement on_fully_approved()")
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        """Called when the workflow is rejected at any stage.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            stage_instance: ApprovalWorkflowStageInstance where rejection occurred (optional)
            
        Example:
            def on_rejected(self, workflow_instance, stage_instance=None):
                self.status = 'rejected'
                self.rejected_at = timezone.now()
                self.save(update_fields=['status', 'rejected_at'])
                # Notify requester, rollback changes, etc.
        """
        raise NotImplementedError("Subclasses must implement on_rejected()")
    
    def on_cancelled(self, workflow_instance, reason=None):
        """Called when the workflow is cancelled.
        
        Args:
            workflow_instance: ApprovalWorkflowInstance object
            reason: String describing why it was cancelled
            
        Example:
            def on_cancelled(self, workflow_instance, reason=None):
                self.status = 'cancelled'
                self.cancellation_reason = reason
                self.save(update_fields=['status', 'cancellation_reason'])
        """
        raise NotImplementedError("Subclasses must implement on_cancelled()")


class ApprovableMixin(models.Model):
    """Mixin to add approval workflow capabilities to any Django model.
    
    Usage:
        1. Add this mixin to your model
        2. Implement the ApprovableInterface methods
        3. Use ApprovalManager to start/manage workflows
        
    Example:
        class MyDocument(ApprovableMixin, models.Model):
            title = models.CharField(max_length=200)
            status = models.CharField(max_length=20)
            
            def on_approval_started(self, workflow_instance):
                self.status = 'pending'
                self.save()
            
            def on_fully_approved(self, workflow_instance):
                self.status = 'approved'
                self.save()
            
            # ... implement other required methods
    """
    
    # Generic relation to workflow instances
    approval_workflows = GenericRelation(
        'approval.ApprovalWorkflowInstance',
        content_type_field='content_type',
        object_id_field='object_id',
        related_query_name='%(app_label)s_%(class)s'
    )
    
    class Meta:
        abstract = True
    
    def get_active_workflow(self):
        """Get the active workflow instance for this object.
        
        Returns:
            ApprovalWorkflowInstance or None
        """
        return self.approval_workflows.filter(
            status__in=['pending', 'in_progress']
        ).first()
    
    def get_current_workflow(self):
        """Alias for get_active_workflow for backward compatibility.
        
        Returns:
            ApprovalWorkflowInstance or None
        """
        return self.get_active_workflow()
    
    def has_pending_workflow(self):
        """Alias for has_pending_approval for backward compatibility.
        
        Returns:
            Boolean
        """
        return self.has_pending_approval()
    
    def get_workflow_status(self):
        """Get the current workflow status.
        
        Returns:
            String: 'no_workflow', 'pending', 'in_progress', 'approved', 'rejected', 'cancelled'
        """
        workflow = self.approval_workflows.order_by('-started_at').first()
        if not workflow:
            return 'no_workflow'
        return workflow.status
    
    def has_pending_approval(self):
        """Check if object has a pending approval workflow.
        
        Returns:
            Boolean
        """
        return self.approval_workflows.filter(
            status__in=['pending', 'in_progress']
        ).exists()
    
    def get_current_approvers(self):
        """Get users who can currently approve this object.
        
        Returns:
            QuerySet of User objects
        """
        User = get_user_model()
        
        workflow = self.get_active_workflow()
        if not workflow:
            return User.objects.none()
        
        active_stages = workflow.stage_instances.filter(status='active')
        if not active_stages.exists():
            return User.objects.none()
        
        # Get all users with pending assignments in active stages
        from core.approval.models import ApprovalAssignment
        
        assignment_ids = ApprovalAssignment.objects.filter(
            stage_instance__in=active_stages,
            status='pending'
        ).values_list('user_id', flat=True)
        
        return User.objects.filter(id__in=assignment_ids)
    
    def get_approval_history(self):
        """Get approval history for this object.
        
        Returns:
            QuerySet of ApprovalAction objects
        """
        from core.approval.models import ApprovalAction
        
        workflow = self.approval_workflows.order_by('-started_at').first()
        if not workflow:
            return ApprovalAction.objects.none()
        
        stage_instances = workflow.stage_instances.all()
        return ApprovalAction.objects.filter(
            stage_instance__in=stage_instances
        ).order_by('created_at')
