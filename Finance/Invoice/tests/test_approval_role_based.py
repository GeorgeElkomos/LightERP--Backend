"""
Test role-based approval workflow for invoices.

Tests the complete invoice approval workflow with 3 stages:
1. Accountant Review (accountant role)
2. Finance Manager Review (manager role)
3. CFO Review (director role)

Ensures that:
- Users can only approve stages matching their role
- Users without proper role cannot approve
- Assignments are only created based on user roles
- Complete workflow progression through all 3 stages
"""

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date
from unittest.mock import patch

from core.job_roles.models import JobRole, UserJobRole
from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
    ApprovalAction,
)
from core.approval.managers import ApprovalManager
from Finance.Invoice.models import Invoice, AP_Invoice
from Finance.BusinessPartner.models import BusinessPartner, Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry

User = get_user_model()


class InvoiceApprovalRoleBasedTest(TestCase):
    """Test role-based approval workflow for invoices."""
    
    def setUp(self):
        """Set up test data with roles, users, and invoice workflow."""
        # Create job roles (they should already exist from the database setup script)
        self.accountant_role, _ = JobRole.objects.get_or_create(
            name='accountant',
            defaults={'code': 'ACCT'}
        )
        self.manager_role, _ = JobRole.objects.get_or_create(
            name='manager',
            defaults={'code': 'MGR'}
        )
        self.director_role, _ = JobRole.objects.get_or_create(
            name='director',
            defaults={'code': 'DIR'}
        )
        
        # Create users with different roles
        self.accountant1 = self._create_user(
            email='accountant1@test.com',
            name='Accountant One',
            phone_number='1111111111',
            role=self.accountant_role
        )
        
        self.accountant2 = self._create_user(
            email='accountant2@test.com',
            name='Accountant Two',
            phone_number='2222222222',
            role=self.accountant_role
        )
        
        self.manager1 = self._create_user(
            email='manager1@test.com',
            name='Manager One',
            phone_number='3333333333',
            role=self.manager_role
        )
        
        self.manager2 = self._create_user(
            email='manager2@test.com',
            name='Manager Two',
            phone_number='4444444444',
            role=self.manager_role
        )
        
        self.director = self._create_user(
            email='director@test.com',
            name='Director CFO',
            phone_number='5555555555',
            role=self.director_role
        )
        
        # Create a user without any relevant role
        self.regular_user = self._create_user(
            email='regular@test.com',
            name='Regular User',
            phone_number='6666666666',
            role=None
        )
        
        # Set up invoice prerequisites
        self.currency, _ = Currency.objects.get_or_create(
            code='USD',
            defaults={
                'name': 'US Dollar',
                'symbol': '$'
            }
        )
        
        self.country, _ = Country.objects.get_or_create(
            code='US',
            defaults={'name': 'United States'}
        )
        
        # Create a supplier
        self.supplier = Supplier.objects.create(
            name='Test Supplier Inc'
        )
        
        # Create a journal entry for GL distributions
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Invoice Journal Entry'
        )
        
        # Ensure the 3-stage workflow template exists and is properly configured
        self._setup_workflow_template()
        
    def _create_user(self, email, name, phone_number, role=None):
        """Helper to create a user with specified role."""
        
        user = User.objects.create_user(
            email=email,
            name=name,
            phone_number=phone_number,
            password='testpass123'
        )
        
        # Create UserJobRole record to properly assign role
        if role:
            UserJobRole.objects.create(
                user=user,
                job_role=role,
                effective_start_date=date.today(),
                effective_end_date=None
            )
        
        return user
    
    def _setup_workflow_template(self):
        """Set up or verify the 3-stage invoice approval workflow."""
        content_type = ContentType.objects.get_for_model(Invoice)
        
        # Get the existing template
        self.template = ApprovalWorkflowTemplate.objects.filter(
            content_type=content_type,
            is_active=True
        ).first()
        
        if not self.template:
            # Create template if it doesn't exist
            self.template = ApprovalWorkflowTemplate.objects.create(
                code='INVOICE_APPROVAL',
                name='Invoice Approval Workflow',
                content_type=content_type,
                description='Three-stage approval workflow for invoices',
                is_active=True,
                version=1
            )
            
            # Stage 1: Accountant Review
            ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=self.template,
                order_index=1,
                name='Accountant Review',
                decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
                required_role=self.accountant_role,
                allow_reject=True,
                allow_delegate=False
            )
            
            # Stage 2: Finance Manager Review
            ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=self.template,
                order_index=2,
                name='Finance Manager Review',
                decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
                required_role=self.manager_role,
                allow_reject=True,
                allow_delegate=False
            )
            
            # Stage 3: CFO Review
            ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=self.template,
                order_index=3,
                name='CFO Review',
                decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
                required_role=self.director_role,
                allow_reject=True,
                allow_delegate=False
            )
        else:
            # Update existing stages to ensure they have the correct roles
            stages = self.template.stages.order_by('order_index')
            if stages.count() >= 3:
                stages[0].required_role = self.accountant_role
                stages[0].save()
                stages[1].required_role = self.manager_role
                stages[1].save()
                stages[2].required_role = self.director_role
                stages[2].save()
    
    def _create_test_invoice(self, invoice_number='TEST-INV-001'):
        """Create a test AP invoice."""
        from decimal import Decimal
        from Finance.Invoice.models import InvoiceItem
        
        invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency,
            country=self.country,
            supplier=self.supplier,
            subtotal=Decimal('1000.00'),
            total=Decimal('1100.00'),
            tax_amount=Decimal('100.00'),
            gl_distributions=self.journal_entry
        )
        
        # Create invoice items that match the subtotal
        InvoiceItem.objects.create(
            invoice=invoice.invoice,
            name='Test Item 1',
            description='Test Item Description',
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00')
        )
        
        return invoice
    
    def _submit_invoice_for_approval(self, invoice):
        """Submit invoice for approval, bypassing GL validation for testing."""
        # Patch the validation to bypass GL balance check for testing
        # In a real scenario, the GL distributions would need to be properly balanced
        with patch.object(invoice.invoice, 'validate_for_submission'):
            return invoice.submit_for_approval()
    
    # =====================================================================
    # Test: Stage 1 - Only Accountants Can Approve
    # =====================================================================
    
    def test_stage1_only_accountants_assigned(self):
        """Test that stage 1 only assigns accountant users."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Get active stage (should be stage 1)
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        self.assertIsNotNone(active_stage)
        self.assertEqual(active_stage.stage_template.order_index, 1)
        self.assertEqual(active_stage.stage_template.name, 'Accountant Review')
        
        # Get assignments
        assignments = active_stage.assignments.all()
        
        # Should have exactly 2 accountants
        self.assertEqual(assignments.count(), 2)
        
        # All assignments should be accountants
        assigned_user_ids = set(assignments.values_list('user_id', flat=True))
        expected_user_ids = {self.accountant1.id, self.accountant2.id}
        self.assertEqual(assigned_user_ids, expected_user_ids)
        
        # Verify role snapshot
        for assignment in assignments:
            self.assertEqual(assignment.role_snapshot, 'accountant')
    
    def test_stage1_non_accountant_cannot_approve(self):
        """Test that non-accountant users cannot approve stage 1."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        # Manager should not have an assignment
        manager_assignment = active_stage.assignments.filter(
            user=self.manager1
        ).first()
        self.assertIsNone(manager_assignment)
        
        # Try to approve as manager without assignment - should fail
        with self.assertRaises(ValueError) as context:
            ApprovalManager.process_action(
                invoice.invoice,
                user=self.manager1,
                action=ApprovalAction.ACTION_APPROVE,
                comment='Manager trying to approve stage 1'
            )
        
        self.assertIn('no assignment', str(context.exception).lower())
        
        # Invoice should still be in stage 1
        workflow.refresh_from_db()
        self.assertEqual(workflow.current_stage_template.order_index, 1)
        self.assertEqual(invoice.approval_status, Invoice.PENDING_APPROVAL)
    
    def test_stage1_regular_user_cannot_approve(self):
        """Test that regular user without role cannot approve stage 1."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        # Regular user should not have an assignment
        regular_assignment = active_stage.assignments.filter(
            user=self.regular_user
        ).first()
        self.assertIsNone(regular_assignment)
        
        # Try to approve as regular user - should fail
        with self.assertRaises(ValueError) as context:
            ApprovalManager.process_action(
                invoice.invoice,
                user=self.regular_user,
                action=ApprovalAction.ACTION_APPROVE,
                comment='Regular user trying to approve'
            )
        
        self.assertIn('no assignment', str(context.exception).lower())
    
    def test_stage1_accountant_can_approve(self):
        """Test that accountant can successfully approve stage 1."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        
        # Accountant approves
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE,
            comment='Accountant approval - all looks good'
        )
        
        # Workflow should progress to stage 2
        workflow.refresh_from_db()
        self.assertEqual(workflow.current_stage_template.order_index, 2)
        self.assertEqual(workflow.current_stage_template.name, 'Finance Manager Review')
        
        # Invoice should still be pending approval
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Invoice.PENDING_APPROVAL)
        
        # Stage 1 should be completed
        stage1 = workflow.stage_instances.get(stage_template__order_index=1)
        self.assertEqual(stage1.status, ApprovalWorkflowStageInstance.STATUS_COMPLETED)
        
        # Stage 2 should be active
        stage2 = workflow.stage_instances.get(stage_template__order_index=2)
        self.assertEqual(stage2.status, ApprovalWorkflowStageInstance.STATUS_ACTIVE)
    
    # =====================================================================
    # Test: Stage 2 - Only Managers Can Approve
    # =====================================================================
    
    def test_stage2_only_managers_assigned(self):
        """Test that stage 2 only assigns manager users."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stage 1
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE,
            comment='Stage 1 approved'
        )
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        
        # Get active stage (should be stage 2)
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        self.assertIsNotNone(active_stage)
        self.assertEqual(active_stage.stage_template.order_index, 2)
        self.assertEqual(active_stage.stage_template.name, 'Finance Manager Review')
        
        # Get assignments
        assignments = active_stage.assignments.all()
        
        # Should have exactly 2 managers
        self.assertEqual(assignments.count(), 2)
        
        # All assignments should be managers
        assigned_user_ids = set(assignments.values_list('user_id', flat=True))
        expected_user_ids = {self.manager1.id, self.manager2.id}
        self.assertEqual(assigned_user_ids, expected_user_ids)
        
        # Verify role snapshot
        for assignment in assignments:
            self.assertEqual(assignment.role_snapshot, 'manager')
    
    def test_stage2_accountant_cannot_approve(self):
        """Test that accountant cannot approve stage 2."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stage 1
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE,
            comment='Stage 1 approved'
        )
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        # Accountant should not have an assignment for stage 2
        accountant_assignment = active_stage.assignments.filter(
            user=self.accountant1
        ).first()
        self.assertIsNone(accountant_assignment)
        
        # Try to approve as accountant - should fail
        with self.assertRaises(ValueError) as context:
            ApprovalManager.process_action(
                invoice.invoice,
                user=self.accountant1,
                action=ApprovalAction.ACTION_APPROVE,
                comment='Accountant trying to approve stage 2'
            )
        
        self.assertIn('no assignment', str(context.exception).lower())
        
        # Workflow should still be on stage 2
        workflow.refresh_from_db()
        self.assertEqual(workflow.current_stage_template.order_index, 2)
    
    def test_stage2_manager_can_approve(self):
        """Test that manager can successfully approve stage 2."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stage 1
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE,
            comment='Stage 1 approved'
        )
        
        # Approve stage 2
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.manager1,
            action=ApprovalAction.ACTION_APPROVE,
            comment='Manager approval - budget approved'
        )
        
        # Workflow should progress to stage 3
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        workflow.refresh_from_db()
        self.assertEqual(workflow.current_stage_template.order_index, 3)
        self.assertEqual(workflow.current_stage_template.name, 'CFO Review')
        
        # Invoice should still be pending approval
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Invoice.PENDING_APPROVAL)
        
        # Stage 2 should be completed
        stage2 = workflow.stage_instances.get(stage_template__order_index=2)
        self.assertEqual(stage2.status, ApprovalWorkflowStageInstance.STATUS_COMPLETED)
        
        # Stage 3 should be active
        stage3 = workflow.stage_instances.get(stage_template__order_index=3)
        self.assertEqual(stage3.status, ApprovalWorkflowStageInstance.STATUS_ACTIVE)
    
    # =====================================================================
    # Test: Stage 3 - Only Director Can Approve
    # =====================================================================
    
    def test_stage3_only_director_assigned(self):
        """Test that stage 3 only assigns director users."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stage 1
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE,
            comment='Stage 1 approved'
        )
        
        # Approve stage 2
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.manager1,
            action=ApprovalAction.ACTION_APPROVE,
            comment='Stage 2 approved'
        )
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        
        # Get active stage (should be stage 3)
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        self.assertIsNotNone(active_stage)
        self.assertEqual(active_stage.stage_template.order_index, 3)
        self.assertEqual(active_stage.stage_template.name, 'CFO Review')
        
        # Get assignments
        assignments = active_stage.assignments.all()
        
        # Should have exactly 1 director
        self.assertEqual(assignments.count(), 1)
        
        # Assignment should be the director
        self.assertEqual(assignments.first().user, self.director)
        self.assertEqual(assignments.first().role_snapshot, 'director')
    
    def test_stage3_manager_cannot_approve(self):
        """Test that manager cannot approve stage 3."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stages 1 and 2
        ApprovalManager.process_action(
            invoice.invoice, user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE, comment='Stage 1'
        )
        ApprovalManager.process_action(
            invoice.invoice, user=self.manager1,
            action=ApprovalAction.ACTION_APPROVE, comment='Stage 2'
        )
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice)
        active_stage = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_ACTIVE
        ).first()
        
        # Manager should not have an assignment for stage 3
        manager_assignment = active_stage.assignments.filter(
            user=self.manager1
        ).first()
        self.assertIsNone(manager_assignment)
        
        # Try to approve as manager - should fail
        with self.assertRaises(ValueError) as context:
            ApprovalManager.process_action(
                invoice.invoice,
                user=self.manager1,
                action=ApprovalAction.ACTION_APPROVE,
                comment='Manager trying to approve stage 3'
            )
        
        self.assertIn('no assignment', str(context.exception).lower())
    
    def test_stage3_director_can_approve_complete_workflow(self):
        """Test that director can approve stage 3 and complete the workflow."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stage 1
        ApprovalManager.process_action(
            invoice.invoice, user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE, comment='Accountant approved'
        )
        
        # Approve stage 2
        ApprovalManager.process_action(
            invoice.invoice, user=self.manager1,
            action=ApprovalAction.ACTION_APPROVE, comment='Manager approved'
        )
        
        # Approve stage 3
        ApprovalManager.process_action(
            invoice.invoice, user=self.director,
            action=ApprovalAction.ACTION_APPROVE, comment='CFO final approval'
        )
        
        # Workflow should be completed
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice, active_only=False)
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        self.assertIsNotNone(workflow.finished_at)
        
        # Invoice should be approved
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Invoice.APPROVED)
        
        # All 3 stages should be completed
        stage1 = workflow.stage_instances.get(stage_template__order_index=1)
        stage2 = workflow.stage_instances.get(stage_template__order_index=2)
        stage3 = workflow.stage_instances.get(stage_template__order_index=3)
        
        self.assertEqual(stage1.status, ApprovalWorkflowStageInstance.STATUS_COMPLETED)
        self.assertEqual(stage2.status, ApprovalWorkflowStageInstance.STATUS_COMPLETED)
        self.assertEqual(stage3.status, ApprovalWorkflowStageInstance.STATUS_COMPLETED)
    
    # =====================================================================
    # Test: Rejection Scenarios
    # =====================================================================
    
    def test_stage1_rejection_by_accountant(self):
        """Test that accountant can reject invoice at stage 1."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Accountant rejects
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.accountant1,
            action=ApprovalAction.ACTION_REJECT,
            comment='Incorrect vendor information'
        )
        
        # Workflow should be rejected
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice, active_only=False)
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Invoice should be rejected
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Invoice.REJECTED)
    
    def test_stage2_rejection_by_manager(self):
        """Test that manager can reject invoice at stage 2."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stage 1
        ApprovalManager.process_action(
            invoice.invoice, user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE, comment='Stage 1'
        )
        
        # Manager rejects stage 2
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.manager1,
            action=ApprovalAction.ACTION_REJECT,
            comment='Budget exceeded'
        )
        
        # Workflow should be rejected
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice, active_only=False)
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Invoice should be rejected
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Invoice.REJECTED)
    
    def test_stage3_only_director_assigned(self):
        """Test that director can reject invoice at stage 3."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Approve stages 1 and 2
        ApprovalManager.process_action(
            invoice.invoice, user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE, comment='Stage 1'
        )
        ApprovalManager.process_action(
            invoice.invoice, user=self.manager1,
            action=ApprovalAction.ACTION_APPROVE, comment='Stage 2'
        )
        
        # Director rejects stage 3
        ApprovalManager.process_action(
            invoice.invoice,
            user=self.director,
            action=ApprovalAction.ACTION_REJECT,
            comment='Strategic concerns'
        )
        
        # Workflow should be rejected
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice, active_only=False)
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Invoice should be rejected
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Invoice.REJECTED)
    
    def test_non_assigned_user_cannot_reject(self):
        """Test that user without assignment cannot reject."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Regular user tries to reject
        with self.assertRaises(ValueError) as context:
            ApprovalManager.process_action(
                invoice.invoice,
                user=self.regular_user,
                action=ApprovalAction.ACTION_REJECT,
                comment='Trying to reject without assignment'
            )
        
        self.assertIn('no assignment', str(context.exception).lower())
        
        # Invoice should still be pending
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Invoice.PENDING_APPROVAL)
    
    # =====================================================================
    # Test: Complete Workflow Audit Trail
    # =====================================================================
    
    def test_complete_workflow_audit_trail(self):
        """Test that complete workflow has proper audit trail."""
        invoice = self._create_test_invoice()
        self._submit_invoice_for_approval(invoice)
        
        # Complete all 3 stages
        ApprovalManager.process_action(
            invoice.invoice, user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE, comment='Accountant approval'
        )
        ApprovalManager.process_action(
            invoice.invoice, user=self.manager2,
            action=ApprovalAction.ACTION_APPROVE, comment='Manager approval'
        )
        ApprovalManager.process_action(
            invoice.invoice, user=self.director,
            action=ApprovalAction.ACTION_APPROVE, comment='Director approval'
        )
        
        workflow = ApprovalManager.get_workflow_instance(invoice.invoice, active_only=False)
        
        # Verify all actions were recorded
        all_actions = ApprovalAction.objects.filter(
            stage_instance__workflow_instance=workflow
        ).order_by('created_at')
        
        # Should have 3 approval actions
        approval_actions = all_actions.filter(action=ApprovalAction.ACTION_APPROVE)
        self.assertEqual(approval_actions.count(), 3)
        
        # Verify each action
        actions_list = list(approval_actions)
        
        # Stage 1 approval
        self.assertEqual(actions_list[0].user, self.accountant1)
        self.assertEqual(actions_list[0].comment, 'Accountant approval')
        self.assertEqual(actions_list[0].stage_instance.stage_template.order_index, 1)
        
        # Stage 2 approval
        self.assertEqual(actions_list[1].user, self.manager2)
        self.assertEqual(actions_list[1].comment, 'Manager approval')
        self.assertEqual(actions_list[1].stage_instance.stage_template.order_index, 2)
        
        # Stage 3 approval
        self.assertEqual(actions_list[2].user, self.director)
        self.assertEqual(actions_list[2].comment, 'Director approval')
        self.assertEqual(actions_list[2].stage_instance.stage_template.order_index, 3)
    
    # =====================================================================
    # Test: Multiple Invoices with Different Paths
    # =====================================================================
    
    def test_multiple_invoices_independent_workflows(self):
        """Test that multiple invoices have independent workflows."""
        # Create two invoices
        invoice1 = self._create_test_invoice('INV-001')
        invoice2 = self._create_test_invoice('INV-002')
        
        # Start both workflows
        self._submit_invoice_for_approval(invoice1)
        self._submit_invoice_for_approval(invoice2)
        
        # Approve invoice1 through stage 1
        ApprovalManager.process_action(
            invoice1.invoice, user=self.accountant1,
            action=ApprovalAction.ACTION_APPROVE, comment='Invoice 1 stage 1'
        )
        
        # Reject invoice2 at stage 1
        ApprovalManager.process_action(
            invoice2.invoice, user=self.accountant2,
            action=ApprovalAction.ACTION_REJECT, comment='Invoice 2 rejected'
        )
        
        # Check invoice1 status - should be at stage 2
        invoice1.refresh_from_db()
        workflow1 = ApprovalManager.get_workflow_instance(invoice1.invoice)
        self.assertEqual(workflow1.current_stage_template.order_index, 2)
        self.assertEqual(invoice1.approval_status, Invoice.PENDING_APPROVAL)
        
        # Check invoice2 status - should be rejected
        invoice2.refresh_from_db()
        workflow2 = ApprovalManager.get_workflow_instance(invoice2.invoice, active_only=False)
        self.assertEqual(workflow2.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        self.assertEqual(invoice2.approval_status, Invoice.REJECTED)
        
        # Complete invoice1
        ApprovalManager.process_action(
            invoice1.invoice, user=self.manager1,
            action=ApprovalAction.ACTION_APPROVE, comment='Invoice 1 stage 2'
        )
        ApprovalManager.process_action(
            invoice1.invoice, user=self.director,
            action=ApprovalAction.ACTION_APPROVE, comment='Invoice 1 stage 3'
        )
        
        # Invoice1 should be approved
        invoice1.refresh_from_db()
        self.assertEqual(invoice1.approval_status, Invoice.APPROVED)
        
        # Invoice2 should still be rejected
        invoice2.refresh_from_db()
        self.assertEqual(invoice2.approval_status, Invoice.REJECTED)
