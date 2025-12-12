"""
Tests for job_roles utils functions.

Tests verify that permission utility functions correctly:
- Check user action permissions
- Retrieve user page permissions
- Handle super admin bypass logic
- Work with job role page access
- Respect user action denials
"""
from django.test import TestCase
from django.core.exceptions import ValidationError

from ..models import (
    JobRole,
    Page,
    Action,
    PageAction,
    JobRolePage,
    UserActionDenial,
)
from ..utils import (
    user_can_perform_action,
    get_user_page_permissions,
    get_user_denied_actions,
    get_user_accessible_pages,
)
from core.user_accounts.models import CustomUser, UserType


class UserCanPerformActionTests(TestCase):
    """Test user_can_perform_action utility function"""
    
    def setUp(self):
        """Set up test data for permission checks"""
        # Create user types
        self.regular_user_type = UserType.objects.create(
            type_name='user',
            description='Regular user'
        )
        self.super_admin_type = UserType.objects.create(
            type_name='super_admin',
            description='Super administrator'
        )
        
        # Create job role
        self.accountant_role = JobRole.objects.create(
            name='Accountant',
            description='Financial role'
        )
        
        # Create page
        self.invoice_page = Page.objects.create(
            name='invoice_page',
            display_name='Invoice Management'
        )
        
        # Create actions
        self.view_action = Action.objects.create(name='view', display_name='View')
        self.delete_action = Action.objects.create(name='delete', display_name='Delete')
        
        # Link actions to page
        self.invoice_view = PageAction.objects.create(
            page=self.invoice_page,
            action=self.view_action
        )
        self.invoice_delete = PageAction.objects.create(
            page=self.invoice_page,
            action=self.delete_action
        )
        
        # Grant page to job role
        JobRolePage.objects.create(
            job_role=self.accountant_role,
            page=self.invoice_page
        )
        
        # Create regular user with job role
        self.regular_user = CustomUser.objects.create_user(
            email='user@example.com',
            name='Regular User',
            phone_number='1234567890',
            password='pass123',
            user_type_name='user'
        )
        self.regular_user.job_role = self.accountant_role
        self.regular_user.save()
        
        # Create super admin
        self.super_admin = CustomUser.objects.create_user(
            email='admin@example.com',
            name='Super Admin',
            phone_number='9876543210',
            password='adminpass',
            user_type_name='super_admin'
        )
    
    def test_super_admin_can_perform_any_action(self):
        """Super admin should bypass all permission checks"""
        allowed, reason = user_can_perform_action(
            self.super_admin,
            'invoice_page',
            'view'
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, 'Super admin has full access')
        
        # Even on pages/actions that don't exist
        allowed, reason = user_can_perform_action(
            self.super_admin,
            'nonexistent_page',
            'nonexistent_action'
        )
        self.assertTrue(allowed)
    
    def test_user_without_job_role_denied(self):
        """User without job role should be denied"""
        user_no_role = CustomUser.objects.create_user(
            email='norole@example.com',
            name='No Role User',
            phone_number='1111111111',
            password='pass123',
            user_type_name='user'
        )
        
        allowed, reason = user_can_perform_action(
            user_no_role,
            'invoice_page',
            'view'
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, 'User has no job role assigned')
    
    def test_user_can_perform_allowed_action(self):
        """User with proper permissions should be allowed"""
        allowed, reason = user_can_perform_action(
            self.regular_user,
            'invoice_page',
            'view'
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, 'Allowed')
    
    def test_user_denied_action_on_inaccessible_page(self):
        """User should be denied on pages not in their job role"""
        # Create page not assigned to user's job role
        hr_page = Page.objects.create(name='hr_page', display_name='HR')
        hr_view = PageAction.objects.create(page=hr_page, action=self.view_action)
        
        allowed, reason = user_can_perform_action(
            self.regular_user,
            'hr_page',
            'view'
        )
        self.assertFalse(allowed)
        self.assertIn('not accessible with job role', reason)
    
    def test_user_denied_nonexistent_page(self):
        """User should be denied on pages that don't exist"""
        allowed, reason = user_can_perform_action(
            self.regular_user,
            'fake_page',
            'view'
        )
        self.assertFalse(allowed)
        self.assertIn('does not exist', reason)
    
    def test_user_denied_nonexistent_action_on_page(self):
        """User should be denied actions that don't exist for a page"""
        allowed, reason = user_can_perform_action(
            self.regular_user,
            'invoice_page',
            'nonexistent_action'
        )
        self.assertFalse(allowed)
        self.assertIn('does not exist for page', reason)
    
    def test_user_with_action_denial_blocked(self):
        """User with explicit action denial should be blocked"""
        # Create denial for delete action
        UserActionDenial.objects.create(
            user=self.regular_user,
            page_action=self.invoice_delete
        )
        
        # User should still be able to view
        allowed, reason = user_can_perform_action(
            self.regular_user,
            'invoice_page',
            'view'
        )
        self.assertTrue(allowed)
        
        # But not delete
        allowed, reason = user_can_perform_action(
            self.regular_user,
            'invoice_page',
            'delete'
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, 'Action denied for this user')


