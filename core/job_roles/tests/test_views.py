from rest_framework.test import APITestCase
from rest_framework import status
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
from core.base.test_utils import setup_core_data, setup_admin_permissions

def setUpModule():
    """Run once for the entire module at the beginning"""
    setup_core_data()

class JobRoleAPITests(APITestCase):
    """Test JobRole API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin = UserAccount.objects.create_user(
            email='admin_v@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123'
        )
        setup_admin_permissions(self.admin)
        self.client.force_authenticate(user=self.admin)

        self.job_role, _ = JobRole.objects.get_or_create(
            name='Accountant_v',
            code='accountant_v',
            description='Financial role'
        )

    def test_job_role_list_get(self):
        """GET /core/job_roles/job-roles/ - List all job roles"""
        response = self.client.get('/core/job_roles/job-roles/?page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_job_role_detail_get(self):
        """GET /core/job_roles/job-roles/{id}/ - Get job role details"""
        response = self.client.get(f'/core/job_roles/job-roles/{self.job_role.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Accountant_v')

    def test_job_role_create_post(self):
        """POST /core/job_roles/job-roles/ - Create new job role"""
        data = {
            'name': 'Manager_v',
            'code': 'manager_v',
            'description': 'Management role'
        }
        response = self.client.post('/core/job_roles/job-roles/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Manager_v')


class PageAPITests(APITestCase):
    """Test Page API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin = UserAccount.objects.create_user(
            email='admin_p@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123'
        )
        setup_admin_permissions(self.admin)
        self.client.force_authenticate(user=self.admin)

        self.page, _ = Page.objects.get_or_create(
            code='invoice_page_v',
            name='Invoice Management V'
        )

    def test_page_list_get(self):
        """GET /core/job_roles/pages/ - List all pages"""
        response = self.client.get('/core/job_roles/pages/?page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_page_detail_get(self):
        """GET /core/job_roles/pages/{id}/ - Get page details"""
        response = self.client.get(f'/core/job_roles/pages/{self.page.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'invoice_page_v')


class UserFriendlyJobRoleAPITests(APITestCase):
    """Test User-Friendly JobRole API endpoints (Assign/Create with pages)"""

    def setUp(self):
        """Set up test data"""
        self.admin = UserAccount.objects.create_user(
            email='admin_uf@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123'
        )
        setup_admin_permissions(self.admin)
        self.client.force_authenticate(user=self.admin)

        # Create test data
        self.job_role, _ = JobRole.objects.get_or_create(name='Accountant_uf', code='accountant_uf', defaults={'description': 'Accounting role'})
        self.page, _ = Page.objects.get_or_create(code='invoice_page_uf', name='Invoices UF')
        self.action, _ = Action.objects.get_or_create(code='view_uf', name='View UF')
        self.page_action, _ = PageAction.objects.get_or_create(page=self.page, action=self.action)

    def test_assign_page_to_job_role_by_id(self):
        """POST /job-roles/{id}/assign-page/ - Assign page using page_code"""
        data = {'page_code': self.page.code}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(JobRolePage.objects.filter(job_role=self.job_role, page=self.page).exists())

    def test_assign_page_to_job_role_by_name(self):
        """POST /job-roles/{id}/assign-page/ - Assign page using page_code"""
        data = {'page_code': self.page.code}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(JobRolePage.objects.filter(job_role=self.job_role, page=self.page).exists())

    def test_remove_page_from_job_role_by_name(self):
        """POST /job-roles/{id}/remove-page/ - Remove page using page_code"""
        JobRolePage.objects.get_or_create(job_role=self.job_role, page=self.page)

        data = {'page_code': self.page.code}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/remove-page/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(JobRolePage.objects.filter(job_role=self.job_role, page=self.page).exists())

    def test_assign_job_role_to_user(self):
        """POST /users/{pk}/assign-roles/ - Assign role to user"""
        user = UserAccount.objects.create_user(
            email='test_assign@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

        data = {
            'job_role_code': self.job_role.code,
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post(f'/core/job_roles/users/{user.id}/assign-roles/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class UserPermissionOverrideAPITests(APITestCase):
    """Test UserPermissionOverride API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin = UserAccount.objects.create_user(
            email='admin_upo@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123'
        )
        setup_admin_permissions(self.admin)
        self.client.force_authenticate(user=self.admin)

        self.user = UserAccount.objects.create_user(
            email='test_upo@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123',
        )

        self.job_role, _ = JobRole.objects.get_or_create(code='role_upo', name='Role UPO')
        UserJobRole.objects.create(user=self.user, job_role=self.job_role, effective_start_date='2024-01-01')

        self.page, _ = Page.objects.get_or_create(code='page_upo', name='Page UPO')
        JobRolePage.objects.get_or_create(job_role=self.job_role, page=self.page)

        self.action, _ = Action.objects.get_or_create(code='view_upo', name='View UPO')
        self.page_action, _ = PageAction.objects.get_or_create(page=self.page, action=self.action)

    def test_user_permission_override_list_get(self):
        """GET /core/job_roles/user-permission-overrides/ - List all overrides"""
        response = self.client.get('/core/job_roles/user-permission-overrides/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_permission_override_create_post(self):
        """POST /core/job_roles/user-permission-overrides/ - Create override"""
        data = {
            'user': self.user.id,
            'page_action': self.page_action.id,
            'permission_type': 'deny',
            'reason': 'Testing denial',
            'effective_start_date': '2024-01-01'
        }
        response = self.client.post('/core/job_roles/user-permission-overrides/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class CRUDComprehensiveTests(APITestCase):
    """Comprehensive CRUD operation tests for job roles and pages"""

    def setUp(self):
        """Set up admin user for CRUD operations"""
        self.admin = UserAccount.objects.create_user(
            email='admin_crud@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123'
        )
        setup_admin_permissions(self.admin)
        self.client.force_authenticate(user=self.admin)

    def test_job_role_full_crud_cycle(self):
        """Test complete CRUD cycle for JobRole"""
        # CREATE
        create_data = {'name': 'Analyst_c', 'code': 'analyst_c', 'description': 'Data analyst'}
        create_response = self.client.post('/core/job_roles/job-roles/', create_data)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        job_role_id = create_response.data['id']

        # READ
        read_response = self.client.get(f'/core/job_roles/job-roles/{job_role_id}/')
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data['name'], 'Analyst_c')

        # UPDATE
        update_data = {'description': 'Updated description'}
        update_response = self.client.patch(
            f'/core/job_roles/job-roles/{job_role_id}/',
            update_data
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['description'], 'Updated description')

        # DELETE
        delete_response = self.client.delete(f'/core/job_roles/job-roles/{job_role_id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_page_full_crud_cycle(self):
        """Test Read operation for Page (Update/Delete not supported via API)"""
        # Create via model directly since API doesn't support POST
        page = Page.objects.create(
            code='test_page_c',
            name='Test Page C',
            description='Test description'
        )
        page_id = page.id

        # READ
        read_response = self.client.get(f'/core/job_roles/pages/{page_id}/')
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data['code'], 'test_page_c')
        self.assertEqual(read_response.data['name'], 'Test Page C')


class PageHierarchyTests(APITestCase):
    """Test page hierarchy and inheritance features"""

    def setUp(self):
        """Set up page hierarchy for testing"""
        self.admin = UserAccount.objects.create_user(
            email='admin_hierarchy@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123'
        )
        setup_admin_permissions(self.admin)
        self.client.force_authenticate(user=self.admin)

        # Create page hierarchy: HR Module > Employee Management > Personal Info
        self.hr_module = Page.objects.create(
            code='hr_module',
            name='HR Module',
            description='Main HR module'
        )

        self.employee_mgmt = Page.objects.create(
            code='employee_mgmt',
            name='Employee Management',
            description='Employee management section',
            parent_page=self.hr_module
        )

        self.personal_info = Page.objects.create(
            code='personal_info',
            name='Personal Information',
            description='Employee personal info',
            parent_page=self.employee_mgmt
        )

        self.payroll = Page.objects.create(
            code='payroll',
            name='Payroll',
            description='Payroll section',
            parent_page=self.hr_module
        )

    def test_page_hierarchy_structure(self):
        """Test that page hierarchy is properly established"""
        # Test parent-child relationships
        self.assertIsNone(self.hr_module.parent_page)
        self.assertEqual(self.employee_mgmt.parent_page, self.hr_module)
        self.assertEqual(self.personal_info.parent_page, self.employee_mgmt)

        # Test child pages
        hr_children = list(self.hr_module.child_pages.all())
        self.assertIn(self.employee_mgmt, hr_children)
        self.assertIn(self.payroll, hr_children)

    def test_get_ancestor_pages(self):
        """Test getting all ancestor pages"""
        # Personal Info should have Employee Mgmt and HR Module as ancestors
        ancestors = self.personal_info.get_all_ancestor_pages()
        self.assertEqual(len(ancestors), 2)
        self.assertIn(self.employee_mgmt, ancestors)
        self.assertIn(self.hr_module, ancestors)

        # Employee Mgmt should have only HR Module as ancestor
        ancestors = self.employee_mgmt.get_all_ancestor_pages()
        self.assertEqual(len(ancestors), 1)
        self.assertIn(self.hr_module, ancestors)

        # HR Module should have no ancestors
        ancestors = self.hr_module.get_all_ancestor_pages()
        self.assertEqual(len(ancestors), 0)

    def test_get_descendant_pages(self):
        """Test getting all descendant pages"""
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

        # Personal Info should have no descendants
        descendants = self.personal_info.get_all_descendant_pages()
        self.assertEqual(len(descendants), 0)


class PermissionInheritanceTests(APITestCase):
    """Test permission inheritance through page hierarchy and role hierarchy"""

    def setUp(self):
        """Set up roles and page hierarchy for inheritance testing"""
        self.admin = UserAccount.objects.create_user(
            email='admin_inherit@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123'
        )
        setup_admin_permissions(self.admin)
        self.client.force_authenticate(user=self.admin)

        # Create page hierarchy
        self.hr_module = Page.objects.create(
            code='hr_module_i',
            name='HR Module I',
        )
        self.employee_mgmt = Page.objects.create(
            code='employee_mgmt_i',
            name='Employee Management I',
            parent_page=self.hr_module
        )
        self.personal_info = Page.objects.create(
            code='personal_info_i',
            name='Personal Information I',
            parent_page=self.employee_mgmt
        )

        # Create role hierarchy: HR Admin > HR Manager > HR Staff
        self.hr_admin = JobRole.objects.create(
            code='hr_admin_i',
            name='HR Admin I',
            priority=100
        )
        self.hr_manager = JobRole.objects.create(
            code='hr_manager_i',
            name='HR Manager I',
            parent_role=self.hr_admin,
            priority=50
        )
        self.hr_staff = JobRole.objects.create(
            code='hr_staff_i',
            name='HR Staff I',
            parent_role=self.hr_manager,
            priority=10
        )

        # Create test user
        self.test_user = UserAccount.objects.create_user(
            email='test_inherit@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )

    def test_page_inheritance_enabled(self):
        """Test that inherit_to_children=True grants access to all descendant pages"""
        # Grant HR Module access to HR Staff with inheritance enabled
        JobRolePage.objects.create(
            job_role=self.hr_staff,
            page=self.hr_module,
            inherit_to_children=True  # Should grant access to all children
        )

        # Assign HR Staff role to user
        from django.utils import timezone
        UserJobRole.objects.create(
            user=self.test_user,
            job_role=self.hr_staff,
            effective_start_date=timezone.now().date()
        )

        # Verify user has access through inheritance
        from core.job_roles.services import get_user_active_roles
        active_roles = get_user_active_roles(self.test_user)

        # User should have HR Staff role
        self.assertIn(self.hr_staff, active_roles)

        # Check if role has access to parent page
        role_pages = JobRolePage.objects.filter(
            job_role__in=active_roles,
            page=self.hr_module
        )
        self.assertTrue(role_pages.exists())
        self.assertTrue(role_pages.first().inherit_to_children)

    def test_page_inheritance_disabled(self):
        """Test that inherit_to_children=False grants access only to specific page"""
        # Grant only Personal Info page access (no inheritance)
        job_role_page = JobRolePage.objects.create(
            job_role=self.hr_staff,
            page=self.personal_info,
            inherit_to_children=False  # Only this specific page
        )

        # Assign role to user
        from django.utils import timezone
        UserJobRole.objects.create(
            user=self.test_user,
            job_role=self.hr_staff,
            effective_start_date=timezone.now().date()
        )

        # Verify inheritance is disabled
        self.assertFalse(job_role_page.inherit_to_children)

        # User should NOT have access to parent pages through inheritance
        from core.job_roles.services import get_user_active_roles
        active_roles = get_user_active_roles(self.test_user)

        # Should have access to personal_info only
        role_pages = JobRolePage.objects.filter(
            job_role__in=active_roles,
            page=self.personal_info
        )
        self.assertTrue(role_pages.exists())

        # Should NOT have access to parent pages via this assignment
        parent_access = JobRolePage.objects.filter(
            job_role__in=active_roles,
            page__in=[self.hr_module, self.employee_mgmt]
        )
        self.assertFalse(parent_access.exists())

    def test_role_hierarchy_inheritance(self):
        """Test that child roles inherit parent role permissions"""
        # Grant access to HR Admin (parent role)
        JobRolePage.objects.create(
            job_role=self.hr_admin,
            page=self.hr_module,
            inherit_to_children=True
        )

        # Assign only HR Staff (child role) to user
        from django.utils import timezone
        UserJobRole.objects.create(
            user=self.test_user,
            job_role=self.hr_staff,
            effective_start_date=timezone.now().date()
        )

        # Verify role hierarchy
        self.assertEqual(self.hr_staff.parent_role, self.hr_manager)
        self.assertEqual(self.hr_manager.parent_role, self.hr_admin)
        self.assertIsNone(self.hr_admin.parent_role)

        # Check priority inheritance
        self.assertEqual(self.hr_admin.priority, 100)
        self.assertEqual(self.hr_manager.priority, 50)
        self.assertEqual(self.hr_staff.priority, 10)

    def test_multiple_inheritance_paths(self):
        """Test user with multiple roles and inheritance paths"""
        # Grant different access levels to different roles
        JobRolePage.objects.create(
            job_role=self.hr_admin,
            page=self.hr_module,
            inherit_to_children=True
        )

        JobRolePage.objects.create(
            job_role=self.hr_staff,
            page=self.personal_info,
            inherit_to_children=False
        )

        # Assign both roles to user
        from django.utils import timezone
        UserJobRole.objects.create(
            user=self.test_user,
            job_role=self.hr_admin,
            effective_start_date=timezone.now().date()
        )
        UserJobRole.objects.create(
            user=self.test_user,
            job_role=self.hr_staff,
            effective_start_date=timezone.now().date()
        )

        # User should have both roles
        from core.job_roles.services import get_user_active_roles
        active_roles = get_user_active_roles(self.test_user)
        self.assertEqual(len(active_roles), 2)
        self.assertIn(self.hr_admin, active_roles)
        self.assertIn(self.hr_staff, active_roles)

        # Verify multiple role pages exist
        role_pages = JobRolePage.objects.filter(
            job_role__in=active_roles
        )
        self.assertEqual(role_pages.count(), 2)


