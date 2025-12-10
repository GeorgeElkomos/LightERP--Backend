"""Test concurrent operations and race conditions.

Tests scenarios where multiple users or processes interact
with the approval system simultaneously.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.db import transaction

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalAction
)
from core.approval.managers import ApprovalManager
from core.approval.models import TestInvoice

User = get_user_model()


class ConcurrencyTest(TransactionTestCase):
    """Test concurrent operations."""
    
    def setUp(self):
        """Set up test data."""
        # Create multiple users
        self.users = []
        for i in range(1, 6):
            user = User.objects.create_user(
                email=f'approver{i}@test.com',
                name=f'Approver {i}',
                phone_number='1234567890',
                password='testpass123'
            )
            self.users.append(user)
        
        # Create template with QUORUM policy
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        self.template = ApprovalWorkflowTemplate.objects.create(
            code='CONCURRENT_TEST',
            name='Concurrent Test Workflow',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        self.stage = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Quorum Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            quorum_count=3,
            allow_reject=True
        )
        
        # Create invoice
        self.invoice = TestInvoice.objects.create(
            invoice_number='INV-CONCURRENT-001',
            vendor_name='Test Vendor',
            total_amount=10000.00,
            description='Test concurrent approvals'
        )
    
    def test_simultaneous_approvals(self):
        """Test multiple users approving at the same time."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Simulate 3 users approving "simultaneously"
        # In reality, they'll be sequential but this tests the logic
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[1], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[2], 'approve')
        
        workflow.refresh_from_db()
        
        # Should be approved after 3 approvals (quorum reached)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # All 3 actions should be recorded
        actions = ApprovalAction.objects.filter(
            stage_instance__workflow_instance=workflow,
            action=ApprovalAction.ACTION_APPROVE
        )
        self.assertEqual(actions.count(), 3)
    
    def test_simultaneous_approval_and_rejection(self):
        """Test one user approving while another rejects."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # User 1 approves
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        
        # User 2 rejects
        ApprovalManager.process_action(self.invoice, self.users[1], 'reject')
        
        workflow.refresh_from_db()
        
        # Rejection should win
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Actions should be recorded (may include auto-cancellation)
        actions = ApprovalAction.objects.filter(
            stage_instance__workflow_instance=workflow
        )
        self.assertGreaterEqual(actions.count(), 2)
        
        # Verify at least one approve and one reject action exist
        approve_actions = actions.filter(action=ApprovalAction.ACTION_APPROVE)
        reject_actions = actions.filter(action=ApprovalAction.ACTION_REJECT)
        self.assertGreaterEqual(approve_actions.count(), 1)
        self.assertGreaterEqual(reject_actions.count(), 1)
    
    def test_racing_to_quorum(self):
        """Test multiple approvals racing to reach quorum."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # First 2 approve
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[1], 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Users 2 and 3 try to approve at "same time"
        # Only need 1 more to reach quorum of 3
        ApprovalManager.process_action(self.invoice, self.users[2], 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # User 4 tries to approve after workflow is done
        with self.assertRaises(ValueError):
            ApprovalManager.process_action(self.invoice, self.users[3], 'approve')
    
    def test_cancel_during_approval(self):
        """Test cancelling while approvals are happening."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # User 1 approves
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        
        # Workflow is cancelled
        ApprovalManager.cancel_workflow(self.invoice, reason='Cancelled mid-approval')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_CANCELLED)
        
        # User 2 tries to approve after cancellation
        with self.assertRaises(ValueError):
            ApprovalManager.process_action(self.invoice, self.users[1], 'approve')
    
    def test_multiple_stage_progression(self):
        """Test stage progression with multiple approvers."""
        # Add second stage
        stage2 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=2,
            name='Second Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY
        )
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Complete first stage (need 3 approvals for quorum)
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[1], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[2], 'approve')
        
        workflow.refresh_from_db()
        
        # Should be in stage 2 now
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # User 3 approves stage 2 (ANY policy)
        ApprovalManager.process_action(self.invoice, self.users[2], 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)


class StressTest(TestCase):
    """Stress test with many approvers and stages."""
    
    def setUp(self):
        """Set up test data."""
        # Create 20 users
        self.users = []
        for i in range(1, 21):
            user = User.objects.create_user(
                email=f'user{i}@test.com',
                name=f'User {i}',
                phone_number='1234567890',
                password='testpass123'
            )
            self.users.append(user)
    
    def test_large_number_of_approvers(self):
        """Test workflow with 20 approvers (ALL policy)."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='LARGE_APPROVERS',
            name='Large Approver Set',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='All Approvers Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL
        )
        
        invoice = TestInvoice.objects.create(
            invoice_number='INV-STRESS-001',
            vendor_name='Vendor',
            total_amount=100000.00,
            description='Large approval test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # All 20 users approve
        for user in self.users:
            ApprovalManager.process_action(invoice, user, 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # Check all actions recorded
        actions = ApprovalAction.objects.filter(
            stage_instance__workflow_instance=workflow
        )
        self.assertEqual(actions.count(), 20)
    
    def test_multiple_concurrent_workflows(self):
        """Test multiple workflows running simultaneously."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='CONCURRENT_WORKFLOWS',
            name='Concurrent Workflows',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='Stage 1',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY
        )
        
        # Create 10 invoices
        invoices = []
        for i in range(1, 11):
            invoice = TestInvoice.objects.create(
                invoice_number=f'INV-CONCURRENT-{i:03d}',
                vendor_name=f'Vendor {i}',
                total_amount=1000.00 * i,
                description=f'Invoice {i}'
            )
            invoices.append(invoice)
        
        # Start all workflows
        workflows = []
        for invoice in invoices:
            workflow = ApprovalManager.start_workflow(invoice)
            workflows.append(workflow)
        
        # Each user approves some invoices
        for i, user in enumerate(self.users[:10]):
            # Each user approves their corresponding invoice
            ApprovalManager.process_action(invoices[i], user, 'approve')
        
        # Check all workflows completed
        for workflow in workflows:
            workflow.refresh_from_db()
            self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