class GetUserPagePermissionsTests(TestCase):
    """Test get_user_page_permissions utility function"""
    
    def setUp(self):
        """Set up comprehensive permission scenario"""
        # Create user types
        UserType.objects.create(type_name='user', description='Regular user')
        UserType.objects.create(type_name='super_admin', description='Super admin')
        
        # Create job role
        self.accountant_role = JobRole.objects.create(name='Accountant')
        
        # Create pages
        self.invoice_page = Page.objects.create(
            name='invoice_page',
            display_name='Invoices'
        )
        self.payment_page = Page.objects.create(
            name='payment_page',
            display_name='Payments'
        )
        
        # Create actions
        self.view_action = Action.objects.create(name='view', display_name='View')
        self.create_action = Action.objects.create(name='create', display_name='Create')
        self.delete_action = Action.objects.create(name='delete', display_name='Delete')
        
        # Link actions to invoice page
        self.invoice_view = PageAction.objects.create(
            page=self.invoice_page,
            action=self.view_action
        )
        self.invoice_create = PageAction.objects.create(
            page=self.invoice_page,
            action=self.create_action
        )
        self.invoice_delete = PageAction.objects.create(
            page=self.invoice_page,
            action=self.delete_action
        )
        
        # Link action to payment page
        self.payment_view = PageAction.objects.create(
            page=self.payment_page,
            action=self.view_action
        )
        
        # Grant only invoice page to accountant role
        JobRolePage.objects.create(
            job_role=self.accountant_role,
            page=self.invoice_page
        )
        
        # Create users
        self.regular_user = CustomUser.objects.create_user(
            email='user@example.com',
            name='Regular User',
            phone_number='1234567890',
            password='pass123',
            user_type_name='user'
        )
        self.regular_user.job_role = self.accountant_role
        self.regular_user.save()
        
        self.super_admin = CustomUser.objects.create_user(
            email='admin@example.com',
            name='Admin User',
            phone_number='9876543210',
            password='adminpass',
            user_type_name='super_admin'
        )
    
    def test_super_admin_gets_all_permissions(self):
        """Super admin should see all pages and all actions"""
        permissions = get_user_page_permissions(self.super_admin)
        
        self.assertEqual(permissions['user_type'], 'super_admin')
        self.assertEqual(permissions['job_role']['name'], 'Super Admin')
        self.assertEqual(len(permissions['pages']), 2)  # Both pages
        
        # Check that all actions are allowed
        for page in permissions['pages']:
            for action in page['actions']:
                self.assertTrue(action['allowed'])
    
    def test_regular_user_gets_job_role_permissions(self):
        """Regular user should only see pages granted to their job role"""
        permissions = get_user_page_permissions(self.regular_user)
        
        self.assertEqual(permissions['user_type'], 'user')
        self.assertEqual(permissions['job_role']['id'], self.accountant_role.id)
        self.assertEqual(permissions['job_role']['name'], 'Accountant')
        
        # Should only have invoice page
        self.assertEqual(len(permissions['pages']), 1)
        self.assertEqual(permissions['pages'][0]['page_name'], 'invoice_page')
        
        # Should have all actions for invoice page
        action_names = [a['name'] for a in permissions['pages'][0]['actions']]
        self.assertIn('view', action_names)
        self.assertIn('create', action_names)
        self.assertIn('delete', action_names)
    
    def test_user_without_job_role_gets_empty_permissions(self):
        """User without job role should get empty page list"""
        user_no_role = CustomUser.objects.create_user(
            email='norole@example.com',
            name='No Role',
            phone_number='1111111111',
            password='pass123',
            user_type_name='user'
        )
        
        permissions = get_user_page_permissions(user_no_role)
        
        self.assertEqual(permissions['job_role'], None)
        self.assertEqual(len(permissions['pages']), 0)
    
    def test_user_permissions_reflect_denials(self):
        """User permissions should show denied actions as not allowed"""
        # Deny delete action for user
        UserActionDenial.objects.create(
            user=self.regular_user,
            page_action=self.invoice_delete
        )
        
        permissions = get_user_page_permissions(self.regular_user)
        
        invoice_actions = permissions['pages'][0]['actions']
        
        # Find the delete action
        delete_permission = next(a for a in invoice_actions if a['name'] == 'delete')
        self.assertFalse(delete_permission['allowed'])
        self.assertIn('denial_id', delete_permission)
        
        # Other actions should still be allowed
        view_permission = next(a for a in invoice_actions if a['name'] == 'view')
        self.assertTrue(view_permission['allowed'])
    
    def test_permissions_structure_completeness(self):
        """Verify the permission structure has all required fields"""
        permissions = get_user_page_permissions(self.regular_user)
        
        # Top-level fields
        self.assertIn('user_id', permissions)
        self.assertIn('name', permissions)
        self.assertIn('user_type', permissions)
        self.assertIn('job_role', permissions)
        self.assertIn('pages', permissions)
        
        # Page-level fields
        if permissions['pages']:
            page = permissions['pages'][0]
            self.assertIn('page_id', page)
            self.assertIn('page_name', page)
            self.assertIn('display_name', page)
            self.assertIn('actions', page)
            
            # Action-level fields
            if page['actions']:
                action = page['actions'][0]
                self.assertIn('action_id', action)
                self.assertIn('name', action)
                self.assertIn('display_name', action)
                self.assertIn('allowed', action)


