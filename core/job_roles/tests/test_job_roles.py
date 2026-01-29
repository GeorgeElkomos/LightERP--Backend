from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.job_roles.models import (
    JobRole,
    Page,
    Action,
    PageAction,
    JobRolePage,
    UserPermissionOverride,
    UserJobRole,
)
from core.user_accounts.models import UserAccount
from core.base.test_utils import setup_core_data

def setUpModule():
    """Run once for the entire module at the beginning"""
    setup_core_data()

class JobRoleModelTests(TestCase):
    """Tests for JobRole model"""

    def test_create_job_role(self):
        """Test creating a job role"""
        job_role, _ = JobRole.objects.get_or_create(
            name='Accountant',
            code='accountant',
            description='Handles financial records'
        )
        self.assertEqual(str(job_role), 'Accountant')
        self.assertEqual(job_role.name, 'Accountant')

    def test_job_role_unique_name(self):
        """Test that job role names must be unique"""
        JobRole.objects.get_or_create(name='Accountant_u', code='accountant_u1')

        with self.assertRaises(IntegrityError):
            JobRole.objects.create(name='Accountant_u', code='accountant_u2')

    def test_job_role_prevent_deletion_if_assigned(self):
        """Test that job roles with assigned users cannot be deleted"""
        # Create job role
        job_role, _ = JobRole.objects.get_or_create(name='Manager_test', code='manager_test')

        # Create user with this job role
        user = UserAccount.objects.create_user(
            email='test_delete@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )
        UserJobRole.objects.create(user=user, job_role=job_role, effective_start_date=timezone.now().date())

        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError):
            job_role.delete()


class PageModelTests(TestCase):
    """Tests for Page model"""

    def test_create_page(self):
        """Test creating a page"""
        page, _ = Page.objects.get_or_create(
            code='invoice_management',
            name='Invoice Management',
            description='Manage invoices'
        )
        self.assertEqual(page.code, 'invoice_management')
        self.assertIn('Invoice Management', str(page))

    def test_page_unique_code(self):
        """Test that page codes must be unique"""
        Page.objects.get_or_create(code='invoice_management_uc', name='Invoices_1')

        with self.assertRaises(IntegrityError):
            Page.objects.create(code='invoice_management_uc', name='Invoices_2')

    def test_page_prevent_deletion_if_linked(self):
        """Test that pages linked to job roles cannot be deleted"""
        job_role, _ = JobRole.objects.get_or_create(name='Accountant_p', code='accountant_p')
        page, _ = Page.objects.get_or_create(code='invoice_page_p', name='Invoices_p')

        # Link page to job role
        JobRolePage.objects.get_or_create(job_role=job_role, page=page)

        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError):
            page.delete()


class ActionModelTests(TestCase):
    """Tests for Action model"""

    def test_create_action(self):
        """Test creating an action"""
        action, _ = Action.objects.get_or_create(
            code='view_test',
            name='View Test',
            description='View records'
        )
        self.assertEqual(action.code, 'view_test')
        self.assertIn('View Test', str(action))

    def test_action_prevent_deletion_if_linked(self):
        """Test that actions linked to pages cannot be deleted"""
        action, _ = Action.objects.get_or_create(code='view_l', name='View_l')
        page, _ = Page.objects.get_or_create(code='invoice_page_l', name='Invoices_l')

        # Link action to page
        PageAction.objects.get_or_create(page=page, action=action)

        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError):
            action.delete()


class PageActionModelTests(TestCase):
    """Tests for PageAction model"""

    def setUp(self):
        """Set up test data"""
        self.page, _ = Page.objects.get_or_create(
            code='invoice_mgmt_pa',
            name='Invoice Management PA'
        )
        self.action, _ = Action.objects.get_or_create(
            code='view_pa',
            name='View PA'
        )

    def test_create_page_action(self):
        """Test linking an action to a page"""
        page_action, _ = PageAction.objects.get_or_create(
            page=self.page,
            action=self.action
        )
        self.assertEqual(page_action.page, self.page)
        self.assertEqual(page_action.action, self.action)

    def test_unique_page_action(self):
        """Test that page-action combination is unique"""
        PageAction.objects.get_or_create(page=self.page, action=self.action)

        # Attempting to create duplicate should fail
        with self.assertRaises(IntegrityError):
            PageAction.objects.create(page=self.page, action=self.action)

    def test_page_action_prevent_deletion_if_has_denials(self):
        """Test that page actions with user denials cannot be deleted"""
        # Create page action
        page_action, _ = PageAction.objects.get_or_create(page=self.page, action=self.action)

        # Create user
        user = UserAccount.objects.create_user(
            email='test_denial@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

        # Create user action denial
        UserPermissionOverride.objects.get_or_create(
            user=user,
            page_action=page_action,
            permission_type='deny',
            defaults={'effective_start_date': timezone.now().date()}
        )

        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError):
            page_action.delete()


