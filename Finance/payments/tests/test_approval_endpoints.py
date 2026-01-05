"""
Comprehensive tests for Payment Approval Workflow API Endpoints.

Tests all new approval endpoints for Payments:
- POST   /payments/{id}/submit-for-approval/     - Submit payment for approval
- GET    /payments/pending-approvals/             - List pending approvals
- POST   /payments/{id}/approval-action/          - Approve/Reject/Delegate/Comment
- POST   /payments/{id}/post-to-gl/               - Post approved payment to GL

Ensures:
- Complete workflow progression through all stages
- Role-based access control
- Assignment-based approval
- Error handling for invalid actions
- Delegation functionality
- Comment functionality
- Status synchronization
- GL posting after approval
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status as http_status
from decimal import Decimal
from datetime import date

from core.job_roles.models import JobRole
from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
    ApprovalAction,
)
from core.approval.managers import ApprovalManager
from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import Invoice, AP_Invoice
from Finance.BusinessPartner.models import Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry, JournalLine, XX_SegmentType, XX_Segment, XX_Segment_combination
from Finance.period.models import Period

User = get_user_model()


class PaymentApprovalEndpointTest(TestCase):
    """Test Payment approval endpoints."""
    
    def setUp(self):
        """Set up test data with roles, users, and workflow template."""
        self.client = APIClient()
        
        # Create job roles
        self.accountant_role, _ = JobRole.objects.get_or_create(name='accountant')
        self.manager_role, _ = JobRole.objects.get_or_create(name='manager')
        self.director_role, _ = JobRole.objects.get_or_create(name='director')
        
        # Create users with different roles
        self.accountant = self._create_user(
            email='accountant@test.com',
            name='John Accountant',
            phone_number='1111111111',
            role=self.accountant_role
        )
        
        self.manager = self._create_user(
            email='manager@test.com',
            name='Jane Manager',
            phone_number='2222222222',
            role=self.manager_role
        )
        
        self.director = self._create_user(
            email='director@test.com',
            name='Bob Director',
            phone_number='3333333333',
            role=self.director_role
        )
        
        # Create a user without proper role
        self.regular_user = self._create_user(
            email='regular@test.com',
            name='Regular User',
            phone_number='4444444444',
            role=None
        )
        
        # Set up payment prerequisites
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True,
            exchange_rate_to_base_currency=Decimal('1.00')
        )
        
        # Create January 2026 period with AR, AP, and GL open
        self.period = Period.objects.create(
            name='January 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            fiscal_year=2026,
            period_number=1
        )
        self.period.ar_period.state = 'open'
        self.period.ar_period.save()
        self.period.ap_period.state = 'open'
        self.period.ap_period.save()
        self.period.gl_period.state = 'open'
        self.period.gl_period.save()
        
        self.country = Country.objects.create(
            code='US',
            name='United States'
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(name='Test Supplier Inc')
        
        # Set up workflow template
        self._setup_workflow_template()
    
    def _create_user(self, email, name, phone_number, role=None):
        """Helper to create a user with specified role."""
        from core.user_accounts.models import UserType
        user_type, _ = UserType.objects.get_or_create(
            type_name='user',
            defaults={'description': 'Regular user'}
        )
        
        user = User.objects.create_user(
            email=email,
            name=name,
            phone_number=phone_number,
            password='testpass123'
        )
        user.job_role = role
        user.save()
        return user
    
    def _setup_workflow_template(self):
        """Set up the 3-stage payment approval workflow."""
        content_type = ContentType.objects.get_for_model(Payment)
        
        # Delete existing templates to ensure clean state
        ApprovalWorkflowTemplate.objects.filter(content_type=content_type).delete()
        
        # Create template
        self.template = ApprovalWorkflowTemplate.objects.create(
            code='PAYMENT_APPROVAL',
            name='Payment Approval Workflow',
            content_type=content_type,
            description='Three-stage approval workflow for payments',
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
            allow_delegate=True
        )
        
        # Stage 2: Finance Manager Review
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=2,
            name='Finance Manager Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.manager_role,
            allow_reject=True,
            allow_delegate=True
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
    
    def _create_balanced_journal_entry(self, total_amount, memo='Test Journal Entry'):
        """Create a balanced journal entry with the specified total."""
        
        # Create or get segment types
        segment_type_1, _ = XX_SegmentType.objects.get_or_create(
            segment_name='Company',
            defaults={'description': 'Company code'}
        )
        segment_type_2, _ = XX_SegmentType.objects.get_or_create(
            segment_name='Account',
            defaults={'description': 'Account number'}
        )
        
        # Create or get segments
        segment_100, _ = XX_Segment.objects.get_or_create(
            segment_type=segment_type_1,
            code='100',
            defaults={'alias': 'Main Company', 'node_type': 'detail'}
        )
        segment_6100, _ = XX_Segment.objects.get_or_create(
            segment_type=segment_type_2,
            code='6100',
            defaults={'alias': 'Expense Account', 'node_type': 'detail'}
        )
        segment_2100, _ = XX_Segment.objects.get_or_create(
            segment_type=segment_type_2,
            code='2100',
            defaults={'alias': 'Payable Account', 'node_type': 'detail'}
        )
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo=memo
        )
        
        # Create debit segment combination (Company 100 + Expense 6100)
        debit_combo_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, segment_100.code),
            (segment_type_2.id, segment_6100.code)
        ], description='Expense combination')
        
        # Create credit segment combination (Company 100 + Payable 2100)
        credit_combo_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, segment_100.code),
            (segment_type_2.id, segment_2100.code)
        ], description='Payable combination')
        
        # Create debit line (expense)
        JournalLine.objects.create(
            entry=journal_entry,
            amount=total_amount,
            type='DEBIT',
            segment_combination_id=debit_combo_id
        )
        
        # Create credit line (payable)
        JournalLine.objects.create(
            entry=journal_entry,
            amount=total_amount,
            type='CREDIT',
            segment_combination_id=credit_combo_id
        )
        
        return journal_entry
    
    def _create_test_invoice(self, total_amount=Decimal('1000.00')):
        """Create a test AP invoice for payment allocation."""
        # Create balanced journal entry
        journal_entry = self._create_balanced_journal_entry(total_amount, 'Invoice GL')
        journal_entry.posted = True
        journal_entry.save()
        
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=total_amount,
            tax_amount=Decimal('0.00'),
            total=total_amount,
            gl_distributions=journal_entry
        )
        return ap_invoice
    
    def _create_test_payment(self, amount=Decimal('500.00'), with_allocation=True):
        """Create a test payment with optional invoice allocation."""
        # Create payment GL entry
        payment_gl = self._create_balanced_journal_entry(amount, 'Payment GL')
        
        payment = Payment.objects.create(
            date=date.today(),
            business_partner=self.supplier.business_partner,
            currency=self.currency,
            exchange_rate=Decimal('1.00'),
            gl_entry=payment_gl
        )
        
        if with_allocation:
            # Create invoice and allocate payment
            invoice = self._create_test_invoice(Decimal('1000.00'))
            payment.allocate_to_invoice(invoice.invoice, amount)
        
        return payment
    
    # ========================================================================
    # Submit for Approval Tests
    # ========================================================================
    
    def test_submit_payment_for_approval_success(self):
        """Test successfully submitting payment for approval."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        url = reverse('finance:payments:payment-submit-for-approval', kwargs={'pk': payment.id})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('workflow_id', response.data)
        self.assertEqual(response.data['approval_status'], 'PENDING_APPROVAL')
        self.assertIn('message', response.data)
        
        # Verify workflow was created
        workflow = ApprovalManager.get_workflow_instance(payment)
        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Verify payment status updated
        payment.refresh_from_db()
        self.assertEqual(payment.approval_status, Payment.PENDING_APPROVAL)
        self.assertIsNotNone(payment.submitted_for_approval_at)
    
    def test_submit_payment_without_allocations_fails(self):
        """Test submitting payment without allocations fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=False)
        url = reverse('finance:payments:payment-submit-for-approval', kwargs={'pk': payment.id})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('allocation', response.data['error'].lower())
    
    def test_submit_payment_already_in_workflow_fails(self):
        """Test submitting payment that already has active workflow fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        url = reverse('finance:payments:payment-submit-for-approval', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_submit_payment_already_approved_fails(self):
        """Test submitting already approved payment fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.approval_status = Payment.APPROVED
        payment.save()
        
        url = reverse('finance:payments:payment-submit-for-approval', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_submit_rejected_payment_success(self):
        """Test resubmitting rejected payment succeeds."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        payment.reject_by_user(self.accountant, comment='Rejected')
        
        # Should be able to resubmit
        url = reverse('finance:payments:payment-submit-for-approval', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['approval_status'], 'PENDING_APPROVAL')
    
    def test_submit_nonexistent_payment_fails(self):
        """Test submitting non-existent payment returns 404."""
        url = reverse('finance:payments:payment-submit-for-approval', kwargs={'pk': 99999})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
    
    # ========================================================================
    # Pending Approvals Tests
    # ========================================================================
    
    def test_get_pending_approvals_for_accountant(self):
        """Test getting pending payments for accountant at stage 1."""
        # Create and submit multiple payments
        payment1 = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment2 = self._create_test_payment(Decimal('750.00'), with_allocation=True)
        
        payment1.submit_for_approval()
        payment2.submit_for_approval()
        
        # Authenticate as accountant
        self.client.force_authenticate(user=self.accountant)
        
        url = reverse('finance:payments:payment-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = response.data['data']['results']
        self.assertEqual(len(results), 2)
        
        # Verify response structure
        for item in results:
            self.assertIn('payment_id', item)
            self.assertIn('business_partner_name', item)
            self.assertIn('amount', item)
            self.assertIn('currency', item)
            self.assertIn('current_stage', item)
            self.assertEqual(item['current_stage'], 'Accountant Review')
            self.assertTrue(item['can_approve'])
            self.assertEqual(item['approval_status'], 'PENDING_APPROVAL')
    
    def test_get_pending_approvals_for_manager_empty(self):
        """Test getting pending approvals for manager when payment is at stage 1."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Authenticate as manager
        self.client.force_authenticate(user=self.manager)
        
        url = reverse('finance:payments:payment-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = response.data['data']['results']
        self.assertEqual(len(results), 0)  # No payments at manager stage yet
    
    def test_get_pending_approvals_for_manager_after_stage1(self):
        """Test getting pending approvals for manager after stage 1 approval."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Accountant approves stage 1
        ApprovalManager.process_action(
            payment,
            user=self.accountant,
            action='approve',
            comment='Stage 1 approved'
        )
        
        # Now manager should see it
        self.client.force_authenticate(user=self.manager)
        url = reverse('finance:payments:payment-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = response.data['data']['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['current_stage'], 'Finance Manager Review')
        self.assertTrue(results[0]['can_approve'])
    
    def test_get_pending_approvals_no_auth_uses_first_user(self):
        """Test pending approvals without authentication uses first user."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Don't authenticate - should use first user (accountant)
        url = reverse('finance:payments:payment-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        # Should work with first user
    
    def test_get_pending_approvals_excludes_approved_payments(self):
        """Test pending approvals excludes fully approved payments."""
        payment1 = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment2 = self._create_test_payment(Decimal('750.00'), with_allocation=True)
        
        payment1.submit_for_approval()
        payment2.submit_for_approval()
        
        # Fully approve payment1
        ApprovalManager.process_action(payment1, self.accountant, 'approve')
        ApprovalManager.process_action(payment1, self.manager, 'approve')
        ApprovalManager.process_action(payment1, self.director, 'approve')
        
        # Accountant should only see payment2
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = response.data['data']['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['payment_id'], payment2.id)
    
    # ========================================================================
    # Approval Action Tests
    # ========================================================================
    
    def test_approval_action_approve_success(self):
        """Test accountant approving payment."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'approve',
            'comment': 'Looks good'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('workflow_id', response.data)
        self.assertEqual(response.data['message'], 'Action approve completed successfully')
        
        # Verify workflow moved to next stage
        workflow = ApprovalManager.get_workflow_instance(payment)
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.stage_template.name, 'Finance Manager Review')
    
    def test_approval_action_reject_success(self):
        """Test accountant rejecting payment."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'reject',
            'comment': 'Incorrect vendor'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify workflow is rejected
        workflow = ApprovalManager.get_workflow_instance(payment, active_only=False)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Verify payment status
        payment.refresh_from_db()
        self.assertEqual(payment.approval_status, Payment.REJECTED)
        self.assertIsNotNone(payment.rejected_at)
        self.assertEqual(payment.rejection_reason, 'Incorrect vendor')
    
    def test_approval_action_without_assignment_fails(self):
        """Test user without assignment cannot approve."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Try to approve as manager (wrong stage)
        self.client.force_authenticate(user=self.manager)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'approve',
            'comment': 'Trying to approve'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_approval_action_delegate_success(self):
        """Test delegating payment approval."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Create another accountant to delegate to
        accountant2 = self._create_user(
            email='accountant2@test.com',
            name='Jane Accountant',
            phone_number='5555555555',
            role=self.accountant_role
        )
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'delegate',
            'comment': 'Delegating to Jane',
            'target_user_id': accountant2.id
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify delegation was created
        workflow = ApprovalManager.get_workflow_instance(payment)
        active_stage = workflow.stage_instances.filter(status='active').first()
        
        # Check that accountant2 now has an assignment
        assignment = active_stage.assignments.filter(user=accountant2).first()
        self.assertIsNotNone(assignment)
    
    def test_approval_action_delegate_without_target_fails(self):
        """Test delegation without target_user_id fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'delegate',
            'comment': 'Delegating'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('target_user_id', response.data['error'].lower())
    
    def test_approval_action_delegate_nonexistent_user_fails(self):
        """Test delegating to non-existent user fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'delegate',
            'comment': 'Delegating',
            'target_user_id': 99999
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
    
    def test_approval_action_comment_success(self):
        """Test adding comment to payment."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'comment',
            'comment': 'Need to verify vendor account number'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify comment was logged
        workflow = ApprovalManager.get_workflow_instance(payment)
        active_stage = workflow.stage_instances.filter(status='active').first()
        comment_action = active_stage.actions.filter(
            action=ApprovalAction.ACTION_COMMENT,
            user=self.accountant
        ).first()
        self.assertIsNotNone(comment_action)
        self.assertEqual(comment_action.comment, 'Need to verify vendor account number')
    
    def test_approval_action_invalid_action_fails(self):
        """Test invalid action parameter fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'invalid_action',
            'comment': 'Test'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('invalid action', response.data['error'].lower())
    
    def test_approval_action_already_approved_fails(self):
        """Test approving already approved payment fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.approval_status = Payment.APPROVED
        payment.save()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'approve',
            'comment': 'Approving'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('already approved', response.data['error'].lower())
    
    def test_approval_action_already_rejected_fails(self):
        """Test rejecting already rejected payment fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.approval_status = Payment.REJECTED
        payment.save()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        response = self.client.post(url, {
            'action': 'reject',
            'comment': 'Rejecting'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('already rejected', response.data['error'].lower())
    
    def test_approval_action_default_action_is_approve(self):
        """Test that default action is 'approve' when not specified."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        # Don't specify action - should default to approve
        response = self.client.post(url, {
            'comment': 'OK'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('approve', response.data['message'].lower())
    
    def test_approval_action_nonexistent_payment_fails(self):
        """Test approval action on non-existent payment returns 404."""
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': 99999})
        
        response = self.client.post(url, {
            'action': 'approve',
            'comment': 'Test'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
    
    # ========================================================================
    # Complete Workflow Tests
    # ========================================================================
    
    def test_complete_workflow_all_stages(self):
        """Test completing full payment approval workflow through all 3 stages."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        # Stage 1: Accountant approves
        self.client.force_authenticate(user=self.accountant)
        response = self.client.post(url, {'action': 'approve', 'comment': 'Stage 1 OK'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify now at stage 2
        workflow = ApprovalManager.get_workflow_instance(payment)
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.stage_template.name, 'Finance Manager Review')
        
        # Stage 2: Manager approves
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(url, {'action': 'approve', 'comment': 'Stage 2 OK'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify now at stage 3
        workflow = ApprovalManager.get_workflow_instance(payment)
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.stage_template.name, 'CFO Review')
        
        # Stage 3: Director approves
        self.client.force_authenticate(user=self.director)
        response = self.client.post(url, {'action': 'approve', 'comment': 'Final approval'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify workflow is completed
        workflow = ApprovalManager.get_workflow_instance(payment, active_only=False)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # Verify payment status
        payment.refresh_from_db()
        self.assertEqual(payment.approval_status, Payment.APPROVED)
        self.assertIsNotNone(payment.approved_at)
    
    def test_rejection_at_stage_2_stops_workflow(self):
        """Test rejection at stage 2 stops the workflow."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        url = reverse('finance:payments:payment-approval-action', kwargs={'pk': payment.id})
        
        # Stage 1: Accountant approves
        self.client.force_authenticate(user=self.accountant)
        self.client.post(url, {'action': 'approve', 'comment': 'Stage 1 OK'})
        
        # Stage 2: Manager rejects
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(url, {'action': 'reject', 'comment': 'Budget exceeded'})
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify workflow is rejected
        workflow = ApprovalManager.get_workflow_instance(payment, active_only=False)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Verify payment status
        payment.refresh_from_db()
        self.assertEqual(payment.approval_status, Payment.REJECTED)
        self.assertEqual(payment.rejection_reason, 'Budget exceeded')
    
    # ========================================================================
    # Post to GL Tests
    # ========================================================================
    
    def test_post_to_gl_success(self):
        """Test posting approved payment to GL via on_fully_approved callback."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Verify GL not yet posted
        self.assertFalse(payment.gl_entry.posted)
        
        # Fully approve payment (this triggers automatic GL posting)
        ApprovalManager.process_action(payment, self.accountant, 'approve')
        ApprovalManager.process_action(payment, self.manager, 'approve')
        ApprovalManager.process_action(payment, self.director, 'approve')
        
        payment.refresh_from_db()
        self.assertEqual(payment.approval_status, Payment.APPROVED)
        
        # Verify GL entry was automatically posted on approval
        self.assertTrue(payment.gl_entry.posted)
    
    def test_post_to_gl_without_approval_fails(self):
        """Test posting unapproved payment to GL fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        
        url = reverse('finance:payments:payment-post-to-gl', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('must be approved', response.data['error'].lower())
    
    def test_post_to_gl_no_journal_entry_fails(self):
        """Test posting payment without journal entry fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.gl_entry = None
        payment.save()
        
        url = reverse('finance:payments:payment-post-to-gl', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('no journal entry', response.data['error'].lower())
    
    def test_post_to_gl_already_posted(self):
        """Test posting already posted journal entry."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Fully approve payment (this automatically posts GL)
        ApprovalManager.process_action(payment, self.accountant, 'approve')
        ApprovalManager.process_action(payment, self.manager, 'approve')
        ApprovalManager.process_action(payment, self.director, 'approve')
        
        payment.refresh_from_db()
        self.assertTrue(payment.gl_entry.posted)
        
        # Try to post again via endpoint
        url = reverse('finance:payments:payment-post-to-gl', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('already posted', response.data['message'].lower())
    
    def test_post_to_gl_pending_approval_fails(self):
        """Test posting payment still pending approval fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        
        # Only stage 1 approved, still pending
        ApprovalManager.process_action(payment, self.accountant, 'approve')
        
        url = reverse('finance:payments:payment-post-to-gl', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('must be approved', response.data['error'].lower())
    
    def test_post_to_gl_rejected_payment_fails(self):
        """Test posting rejected payment fails."""
        payment = self._create_test_payment(Decimal('500.00'), with_allocation=True)
        payment.submit_for_approval()
        payment.reject_by_user(self.accountant, comment='Rejected')
        
        url = reverse('finance:payments:payment-post-to-gl', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('must be approved', response.data['error'].lower())
    
    def test_post_to_gl_nonexistent_payment_fails(self):
        """Test posting non-existent payment returns 404."""
        url = reverse('finance:payments:payment-post-to-gl', kwargs={'pk': 99999})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)


# Run tests with: python manage.py test Finance.payments.tests.test_approval_endpoints -v 2
