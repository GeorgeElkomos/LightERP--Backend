"""Role-based filtering tests for approval workflows.

Tests that the approval system correctly filters users by Role
when required_role is specified in stage templates.
"""

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.job_roles.models import JobRole, UserJobRole
from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
    ApprovalAction,
    TestInvoice,
)
from core.approval.managers import ApprovalManager

User = get_user_model()


class RoleFilteringTest(TestCase):
    """Test role-based user filtering in approval workflows."""
    
    def setUp(self):
        """Set up test data with roles and users."""
        # Create job roles
        self.manager_role = JobRole.objects.create(name='manager', code='MANAGER')
        self.director_role = JobRole.objects.create(name='director', code='DIRECTOR')
        self.supervisor_role = JobRole.objects.create(name='supervisor', code='SUPERVISOR')
        self.employee_role = JobRole.objects.create(name='employee', code='EMPLOYEE')
        
        # Create users with different roles
        self.manager1 = User.objects.create_user(
            email='manager1@test.com',
            name='Manager One',
            phone_number='1111111111',
            password='testpass123'
        )
        UserJobRole.objects.create(
            user=self.manager1,
            job_role=self.manager_role,
            effective_start_date=timezone.now().date()
        )
        
        self.manager2 = User.objects.create_user(
            email='manager2@test.com',
            name='Manager Two',
            phone_number='2222222222',
            password='testpass123'
        )
        UserJobRole.objects.create(
            user=self.manager2,
            job_role=self.manager_role,
            effective_start_date=timezone.now().date()
        )
        
        self.director = User.objects.create_user(
            email='director@test.com',
            name='Director',
            phone_number='3333333333',
            password='testpass123'
        )
        UserJobRole.objects.create(
            user=self.director,
            job_role=self.director_role,
            effective_start_date=timezone.now().date()
        )
        
        self.supervisor = User.objects.create_user(
            email='supervisor@test.com',
            name='Supervisor',
            phone_number='4444444444',
            password='testpass123'
        )
        UserJobRole.objects.create(
            user=self.supervisor,
            job_role=self.supervisor_role,
            effective_start_date=timezone.now().date()
        )
        
        self.employee = User.objects.create_user(
            email='employee@test.com',
            name='Employee',
            phone_number='5555555555',
            password='testpass123'
        )
        UserJobRole.objects.create(
            user=self.employee,
            job_role=self.employee_role,
            effective_start_date=timezone.now().date()
        )
        
        # Create workflow template
        ct = ContentType.objects.get_for_model(TestInvoice)
        
        self.template = ApprovalWorkflowTemplate.objects.create(
            code='ROLE_FILTER_TEST',
            name='Role Filter Test Workflow',
            content_type=ct,
            is_active=True,
            version=1
        )
    
    def test_single_role_filter(self):
        """Test that stage only assigns users with specified role."""
        # Create stage with manager role requirement
        stage = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Only Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.manager_role
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-001',
            vendor_name='Test Vendor',
            total_amount=5000.00,
            description='Test invoice'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Get active stage
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertIsNotNone(active_stage)
        
        # Get assignments
        assignments = active_stage.assignments.all()
        
        # Should have exactly 2 managers
        self.assertEqual(assignments.count(), 2)
        
        # All assignments should be managers
        for assignment in assignments:
            self.assertTrue(assignment.user.user_job_roles.filter(job_role=self.manager_role).exists())
        
        # Verify specific users
        assigned_users = set(assignments.values_list('user', flat=True))
        expected_users = {self.manager1.id, self.manager2.id}
        self.assertEqual(assigned_users, expected_users)
    
    def test_multiple_stages_different_roles(self):
        """Test workflow with multiple stages requiring different roles."""
        # Stage 1: Managers
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.manager_role
        )
        
        # Stage 2: Director
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=2,
            name='Director Approval',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            required_role=self.director_role
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-002',
            vendor_name='Test Vendor 2',
            total_amount=10000.00,
            description='Multi-stage test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Check first stage has only managers
        stage1 = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(stage1.stage_template.order_index, 1)
        
        assignments1 = stage1.assignments.all()
        self.assertEqual(assignments1.count(), 2)
        for assignment in assignments1:
            self.assertTrue(assignment.user.user_job_roles.filter(job_role=self.manager_role).exists())
        
        # Approve first stage
        ApprovalManager.process_action(invoice, self.manager1, 'approve')
        
        # Check second stage has only director
        workflow.refresh_from_db()
        stage2 = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(stage2.stage_template.order_index, 2)
        
        assignments2 = stage2.assignments.all()
        self.assertEqual(assignments2.count(), 1)
        self.assertEqual(assignments2.first().user, self.director)
        self.assertTrue(assignments2.first().user.user_job_roles.filter(job_role=self.director_role).exists())
    
    def test_no_role_requirement_assigns_all_users(self):
        """Test that stage without role requirement assigns all users."""
        # Create stage without role requirement
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='All Users Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            required_role=None,  # No role filter
            quorum_count=3
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-003',
            vendor_name='Test Vendor 3',
            total_amount=3000.00,
            description='No role filter test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Get active stage
        active_stage = workflow.stage_instances.filter(status='active').first()
        
        # Get assignments
        assignments = active_stage.assignments.all()
        
        # Should have all 5 users
        self.assertEqual(assignments.count(), 5)
        
        # Verify all users are assigned
        assigned_user_ids = set(assignments.values_list('user_id', flat=True))
        expected_user_ids = {
            self.manager1.id,
            self.manager2.id,
            self.director.id,
            self.supervisor.id,
            self.employee.id
        }
        self.assertEqual(assigned_user_ids, expected_user_ids)
    
    def test_role_with_no_users_skips_stage(self):
        """Test that stage is skipped if no users have required role."""
        # Create a job role with no users
        empty_role = JobRole.objects.create(name='cfo', code='CFO')
        
        # Create stage requiring this role
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='CFO Approval',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=empty_role
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-004',
            vendor_name='Test Vendor 4',
            total_amount=2000.00,
            description='Empty role test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Stage should be skipped
        stage = workflow.stage_instances.first()
        self.assertEqual(stage.status, ApprovalWorkflowStageInstance.STATUS_SKIPPED)
        
        # Workflow should be approved (no more stages)
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_user_without_role_not_assigned(self):
        """Test that users without a role are not assigned when role is required."""
        # Create user without role
        user_no_role = User.objects.create_user(
            email='norole@test.com',
            name='No Role User',
            phone_number='6666666666',
            password='testpass123'
        )
        # Don't assign a job role (job_role field is nullable)
        
        # Create stage requiring manager role
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.manager_role
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-005',
            vendor_name='Test Vendor 5',
            total_amount=1000.00,
            description='User without role test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Get assignments
        active_stage = workflow.stage_instances.filter(status='active').first()
        assignments = active_stage.assignments.all()
        
        # Should only have the 2 managers, not the user without role
        self.assertEqual(assignments.count(), 2)
        assigned_user_ids = set(assignments.values_list('user_id', flat=True))
        self.assertNotIn(user_no_role.id, assigned_user_ids)
    
    def test_role_snapshot_saved_in_assignment(self):
        """Test that role is captured in assignment snapshot."""
        # Create stage with manager role
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.manager_role
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-006',
            vendor_name='Test Vendor 6',
            total_amount=7500.00,
            description='Role snapshot test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Get assignment
        active_stage = workflow.stage_instances.filter(status='active').first()
        assignment = active_stage.assignments.filter(user=self.manager1).first()
        
        # Role name should be captured in snapshot (role_snapshot is CharField)
        self.assertIsNotNone(assignment.role_snapshot)
        self.assertEqual(assignment.role_snapshot, self.manager_role.name)
    
    def test_quorum_policy_with_role_filter(self):
        """Test QUORUM policy works correctly with role filtering."""
        # Create stage requiring 2 managers (QUORUM)
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Quorum',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            required_role=self.manager_role,
            quorum_count=2
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-007',
            vendor_name='Test Vendor 7',
            total_amount=20000.00,
            description='Quorum with role test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Should have 2 manager assignments
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.assignments.count(), 2)
        
        # First approval - workflow should continue
        ApprovalManager.process_action(invoice, self.manager1, 'approve')
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_IN_PROGRESS)
        
        # Second approval - should complete
        ApprovalManager.process_action(invoice, self.manager2, 'approve')
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_all_policy_with_role_filter(self):
        """Test ALL policy requires all users of specified role to approve."""
        # Create stage requiring ALL supervisors
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Supervisor Unanimous',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            required_role=self.supervisor_role
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-008',
            vendor_name='Test Vendor 8',
            total_amount=15000.00,
            description='ALL policy with role test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Should have 1 supervisor assignment
        active_stage = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(active_stage.assignments.count(), 1)
        
        # Supervisor approves - should complete (only 1 supervisor exists)
        ApprovalManager.process_action(invoice, self.supervisor, 'approve')
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
    
    def test_complex_multi_role_workflow(self):
        """Test complex workflow with multiple roles across stages."""
        # Stage 1: Supervisors
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Supervisor Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.supervisor_role
        )
        
        # Stage 2: Managers (QUORUM 2)
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=2,
            name='Manager Review',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_QUORUM,
            required_role=self.manager_role,
            quorum_count=2
        )
        
        # Stage 3: Director
        ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=3,
            name='Director Final Approval',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ALL,
            required_role=self.director_role
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-009',
            vendor_name='Test Vendor 9',
            total_amount=50000.00,
            description='Complex multi-role workflow test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        
        # Stage 1: Supervisor
        stage1 = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(stage1.assignments.count(), 1)
        self.assertEqual(stage1.assignments.first().user, self.supervisor)
        
        ApprovalManager.process_action(invoice, self.supervisor, 'approve', 
                                       comment='Supervisor approved')
        
        # Stage 2: Managers
        workflow.refresh_from_db()
        stage2 = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(stage2.assignments.count(), 2)
        
        ApprovalManager.process_action(invoice, self.manager1, 'approve',
                                       comment='Manager 1 approved')
        ApprovalManager.process_action(invoice, self.manager2, 'approve',
                                       comment='Manager 2 approved')
        
        # Stage 3: Director
        workflow.refresh_from_db()
        stage3 = workflow.stage_instances.filter(status='active').first()
        self.assertEqual(stage3.assignments.count(), 1)
        self.assertEqual(stage3.assignments.first().user, self.director)
        
        ApprovalManager.process_action(invoice, self.director, 'approve',
                                       comment='Director final approval')
        
        # Workflow should be complete
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)
        
        # Verify all stages completed
        completed_stages = workflow.stage_instances.filter(
            status=ApprovalWorkflowStageInstance.STATUS_COMPLETED
        )
        self.assertEqual(completed_stages.count(), 3)
    
    def test_delegation_respects_role_requirements(self):
        """Test that delegation creates assignments correctly."""
        # Create stage with manager role
        stage_template = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=self.template,
            order_index=1,
            name='Manager Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=self.manager_role,
            allow_delegate=True
        )
        
        # Create invoice and start workflow
        invoice = TestInvoice.objects.create(
            invoice_number='INV-ROLE-010',
            vendor_name='Test Vendor 10',
            total_amount=8000.00,
            description='Delegation test'
        )
        
        workflow = ApprovalManager.start_workflow(invoice)
        active_stage = workflow.stage_instances.filter(status='active').first()
        
        # Manager1 delegates to director (different role)
        ApprovalManager.delegate(
            self.manager1,
            self.director,
            active_stage,
            comment='Delegating to director'
        )
        
        # Director should now have an assignment
        director_assignment = active_stage.assignments.filter(
            user=self.director
        ).first()
        self.assertIsNotNone(director_assignment)
        
        # Director can approve even though they don't have manager role
        ApprovalManager.process_action(invoice, self.director, 'approve',
                                       comment='Approved as delegate')
        
        workflow.refresh_from_db()
        self.assertEqual(workflow.status, ApprovalWorkflowInstance.STATUS_APPROVED)


