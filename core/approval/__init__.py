"""
Dynamic Approval Workflow System for Django

Usage:
    from core.approval.managers import ApprovalManager
    from core.approval.mixins import ApprovableMixin
    
    class MyModel(ApprovableMixin, models.Model):
        # ... your fields ...
        
        def on_approval_started(self, workflow_instance):
            # Your logic here
            pass
        
        # ... implement other required methods
    
    # Start workflow
    ApprovalManager.start_workflow(my_object)
    
    # Process action
    ApprovalManager.process_action(my_object, user, 'approve', comment='OK')
"""

# Don't import models/managers at module level to avoid AppRegistryNotReady errors
# Import them directly from their modules when needed:
# from core.approval.managers import ApprovalManager
# from core.approval.mixins import ApprovableMixin, ApprovableInterface
# from core.approval.models import ApprovalWorkflowTemplate, etc.

__all__ = [
    'ApprovalManager',
    'ApprovableMixin',
    'ApprovableInterface',
    'ApprovalWorkflowTemplate',
    'ApprovalWorkflowStageTemplate',
    'ApprovalWorkflowInstance',
    'ApprovalWorkflowStageInstance',
    'ApprovalAssignment',
    'ApprovalAction',
    'ApprovalDelegation',
]

__version__ = '1.0.0'