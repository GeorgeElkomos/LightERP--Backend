"""Test different decision policies.

Tests ALL, ANY, and QUORUM decision policies in various scenarios.
"""

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance
)
from core.approval.managers import ApprovalManager
from core.approval.models import TestInvoice

User = get_user_model()


class DecisionPolicyTest(TestCase):
    """Test different decision policies."""
    
    def setUp(self):
        """Set up test data."""
        # Create 5 users
        self.users = []
        for i in range(1, 6):
            user = User.objects.create_user(
                email=f'approver{i}@test.com',
                name=f'Approver {i}',
                phone_number='1234567890',
                password='testpass123'
            )
            self.users.append(user)
        
        # Create invoice
        self.invoice = TestInvoice.objects.create(
            invoice_number='INV-POLICY-001',
            vendor_name='Test Vendor',
            total_amount=10000.00,
            description='Test invoice for policy testing'
        )
    
    def create_template_with_policy(self, policy, quorum_count=None):
        """Helper to create template with specific policy."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code=f'TEST_POLICY_{policy}',
            name=f'Test {policy} Policy',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name=f'{policy} Policy Stage',
            decision_policy=policy,
            quorum_count=quorum_count,
            allow_reject=True
        )
        
        return template
    
    def test_any_policy_single_approval(self):
        """Test ANY policy - single approval completes stage."""
        self.create_template_with_policy(ApprovalWorkflowStageTemplate.POLICY_ANY)
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Only one user approves
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        # Should be fully approved
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        self.assertTrue(self.invoice.fully_approved_called)
    
    def test_any_policy_first_wins(self):
        """Test ANY policy - first approval wins."""
        self.create_template_with_policy(ApprovalWorkflowStageTemplate.POLICY_ANY)
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # User 2 approves first
        ApprovalManager.process_action(self.invoice, self.users[1], 'approve')
        
        workflow.refresh_from_db()
        
        # Should be approved
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # User 3 cannot approve (workflow already done)
        stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        self.assertIsNone(stage)  # No active stages
    
    def test_all_policy_requires_everyone(self):
        """Test ALL policy - all users must approve."""
        self.create_template_with_policy(ApprovalWorkflowStageTemplate.POLICY_ALL)
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # First 4 users approve
        for i in range(4):
            ApprovalManager.process_action(self.invoice, self.users[i], 'approve')
            workflow.refresh_from_db()
            
            # Should still be in progress
            self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Last user approves
        ApprovalManager.process_action(self.invoice, self.users[4], 'approve')
        
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        # Now should be approved
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        self.assertTrue(self.invoice.fully_approved_called)
    
    def test_all_policy_missing_one_approval(self):
        """Test ALL policy - missing one approval keeps it pending."""
        self.create_template_with_policy(ApprovalWorkflowStageTemplate.POLICY_ALL)
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Only 4 out of 5 approve
        for i in range(4):
            ApprovalManager.process_action(self.invoice, self.users[i], 'approve')
        
        workflow.refresh_from_db()
        
        # Should still be in progress
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Active stage should still exist
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        self.assertIsNotNone(active_stage)
    
    def test_quorum_policy_exact_count(self):
        """Test QUORUM policy - exact quorum count."""
        # Require 3 out of 5
        self.create_template_with_policy(
            ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            quorum_count=3
        )
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # First 2 approve - not enough
        for i in range(2):
            ApprovalManager.process_action(self.invoice, self.users[i], 'approve')
            workflow.refresh_from_db()
            self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # 3rd approval - should complete
        ApprovalManager.process_action(self.invoice, self.users[2], 'approve')
        
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        self.assertTrue(self.invoice.fully_approved_called)
    
    def test_quorum_policy_more_than_required(self):
        """Test QUORUM policy - more approvals than required still works."""
        # Require 3 out of 5
        self.create_template_with_policy(
            ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            quorum_count=3
        )
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # All 5 approve (more than required 3)
        for user in self.users:
            if workflow.status != ApprovalWorkflowInstance.STATUS_APPROVED:
                ApprovalManager.process_action(self.invoice, user, 'approve')
                workflow.refresh_from_db()
        
        # Should be approved after 3rd approval
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_quorum_policy_majority(self):
        """Test QUORUM with majority (3 out of 5)."""
        self.create_template_with_policy(
            ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            quorum_count=3
        )
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # 3 users approve (majority)
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[2], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[4], 'approve')
        
        workflow.refresh_from_db()
        
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_any_policy_rejection(self):
        """Test ANY policy - one rejection fails the workflow."""
        self.create_template_with_policy(ApprovalWorkflowStageTemplate.POLICY_ANY)
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # One user rejects
        ApprovalManager.process_action(
            self.invoice,
            self.users[0],
            'reject',
            comment='Not approved'
        )
        
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        self.assertTrue(self.invoice.rejected_called)
    
    def test_all_policy_rejection(self):
        """Test ALL policy - one rejection fails even if others approve."""
        self.create_template_with_policy(ApprovalWorkflowStageTemplate.POLICY_ALL)
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # 3 users approve
        for i in range(3):
            ApprovalManager.process_action(self.invoice, self.users[i], 'approve')
        
        # 1 user rejects
        ApprovalManager.process_action(
            self.invoice,
            self.users[3],
            'reject',
            comment='I reject this'
        )
        
        workflow.refresh_from_db()
        self.invoice.refresh_from_db()
        
        # Should be rejected
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        self.assertTrue(self.invoice.rejected_called)
    
    def test_quorum_policy_rejection(self):
        """Test QUORUM policy - rejection before quorum reached."""
        self.create_template_with_policy(
            ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            quorum_count=3
        )
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # 2 approve, 1 rejects
        ApprovalManager.process_action(self.invoice, self.users[0], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[1], 'approve')
        ApprovalManager.process_action(self.invoice, self.users[2], 'reject')
        
        workflow.refresh_from_db()
        
        # Should be rejected
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