class RoleModelIntegrationTest(TestCase):
    """Test Role model integration with approval system."""
    
    def test_role_model_exists(self):
        """Test that Role model can be created and queried."""
        role = JobRole.objects.create(name='test_role')
        self.assertIsNotNone(role.id)
        self.assertEqual(role.name, 'test_role')
        self.assertEqual(str(role), 'test_role')
    
    def test_role_name_unique(self):
        """Test that role names are unique."""
        JobRole.objects.create(name='unique_role')
        
        with self.assertRaises(Exception):
            JobRole.objects.create(name='unique_role')
    
    def test_user_role_relationship(self):
        """Test ForeignKey relationship between User and Role."""
        role = JobRole.objects.create(name='test_user_role')
        
        user = User.objects.create_user(
            email='roletest@test.com',
            name='Role Test User',
            phone_number='9999999999',
            password='testpass123'
        )
        
        # Assign job role
        UserJobRole.objects.create(
            user=user,
            job_role=role,
            effective_start_date=timezone.now().date()
        )
        
        # Retrieve and verify
        self.assertTrue(user.user_job_roles.filter(job_role=role).exists())
        
        # Test reverse relationship
        users_with_role = User.objects.filter(user_job_roles__job_role=role)
        self.assertIn(user, users_with_role)
    
    def test_role_can_be_null(self):
        """Test that user.job_role can be null."""
        user = User.objects.create_user(
            email='norole@test.com',
            name='No Role User',
            phone_number='8888888888',
            password='testpass123'
        )
        
        # Job role should be None
        self.assertFalse(user.user_job_roles.exists())
        
        # Should be able to save without job role
        user.save()
        user.refresh_from_db()
        self.assertFalse(user.user_job_roles.exists())
    
    def test_stage_template_role_relationship(self):
        """Test ForeignKey relationship between StageTemplate and Role."""
        role = JobRole.objects.create(name='stage_role')
        
        ct = ContentType.objects.get_for_model(TestInvoice)
        template = ApprovalWorkflowTemplate.objects.create(
            code='ROLE_REL_TEST',
            name='Role Relationship Test',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        stage = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='Test Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=role
        )
        
        # Verify relationship
        stage.refresh_from_db()
        self.assertEqual(stage.required_role, role)
    
    def test_role_deletion_with_set_null(self):
        """Test that deleting role sets stage template required_role to null."""
        role = JobRole.objects.create(name='deletable_role')
        
        ct = ContentType.objects.get_for_model(TestInvoice)
        template = ApprovalWorkflowTemplate.objects.create(
            code='DELETE_TEST',
            name='Delete Test',
            content_type=ct,
            is_active=True,
            version=1
        )
        
        stage = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            order_index=1,
            name='Test Stage',
            decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,
            required_role=role
        )
        
        # Delete role
        role.delete()
        
        # Stage should still exist with null role
        stage.refresh_from_db()
        self.assertIsNone(stage.required_role)
