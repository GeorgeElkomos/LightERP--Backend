"""
Tests for Payment Approval Integration

Verifies that the Payment model correctly integrates with the approval workflow system.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date
from unittest.mock import patch

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import Invoice, AP_Invoice
from Finance.BusinessPartner.models import BusinessPartner, Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry
from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
)
from core.approval.managers import ApprovalManager
from core.user_accounts.models import Role, UserType

User = get_user_model()


class PaymentApprovalIntegrationTest(TestCase):
    """Test Payment model integration with approval workflow system."""
    
    def setUp(self):
        """Set up test data for each test."""
        # Create roles
        self.manager_role, _ = Role.objects.get_or_create(name='manager')
        self.director_role, _ = Role.objects.get_or_create(name='director')
        
        # Create user type
        self.user_type, _ = UserType.objects.get_or_create(
            type_name='user',
            defaults={'description': 'Regular user'}
        )
        
        # Create users
        self.manager = self._create_user(
            email='manager@test.com',
            name='Manager User',
            phone_number='1111111111',
            role=self.manager_role
        )
        
        self.director = self._create_user(
            email='director@test.com',
            name='Director User',
            phone_number='2222222222',
            role=self.director_role
        )
        
        # Create currency and country
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
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            name='Test Supplier Inc'
        )
        
        # Create approval workflow template for Payment
        self._setup_workflow_template()
        
        # Create GL entries and invoice for testing
        self.invoice_gl = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Invoice GL',
            posted=True
        )
        
        self.payment_gl = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Payment GL'
        )
        
        # Create AP invoice for payment allocation
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency,
            country=self.country,
            supplier=self.supplier,
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('0.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.invoice_gl
        )
        
        # Create payment
        self.payment = Payment.objects.create(
            date=date.today(),
            business_partner=self.supplier.business_partner,
            currency=self.currency,
            exchange_rate=Decimal('1.00'),
            gl_entry=self.payment_gl
        )
    
    def _create_user(self, email, name, phone_number, role=None):
        """Helper to create a user with specified role."""
        user = User.objects.create_user(
            email=email,
            name=name,
            phone_number=phone_number,
            password='testpass123'
        )
        user.role = role
        user.save()
        return user
    
    def _setup_workflow_template(self):
        """Set up the 2-stage payment approval workflow."""
        content_type = ContentType.objects.get_for_model(Payment)
        
        # Delete any existing templates to ensure clean state
        ApprovalWorkflowTemplate.objects.filter(
            content_type=content_type
        ).delete()
        
        # Create template
        self.template = ApprovalWorkflowTemplate.objects.create(
            code='PAYMENT_TEST',
            name='Payment Test Workflow',
            description='Test workflow for payments',
            content_type=content_type,
            is_active=True,
            version=1
        )
        
        # Create workflow stages
        self.stage1 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Approval',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.manager_role,
            allow_reject=True,
            allow_delegate=False
        )
        
        self.stage2 = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=2,
            name='Director Approval',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            required_role=self.director_role,
            allow_reject=True,
            allow_delegate=False
        )
    
    def test_payment_has_approvable_mixin(self):
        """Test that Payment model has approval workflow capabilities."""
        # Check for GenericRelation
        self.assertTrue(hasattr(self.payment, 'approval_workflows'))
        
        # Check for mixin methods
        self.assertTrue(hasattr(self.payment, 'get_active_workflow'))
        self.assertTrue(hasattr(self.payment, 'has_pending_approval'))
        self.assertTrue(hasattr(self.payment, 'get_current_approvers'))
    
    def test_payment_implements_approvable_interface(self):
        """Test that Payment implements all required interface methods."""
        required_methods = [
            'on_approval_started',
            'on_stage_approved',
            'on_fully_approved',
            'on_rejected',
            'on_cancelled',
        ]
        
        for method_name in required_methods:
            self.assertTrue(
                hasattr(self.payment, method_name),
                f"Payment missing required method: {method_name}"
            )
            self.assertTrue(
                callable(getattr(self.payment, method_name)),
                f"{method_name} is not callable"
            )
    
    def test_submit_payment_for_approval(self):
        """Test submitting a payment for approval workflow."""
        # Add allocation to make payment valid
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        
        # Submit for approval
        workflow = self.payment.submit_for_approval()
        
        # Verify workflow was created
        self.assertIsNotNone(workflow)
        self.assertIsInstance(workflow, ApprovalWorkflowInstance)
        
        # Verify payment status updated
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.approval_status, Payment.PENDING_APPROVAL)
        self.assertIsNotNone(self.payment.submitted_for_approval_at)
    
    def test_cannot_submit_without_allocations(self):
        """Test that payment without allocations cannot be submitted."""
        with self.assertRaises(ValidationError) as context:
            self.payment.submit_for_approval()
        
        self.assertIn('allocation', str(context.exception).lower())
    
    def test_cannot_submit_already_pending_payment(self):
        """Test that payment already pending cannot be resubmitted."""
        # Add allocation and submit
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        
        # Try to submit again
        with self.assertRaises(ValidationError) as context:
            self.payment.submit_for_approval()
        
        self.assertIn('PENDING_APPROVAL', str(context.exception))
    
    def test_workflow_has_correct_template(self):
        """Test that workflow instance uses correct template."""
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        workflow = self.payment.submit_for_approval()
        
        self.assertEqual(workflow.template, self.template)
        self.assertEqual(workflow.template.code, 'PAYMENT_TEST')
    
    def test_manager_can_approve_first_stage(self):
        """Test that manager can approve the first stage."""
        # Submit payment
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        workflow = self.payment.submit_for_approval()
        
        # Check that manager can approve
        self.assertTrue(self.payment.can_be_approved_by(self.manager))
        
        # Approve as manager
        workflow = self.payment.approve_by_user(
            self.manager,
            comment="Approved by manager"
        )
        
        # Workflow should move to stage 2
        workflow.refresh_from_db()
        self.assertEqual(workflow.current_stage_template, self.stage2)
    
    def test_director_approves_second_stage(self):
        """Test full approval workflow through both stages."""
        # Submit payment
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        
        # Manager approves
        self.payment.approve_by_user(self.manager, comment="Manager approved")
        
        # Director approves
        self.payment.approve_by_user(self.director, comment="Director approved")
        
        # Payment should be fully approved
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.approval_status, Payment.APPROVED)
        self.assertIsNotNone(self.payment.approved_at)
    
    def test_rejection_updates_payment_status(self):
        """Test that rejection updates payment status correctly."""
        # Submit payment
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        
        # Manager rejects
        rejection_comment = "Missing documentation"
        self.payment.reject_by_user(self.manager, comment=rejection_comment)
        
        # Payment should be rejected
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.approval_status, Payment.REJECTED)
        self.assertIsNotNone(self.payment.rejected_at)
        self.assertEqual(self.payment.rejection_reason, rejection_comment)
    
    def test_can_resubmit_after_rejection(self):
        """Test that rejected payment can be resubmitted."""
        # Submit and reject
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        self.payment.reject_by_user(self.manager, comment="Rejected")
        
        # Should be able to submit again
        workflow = self.payment.submit_for_approval()
        
        self.assertIsNotNone(workflow)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.approval_status, Payment.PENDING_APPROVAL)
    
    def test_workflow_cancellation(self):
        """Test cancelling a workflow."""
        # Submit payment
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        
        # Cancel workflow
        reason = "Payment cancelled by requester"
        ApprovalManager.cancel_workflow(self.payment, reason=reason)
        
        # Payment should return to draft
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.approval_status, Payment.DRAFT)
        self.assertEqual(self.payment.rejection_reason, reason)
    
    def test_get_current_approvers(self):
        """Test getting list of current approvers."""
        # Submit payment
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        
        # Get current approvers (should be managers at stage 1)
        approvers = self.payment.get_current_approvers()
        
        self.assertIn(self.manager, approvers)
        self.assertNotIn(self.director, approvers)  # Director is stage 2
    
    def test_approval_history(self):
        """Test that approval actions are logged."""
        # Submit and approve through both stages
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        self.payment.approve_by_user(self.manager, comment="Manager OK")
        self.payment.approve_by_user(self.director, comment="Director OK")
        
        # Get approval history
        history = self.payment.get_approval_history()
        
        # Should have 2 approve actions
        self.assertEqual(history.count(), 2)
        self.assertEqual(history.filter(action='approve').count(), 2)
    
    def test_validate_for_submission(self):
        """Test payment validation before submission."""
        # Without allocations - should fail
        with self.assertRaises(ValidationError):
            self.payment.validate_for_submission()
        
        # With allocations - should pass
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        
        # Should not raise
        try:
            self.payment.validate_for_submission()
        except ValidationError:
            self.fail("validate_for_submission raised ValidationError unexpectedly")
    
    def test_convenience_methods(self):
        """Test convenience methods like can_post_to_gl."""
        # Before approval - cannot post
        self.assertFalse(self.payment.can_post_to_gl())
        
        # After approval - can post
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        self.payment.approve_by_user(self.manager)
        self.payment.approve_by_user(self.director)
        
        self.assertTrue(self.payment.can_post_to_gl())
    
    def test_unauthorized_user_cannot_approve(self):
        """Test that unauthorized user cannot approve."""
        # Create user without approval role
        unauthorized_user = self._create_user(
            email='unauth@test.com',
            name='Unauthorized User',
            phone_number='3333333333',
            role=None
        )
        
        # Submit payment
        self.payment.allocate_to_invoice(self.ap_invoice.invoice, Decimal('500.00'))
        self.payment.submit_for_approval()
        
        # Check that unauthorized user cannot approve
        self.assertFalse(self.payment.can_be_approved_by(unauthorized_user))


# Run tests with: python manage.py test Finance.payments.tests.test_approval_integration -v 2
