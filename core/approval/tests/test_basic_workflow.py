"""Basic workflow tests.

Tests fundamental workflow operations like starting, completing,
and cancelling workflows.
"""

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
    ApprovalAction,
)
from core.approval.managers import ApprovalManager
from core.approval.models import TestInvoice

User = get_user_model()


class BasicWorkflowTest(TestCase):
    """Test basic workflow creation and progression."""
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.manager1 = User.objects.create_user(
            email='manager1@test.com',
            name='Manager One',
            phone_number='1234567890',
            password='testpass123'
        )
        
        self.manager2 = User.objects.create_user(
            email='manager2@test.com',
            name='Manager Two',
            phone_number='1234567891',
            password='testpass123'
        )
        
        self.director = User.objects.create_user(
            email='director@test.com',
            name='Director',
            phone_number='1234567892',
            password='testpass123'
        )
        
        # Create workflow template
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        self.template = ApprovalWorkflowTemplate.objects.create(
            code='TEST_INVOICE_APPROVAL_V1',
            name='Test Invoice Approval',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        # Create stages
        self.stage1 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Approval',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            allow_reject=True,
            allow_delegate=True
        )
        
        self.stage2 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=2,
            name='Director Approval',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            allow_reject=True,
            allow_delegate=False
        )
        
        # Create test invoice
        self.invoice = TestInvoice.objects.create(
            invoice_number='INV-001',
            vendor_name='Test Vendor',
            total_amount=10000.00,
            description='Test invoice for workflow'
        )
    
    def test_workflow_creation(self):
        """Test that workflow instance is created correctly."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        self.assertEqual(workflow.template, self.template)
        self.assertEqual(workflow.content_object, self.invoice)
    
    def test_on_approval_started_called(self):
        """Test that on_approval_started hook is called."""
        self.assertEqual(self.invoice.status, TestInvoice.STATUS_DRAFT)
        self.assertEqual(self.invoice.approval_started_count, 0)
        
        ApprovalManager.start_workflow(self.invoice)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, TestInvoice.STATUS_PENDING)
        self.assertEqual(self.invoice.approval_started_count, 1)
    
    def test_first_stage_activated(self):
        """Test that first stage is activated on workflow start."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        active_stages = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        )
        
        self.assertEqual(active_stages.count(), 1)
        self.assertEqual(active_stages.first().stage_template, self.stage1)
    
    def test_assignments_created(self):
        """Test that assignments are created for eligible users."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        assignments = active_stage.assignments.all()
        
        # All users are assigned (no user_level filtering)
        # We have manager1, manager2, director = 3 users
        self.assertEqual(assignments.count(), 3)
        
        assigned_users = [a.user for a in assignments]
        self.assertIn(self.manager1, assigned_users)
        self.assertIn(self.manager2, assigned_users)
        self.assertIn(self.director, assigned_users)
    
    def test_single_approval_completes_any_policy(self):
        """Test that ANY policy completes with single approval."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Manager1 approves (ANY policy - should complete stage)
        ApprovalManager.process_action(
            self.invoice,
            self.manager1,
            'approve',
            comment='Looks good'
        )
        
        workflow.refresh_from_db()
        
        # First stage should be completed
        stage1_instance = workflow.stage_instances.get(stage_template=self.stage1)
        self.assertEqual(stage1_instance.status, ApprovalWorkflowStageInstance.STATUS_COMPLETED)
        
        # Second stage should be active
        stage2_instance = workflow.stage_instances.get(stage_template=self.stage2)
        self.assertEqual(stage2_instance.status, ApprovalWorkflowStageInstance.STATUS_ACTIVE)
    
    def test_all_policy_requires_all_approvals(self):
        """Test that ALL policy requires all users to approve."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Complete first stage (ANY policy - any user can approve)
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        workflow.refresh_from_db()
        
        # Stage 2 (ALL policy) requires all assigned users
        # Since we removed user_level filtering, all 3 users are assigned
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        ApprovalManager.process_action(self.invoice, self.manager2, 'approve')
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Director approves (last one - should complete workflow)
        ApprovalManager.process_action(
            self.invoice,
            self.director,
            'approve',
            comment='Approved'
        )
        
        workflow.refresh_from_db()
        
        # Workflow should be approved
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_full_workflow_approval(self):
        """Test complete workflow from start to finish."""
        # Start workflow
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Stage 1: ANY policy - manager1 approves
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        # Stage 2: ALL policy - all users must approve
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        ApprovalManager.process_action(self.invoice, self.manager2, 'approve')
        ApprovalManager.process_action(self.invoice, self.director, 'approve')
        
        # Refresh
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        # Check workflow status
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # Check invoice status
        self.assertEqual(self.invoice.status, TestInvoice.STATUS_APPROVED)
        self.assertTrue(self.invoice.fully_approved_called)
        self.assertIsNotNone(self.invoice.approved_at)
    
    def test_workflow_rejection(self):
        """Test workflow rejection."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Manager rejects
        ApprovalManager.process_action(
            self.invoice,
            self.manager1,
            'reject',
            comment='Incorrect amount'
        )
        
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        # Workflow should be rejected
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Invoice should be rejected
        self.assertEqual(self.invoice.status, TestInvoice.STATUS_REJECTED)
        self.assertTrue(self.invoice.rejected_called)
        self.assertIsNotNone(self.invoice.rejected_at)
    
    def test_workflow_cancellation(self):
        """Test workflow cancellation."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Cancel workflow
        ApprovalManager.cancel_workflow(self.invoice, reason='Duplicate invoice')
        
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        # Workflow should be cancelled
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_CANCELLED)
        
        # Invoice should be cancelled
        self.assertEqual(self.invoice.status, TestInvoice.STATUS_CANCELLED)
        self.assertTrue(self.invoice.cancelled_called)
    
    def test_workflow_restart(self):
        """Test workflow restart after cancellation."""
        # Start and cancel
        workflow1 = ApprovalManager.start_workflow(self.invoice)
        ApprovalManager.cancel_workflow(self.invoice)
        
        # Restart
        workflow2 = ApprovalManager.restart_workflow(self.invoice)
        
        # Should have new workflow instance
        self.assertNotEqual(workflow1.id, workflow2.id)
        self.assertEqual(workflow2.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Old workflow should be cancelled
        workflow1.refresh_from_db()
        self.assertEqual(workflow1.status, ApprovalWorkflowInstance.STATUS_CANCELLED)
    
    def test_duplicate_approval_prevented(self):
        """Test that user cannot approve same stage twice."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Stage 1 (ANY policy) - Manager1 approves, stage completes
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        # Now on stage 2 (ALL policy) - Manager1 approves
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        # Try to approve stage 2 again - should raise error
        with self.assertRaises(ValueError) as context:
            ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        self.assertIn('already', str(context.exception).lower())
    
    def test_action_audit_log(self):
        """Test that all actions are logged."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Perform actions
        ApprovalManager.process_action(
            self.invoice,
            self.manager1,
            'approve',
            comment='Manager approval'
        )
        
        ApprovalManager.process_action(
            self.invoice,
            self.director,
            'approve',
            comment='Director approval'
        )
        
        # Check actions
        all_actions = ApprovalAction.objects.filter(
            stage_instance__workflow_instance=workflow
        )
        
        self.assertEqual(all_actions.count(), 2)
        
        # Check first action
        action1 = all_actions.filter(user=self.manager1).first()
        self.assertEqual(action1.action, ApprovalAction.ACTION_APPROVE)
        self.assertEqual(action1.comment, 'Manager approval')
        
        # Check second action
        action2 = all_actions.filter(user=self.director).first()
        self.assertEqual(action2.action, ApprovalAction.ACTION_APPROVE)
        self.assertEqual(action2.comment, 'Director approval')
    
    def test_get_user_pending_approvals(self):
        """Test getting user's pending approvals."""
        # Create multiple invoices
        invoice2 = TestInvoice.objects.create(
            invoice_number='INV-002',
            vendor_name='Vendor 2',
            total_amount=5000.00,
            description='Another invoice'
        )
        
        # Start workflows
        ApprovalManager.start_workflow(self.invoice)
        ApprovalManager.start_workflow(invoice2)
        
        # Get manager's pending approvals
        pending = ApprovalManager.get_user_pending_approvals(self.manager1)
        
        # Manager should have 2 pending approvals (one for each invoice)
        self.assertEqual(pending.count(), 2)
        
        # Approve stage 1 of first invoice (moves to stage 2)
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        # Still has 2 pending: invoice1 stage 2 + invoice2 stage 1
        pending = ApprovalManager.get_user_pending_approvals(self.manager1)
        self.assertEqual(pending.count(), 2)