class GetUserDeniedActionsTests(TestCase):
    """Test get_user_denied_actions utility function"""
    
    def setUp(self):
        """Set up test data with denials"""
        UserType.objects.create(type_name='user', description='Regular user')
        
        self.job_role = JobRole.objects.create(name='Accountant')
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        
        self.view_action = Action.objects.create(name='view', display_name='View')
        self.delete_action = Action.objects.create(name='delete', display_name='Delete')
        
        self.page_view = PageAction.objects.create(page=self.page, action=self.view_action)
        self.page_delete = PageAction.objects.create(page=self.page, action=self.delete_action)
        
        JobRolePage.objects.create(job_role=self.job_role, page=self.page)
        
        self.user = CustomUser.objects.create_user(
            email='user@example.com',
            name='Test User',
            phone_number='1234567890',
            password='pass123',
            user_type_name='user'
        )
        self.user.job_role = self.job_role
        self.user.save()
    
    def test_user_with_no_denials_returns_empty_list(self):
        """User with no denials should get empty list"""
        denials = get_user_denied_actions(self.user)
        
        self.assertEqual(denials['user_id'], self.user.id)
        self.assertEqual(len(denials['denied_actions']), 0)
    
    def test_user_with_denials_gets_denial_list(self):
        """User with denials should get complete denial information"""
        # Create denials
        denial1 = UserActionDenial.objects.create(
            user=self.user,
            page_action=self.page_delete
        )
        
        denials = get_user_denied_actions(self.user)
        
        self.assertEqual(len(denials['denied_actions']), 1)
        
        denied_action = denials['denied_actions'][0]
        self.assertEqual(denied_action['denial_id'], denial1.id)
        self.assertEqual(denied_action['page_name'], 'invoice_page')
        self.assertEqual(denied_action['action_name'], 'delete')
        self.assertIn('denied_at', denied_action)
    
    def test_multiple_denials_all_returned(self):
        """Multiple denials should all be returned"""
        UserActionDenial.objects.create(user=self.user, page_action=self.page_view)
        UserActionDenial.objects.create(user=self.user, page_action=self.page_delete)
        
        denials = get_user_denied_actions(self.user)
        
        self.assertEqual(len(denials['denied_actions']), 2)
        
        action_names = {d['action_name'] for d in denials['denied_actions']}
        self.assertEqual(action_names, {'view', 'delete'})


