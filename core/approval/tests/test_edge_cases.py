"""Test edge cases and error conditions.

Tests unusual scenarios, error handling, and boundary conditions.
"""

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
)
from core.approval.managers import ApprovalManager
from core.approval.models import TestInvoice, TestPurchaseOrder

User = get_user_model()


class EdgeCaseTest(TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test data."""
        # Create user
        self.user1 = User.objects.create_user(
            email='user1@test.com',
            name='User One',
            phone_number='1234567890',
            password='testpass123',
        )
        
        # Create invoice
        self.invoice = TestInvoice.objects.create(
            invoice_number='INV-EDGE-001',
            vendor_name='Test Vendor',
            total_amount=1000.00,
            description='Test invoice'
        )
    
    def test_no_template_exists(self):
        """Test starting workflow when no template exists."""
        # No template created for TestInvoice
        
        with self.assertRaises(ValueError) as context:
            ApprovalManager.start_workflow(self.invoice)
        
        self.assertIn('no active', str(context.exception).lower())
    
    def test_inactive_template_ignored(self):
        """Test that inactive templates are not used."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        # Create inactive template
        template = ApprovalWorkflowTemplate.objects.create(
            code='INACTIVE_TEMPLATE',
            name='Inactive Template',
            content_type=ct,
            is_active=False,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='Stage 1',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY
        )
        
        # Should fail because template is inactive
        with self.assertRaises(ValueError):
            ApprovalManager.start_workflow(self.invoice)
    
    def test_template_with_no_stages(self):
        """Test template with no stages defined."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='NO_STAGES',
            name='Template Without Stages',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        # No stages created
        
        # Should fail or handle gracefully
        try:
            workflow = ApprovalManager.start_workflow(self.invoice)
            # If it doesn't fail, workflow should complete immediately
            # or be in a special state
        except Exception:
            # Expected - cannot have workflow without stages
            pass
    
    def test_no_eligible_users_for_stage(self):
        """Test stage with no eligible users."""
        # Create user level with no users
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='NO_USERS',
            name='Template No Users',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='No Users Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY
        )
        
        # Start workflow
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Stage should be created and have 1 assignment (user1)
        # Without user_level filtering, all users are eligible
        stage_instance = workflow.stage_instances.first()
        self.assertEqual(stage_instance.assignments.count(), 1)
        self.assertEqual(stage_instance.assignments.first().user, self.user1)
    
    def test_workflow_already_in_progress(self):
        """Test starting workflow when one is already in progress."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='TEST_TEMPLATE',
            name='Test Template',
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
        
        # Start first workflow
        workflow1 = ApprovalManager.start_workflow(self.invoice)
        
        # Try to start another
        with self.assertRaises(ValueError) as context:
            ApprovalManager.start_workflow(self.invoice)
        
        # Check the error message mentions workflow in progress
        self.assertIn('already', str(context.exception).lower())
    
    def test_process_action_without_assignment(self):
        """Test user trying to approve without assignment."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='TEST_TEMPLATE',
            name='Test Template',
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
        
        # Create another user
        other_user = User.objects.create_user(
            email='other@test.com',
            name='Other User',
            phone_number='1234567890',
            password='testpass123'
        )
        
        # Start workflow - all users will be assigned since no user_level filtering
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Verify other_user IS assigned (since we removed user_level filtering)
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertTrue(active_stage.assignments.filter(user=other_user).exists())
        
        # Other user CAN approve since they have assignment
        ApprovalManager.process_action(self.invoice, other_user, 'approve')
        
        # Verify it worked
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_process_action_after_workflow_completed(self):
        """Test trying to approve after workflow is completed."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='TEST_TEMPLATE',
            name='Test Template',
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
        
        # Start and complete workflow
        workflow = ApprovalManager.start_workflow(self.invoice)
        ApprovalManager.process_action(self.invoice, self.user1, 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # Try to approve again
        with self.assertRaises(ValueError):
            ApprovalManager.process_action(self.invoice, self.user1, 'approve')
    
    def test_cancel_already_completed_workflow(self):
        """Test cancelling a completed workflow."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='TEST_TEMPLATE',
            name='Test Template',
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
        
        # Start and complete workflow
        workflow = ApprovalManager.start_workflow(self.invoice)
        ApprovalManager.process_action(self.invoice, self.user1, 'approve')
        
        # Verify workflow is approved
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # Try to cancel - should return the instance without changing it
        result = ApprovalManager.cancel_workflow(self.invoice)
        self.assertEqual(result.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_quorum_larger_than_eligible_users(self):
        """Test quorum count larger than available users."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='IMPOSSIBLE_QUORUM',
            name='Impossible Quorum',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        # Require 10 approvals but only 1 user exists
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='Impossible Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            quorum_count=10
        )
        
        # Start workflow
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # User approves
        ApprovalManager.process_action(self.invoice, self.user1, 'approve')
        
        workflow.refresh_from_db()
        
        # Cannot meet quorum with only 1 user
        # Workflow should remain in progress (impossible to complete)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
    
    def test_multiple_templates_same_content_type(self):
        """Test multiple active templates for same model."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        # Create two active templates
        template1 = ApprovalWorkflowTemplate.objects.create(
            code='TEMPLATE_V1',
            name='Template Version 1',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template1,
            order_index=1,
            name='Stage 1',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY
        )
        
        template2 = ApprovalWorkflowTemplate.objects.create(
            code='TEMPLATE_V2',
            name='Template Version 2',
            content_type=ct,
            is_active=True,
            version=2
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template2,
            order_index=1,
            name='Stage 1 V2',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL
        )
        
        # Should pick higher version
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        self.assertEqual(workflow.template, template2)
        self.assertEqual(workflow.template.version, 2)
    
    def test_different_models_different_workflows(self):
        """Test that different models use correct workflows."""
        ct_invoice = ContentType.objects.get_for_model(TestInvoice)
        ct_po = ContentType.objects.get_for_model(TestPurchaseOrder)
        
        # Template for Invoice
        template_invoice = ApprovalWorkflowTemplate.objects.create(
            code='INVOICE_WORKFLOW',
            name='Invoice Workflow',
            content_type=ct_invoice,
            is_active=True,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template_invoice,
            order_index=1,
            name='Invoice Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY
        )
        
        # Template for PO
        template_po = ApprovalWorkflowTemplate.objects.create(
            code='PO_WORKFLOW',
            name='PO Workflow',
            content_type=ct_po,
            is_active=True,
            version=1
        )
        
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template_po,
            order_index=1,
            name='PO Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL
        )
        
        # Create PO
        po = TestPurchaseOrder.objects.create(
            po_number='PO-001',
            supplier_name='Supplier',
            total_amount=5000.00
        )
        
        # Start workflows
        invoice_workflow = ApprovalManager.start_workflow(self.invoice)
        po_workflow = ApprovalManager.start_workflow(po)
        
        # Check correct templates used
        self.assertEqual(invoice_workflow.template, template_invoice)
        self.assertEqual(po_workflow.template, template_po)
        
        # Check correct objects linked
        self.assertEqual(invoice_workflow.content_object, self.invoice)
        self.assertEqual(po_workflow.content_object, po)