class UserPermissionOverrideModelTests(TestCase):
    """Tests for UserPermissionOverride model"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = UserAccount.objects.create_user(
            email='test_override@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

        # Create page and action
        self.page, _ = Page.objects.get_or_create(code='invoice_page_o', name='Invoices_o')
        self.action, _ = Action.objects.get_or_create(code='delete_o', name='Delete_o')
        self.page_action, _ = PageAction.objects.get_or_create(page=self.page, action=self.action)

    def test_create_user_permission_override_deny(self):
        """Test creating a user permission override (deny type)"""
        override = UserPermissionOverride.objects.create(
            user=self.user,
            page_action=self.page_action,
            permission_type='deny',
            reason='Test denial',
            effective_start_date=timezone.now().date()
        )
        self.assertEqual(override.user, self.user)
        self.assertEqual(override.page_action, self.page_action)
        self.assertEqual(override.permission_type, 'deny')

    def test_create_user_permission_override_grant(self):
        """Test creating a user permission override (grant type)"""
        override = UserPermissionOverride.objects.create(
            user=self.user,
            page_action=self.page_action,
            permission_type='grant',
            reason='Test grant',
            effective_start_date=timezone.now().date()
        )
        self.assertEqual(override.permission_type, 'grant')


class PermissionLogicIntegrationTests(TestCase):
    """Test the complete permission logic flow"""

    def setUp(self):
        """Set up comprehensive test scenario"""
        # Create job roles
        self.accountant_role, _ = JobRole.objects.get_or_create(name='Accountant_i', code='accountant_i')
        self.manager_role, _ = JobRole.objects.get_or_create(name='Manager_i', code='manager_i')

        # Create pages
        self.invoice_page, _ = Page.objects.get_or_create(
            code='invoice_page_i',
            name='Invoice Management I'
        )
        self.report_page, _ = Page.objects.get_or_create(
            code='report_page_i',
            name='Reports I'
        )

        # Create actions
        self.view_action, _ = Action.objects.get_or_create(code='view_i', name='View I')
        self.create_action, _ = Action.objects.get_or_create(code='create_i', name='Create I')
        self.edit_action, _ = Action.objects.get_or_create(code='edit_i', name='Edit I')
        self.delete_action, _ = Action.objects.get_or_create(code='delete_i', name='Delete I')

        # Link actions to invoice page
        self.invoice_view, _ = PageAction.objects.get_or_create(
            page=self.invoice_page, action=self.view_action
        )
        self.invoice_create, _ = PageAction.objects.get_or_create(
            page=self.invoice_page, action=self.create_action
        )
        self.invoice_edit, _ = PageAction.objects.get_or_create(
            page=self.invoice_page, action=self.edit_action
        )
        self.invoice_delete, _ = PageAction.objects.get_or_create(
            page=self.invoice_page, action=self.delete_action
        )

        # Grant invoice page to accountant role
        JobRolePage.objects.get_or_create(
            job_role=self.accountant_role,
            page=self.invoice_page
        )

        # Grant report page to manager role
        JobRolePage.objects.get_or_create(
            job_role=self.manager_role,
            page=self.report_page
        )

        # Create users
        self.accountant_user = UserAccount.objects.create_user(
            email='accountant_i@example.com',
            name='Accountant User',
            phone_number='1111111111',
            password='pass123',
        )
        UserJobRole.objects.create(user=self.accountant_user, job_role=self.accountant_role, effective_start_date=timezone.now().date())

        self.manager_user = UserAccount.objects.create_user(
            email='manager_i@example.com',
            name='Manager User',
            phone_number='2222222222',
            password='pass123',
        )
        UserJobRole.objects.create(user=self.manager_user, job_role=self.manager_role, effective_start_date=timezone.now().date())

    def test_user_has_page_access_via_job_role(self):
        """Test that user can access pages granted to their job role"""
        from core.job_roles.services import get_user_active_roles
        # Accountant should have access to invoice page
        job_role_pages = JobRolePage.objects.filter(
            job_role__in=get_user_active_roles(self.accountant_user),
            page=self.invoice_page
        )
        self.assertTrue(job_role_pages.exists())

        # Manager should NOT have access to invoice page
        job_role_pages = JobRolePage.objects.filter(
            job_role__in=get_user_active_roles(self.manager_user),
            page=self.invoice_page
        )
        self.assertFalse(job_role_pages.exists())

    def test_user_action_denial_removes_specific_permission(self):
        """Test that action denial removes permission for specific user"""
        # Deny delete action for accountant on invoice page
        UserPermissionOverride.objects.get_or_create(
            user=self.accountant_user,
            page_action=self.invoice_delete,
            permission_type='deny',
            defaults={'effective_start_date': timezone.now().date()}
        )

        # Verify denial exists
        denials = UserPermissionOverride.objects.filter(
            user=self.accountant_user,
            page_action__page=self.invoice_page,
            page_action__action=self.delete_action,
            permission_type='deny'
        )
        self.assertTrue(denials.exists())

    def test_reusable_actions_across_pages(self):
        """Test that same action can be used by multiple pages"""
        # Link view action to report page
        PageAction.objects.get_or_create(page=self.report_page, action=self.view_action)

        # Verify view action is linked to both pages
        pages_with_view = PageAction.objects.filter(
            action=self.view_action
        ).values_list('page__code', flat=True)

        self.assertIn('invoice_page_i', pages_with_view)
        self.assertIn('report_page_i', pages_with_view)


class PageHierarchyTests(TestCase):
    """Test page hierarchy and descendant/ancestor methods"""

    def setUp(self):
        """Set up page hierarchy: HR Module > Employee Mgmt > Personal Info"""
        self.hr_module = Page.objects.create(
            code='hr_module_h',
            name='HR Module H'
        )

        self.employee_mgmt = Page.objects.create(
            code='employee_mgmt_h',
            name='Employee Management H',
            parent_page=self.hr_module
        )

        self.personal_info = Page.objects.create(
            code='personal_info_h',
            name='Personal Information H',
            parent_page=self.employee_mgmt
        )

        self.payroll = Page.objects.create(
            code='payroll_h',
            name='Payroll H',
            parent_page=self.hr_module
        )

    def test_page_parent_child_relationships(self):
        """Test that parent-child relationships are correctly established"""
        # Test parent relationships
        self.assertIsNone(self.hr_module.parent_page)
        self.assertEqual(self.employee_mgmt.parent_page, self.hr_module)
        self.assertEqual(self.personal_info.parent_page, self.employee_mgmt)

        # Test child relationships
        hr_children = list(self.hr_module.child_pages.all())
        self.assertEqual(len(hr_children), 2)
        self.assertIn(self.employee_mgmt, hr_children)
        self.assertIn(self.payroll, hr_children)

        emp_children = list(self.employee_mgmt.child_pages.all())
        self.assertEqual(len(emp_children), 1)
        self.assertIn(self.personal_info, emp_children)

    def test_get_ancestor_pages(self):
        """Test getting all ancestor pages up the hierarchy"""
        # Personal Info → Employee Mgmt → HR Module
        ancestors = self.personal_info.get_all_ancestor_pages()
        self.assertEqual(len(ancestors), 2)
        self.assertIn(self.employee_mgmt, ancestors)
        self.assertIn(self.hr_module, ancestors)

        # Employee Mgmt → HR Module
        ancestors = self.employee_mgmt.get_all_ancestor_pages()
        self.assertEqual(len(ancestors), 1)
        self.assertIn(self.hr_module, ancestors)

        # HR Module has no ancestors (root)
        ancestors = self.hr_module.get_all_ancestor_pages()
        self.assertEqual(len(ancestors), 0)

    def test_get_all_descendant_pages(self):
        """Test getting all descendant pages down the hierarchy"""
        # HR Module should have all children and grandchildren
        descendants = self.hr_module.get_all_descendant_pages()
        self.assertEqual(len(descendants), 3)
        self.assertIn(self.employee_mgmt, descendants)
        self.assertIn(self.personal_info, descendants)
        self.assertIn(self.payroll, descendants)

        # Employee Mgmt should have only Personal Info
        descendants = self.employee_mgmt.get_all_descendant_pages()
        self.assertEqual(len(descendants), 1)
        self.assertIn(self.personal_info, descendants)

        # Personal Info and Payroll should have no descendants (leaves)
        self.assertEqual(len(self.personal_info.get_all_descendant_pages()), 0)
        self.assertEqual(len(self.payroll.get_all_descendant_pages()), 0)

    def test_circular_reference_prevention(self):
        """Test that circular references in page hierarchy are prevented"""
        # Try to make hr_module a child of personal_info (would create circular reference)
        self.hr_module.parent_page = self.personal_info
        with self.assertRaises(ValidationError):
            self.hr_module.clean()


class JobRoleHierarchyTests(TestCase):
    """Test job role hierarchy and inheritance"""

    def setUp(self):
        """Set up role hierarchy: Admin > Manager > Staff"""
        self.admin_role = JobRole.objects.create(
            code='admin_rh',
            name='Admin RH',
            priority=100
        )

        self.manager_role = JobRole.objects.create(
            code='manager_rh',
            name='Manager RH',
            parent_role=self.admin_role,
            priority=50
        )

        self.staff_role = JobRole.objects.create(
            code='staff_rh',
            name='Staff RH',
            parent_role=self.manager_role,
            priority=10
        )

    def test_role_parent_child_relationships(self):
        """Test that role hierarchy is correctly established"""
        # Test parent relationships
        self.assertIsNone(self.admin_role.parent_role)
        self.assertEqual(self.manager_role.parent_role, self.admin_role)
        self.assertEqual(self.staff_role.parent_role, self.manager_role)

        # Test child relationships
        admin_children = list(self.admin_role.child_roles.all())
        self.assertEqual(len(admin_children), 1)
        self.assertIn(self.manager_role, admin_children)

        manager_children = list(self.manager_role.child_roles.all())
        self.assertEqual(len(manager_children), 1)
        self.assertIn(self.staff_role, manager_children)

    def test_role_priority_levels(self):
        """Test that role priorities are correctly set for hierarchy"""
        self.assertEqual(self.admin_role.priority, 100)
        self.assertEqual(self.manager_role.priority, 50)
        self.assertEqual(self.staff_role.priority, 10)

        # Higher priority role should have higher value
        self.assertGreater(self.admin_role.priority, self.manager_role.priority)
        self.assertGreater(self.manager_role.priority, self.staff_role.priority)


class PermissionInheritanceTests(TestCase):
    """Test permission inheritance through page hierarchy and inherit_to_children flag"""

    def setUp(self):
        """Set up complex scenario with page hierarchy and roles"""
        # Create page hierarchy
        self.hr_module = Page.objects.create(
            code='hr_module_pi',
            name='HR Module PI'
        )

        self.employee_mgmt = Page.objects.create(
            code='employee_mgmt_pi',
            name='Employee Management PI',
            parent_page=self.hr_module
        )

        self.personal_info = Page.objects.create(
            code='personal_info_pi',
            name='Personal Information PI',
            parent_page=self.employee_mgmt
        )

        self.payroll = Page.objects.create(
            code='payroll_pi',
            name='Payroll PI',
            parent_page=self.hr_module
        )

        # Create roles
        self.hr_manager = JobRole.objects.create(
            code='hr_manager_pi',
            name='HR Manager PI'
        )

        self.hr_staff = JobRole.objects.create(
            code='hr_staff_pi',
            name='HR Staff PI'
        )

        # Create user
        self.user = UserAccount.objects.create_user(
            email='test_pi@example.com',
            name='Test User PI',
            phone_number='1234567890',
            password='testpass123'
        )

    def test_inherit_to_children_enabled(self):
        """Test that inherit_to_children=True grants access to all descendant pages"""
        # Grant HR Module access with inheritance enabled
        job_role_page = JobRolePage.objects.create(
            job_role=self.hr_manager,
            page=self.hr_module,
            inherit_to_children=True
        )

        self.assertTrue(job_role_page.inherit_to_children)

        # Assign role to user
        UserJobRole.objects.create(
            user=self.user,
            job_role=self.hr_manager,
            effective_start_date=timezone.now().date()
        )

        # Get all descendant pages
        descendants = self.hr_module.get_all_descendant_pages()
        self.assertEqual(len(descendants), 3)  # employee_mgmt, personal_info, payroll

        # User should have access to parent page
        from core.job_roles.services import get_user_active_roles
        active_roles = get_user_active_roles(self.user)

        role_page_access = JobRolePage.objects.filter(
            job_role__in=active_roles,
            page=self.hr_module
        )
        self.assertTrue(role_page_access.exists())
        self.assertTrue(role_page_access.first().inherit_to_children)

    def test_inherit_to_children_disabled(self):
        """Test that inherit_to_children=False grants access only to specific page"""
        # Grant only Personal Info page access (no inheritance)
        job_role_page = JobRolePage.objects.create(
            job_role=self.hr_staff,
            page=self.personal_info,
            inherit_to_children=False
        )

        self.assertFalse(job_role_page.inherit_to_children)

        # Assign role to user
        UserJobRole.objects.create(
            user=self.user,
            job_role=self.hr_staff,
            effective_start_date=timezone.now().date()
        )

        # User should NOT have access to parent or sibling pages through this assignment
        from core.job_roles.services import get_user_active_roles
        active_roles = get_user_active_roles(self.user)

        # Has access to personal_info only
        personal_access = JobRolePage.objects.filter(
            job_role__in=active_roles,
            page=self.personal_info
        )
        self.assertTrue(personal_access.exists())

        # Should NOT have access to parent pages
        parent_access = JobRolePage.objects.filter(
            job_role__in=active_roles,
            page__in=[self.hr_module, self.employee_mgmt]
        )
        self.assertFalse(parent_access.exists())

        # Should NOT have access to sibling pages
        sibling_access = JobRolePage.objects.filter(
            job_role__in=active_roles,
            page=self.payroll
        )
        self.assertFalse(sibling_access.exists())

    def test_multiple_inheritance_levels(self):
        """Test inheritance through multiple levels of page hierarchy"""
        # Grant root access with inheritance
        JobRolePage.objects.create(
            job_role=self.hr_manager,
            page=self.hr_module,
            inherit_to_children=True
        )

        UserJobRole.objects.create(
            user=self.user,
            job_role=self.hr_manager,
            effective_start_date=timezone.now().date()
        )

        # Verify all levels are accessible
        descendants = self.hr_module.get_all_descendant_pages()

        # Should include:
        # Level 1: employee_mgmt, payroll
        # Level 2: personal_info
        self.assertIn(self.employee_mgmt, descendants)
        self.assertIn(self.personal_info, descendants)
        self.assertIn(self.payroll, descendants)

        # Verify depth of hierarchy
        # personal_info is 2 levels deep from hr_module
        ancestors = self.personal_info.get_all_ancestor_pages()
        self.assertEqual(len(ancestors), 2)

    def test_mixed_inheritance_settings(self):
        """Test scenario with both inherited and non-inherited page access"""
        # Grant HR Module with inheritance
        JobRolePage.objects.create(
            job_role=self.hr_manager,
            page=self.hr_module,
            inherit_to_children=True
        )

        # Grant specific page without inheritance
        JobRolePage.objects.create(
            job_role=self.hr_staff,
            page=self.personal_info,
            inherit_to_children=False
        )

        # Assign both roles to user
        UserJobRole.objects.create(
            user=self.user,
            job_role=self.hr_manager,
            effective_start_date=timezone.now().date()
        )
        UserJobRole.objects.create(
            user=self.user,
            job_role=self.hr_staff,
            effective_start_date=timezone.now().date()
        )

        from core.job_roles.services import get_user_active_roles
        active_roles = get_user_active_roles(self.user)

        # User should have 2 roles
        self.assertEqual(len(active_roles), 2)

        # Should have access through both paths
        role_pages = JobRolePage.objects.filter(
            job_role__in=active_roles
        )
        self.assertEqual(role_pages.count(), 2)

        # One with inheritance, one without
        with_inheritance = role_pages.filter(inherit_to_children=True).count()
        without_inheritance = role_pages.filter(inherit_to_children=False).count()
        self.assertEqual(with_inheritance, 1)
        self.assertEqual(without_inheritance, 1)



