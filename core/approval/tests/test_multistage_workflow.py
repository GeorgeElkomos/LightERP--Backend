"""Test multi-stage approval workflows.

Tests scenarios involving workflows with multiple sequential stages,
including stage progression, rejection at different stages, and hooks.
"""

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAction
)
from core.approval.managers import ApprovalManager
from core.approval.models import TestInvoice

User = get_user_model()


class MultiStageWorkflowTest(TestCase):
    """Test multi-stage workflows."""
    
    def setUp(self):
        """Set up test data."""
        # Create users for different stages
        self.supervisor1 = User.objects.create_user(
            email='supervisor1@test.com',
            name='Supervisor One',
            phone_number='1234567890',
            password='testpass123'
        )
        self.supervisor2 = User.objects.create_user(
            email='supervisor2@test.com',
            name='Supervisor Two',
            phone_number='1234567890',
            password='testpass123'
        )
        self.manager1 = User.objects.create_user(
            email='manager1@test.com',
            name='Manager One',
            phone_number='1234567890',
            password='testpass123'
        )
        self.manager2 = User.objects.create_user(
            email='manager2@test.com',
            name='Manager Two',
            phone_number='1234567890',
            password='testpass123'
        )
        self.director = User.objects.create_user(
            email='director@test.com',
            name='Director',
            phone_number='1234567890',
            password='testpass123'
        )
        self.cfo = User.objects.create_user(
            email='cfo@test.com',
            name='CFO',
            phone_number='1234567890',
            password='testpass123'
        )
        
        # Create invoice
        self.invoice = TestInvoice.objects.create(
            invoice_number='INV-MULTI-001',
            vendor_name='Test Vendor',
            total_amount=50000.00,
            description='Test multi-stage approval'
        )
    
    def create_four_stage_workflow(self):
        """Create a 4-stage workflow for testing."""
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        template = ApprovalWorkflowTemplate.objects.create(
            code='MULTI_STAGE_TEST',
            name='Multi-Stage Test Workflow',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        # Stage 1: Supervisor approval (ANY policy)
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='Supervisor Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            allow_reject=True
        )
        
        # Stage 2: Manager approval (ALL policy)
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=2,
            name='Manager Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            allow_reject=True
        )
        
        # Stage 3: Director approval (ANY policy)
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=3,
            name='Director Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            allow_reject=True
        )
        
        # Stage 4: CFO approval (ANY policy)
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=4,
            name='CFO Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            allow_reject=True
        )
        
        return template
    
    def test_stage_progression_tracking(self):
        """Test that stage progression is tracked correctly."""
        self.create_four_stage_workflow()
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Initially, only stage 1 should exist and be active
        # Other stages created as workflow progresses
        stage_instances = workflow.stage_instances.all().order_by('stage_template__order_index')
        self.assertEqual(stage_instances.count(), 1)
        
        self.assertEqual(stage_instances[0].status, ApprovalWorkflowStageInstance.STATUS_ACTIVE)
        self.assertEqual(stage_instances[0].stage_template.order_index, 1)
    
    def test_four_stage_complete_workflow(self):
        """Test complete 4-stage workflow from start to finish."""
        self.create_four_stage_workflow()
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        stage_approved_count = 0
        
        # Override on_stage_approved to track calls
        original_method = self.invoice.on_stage_approved
        def track_stage_approved(stage_instance):
            nonlocal stage_approved_count
            stage_approved_count += 1
            original_method(stage_instance)
        
        self.invoice.on_stage_approved = track_stage_approved
        
        # Stage 1: Supervisor approval (ANY policy - any supervisor can approve)
        ApprovalManager.process_action(self.invoice, self.supervisor1, 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        self.assertEqual(stage_approved_count, 1)
        
        # Stage 2: Manager approval (ALL policy - all users must approve)
        all_users = [self.supervisor1, self.supervisor2, self.manager1, self.manager2, self.director, self.cfo]
        for user in all_users:
            ApprovalManager.process_action(self.invoice, user, 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        self.assertEqual(stage_approved_count, 2)
        
        # Stage 3: Director approval (ANY policy - only one user needed)
        ApprovalManager.process_action(self.invoice, self.director, 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        self.assertEqual(stage_approved_count, 3)
        
        # Stage 4: CFO approval (ANY policy - only one user needed)
        ApprovalManager.process_action(self.invoice, self.cfo, 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        self.assertEqual(stage_approved_count, 4)
    
    def test_rejection_at_stage_2(self):
        """Test rejection in middle of multi-stage workflow."""
        self.create_four_stage_workflow()
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Stage 1: Approve
        ApprovalManager.process_action(self.invoice, self.supervisor1, 'approve')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Stage 2: Reject
        ApprovalManager.process_action(self.invoice, self.manager1, 'reject')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Stages 3 and 4 should not exist (never created since workflow was rejected)
        stage_count = workflow.stage_instances.filter(
            stage_template__order_index__in=[3, 4]
        ).count()
        self.assertEqual(stage_count, 0)
    
    def test_skipping_stage_not_allowed(self):
        """Test that stages must be completed in order."""
        self.create_four_stage_workflow()
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Stage 2 doesn't exist yet (created only when stage 1 completes)
        stage2_exists = workflow.stage_instances.filter(
            stage_template__order_index=2
        ).exists()
        self.assertFalse(stage2_exists)
        
        # Process approval on stage 1
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        # This should have approved stage 1
        workflow.refresh_from_db()
        stage1 = workflow.stage_instances.get(stage_template__order_index=1)
        self.assertEqual(stage1.status, ApprovalWorkflowStageInstance.STATUS_COMPLETED)
        
        # Now stage 2 should be created and active
        stage2 = workflow.stage_instances.get(stage_template__order_index=2)
        self.assertEqual(stage2.status, ApprovalWorkflowStageInstance.STATUS_ACTIVE)
    
    def test_on_stage_approved_called_for_each_stage(self):
        """Test that on_stage_approved is called for each stage."""
        self.create_four_stage_workflow()
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        stages_approved = []
        
        # Override on_stage_approved to track calls
        original_method = self.invoice.on_stage_approved
        def track_stage_approved(stage_instance):
            stages_approved.append(stage_instance.stage_template.order_index)
            original_method(stage_instance)
        
        self.invoice.on_stage_approved = track_stage_approved
        
        # Stage 1: Supervisor approval (ANY)
        ApprovalManager.process_action(self.invoice, self.supervisor1, 'approve')
        self.assertEqual(len(stages_approved), 1)
        self.assertEqual(stages_approved[0], 1)
        
        # Stage 2: Manager approval (ALL - all users must approve)
        all_users = [self.supervisor1, self.supervisor2, self.manager1, self.manager2, self.director, self.cfo]
        for user in all_users:
            ApprovalManager.process_action(self.invoice, user, 'approve')
        
        self.assertEqual(len(stages_approved), 2)
        self.assertEqual(stages_approved[1], 2)
        
        # Stage 3: Director approval (ANY - only one user needed)
        ApprovalManager.process_action(self.invoice, self.director, 'approve')
        
        self.assertEqual(len(stages_approved), 3)
        self.assertEqual(stages_approved[2], 3)
        
        # Stage 4: CFO approval (ANY - only one user needed)
        ApprovalManager.process_action(self.invoice, self.cfo, 'approve')
        
        self.assertEqual(len(stages_approved), 4)
        self.assertEqual(stages_approved[3], 4)
    
    def test_parallel_approval_attempt(self):
        """Test that only active stage can receive approvals."""
        self.create_four_stage_workflow()
        
        workflow = ApprovalManager.start_workflow(self.invoice)
        
        # Only stage 1 exists and is active
        # Stages 2, 3, 4 don't exist yet (created as workflow progresses)
        self.assertEqual(workflow.stage_instances.count(), 1)
        
        # Manager1 can approve stage 1
        ApprovalManager.process_action(self.invoice, self.manager1, 'approve')
        
        # Stage 1 completed (ANY policy), now stage 2 should be created and active
        workflow.refresh_from_db()
        self.assertEqual(workflow.stage_instances.count(), 2)
        
        stage2 = workflow.stage_instances.get(stage_template__order_index=2)
        self.assertEqual(stage2.status, ApprovalWorkflowStageInstance.STATUS_ACTIVE)
        
        # Stages 3 and 4 still don't exist
        stage_3_4_exists = workflow.stage_instances.filter(
            stage_template__order_index__in=[3, 4]
        ).exists()
        self.assertFalse(stage_3_4_exists)
