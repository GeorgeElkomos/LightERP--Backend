"""
Comprehensive tests for Invoice Approval Workflow API Endpoints.

Tests all new approval endpoints for AP, AR, and One-Time Supplier invoices:
- POST   /{type}/{id}/submit-for-approval/     - Submit invoice for approval
- GET    /{type}/pending-approvals/             - List pending approvals
- POST   /{type}/{id}/approval-action/          - Approve/Reject/Delegate/Comment

Ensures:
- Complete workflow progression through all 3 stages
- Role-based access control
- Assignment-based approval
- Error handling for invalid actions
- Delegation functionality
- Comment functionality
- Status synchronization
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status as http_status
from decimal import Decimal
from datetime import date

from core.user_accounts.models import UserType
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
from Finance.Invoice.models import Invoice, AP_Invoice, AR_Invoice, OneTimeSupplier, InvoiceItem
from Finance.BusinessPartner.models import Supplier, Customer
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry, JournalLine, XX_SegmentType, XX_Segment, XX_Segment_combination

User = get_user_model()


class BaseApprovalEndpointTest(TestCase):
    """Base test class with common setup for all approval endpoint tests."""
    
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
        
        # Set up invoice prerequisites
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True,
            exchange_rate_to_base_currency=Decimal('1.00')
        )
        
        self.country = Country.objects.create(
            code='US',
            name='United States'
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(name='Test Supplier Inc')
        
        # Create customer
        self.customer = Customer.objects.create(
            name='Test Customer Corp'
        )
        
        # Create journal entry
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Journal Entry'
        )
        
        # Set up workflow template
        self._setup_workflow_template()
    
    def _create_user(self, email, name, phone_number, role=None):
        """Helper to create a user with specified role."""        
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
        """Set up the 3-stage invoice approval workflow."""
        content_type = ContentType.objects.get_for_model(Invoice)
        
        # Delete existing templates to ensure clean state
        ApprovalWorkflowTemplate.objects.filter(content_type=content_type).delete()
        
        # Create template
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
    
    def _create_balanced_journal_entry(self, total_amount):
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
            memo='Test Journal Entry'
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
    
    def _create_test_ap_invoice(self):
        """Create a test AP invoice."""
        # Calculate total
        total = Decimal('1150.00')
        
        # Create balanced journal entry
        journal_entry = self._create_balanced_journal_entry(total)
        
        ap_invoice = AP_Invoice.objects.create(
            supplier=self.supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('150.00'),
            total=total,
            gl_distributions=journal_entry
        )
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=ap_invoice.invoice,
            name='Test Item',
            description='Test AP Item',
            quantity=Decimal('10'),
            unit_price=Decimal('100.00')
        )
        return ap_invoice
    
    def _create_test_ar_invoice(self):
        """Create a test AR invoice."""
        # Calculate total
        total = Decimal('2300.00')
        
        # Create balanced journal entry
        journal_entry = self._create_balanced_journal_entry(total)
        
        ar_invoice = AR_Invoice.objects.create(
            customer=self.customer,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('2000.00'),
            tax_amount=Decimal('300.00'),
            total=total,
            gl_distributions=journal_entry
        )
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=ar_invoice.invoice,
            name='Test Service',
            description='Test AR Service',
            quantity=Decimal('20'),
            unit_price=Decimal('100.00')
        )
        return ar_invoice
    
    def _create_test_one_time_invoice(self):
        """Create a test one-time supplier invoice."""
        # Calculate total
        total = Decimal('500.00')
        
        # Create balanced journal entry
        journal_entry = self._create_balanced_journal_entry(total)
        
        # Create one-time supplier using the OneTime model
        from Finance.BusinessPartner.models import OneTime
        one_time_supplier = OneTime.objects.create(name='Temp Supplier LLC')
        
        ots_invoice = OneTimeSupplier.objects.create(
            one_time_supplier=one_time_supplier,
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('500.00'),
            tax_amount=Decimal('0.00'),
            total=total,
            gl_distributions=journal_entry
        )
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=ots_invoice.invoice,
            name='One-time Service',
            description='One-time Service Description',
            quantity=Decimal('5'),
            unit_price=Decimal('100.00')
        )
        return ots_invoice


class APInvoiceApprovalEndpointTest(BaseApprovalEndpointTest):
    """Test AP Invoice approval endpoints."""
    
    def test_submit_ap_invoice_for_approval_success(self):
        """Test successfully submitting AP invoice for approval."""
        ap_invoice = self._create_test_ap_invoice()
        url = reverse('finance:invoice:ap-invoice-submit-for-approval', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('workflow_id', response.data)
        self.assertEqual(response.data['approval_status'], 'PENDING_APPROVAL')
        
        # Verify workflow was created
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
    
    def test_submit_ap_invoice_already_in_workflow(self):
        """Test submitting AP invoice that already has active workflow."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        url = reverse('finance:invoice:ap-invoice-submit-for-approval', kwargs={'pk': ap_invoice.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_get_ap_pending_approvals_for_accountant(self):
        """Test getting pending AP approvals for accountant."""
        # Create and submit invoices
        ap1 = self._create_test_ap_invoice()
        ap2 = self._create_test_ap_invoice()
        
        ap1.submit_for_approval()
        ap2.submit_for_approval()
        
        # Authenticate as accountant
        self.client.force_authenticate(user=self.accountant)
        
        url = reverse('finance:invoice:ap-invoice-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 2)
        
        # Verify response structure
        for item in response.data['data']['results']:
            self.assertIn('invoice_id', item)
            self.assertIn('supplier_name', item)
            self.assertIn('total', item)
            self.assertIn('current_stage', item)
            self.assertEqual(item['current_stage'], 'Accountant Review')
            self.assertTrue(item['can_approve'])
    
    def test_get_ap_pending_approvals_for_manager_empty(self):
        """Test getting pending approvals for manager when invoice is at stage 1."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        # Authenticate as manager
        self.client.force_authenticate(user=self.manager)
        
        url = reverse('finance:invoice:ap-invoice-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 0)  # No invoices at manager stage yet
    
    def test_ap_approval_action_approve_success(self):
        """Test accountant approving AP invoice."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'approve',
            'comment': 'Looks good'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('workflow_id', response.data)
        self.assertEqual(response.data['message'], 'Action approve completed successfully')
        
        # Verify workflow moved to next stage
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.stage_template.name, 'Finance Manager Review')
    
    def test_ap_approval_action_reject_success(self):
        """Test accountant rejecting AP invoice."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'reject',
            'comment': 'Incorrect vendor'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify workflow is rejected
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice, active_only=False)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
        
        # Verify invoice status
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.approval_status, Invoice.REJECTED)
    
    def test_ap_approval_action_without_assignment_fails(self):
        """Test user without assignment cannot approve."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        # Try to approve as manager (wrong stage)
        self.client.force_authenticate(user=self.manager)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'approve',
            'comment': 'Trying to approve'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('no assignment', response.data['error'].lower())
    
    def test_ap_approval_action_delegate_success(self):
        """Test delegating AP invoice approval."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        # Create another accountant to delegate to
        accountant2 = self._create_user(
            email='accountant2@test.com',
            name='Jane Accountant',
            phone_number='5555555555',
            role=self.accountant_role
        )
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'delegate',
            'comment': 'Delegating to Jane',
            'target_user_id': accountant2.id
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify delegation was created
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        active_stage = workflow.stage_instances.filter(status='active').first()
        
        # Check that accountant2 now has an assignment
        assignment = active_stage.assignments.filter(user=accountant2).first()
        self.assertIsNotNone(assignment)
    
    def test_ap_approval_action_delegate_without_target_fails(self):
        """Test delegation without target_user_id fails."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'delegate',
            'comment': 'Delegating'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('target_user_id', response.data['error'].lower())
    
    def test_ap_approval_action_comment_success(self):
        """Test adding comment to AP invoice."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'comment',
            'comment': 'Need to verify vendor tax ID'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify comment was logged
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        active_stage = workflow.stage_instances.filter(status='active').first()
        comment_action = active_stage.actions.filter(
            action=ApprovalAction.ACTION_COMMENT,
            user=self.accountant
        ).first()
        self.assertIsNotNone(comment_action)
        self.assertEqual(comment_action.comment, 'Need to verify vendor tax ID')
    
    def test_ap_approval_action_invalid_action_fails(self):
        """Test invalid action parameter fails."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'invalid_action',
            'comment': 'Test'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('invalid action', response.data['error'].lower())
    
    def test_ap_complete_workflow_all_stages(self):
        """Test completing full AP invoice approval workflow through all 3 stages."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        # Stage 1: Accountant approves
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        response = self.client.post(url, {'action': 'approve', 'comment': 'Stage 1 OK'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify now at stage 2
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.stage_template.name, 'Finance Manager Review')
        
        # Stage 2: Manager approves
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(url, {'action': 'approve', 'comment': 'Stage 2 OK'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify now at stage 3
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.stage_template.name, 'CFO Review')
        
        # Stage 3: Director approves
        self.client.force_authenticate(user=self.director)
        response = self.client.post(url, {'action': 'approve', 'comment': 'Final approval'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify workflow is completed
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice, active_only=False)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # Verify invoice status
        ap_invoice.refresh_from_db()
        self.assertEqual(ap_invoice.approval_status, Invoice.APPROVED)


class ARInvoiceApprovalEndpointTest(BaseApprovalEndpointTest):
    """Test AR Invoice approval endpoints."""
    
    def test_submit_ar_invoice_for_approval_success(self):
        """Test successfully submitting AR invoice for approval."""
        ar_invoice = self._create_test_ar_invoice()
        url = reverse('finance:invoice:ar-invoice-submit-for-approval', kwargs={'pk': ar_invoice.invoice_id})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('workflow_id', response.data)
        self.assertEqual(response.data['approval_status'], 'PENDING_APPROVAL')
    
    def test_get_ar_pending_approvals_for_manager(self):
        """Test getting pending AR approvals after stage 1 approval."""
        ar_invoice = self._create_test_ar_invoice()
        ar_invoice.submit_for_approval()
        
        # Accountant approves stage 1
        ApprovalManager.process_action(
            ar_invoice.invoice,
            user=self.accountant,
            action='approve',
            comment='Stage 1 approved'
        )
        
        # Now manager should see it
        self.client.force_authenticate(user=self.manager)
        url = reverse('finance:invoice:ar-invoice-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['current_stage'], 'Finance Manager Review')
        self.assertTrue(response.data['data']['results'][0]['can_approve'])
    
    def test_ar_approval_action_manager_rejects_at_stage_2(self):
        """Test manager rejecting AR invoice at stage 2."""
        ar_invoice = self._create_test_ar_invoice()
        ar_invoice.submit_for_approval()
        
        # Accountant approves stage 1
        ApprovalManager.process_action(ar_invoice.invoice, self.accountant, 'approve')
        
        # Manager rejects at stage 2
        self.client.force_authenticate(user=self.manager)
        url = reverse('finance:invoice:ar-invoice-approval-action', kwargs={'pk': ar_invoice.invoice_id})
        
        response = self.client.post(url, {
            'action': 'reject',
            'comment': 'Customer credit limit exceeded'
        })
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Verify workflow is rejected
        workflow = ApprovalManager.get_workflow_instance(ar_invoice.invoice, active_only=False)
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_REJECTED)
    
    def test_ar_complete_workflow_success(self):
        """Test completing full AR invoice approval workflow."""
        ar_invoice = self._create_test_ar_invoice()
        url = reverse('finance:invoice:ar-invoice-approval-action', kwargs={'pk': ar_invoice.invoice_id})
        
        # Submit
        submit_url = reverse('finance:invoice:ar-invoice-submit-for-approval', kwargs={'pk': ar_invoice.invoice_id})
        self.client.post(submit_url)
        
        # Stage 1
        self.client.force_authenticate(user=self.accountant)
        self.client.post(url, {'action': 'approve'})
        
        # Stage 2
        self.client.force_authenticate(user=self.manager)
        self.client.post(url, {'action': 'approve'})
        
        # Stage 3
        self.client.force_authenticate(user=self.director)
        response = self.client.post(url, {'action': 'approve'})
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        ar_invoice.refresh_from_db()
        self.assertEqual(ar_invoice.approval_status, Invoice.APPROVED)


class OneTimeSupplierApprovalEndpointTest(BaseApprovalEndpointTest):
    """Test One-Time Supplier Invoice approval endpoints."""
    
    def test_submit_one_time_invoice_for_approval_success(self):
        """Test successfully submitting one-time supplier invoice for approval."""
        ots_invoice = self._create_test_one_time_invoice()
        url = reverse('finance:invoice:one-time-supplier-submit-for-approval', kwargs={'pk': ots_invoice.invoice_id})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('workflow_id', response.data)
        self.assertEqual(response.data['approval_status'], 'PENDING_APPROVAL')
    
    def test_get_one_time_pending_approvals_for_director(self):
        """Test getting pending one-time invoices for director at stage 3."""
        ots_invoice = self._create_test_one_time_invoice()
        ots_invoice.submit_for_approval()
        
        # Approve stages 1 and 2
        ApprovalManager.process_action(ots_invoice.invoice, self.accountant, 'approve')
        ApprovalManager.process_action(ots_invoice.invoice, self.manager, 'approve')
        
        # Director should now see it
        self.client.force_authenticate(user=self.director)
        url = reverse('finance:invoice:one-time-supplier-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['current_stage'], 'CFO Review')
        self.assertTrue(response.data['data']['results'][0]['can_approve'])
    
    def test_one_time_complete_workflow_success(self):
        """Test completing full one-time supplier invoice approval workflow."""
        ots_invoice = self._create_test_one_time_invoice()
        url = reverse('finance:invoice:one-time-supplier-approval-action', kwargs={'pk': ots_invoice.invoice_id})
        
        # Submit
        submit_url = reverse('finance:invoice:one-time-supplier-submit-for-approval', kwargs={'pk': ots_invoice.invoice_id})
        self.client.post(submit_url)
        
        # Stage 1
        self.client.force_authenticate(user=self.accountant)
        self.client.post(url, {'action': 'approve'})
        
        # Stage 2
        self.client.force_authenticate(user=self.manager)
        self.client.post(url, {'action': 'approve'})
        
        # Stage 3
        self.client.force_authenticate(user=self.director)
        response = self.client.post(url, {'action': 'approve'})
        
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        ots_invoice.refresh_from_db()
        self.assertEqual(ots_invoice.approval_status, Invoice.APPROVED)


class MixedInvoiceTypesApprovalTest(BaseApprovalEndpointTest):
    """Test approval workflows with mixed invoice types."""
    
    def test_pending_approvals_shows_only_correct_type(self):
        """Test that pending approvals endpoint filters by invoice type correctly."""
        # Create one of each type
        ap = self._create_test_ap_invoice()
        ar = self._create_test_ar_invoice()
        ots = self._create_test_one_time_invoice()
        
        # Submit all
        ap.submit_for_approval()
        ar.submit_for_approval()
        ots.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        
        # Check AP endpoint shows only AP invoices
        ap_url = reverse('finance:invoice:ap-invoice-pending-approvals')
        response = self.client.get(ap_url)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertIn('supplier_name', response.data['data']['results'][0])
        
        # Check AR endpoint shows only AR invoices
        ar_url = reverse('finance:invoice:ar-invoice-pending-approvals')
        response = self.client.get(ar_url)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertIn('customer_name', response.data['data']['results'][0])
        
        # Check one-time endpoint shows only one-time invoices
        ots_url = reverse('finance:invoice:one-time-supplier-pending-approvals')
        response = self.client.get(ots_url)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertIn('supplier_name', response.data['data']['results'][0])
    
    def test_multiple_invoices_at_different_stages(self):
        """Test pending approvals when invoices are at different stages."""
        # Create 3 AP invoices
        ap1 = self._create_test_ap_invoice()
        ap2 = self._create_test_ap_invoice()
        ap3 = self._create_test_ap_invoice()
        
        # Submit all
        ap1.submit_for_approval()
        ap2.submit_for_approval()
        ap3.submit_for_approval()
        
        # Approve ap1 through stage 1
        ApprovalManager.process_action(ap1.invoice, self.accountant, 'approve')
        
        # Approve ap2 through stages 1 and 2
        ApprovalManager.process_action(ap2.invoice, self.accountant, 'approve')
        ApprovalManager.process_action(ap2.invoice, self.manager, 'approve')
        
        # Leave ap3 at stage 1
        
        # Accountant should see only ap3
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-pending-approvals')
        response = self.client.get(url)
        self.assertEqual(len(response.data['data']['results']), 1)
        
        # Manager should see only ap1
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(url)
        self.assertEqual(len(response.data['data']['results']), 1)
        
        # Director should see only ap2
        self.client.force_authenticate(user=self.director)
        response = self.client.get(url)
        self.assertEqual(len(response.data['data']['results']), 1)


class ApprovalEndpointErrorHandlingTest(BaseApprovalEndpointTest):
    """Test error handling for approval endpoints."""
    
    def test_submit_nonexistent_invoice_returns_404(self):
        """Test submitting non-existent invoice returns 404."""
        url = reverse('finance:invoice:ap-invoice-submit-for-approval', kwargs={'pk': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
    
    def test_approval_action_on_nonexistent_invoice_returns_404(self):
        """Test approval action on non-existent invoice returns 404."""
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': 99999})
        self.client.force_authenticate(user=self.accountant)
        response = self.client.post(url, {'action': 'approve'})
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
    
    def test_approval_action_without_workflow_fails(self):
        """Test approval action on invoice without workflow fails."""
        ap_invoice = self._create_test_ap_invoice()
        # Don't submit for approval
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        response = self.client.post(url, {'action': 'approve'})
        
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_double_approval_by_same_user_fails(self):
        """Test that same user cannot approve twice."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        # First approval succeeds
        response = self.client.post(url, {'action': 'approve'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Revert to stage 1 for testing (in real scenario this wouldn't happen)
        # Instead, test at the next stage where accountant has no assignment
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        active_stage = workflow.stage_instances.filter(status='active').first()
        
        # Accountant tries to approve manager stage - should fail
        response = self.client.post(url, {'action': 'approve'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
    
    def test_unauthenticated_user_uses_fallback(self):
        """Test that unauthenticated requests use first user as fallback."""
        ap_invoice = self._create_test_ap_invoice()
        
        # Don't authenticate
        url = reverse('finance:invoice:ap-invoice-pending-approvals')
        response = self.client.get(url)
        
        # Should not fail, should use fallback user
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)


class ApprovalEndpointResponseFormatTest(BaseApprovalEndpointTest):
    """Test response format of approval endpoints."""
    
    def test_submit_response_format(self):
        """Test submit endpoint returns correct response format."""
        ap_invoice = self._create_test_ap_invoice()
        url = reverse('finance:invoice:ap-invoice-submit-for-approval', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url)
        
        self.assertIn('message', response.data)
        self.assertIn('invoice_id', response.data)
        self.assertIn('workflow_id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('approval_status', response.data)
    
    def test_pending_approvals_response_format(self):
        """Test pending approvals endpoint returns correct response format."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-pending-approvals')
        response = self.client.get(url)
        
        self.assertEqual(len(response.data['data']['results']), 1)
        item = response.data['data']['results'][0]
        
        # Check all required fields
        required_fields = [
            'invoice_id', 'supplier_name', 'date', 'total', 'currency',
            'approval_status', 'workflow_id', 'current_stage',
            'can_approve', 'can_reject', 'can_delegate'
        ]
        for field in required_fields:
            self.assertIn(field, item)
    
    def test_approval_action_response_format(self):
        """Test approval action endpoint returns correct response format."""
        ap_invoice = self._create_test_ap_invoice()
        ap_invoice.submit_for_approval()
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse('finance:invoice:ap-invoice-approval-action', kwargs={'pk': ap_invoice.invoice_id})
        
        response = self.client.post(url, {'action': 'approve', 'comment': 'OK'})
        
        self.assertIn('message', response.data)
        self.assertIn('invoice_id', response.data)
        self.assertIn('workflow_id', response.data)
        self.assertIn('workflow_status', response.data)
        self.assertIn('approval_status', response.data)