class GetUserAccessiblePagesTests(TestCase):
    """Test get_user_accessible_pages utility function"""
    
    def setUp(self):
        """Set up test data"""
        UserType.objects.create(type_name='user', description='Regular user')
        UserType.objects.create(type_name='super_admin', description='Super admin')
        
        self.job_role = JobRole.objects.create(name='Accountant')
        
        self.page1 = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.page2 = Page.objects.create(name='payment_page', display_name='Payments')
        self.page3 = Page.objects.create(name='report_page', display_name='Reports')
        
        # Grant only page1 and page2 to job role
        JobRolePage.objects.create(job_role=self.job_role, page=self.page1)
        JobRolePage.objects.create(job_role=self.job_role, page=self.page2)
        
        self.user = CustomUser.objects.create_user(
            email='user@example.com',
            name='Regular User',
            phone_number='1234567890',
            password='pass123',
            user_type_name='user'
        )
        self.user.job_role = self.job_role
        self.user.save()
        
        self.admin = CustomUser.objects.create_user(
            email='admin@example.com',
            name='Admin',
            phone_number='9876543210',
            password='adminpass',
            user_type_name='super_admin'
        )
    
    def test_super_admin_sees_all_pages(self):
        """Super admin should see all pages in system"""
        pages = get_user_accessible_pages(self.admin)
        
        self.assertEqual(len(pages), 3)
        page_names = {p['name'] for p in pages}
        self.assertEqual(page_names, {'invoice_page', 'payment_page', 'report_page'})
    
    def test_regular_user_sees_only_job_role_pages(self):
        """Regular user should only see pages granted to job role"""
        pages = get_user_accessible_pages(self.user)
        
        self.assertEqual(len(pages), 2)
        page_names = {p['name'] for p in pages}
        self.assertEqual(page_names, {'invoice_page', 'payment_page'})
    
    def test_user_without_job_role_sees_no_pages(self):
        """User without job role should see no pages"""
        user_no_role = CustomUser.objects.create_user(
            email='norole@example.com',
            name='No Role',
            phone_number='1111111111',
            password='pass123',
            user_type_name='user'
        )
        
        pages = get_user_accessible_pages(user_no_role)
        self.assertEqual(len(pages), 0)
    
    def test_page_structure_has_required_fields(self):
        """Returned pages should have required fields"""
        pages = get_user_accessible_pages(self.user)
        
        for page in pages:
            self.assertIn('name', page)
            self.assertIn('display_name', page)


