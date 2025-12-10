"""Generic approval workflow manager.

Central manager for handling approval workflows on any Django model.
"""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
    ApprovalAction,
    ApprovalDelegation,
)

User = get_user_model()


class ApprovalManager:
    """Central manager for dynamic approval workflows.
    
    Works with any Django model that implements ApprovableInterface.
    """
    
    # ----------------------
    # Helper Methods
    # ----------------------
    
    @staticmethod
    def _get_system_user():
        """Return a user to log system actions.
        
        Configure settings.APPROVAL_SYSTEM_USER_ID.
        Fallback to first superuser.
        """
        user_id = getattr(settings, "APPROVAL_SYSTEM_USER_ID", None)
        if user_id:
            try:
                return User.objects.get(pk=user_id)
            except User.DoesNotExist:
                pass
        
        # Fallback: first super_admin user type, or just first user
        try:
            # Try to get a super_admin user
            from core.user_accounts.models import UserType
            super_admin_type = UserType.objects.filter(type_name='super_admin').first()
            if super_admin_type:
                return User.objects.filter(user_type=super_admin_type).first() or User.objects.first()
            return User.objects.first()
        except Exception:
            raise ValueError(
                "No system user available. Set settings.APPROVAL_SYSTEM_USER_ID."
            )
    
    @staticmethod
    def _get_content_type(obj):
        """Get ContentType for an object."""
        return ContentType.objects.get_for_model(obj)
    
    @staticmethod
    def _validate_approvable(obj):
        """Validate that object implements required interface methods."""
        required_methods = [
            'on_approval_started',
            'on_stage_approved',
            'on_fully_approved',
            'on_rejected',
            'on_cancelled',
        ]
        
        for method_name in required_methods:
            if not hasattr(obj, method_name) or not callable(getattr(obj, method_name)):
                raise ValueError(
                    f"Object {obj.__class__.__name__} must implement {method_name}() method. "
                    f"Use ApprovableMixin and implement ApprovableInterface."
                )
    
    # ----------------------
    # Workflow Creation & Starting
    # ----------------------
    
    @classmethod
    def create_instance(cls, obj) -> ApprovalWorkflowInstance:
        """Create a workflow instance for any model object.
        
        Args:
            obj: Django model instance (must implement ApprovableInterface)
        
        Returns:
            ApprovalWorkflowInstance
            
        Raises:
            ValueError: If no suitable template found or object doesn't implement interface
        """
        cls._validate_approvable(obj)
        
        content_type = cls._get_content_type(obj)
        
        # Find appropriate template
        template = cls._find_template(content_type)
        
        if not template:
            raise ValueError(
                f"No active workflow template found for {content_type.model}"
            )
        
        # Validate template stages
        cls._validate_template(template)
        
        # Create workflow instance
        instance = ApprovalWorkflowInstance.objects.create(
            content_type=content_type,
            object_id=obj.pk,
            template=template,
            status=ApprovalWorkflowInstance.STATUS_PENDING,
        )
        
        # Don't create any stage instances here
        # Stages will be created on-demand by _activate_next_stage_internal
        # as the workflow progresses
        
        return instance
    
    @classmethod
    def _find_template(cls, content_type):
        """Find most recent active template for content type."""
        return ApprovalWorkflowTemplate.objects.filter(
            content_type=content_type,
            is_active=True
        ).order_by('-version').first()
    
    @classmethod
    def _validate_template(cls, template):
        """Validate template configuration."""
        for stage in template.stages.all():
            if stage.decision_policy == ApprovalWorkflowStageTemplate.POLICY_QUORUM:
                if stage.quorum_count and stage.quorum_count < 1:
                    raise ValueError(
                        f"Invalid quorum_count {stage.quorum_count} on stage {stage}"
                    )
    
    @classmethod
    def start_workflow(cls, obj) -> ApprovalWorkflowInstance:
        """Start approval workflow for an object.
        
        Args:
            obj: Django model instance (must implement ApprovableInterface)
        
        Returns:
            ApprovalWorkflowInstance
            
        Raises:
            ValueError: If workflow already in progress
        """
        cls._validate_approvable(obj)
        
        # Check if workflow already exists
        instance = cls.get_workflow_instance(obj)
        
        if instance:
            if instance.status in ['pending', 'in_progress']:
                raise ValueError(
                    f"Workflow already in progress for {obj}. "
                    f"Cancel or complete existing workflow first."
                )
        
        if not instance:
            instance = cls.create_instance(obj)
        
        # If pending, activate first stage(s)
        if instance.status == ApprovalWorkflowInstance.STATUS_PENDING:
            instance = cls._activate_next_stage_internal(obj, instance)
            
            # Call hook
            obj.on_approval_started(instance)
        
        return instance
    
    @classmethod
    def restart_workflow(cls, obj) -> ApprovalWorkflowInstance:
        """Cancel current workflow and start a fresh one.
        
        Args:
            obj: Django model instance
        
        Returns:
            New ApprovalWorkflowInstance
        """
        cls.cancel_workflow(obj, reason="Restarted by system/user")
        return cls.start_workflow(obj)
    
    @classmethod
    def cancel_workflow(cls, obj, reason=None) -> ApprovalWorkflowInstance:
        """Cancel the active workflow for an object.
        
        Args:
            obj: Django model instance
            reason: Optional cancellation reason
        
        Returns:
            ApprovalWorkflowInstance
        """
        instance = cls.get_workflow_instance(obj, active_only=False)
        
        if not instance:
            raise ValueError("No workflow instance found to cancel")
        
        if instance.status in [
            ApprovalWorkflowInstance.STATUS_APPROVED,
            ApprovalWorkflowInstance.STATUS_REJECTED,
            ApprovalWorkflowInstance.STATUS_CANCELLED,
        ]:
            return instance
        
        with transaction.atomic():
            instance = ApprovalWorkflowInstance.objects.select_for_update().get(
                pk=instance.pk
            )
            
            # Cancel active stages
            active_stages = instance.stage_instances.filter(
                status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
            )
            now = timezone.now()
            
            for stage in active_stages:
                stage.status = ApprovalWorkflowStageInstance.STATUS_CANCELLED
                stage.completed_at = now
                stage.save(update_fields=["status", "completed_at"])
                
                # Deactivate delegations
                stage.delegations.filter(active=True).update(
                    active=False,
                    deactivated_at=now
                )
            
            # Update workflow instance
            instance.status = ApprovalWorkflowInstance.STATUS_CANCELLED
            instance.finished_at = now
            instance.current_stage_template = None
            instance.save(update_fields=["status", "finished_at", "current_stage_template"])
            
            # Log system action
            system_user = cls._get_system_user()
            if active_stages.exists():
                ApprovalAction.objects.create(
                    stage_instance=active_stages.first(),
                    user=system_user,
                    assignment=None,
                    action=ApprovalAction.ACTION_COMMENT,
                    comment=f"Workflow cancelled. Reason: {reason or 'No reason provided'}",
                    triggers_stage_completion=False,
                )
            
            # Call hook
            if hasattr(obj, 'on_cancelled'):
                obj.on_cancelled(instance, reason)
        
        return instance
    
    # ----------------------
    # Stage Activation & Assignment
    # ----------------------
    
    @classmethod
    def _create_assignments(cls, stage_instance: ApprovalWorkflowStageInstance):
        """Create assignments based on stage template filters.
        
        Returns:
            List of created ApprovalAssignment objects
        """
        stage_template = stage_instance.stage_template
        qs = User.objects.all()
        
        # Filter by role if specified (now uses ForeignKey relationship)
        if stage_template.required_role:
            qs = qs.filter(role=stage_template.required_role)
        
        created = []
        for user in qs.distinct():
            # Get role name for snapshot (role_snapshot is CharField)
            role_name = user.role.name if user.role else None
            
            obj, created_flag = ApprovalAssignment.objects.get_or_create(
                stage_instance=stage_instance,
                user=user,
                defaults={
                    "role_snapshot": role_name,
                    "level_snapshot": None,
                    "is_mandatory": True,
                    "status": ApprovalAssignment.STATUS_PENDING,
                },
            )
            if created_flag:
                created.append(obj)
        
        return created
    
    @classmethod
    def _activate_next_stage_internal(cls, obj, instance=None):
        """Activate the next set of stage_instances.
        
        Args:
            obj: The model object being approved
            instance: ApprovalWorkflowInstance (optional, will fetch if not provided)
        
        Returns:
            Updated ApprovalWorkflowInstance
        """
        if not instance:
            instance = cls.get_workflow_instance(obj)
            if not instance:
                raise ValueError("No workflow instance to progress")
        
        with transaction.atomic():
            instance = ApprovalWorkflowInstance.objects.select_for_update().get(
                pk=instance.pk
            )
            
            # Prevent progressing finished workflows
            if instance.status in {
                ApprovalWorkflowInstance.STATUS_APPROVED,
                ApprovalWorkflowInstance.STATUS_REJECTED,
                ApprovalWorkflowInstance.STATUS_CANCELLED,
            }:
                return instance
            
            # Find next stages to activate
            next_order = cls._find_next_order_index(instance)
            
            if next_order is None:
                # No more stages - workflow complete!
                instance.status = ApprovalWorkflowInstance.STATUS_APPROVED
                instance.finished_at = timezone.now()
                instance.current_stage_template = None
                instance.save(update_fields=["status", "finished_at", "current_stage_template"])
                
                # Call hook
                if hasattr(obj, 'on_fully_approved'):
                    obj.on_fully_approved(instance)
                
                return instance
            
            # Get stage templates at next_order
            next_stage_templates = instance.template.stages.filter(
                order_index=next_order
            ).order_by("order_index")
            
            if not next_stage_templates.exists():
                # No stages at this order, workflow might be misconfigured
                # Try to complete workflow
                instance.status = ApprovalWorkflowInstance.STATUS_APPROVED
                instance.finished_at = timezone.now()
                instance.current_stage_template = None
                instance.save(update_fields=["status", "finished_at", "current_stage_template"])
                
                if hasattr(obj, 'on_fully_approved'):
                    obj.on_fully_approved(instance)
                
                return instance
            
            created_stage_instances = []
            now = timezone.now()
            
            # Create and activate new stage instances
            for stage_template in next_stage_templates:
                stage_instance = ApprovalWorkflowStageInstance.objects.create(
                    workflow_instance=instance,
                    stage_template=stage_template,
                    status=ApprovalWorkflowStageInstance.STATUS_ACTIVE,
                    activated_at=now,
                )
                created_stage_instances.append(stage_instance)
                
                # Create assignments
                assignments = cls._create_assignments(stage_instance)
                
                # Auto-skip if no assignments
                if not assignments:
                    stage_instance.status = ApprovalWorkflowStageInstance.STATUS_SKIPPED
                    stage_instance.completed_at = now
                    stage_instance.save(update_fields=["status", "completed_at"])
                    
                    # Log skip
                    system_user = cls._get_system_user()
                    ApprovalAction.objects.create(
                        stage_instance=stage_instance,
                        user=system_user,
                        assignment=None,
                        action=ApprovalAction.ACTION_COMMENT,
                        comment="Stage auto-skipped: no eligible approvers",
                        triggers_stage_completion=True,
                    )
                    
                    # Call hook if available
                    if hasattr(cls, 'on_stage_skipped'):
                        cls.on_stage_skipped(stage_instance)
            
            # Update workflow instance
            instance.status = ApprovalWorkflowInstance.STATUS_IN_PROGRESS
            instance.current_stage_template = (
                created_stage_instances[0].stage_template
                if created_stage_instances else None
            )
            instance.save(update_fields=["status", "current_stage_template"])
            
            # Check if all stages were skipped - if so, try to progress
            active_stages = instance.stage_instances.filter(
                status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
            )
            if not active_stages.exists() and created_stage_instances:
                # All stages skipped, try to activate next
                return cls._activate_next_stage_internal(obj, instance)
        
        return instance
    
    @classmethod
    def _find_next_order_index(cls, instance):
        """Find the next order_index to activate.
        
        Returns:
            Integer order_index or None if no more stages
        """
        active = instance.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        )
        
        if not active.exists():
            # No active stages - find first uncompleted
            completed = instance.stage_instances.filter(
                status__in=[
                    ApprovalWorkflowStageInstance.STATUS_COMPLETED,
                    ApprovalWorkflowStageInstance.STATUS_SKIPPED,
                ]
            ).order_by("-stage_template__order_index")
            
            if completed.exists():
                last_order = completed.first().stage_template.order_index
                next_template = instance.template.stages.filter(
                    order_index__gt=last_order
                ).order_by("order_index").first()
                
                return next_template.order_index if next_template else None
            else:
                # Start from beginning
                first = instance.template.stages.order_by("order_index").first()
                return first.order_index if first else None
        else:
            # Find next after current active
            current_order = active.first().stage_template.order_index
            next_template = instance.template.stages.filter(
                order_index__gt=current_order
            ).order_by("order_index").first()
            
            return next_template.order_index if next_template else None
    
    # ----------------------
    # Stage Evaluation
    # ----------------------
    
    @classmethod
    def check_finished_stage(cls, obj):
        """Evaluate active stage group and determine if finished.
        
        Args:
            obj: Model object being approved
        
        Returns:
            Tuple: (is_finished: bool, outcome: str)
            outcome in {"approved", "rejected", "pending"}
        """
        instance = cls.get_workflow_instance(obj)
        
        if not instance:
            raise ValueError("No workflow instance found")
        
        active_stages = instance.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        )
        
        if not active_stages.exists():
            return False, "pending"
        
        # Evaluate stages at same order_index
        order_index = active_stages.order_by("stage_template__order_index").first().stage_template.order_index
        group_stages = active_stages.filter(stage_template__order_index=order_index)
        
        any_rejected = False
        all_approved = True
        
        for stage in group_stages:
            template = stage.stage_template
            
            # Check for rejection
            if template.allow_reject and stage.actions.filter(
                action=ApprovalAction.ACTION_REJECT
            ).exists():
                any_rejected = True
                continue
            
            # Count approvals
            approved_assignment_ids = stage.actions.filter(
                action=ApprovalAction.ACTION_APPROVE
            ).values_list("assignment_id", flat=True).distinct()
            approved_count = len([x for x in approved_assignment_ids if x])
            
            total_assignments = stage.assignments.count()
            
            # Check decision policy
            if template.decision_policy == ApprovalWorkflowStageTemplate.POLICY_ALL:
                all_ids = set(stage.assignments.values_list("id", flat=True))
                if set(approved_assignment_ids) != all_ids:
                    all_approved = False
            
            elif template.decision_policy == ApprovalWorkflowStageTemplate.POLICY_ANY:
                if approved_count < 1:
                    all_approved = False
            
            elif template.decision_policy == ApprovalWorkflowStageTemplate.POLICY_QUORUM:
                quorum = template.quorum_count or max(1, total_assignments // 2 + 1)
                if approved_count < quorum:
                    all_approved = False
        
        if any_rejected:
            return True, "rejected"
        if all_approved:
            return True, "approved"
        
        return False, "pending"
    
    @classmethod
    def _complete_active_stage_group(cls, obj, instance, outcome, comment=None):
        """Mark active stage group as completed and handle outcome.
        
        Args:
            obj: Model object being approved
            instance: ApprovalWorkflowInstance
            outcome: "approved" or "rejected"
            comment: Optional comment
        """
        active_stages = instance.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        )
        
        if not active_stages.exists():
            return
        
        order_index = active_stages.order_by("stage_template__order_index").first().stage_template.order_index
        group_stages = active_stages.filter(stage_template__order_index=order_index)
        
        now = timezone.now()
        system_user = cls._get_system_user()
        
        if outcome == "approved":
            for stage in group_stages:
                stage.status = ApprovalWorkflowStageInstance.STATUS_COMPLETED
                stage.completed_at = now
                stage.save(update_fields=["status", "completed_at"])
                
                # Deactivate delegations
                stage.delegations.filter(active=True).update(
                    active=False,
                    deactivated_at=now
                )
                
                # Delete pending assignments
                stage.assignments.filter(status=ApprovalAssignment.STATUS_PENDING).delete()
                
                # Call hook
                if hasattr(obj, 'on_stage_approved'):
                    obj.on_stage_approved(stage)
        
        elif outcome == "rejected":
            for stage in group_stages:
                stage.status = ApprovalWorkflowStageInstance.STATUS_COMPLETED
                stage.completed_at = now
                stage.save(update_fields=["status", "completed_at"])
                
                stage.delegations.filter(active=True).update(
                    active=False,
                    deactivated_at=now
                )
                
                stage.assignments.filter(status=ApprovalAssignment.STATUS_PENDING).delete()
            
            # Mark workflow rejected
            instance.status = ApprovalWorkflowInstance.STATUS_REJECTED
            instance.finished_at = now
            instance.current_stage_template = None
            instance.save(update_fields=["status", "finished_at", "current_stage_template"])
            
            # Log rejection
            ApprovalAction.objects.create(
                stage_instance=group_stages.first(),
                user=system_user,
                assignment=None,
                action=ApprovalAction.ACTION_REJECT,
                comment=comment or "Workflow rejected",
                triggers_stage_completion=True,
            )
            
            # Call hook
            if hasattr(obj, 'on_rejected'):
                obj.on_rejected(instance, group_stages.first())
    
    # ----------------------
    # User Actions
    # ----------------------
    
    @classmethod
    def process_action(cls, obj, user, action, comment=None, target_user=None):
        """Process user action on workflow.
        
        Args:
            obj: Model object being approved
            user: User performing action
            action: "approve", "reject", "delegate", or "comment"
            comment: Optional comment
            target_user: Required for delegation
        
        Returns:
            ApprovalWorkflowInstance
        """
        instance = cls.get_workflow_instance(obj)
        
        if not instance:
            raise ValueError("No workflow instance found")
        
        with transaction.atomic():
            instance = ApprovalWorkflowInstance.objects.select_for_update().get(
                pk=instance.pk
            )
            
            active_stage = instance.stage_instances.filter(
                status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
            ).first()
            
            if not active_stage:
                raise ValueError("No active stage to act on")
            
            assignment = active_stage.assignments.filter(user=user).first()
            
            if not assignment:
                raise ValueError(f"User {user} has no assignment in this active stage")
            
            # Validate action
            if action not in {
                ApprovalAction.ACTION_APPROVE,
                ApprovalAction.ACTION_REJECT,
                ApprovalAction.ACTION_DELEGATE,
                ApprovalAction.ACTION_COMMENT,
            }:
                raise ValueError(f"Invalid action: {action}")
            
            # Enforce policies
            if action == ApprovalAction.ACTION_REJECT and not active_stage.stage_template.allow_reject:
                raise ValueError("Rejection not allowed in this stage")
            
            if action == ApprovalAction.ACTION_DELEGATE and not active_stage.stage_template.allow_delegate:
                raise ValueError("Delegation not allowed in this stage")
            
            # Prevent duplicate approve/reject
            if action in {ApprovalAction.ACTION_APPROVE, ApprovalAction.ACTION_REJECT}:
                existing = ApprovalAction.objects.filter(
                    stage_instance=active_stage,
                    user=user,
                    action__in=[ApprovalAction.ACTION_APPROVE, ApprovalAction.ACTION_REJECT],
                ).exists()
                
                if existing:
                    raise ValueError(f"User {user} already {action}d this stage")
            
            # Handle delegation
            if action == ApprovalAction.ACTION_DELEGATE:
                if not target_user:
                    raise ValueError("target_user required for delegation")
                
                cls.delegate(user, target_user, active_stage, comment=comment)
                return instance
            
            # Create action log
            ApprovalAction.objects.create(
                stage_instance=active_stage,
                user=user,
                assignment=assignment,
                action=action,
                comment=comment,
                triggers_stage_completion=False,
            )
            
            # Update assignment status
            if action in (ApprovalAction.ACTION_APPROVE, ApprovalAction.ACTION_REJECT):
                assignment.status = action
                assignment.save(update_fields=["status"])
            
            # Evaluate stage completion
            finished, outcome = cls.check_finished_stage(obj)
            
            if finished:
                cls._complete_active_stage_group(obj, instance, outcome, comment=comment)
                
                if outcome == "approved":
                    # Activate next stage
                    cls._activate_next_stage_internal(obj, instance)
        
        return instance
    
    # ----------------------
    # Delegation
    # ----------------------
    
    @classmethod
    def delegate(cls, from_user, to_user, stage_instance, comment=None):
        """Delegate approval to another user.
        
        Args:
            from_user: User delegating
            to_user: User receiving delegation
            stage_instance: ApprovalWorkflowStageInstance
            comment: Optional comment
        
        Returns:
            ApprovalDelegation
        """
        if not stage_instance.stage_template.allow_delegate:
            raise ValueError("Delegation not allowed in this stage")
        
        with transaction.atomic():
            from_assignment = stage_instance.assignments.filter(
                user=from_user
            ).select_for_update().first()
            
            if not from_assignment:
                raise ValueError(f"{from_user} has no assignment in this stage")
            
            if from_assignment.status != ApprovalAssignment.STATUS_PENDING:
                raise ValueError("Assignment already processed")
            
            # Check if target user already involved
            existing = stage_instance.assignments.filter(user=to_user).exists()
            if existing:
                raise ValueError("Target user already involved in this stage")
            
            # Create delegation
            delegation = ApprovalDelegation.objects.create(
                from_user=from_user,
                to_user=to_user,
                stage_instance=stage_instance,
                active=True,
            )
            
            # Create assignment for delegate
            ApprovalAssignment.objects.create(
                stage_instance=stage_instance,
                user=to_user,
                role_snapshot=getattr(to_user, "role", None),
                level_snapshot=None,
                is_mandatory=from_assignment.is_mandatory,
                status=ApprovalAssignment.STATUS_PENDING,
            )
            
            # Update original assignment
            from_assignment.status = ApprovalAssignment.STATUS_DELEGATED
            from_assignment.save(update_fields=["status"])
            
            # Log delegation
            ApprovalAction.objects.create(
                stage_instance=stage_instance,
                user=from_user,
                assignment=from_assignment,
                action=ApprovalAction.ACTION_DELEGATE,
                comment=comment or f"Delegated to {to_user}",
                triggers_stage_completion=False,
            )
        
        return delegation
    
    # ----------------------
    # Utility Methods
    # ----------------------
    
    @staticmethod
    def get_workflow_instance(obj, active_only=True):
        """Get the workflow instance for an object.
        
        Args:
            obj: Model object
            active_only: If True, only return active workflows (pending/in_progress)
        
        Returns:
            ApprovalWorkflowInstance or None
        """
        content_type = ContentType.objects.get_for_model(obj)
        
        query = ApprovalWorkflowInstance.objects.filter(
            content_type=content_type,
            object_id=obj.pk
        )
        
        if active_only:
            query = query.filter(
                status__in=[
                    ApprovalWorkflowInstance.STATUS_PENDING,
                    ApprovalWorkflowInstance.STATUS_IN_PROGRESS,
                ]
            )
        
        return query.order_by('-started_at').first()
    
    @staticmethod
    def get_user_pending_approvals(user):
        """Get all objects waiting for user's approval.
        
        Args:
            user: User object
        
        Returns:
            QuerySet of ApprovalWorkflowInstance objects
        """
        return ApprovalWorkflowInstance.objects.filter(
            status=ApprovalWorkflowInstance.STATUS_IN_PROGRESS,
            stage_instances__status=ApprovalWorkflowStageInstance.STATUS_ACTIVE,
            stage_instances__assignments__user=user,
            stage_instances__assignments__status=ApprovalAssignment.STATUS_PENDING,
        ).distinct()
    
    @staticmethod
    def is_workflow_finished(obj):
        """Check if workflow is finished for an object.
        
        Args:
            obj: Model object
        
        Returns:
            Tuple: (is_finished: bool, status: str)
        """
        content_type = ContentType.objects.get_for_model(obj)
        
        instance = ApprovalWorkflowInstance.objects.filter(
            content_type=content_type,
            object_id=obj.pk
        ).order_by('-started_at').first()
        
        if not instance:
            return False, "no_instance"
        
        if instance.status in {
            ApprovalWorkflowInstance.STATUS_APPROVED,
            ApprovalWorkflowInstance.STATUS_REJECTED,
            ApprovalWorkflowInstance.STATUS_CANCELLED,
        }:
            return True, instance.status
        
        return False, instance.status
