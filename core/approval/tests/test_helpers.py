"""Test helper functions and utilities.

Tests mixin methods, manager utilities, and helper functions.
"""

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance
)
from core.approval.managers import ApprovalManager
from core.approval.models import TestInvoice

User = get_user_model()


class HelperFunctionsTest(TestCase):
    """Test helper functions and utilities."""
    
    def setUp(self):
        """Set up test data."""
        # Create user level
# Create users
        self.user1 = User.objects.create_user(
            email='user1@test.com',
            name='User 1',
            phone_number='1234567890',
            password='testpass123'
        )
        
        self.user2 = User.objects.create_user(
            email='user2@test.com',
            name='User 2',
            phone_number='1234567890',
            password='testpass123'
        )
        
        # Create template
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        self.template = ApprovalWorkflowTemplate.objects.create(
            code='TEST_HELPERS',
            name='Test Helpers',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        self.stage = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Test Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY
        )
        
        # Create invoice
        self.invoice = TestInvoice.objects.create(
            invoice_number='INV-HELPER-001',
            vendor_name='Test Vendor',
            total_amount=5000.00,
            description='Test helpers'
        )
    
    def test_get_current_workflow(self):
        """Test getting current workflow from mixin."""
        # No workflow yet
        current = self.invoice.get_current_workflow()
        self.assertIsNone(current)
        
        # Start workflow
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Now should get it
        current = self.invoice.get_current_workflow()
        self.assertEqual(current, workflow)
    
    def test_has_pending_workflow(self):
        """Test checking if object has pending workflow."""
        # No workflow
        self.assertFalse(self.invoice.has_pending_workflow())
        
        # Start workflow
        ApprovalManager.start_workflow(self.invoice)
        
        # Should have pending
        self.assertTrue(self.invoice.has_pending_workflow())
        
        # Approve workflow
        ApprovalManager.process_action(self.invoice, self.user1, 'approve')
        
        # No longer pending
        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.has_pending_workflow())
    
    def test_get_approval_history(self):
        """Test getting approval history for object."""
        # Start workflow
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Approve
        ApprovalManager.process_action(
            self.invoice,
            self.user1,
            'approve',
            comment='Test approval'
        )
        
        # Get history
        history = self.invoice.get_approval_history()
        
        # Should have 1 action
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().action, 'approve')
        self.assertEqual(history.first().user, self.user1)
    
    def test_get_user_pending_approvals_empty(self):
        """Test getting pending approvals when user has none."""
        pending = ApprovalManager.get_user_pending_approvals(self.user1)
        self.assertEqual(pending.count(), 0)
    
    def test_get_user_pending_approvals_with_items(self):
        """Test getting user's pending approvals."""
        # Create multiple invoices
        invoice2 = TestInvoice.objects.create(
            invoice_number='INV-HELPER-002',
            vendor_name='Vendor 2',
            total_amount=3000.00,
            description='Invoice 2'
        )
        
        invoice3 = TestInvoice.objects.create(
            invoice_number='INV-HELPER-003',
            vendor_name='Vendor 3',
            total_amount=7000.00,
            description='Invoice 3'
        )
        
        # Start workflows
        ApprovalManager.start_workflow(self.invoice)
        ApprovalManager.start_workflow(invoice2)
        ApprovalManager.start_workflow(invoice3)
        
        # User1 has 3 pending
        pending = ApprovalManager.get_user_pending_approvals(self.user1)
        self.assertEqual(pending.count(), 3)
        
        # Approve one
        ApprovalManager.process_action(self.invoice, self.user1, 'approve')
        
        # Now 2 pending
        pending = ApprovalManager.get_user_pending_approvals(self.user1)
        self.assertEqual(pending.count(), 2)
    
    def test_workflow_instance_str(self):
        """Test string representation of workflow instance."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        str_repr = str(workflow)
        self.assertIn('Invoice INV-HELPER-001', str_repr)
    
    def test_stage_instance_str(self):
        """Test string representation of stage instance."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        stage_instance = workflow.stage_instances.first()
        
        str_repr = str(stage_instance)
        self.assertIn('Test Stage', str_repr)
    
    def test_assignment_str(self):
        """Test string representation of assignment."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        stage_instance = workflow.stage_instances.first()
        assignment = stage_instance.assignments.first()
        
        str_repr = str(assignment)
        # Should contain username
        self.assertIsNotNone(str_repr)
    
    def test_action_str(self):
        """Test string representation of action."""
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        ApprovalManager.process_action(
            self.invoice,
            self.user1,
            'approve',
            comment='Test'
        )
        
        stage_instance = workflow.stage_instances.first()
        action = stage_instance.actions.first()
        
        str_repr = str(action)
        self.assertIn('approve', str_repr.lower())
    
    def test_template_str(self):
        """Test string representation of template."""
        str_repr = str(self.template)
        self.assertIn('Test Helpers', str_repr)
    
    def test_stage_template_str(self):
        """Test string representation of stage template."""
        str_repr = str(self.stage)
        self.assertIn('Test Stage', str_repr)
    
    def test_is_active_property(self):
        """Test is_active property on delegation."""
        from core.approval.models import ApprovalDelegation
        from django.utils import timezone
        
        # Active delegation
        delegation = ApprovalDelegation.objects.create(
            from_user=self.user1,
            to_user=self.user2,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=5)
        )
        
        self.assertTrue(delegation.is_active)
        
        # Expired delegation
        expired = ApprovalDelegation.objects.create(
            from_user=self.user1,
            to_user=self.user2,
            start_date=timezone.now().date() - timezone.timedelta(days=10),
            end_date=timezone.now().date() - timezone.timedelta(days=5)
        )
        
        self.assertFalse(expired.is_active)
    
    def test_restart_workflow_creates_new_instance(self):
        """Test that restart creates new workflow instance."""
        # Start first workflow
        workflow1 = ApprovalManager.start_workflow(self.invoice)
        workflow1_id = workflow1.id
        
        # Cancel it
        ApprovalManager.cancel_workflow(self.invoice)
        
        # Restart
        workflow2 = ApprovalManager.restart_workflow(self.invoice)
        
        # Should be different instance
        self.assertNotEqual(workflow1_id, workflow2.id)
        self.assertEqual(workflow2.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
    
    def test_workflow_template_versioning(self):
        """Test that template versioning works."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        # Create v2
        template_v2 = ApprovalWorkflowTemplate.objects.create(
            code='TEST_HELPERS_V2',
            name='Test Helpers V2',
            content_type=ct,
            is_active=True,
            version=2
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template_v2,
            order_index=1,
            name='V2 Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL
        )
        
        # Deactivate v1
        self.template.is_active = False
        self.template.save()
        
        # Create new invoice
        invoice2 = TestInvoice.objects.create(
            invoice_number='INV-HELPER-V2',
            vendor_name='Vendor',
            total_amount=1000.00,
            description='V2 test'
        )
        
        # Should use v2
        workflow = ApprovalManager.start_workflow(invoice2)
        self.assertEqual(workflow.template, template_v2)