class PermissionUtilsIntegrationTests(TestCase):
    """Integration tests for complete permission workflows using utils"""
    
    def setUp(self):
        """Set up a realistic permission scenario"""
        # Create user types
        UserType.objects.create(type_name='user')
        UserType.objects.create(type_name='admin')
        UserType.objects.create(type_name='super_admin')
        
        # Create job roles
        self.accountant_role = JobRole.objects.create(name='Accountant')
        self.auditor_role = JobRole.objects.create(name='Auditor')
        
        # Create pages
        self.invoice_page = Page.objects.create(
            name='invoice_page',
            display_name='Invoice Management'
        )
        self.payment_page = Page.objects.create(
            name='payment_page',
            display_name='Payment Processing'
        )
        
        # Create actions
        self.view_action = Action.objects.create(name='view', display_name='View')
        self.create_action = Action.objects.create(name='create', display_name='Create')
        self.edit_action = Action.objects.create(name='edit', display_name='Edit')
        self.delete_action = Action.objects.create(name='delete', display_name='Delete')
        self.approve_action = Action.objects.create(name='approve', display_name='Approve')
        
        # Link actions to invoice page
        self.invoice_view = PageAction.objects.create(page=self.invoice_page, action=self.view_action)
        self.invoice_create = PageAction.objects.create(page=self.invoice_page, action=self.create_action)
        self.invoice_edit = PageAction.objects.create(page=self.invoice_page, action=self.edit_action)
        self.invoice_delete = PageAction.objects.create(page=self.invoice_page, action=self.delete_action)
        self.invoice_approve = PageAction.objects.create(page=self.invoice_page, action=self.approve_action)
        
        # Link actions to payment page
        self.payment_view = PageAction.objects.create(page=self.payment_page, action=self.view_action)
        self.payment_create = PageAction.objects.create(page=self.payment_page, action=self.create_action)
        
        # Grant pages to roles
        JobRolePage.objects.create(job_role=self.accountant_role, page=self.invoice_page)
        JobRolePage.objects.create(job_role=self.accountant_role, page=self.payment_page)
        JobRolePage.objects.create(job_role=self.auditor_role, page=self.invoice_page)
        
        # Create users
        self.accountant = CustomUser.objects.create_user(
            email='accountant@example.com',
            name='Accountant User',
            phone_number='1111111111',
            password='pass123',
            user_type_name='user'
        )
        self.accountant.job_role = self.accountant_role
        self.accountant.save()
        
        self.auditor = CustomUser.objects.create_user(
            email='auditor@example.com',
            name='Auditor User',
            phone_number='2222222222',
            password='pass123',
            user_type_name='user'
        )
        self.auditor.job_role = self.auditor_role
        self.auditor.save()
    
    def test_accountant_workflow(self):
        """Test complete workflow for accountant user"""
        # Accountant should see both invoice and payment pages
        pages = get_user_accessible_pages(self.accountant)
        self.assertEqual(len(pages), 2)
        
        # Accountant can view invoices
        can_view, _ = user_can_perform_action(self.accountant, 'invoice_page', 'view')
        self.assertTrue(can_view)
        
        # Accountant can create invoices
        can_create, _ = user_can_perform_action(self.accountant, 'invoice_page', 'create')
        self.assertTrue(can_create)
        
        # Deny approve action for accountant
        UserActionDenial.objects.create(
            user=self.accountant,
            page_action=self.invoice_approve
        )
        
        # Now accountant cannot approve
        can_approve, reason = user_can_perform_action(self.accountant, 'invoice_page', 'approve')
        self.assertFalse(can_approve)
        self.assertEqual(reason, 'Action denied for this user')
        
        # Check denials list
        denials = get_user_denied_actions(self.accountant)
        self.assertEqual(len(denials['denied_actions']), 1)
        self.assertEqual(denials['denied_actions'][0]['action_name'], 'approve')
        
        # Full permissions should reflect the denial
        permissions = get_user_page_permissions(self.accountant)
        invoice_page_perms = next(p for p in permissions['pages'] if p['page_name'] == 'invoice_page')
        approve_perm = next(a for a in invoice_page_perms['actions'] if a['name'] == 'approve')
        self.assertFalse(approve_perm['allowed'])
    
    def test_auditor_workflow(self):
        """Test complete workflow for auditor user (read-only)"""
        # Auditor should only see invoice page
        pages = get_user_accessible_pages(self.auditor)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]['name'], 'invoice_page')
        
        # Deny all write actions for auditor
        UserActionDenial.objects.create(user=self.auditor, page_action=self.invoice_create)
        UserActionDenial.objects.create(user=self.auditor, page_action=self.invoice_edit)
        UserActionDenial.objects.create(user=self.auditor, page_action=self.invoice_delete)
        UserActionDenial.objects.create(user=self.auditor, page_action=self.invoice_approve)
        
        # Auditor can view
        can_view, _ = user_can_perform_action(self.auditor, 'invoice_page', 'view')
        self.assertTrue(can_view)
        
        # But cannot modify
        can_edit, _ = user_can_perform_action(self.auditor, 'invoice_page', 'edit')
        self.assertFalse(can_edit)
        
        can_delete, _ = user_can_perform_action(self.auditor, 'invoice_page', 'delete')
        self.assertFalse(can_delete)
        
        # Check that permissions show correct read-only state
        permissions = get_user_page_permissions(self.auditor)
        invoice_actions = permissions['pages'][0]['actions']
        
        view_action = next(a for a in invoice_actions if a['name'] == 'view')
        self.assertTrue(view_action['allowed'])
        
        write_actions = [a for a in invoice_actions if a['name'] in ['create', 'edit', 'delete', 'approve']]
        for action in write_actions:
            self.assertFalse(action['allowed'])
