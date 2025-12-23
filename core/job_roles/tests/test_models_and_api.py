"""
Tests for Job Roles and Permissions module.

Tests verify:
- Model creation and relationships
- Permission logic and validation rules
- API endpoints for CRUD operations
- Deletion protection mechanisms
"""
from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status

from ..models import (
    JobRole,
    Page,
    Action,
    PageAction,
    JobRolePage,
    UserActionDenial,
)
from core.user_accounts.models import CustomUser, UserType


# ============================================================================
# Model Tests
# ============================================================================

class JobRoleModelTests(TestCase):
    """Tests for JobRole model"""
    
    def test_create_job_role(self):
        """Test creating a job role"""
        job_role = JobRole.objects.create(
            name='Accountant',
            description='Handles financial records'
        )
        self.assertEqual(str(job_role), 'Accountant')
        self.assertEqual(job_role.name, 'Accountant')
        self.assertIsNotNone(job_role.created_at)
        self.assertIsNotNone(job_role.updated_at)
    
    def test_job_role_unique_name(self):
        """Test that job role names must be unique"""
        JobRole.objects.create(name='Accountant')
        
        with self.assertRaises(IntegrityError):
            JobRole.objects.create(name='Accountant')
    
    def test_job_role_prevent_deletion_if_assigned(self):
        """Test that job roles with assigned users cannot be deleted"""
        # Create user type first
        UserType.objects.get_or_create(type_name='user', defaults={'description': 'Regular user'})
        
        # Create job role
        job_role = JobRole.objects.create(name='Manager')
        
        # Create user with this job role
        user = CustomUser.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123',
            user_type_name='user'
        )
        user.job_role = job_role
        user.save()
        
        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            job_role.delete()
        
        self.assertIn('Cannot delete job role', str(context.exception))


class PageModelTests(TestCase):
    """Tests for Page model"""
    
    def test_create_page(self):
        """Test creating a page"""
        page = Page.objects.create(
            name='invoice_management',
            display_name='Invoice Management',
            description='Manage invoices'
        )
        self.assertEqual(page.name, 'invoice_management')
        self.assertIn('Invoice Management', str(page))
        self.assertIsNotNone(page.created_at)
    
    def test_page_unique_name(self):
        """Test that page names must be unique"""
        Page.objects.create(name='invoice_management', display_name='Invoices')
        
        with self.assertRaises(IntegrityError):
            Page.objects.create(name='invoice_management', display_name='Invoices 2')
    
    def test_page_prevent_deletion_if_linked(self):
        """Test that pages linked to job roles cannot be deleted"""
        job_role = JobRole.objects.create(name='Accountant')
        page = Page.objects.create(name='invoice_page', display_name='Invoices')
        
        # Link page to job role
        JobRolePage.objects.create(job_role=job_role, page=page)
        
        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            page.delete()
        
        self.assertIn('Cannot delete page', str(context.exception))


class ActionModelTests(TestCase):
    """Tests for Action model"""
    
    def test_create_action(self):
        """Test creating an action"""
        action = Action.objects.create(
            name='view',
            display_name='View',
            description='View records'
        )
        self.assertEqual(action.name, 'view')
        self.assertIn('View', str(action))
        self.assertIsNotNone(action.created_at)
    
    def test_action_unique_name(self):
        """Test that action names must be unique"""
        Action.objects.create(name='view', display_name='View')
        
        with self.assertRaises(IntegrityError):
            Action.objects.create(name='view', display_name='View Again')
    
    def test_action_prevent_deletion_if_linked(self):
        """Test that actions linked to pages cannot be deleted"""
        action = Action.objects.create(name='view', display_name='View')
        page = Page.objects.create(name='invoice_page', display_name='Invoices')
        
        # Link action to page
        PageAction.objects.create(page=page, action=action)
        
        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            action.delete()
        
        self.assertIn('Cannot delete action', str(context.exception))


class PageActionModelTests(TestCase):
    """Tests for PageAction model"""
    
    def setUp(self):
        """Set up test data"""
        self.page = Page.objects.create(
            name='invoice_management',
            display_name='Invoice Management'
        )
        self.action = Action.objects.create(
            name='view',
            display_name='View'
        )
    
    def test_create_page_action(self):
        """Test linking an action to a page"""
        page_action = PageAction.objects.create(
            page=self.page,
            action=self.action
        )
        self.assertEqual(page_action.page, self.page)
        self.assertEqual(page_action.action, self.action)
        self.assertIsNotNone(page_action.created_at)
    
    def test_unique_page_action(self):
        """Test that page-action combination is unique"""
        PageAction.objects.create(page=self.page, action=self.action)
        
        # Attempting to create duplicate should fail
        with self.assertRaises(IntegrityError):
            PageAction.objects.create(page=self.page, action=self.action)
    
    def test_page_action_string_representation(self):
        """Test the string representation of PageAction"""
        page_action = PageAction.objects.create(page=self.page, action=self.action)
        expected_str = f"{self.page.name} - {self.action.display_name}"
        self.assertEqual(str(page_action), expected_str)
    
    def test_page_action_prevent_deletion_if_has_denials(self):
        """Test that page actions with user denials cannot be deleted"""
        # Create user type first
        UserType.objects.get_or_create(type_name='user', defaults={'description': 'Regular user'})
        
        # Create page action
        page_action = PageAction.objects.create(page=self.page, action=self.action)
        
        # Create user
        user = CustomUser.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123',
            user_type_name='user'
        )
        
        # Create user action denial
        UserActionDenial.objects.create(user=user, page_action=page_action)
        
        # Attempt to delete should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            page_action.delete()
        
        self.assertIn('Cannot delete page action', str(context.exception))


class JobRolePageModelTests(TestCase):
    """Tests for JobRolePage model"""
    
    def setUp(self):
        """Set up test data"""
        self.job_role = JobRole.objects.create(name='Accountant')
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
    
    def test_create_job_role_page(self):
        """Test linking a page to a job role"""
        job_role_page = JobRolePage.objects.create(
            job_role=self.job_role,
            page=self.page
        )
        self.assertEqual(job_role_page.job_role, self.job_role)
        self.assertEqual(job_role_page.page, self.page)
    
    def test_unique_job_role_page(self):
        """Test that job_role-page combination is unique"""
        JobRolePage.objects.create(job_role=self.job_role, page=self.page)
        
        with self.assertRaises(IntegrityError):
            JobRolePage.objects.create(job_role=self.job_role, page=self.page)


class UserActionDenialModelTests(TestCase):
    """Tests for UserActionDenial model"""
    
    def setUp(self):
        """Set up test data"""
        # Create user type
        self.user_type, _ = UserType.objects.get_or_create(type_name='user', defaults={'description': 'Regular user'})
        
        # Create user
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123',
            user_type_name='user'
        )
        
        # Create page and action
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.action = Action.objects.create(name='delete', display_name='Delete')
        self.page_action = PageAction.objects.create(page=self.page, action=self.action)
    
    def test_create_user_action_denial(self):
        """Test creating a user action denial"""
        denial = UserActionDenial.objects.create(
            user=self.user,
            page_action=self.page_action
        )
        self.assertEqual(denial.user, self.user)
        self.assertEqual(denial.page_action, self.page_action)
        self.assertIsNotNone(denial.created_at)
    
    def test_unique_user_page_action(self):
        """Test that user-page_action combination is unique"""
        UserActionDenial.objects.create(user=self.user, page_action=self.page_action)
        
        with self.assertRaises(IntegrityError):
            UserActionDenial.objects.create(user=self.user, page_action=self.page_action)


# ============================================================================
# API Tests
# ============================================================================

class JobRoleAPITests(APITestCase):
    """Test JobRole API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.job_role = JobRole.objects.create(
            name='Accountant',
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
        self.assertEqual(response.data['name'], 'Accountant')
    
    def test_job_role_create_post(self):
        """POST /core/job_roles/job-roles/ - Create new job role"""
        data = {
            'name': 'Manager',
            'description': 'Management role'
        }
        response = self.client.post('/core/job_roles/job-roles/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Manager')


class PageAPITests(APITestCase):
    """Test Page API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.page = Page.objects.create(
            name='invoice_page',
            display_name='Invoice Management'
        )
    
    def test_page_list_get(self):
        """GET /core/job_roles/pages/ - List all pages"""
        response = self.client.get('/core/job_roles/pages/?page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_page_detail_get(self):
        """GET /core/job_roles/pages/{id}/ - Get page details"""
        response = self.client.get(f'/core/job_roles/pages/{self.page.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'invoice_page')


class ActionAPITests(APITestCase):
    """Test Action API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.action = Action.objects.create(
            name='view',
            display_name='View'
        )
    
    def test_action_list_get(self):
        """GET /core/job_roles/actions/ - List all actions"""
        response = self.client.get('/core/job_roles/actions/?page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_action_detail_get(self):
        """GET /core/job_roles/actions/{id}/ - Get action details"""
        response = self.client.get(f'/core/job_roles/actions/{self.action.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'view')
    
    def test_action_create_post(self):
        """POST /core/job_roles/actions/ - Create new action"""
        data = {
            'name': 'delete',
            'display_name': 'Delete',
            'description': 'Delete records'
        }
        response = self.client.post('/core/job_roles/actions/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'delete')
    
    def test_action_update_patch(self):
        """PATCH /core/job_roles/actions/{id}/ - Update action"""
        data = {'description': 'Updated description'}
        response = self.client.patch(f'/core/job_roles/actions/{self.action.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated description')
    
    def test_action_delete(self):
        """DELETE /core/job_roles/actions/{id}/ - Delete action"""
        action = Action.objects.create(name='temp', display_name='Temp')
        response = self.client.delete(f'/core/job_roles/actions/{action.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Action.objects.filter(id=action.id).exists())
    
    def test_action_list_filter_by_name(self):
        """GET /core/job_roles/actions/?name=view - Filter by name"""
        Action.objects.create(name='create', display_name='Create')
        response = self.client.get('/core/job_roles/actions/?name=view&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_action_list_search(self):
        """GET /core/job_roles/actions/?search=view - Search actions"""
        Action.objects.create(name='create', display_name='Create')
        response = self.client.get('/core/job_roles/actions/?search=view&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PageActionAPITests(APITestCase):
    """Test PageAction API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.action = Action.objects.create(name='view', display_name='View')
        self.page_action = PageAction.objects.create(page=self.page, action=self.action)
    
    def test_page_action_list_get(self):
        """GET /core/job_roles/page-actions/ - List all page-actions"""
        response = self.client.get('/core/job_roles/page-actions/?page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_page_action_detail_get(self):
        """GET /core/job_roles/page-actions/{id}/ - Get page-action details"""
        response = self.client.get(f'/core/job_roles/page-actions/{self.page_action.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_page_action_create_post(self):
        """POST /core/job_roles/page-actions/ - Create new page-action"""
        action2 = Action.objects.create(name='create', display_name='Create')
        data = {
            'page': self.page.id,
            'action_id': action2.id
        }
        response = self.client.post('/core/job_roles/page-actions/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_page_action_filter_by_page(self):
        """GET /core/job_roles/page-actions/?page={id} - Filter by page"""
        response = self.client.get(f'/core/job_roles/page-actions/?page={self.page.id}&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_page_action_filter_by_action(self):
        """GET /core/job_roles/page-actions/?action={id} - Filter by action"""
        response = self.client.get(f'/core/job_roles/page-actions/?action={self.action.id}&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class JobRolePageAPITests(APITestCase):
    """Test Job Role Page assignment API"""
    
    def setUp(self):
        """Set up test data"""
        self.job_role = JobRole.objects.create(name='Accountant')
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
    
    def test_assign_page_to_job_role(self):
        """POST /core/job_roles/job-roles/{id}/assign-page/ - Assign page"""
        data = {'page_id': self.page.id}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'Page assigned successfully')
        
        # Verify assignment exists
        self.assertTrue(
            JobRolePage.objects.filter(job_role=self.job_role, page=self.page).exists()
        )
    
    def test_assign_page_already_assigned(self):
        """POST /core/job_roles/job-roles/{id}/assign-page/ - Assign already assigned page"""
        JobRolePage.objects.create(job_role=self.job_role, page=self.page)
        
        data = {'page_id': self.page.id}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Page already assigned')
    
    def test_assign_page_missing_page_id(self):
        """POST /core/job_roles/job-roles/{id}/assign-page/ - Missing page_id"""
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            {}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('page_id is required', response.data['error'])
    
    def test_assign_nonexistent_page(self):
        """POST /core/job_roles/job-roles/{id}/assign-page/ - Nonexistent page"""
        data = {'page_id': 99999}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_remove_page_from_job_role(self):
        """POST /core/job_roles/job-roles/{id}/remove-page/ - Remove page"""
        JobRolePage.objects.create(job_role=self.job_role, page=self.page)
        
        data = {'page_id': self.page.id}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/remove-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Page removed successfully')
        
        # Verify assignment removed
        self.assertFalse(
            JobRolePage.objects.filter(job_role=self.job_role, page=self.page).exists()
        )
    
    def test_remove_page_not_assigned(self):
        """POST /core/job_roles/job-roles/{id}/remove-page/ - Remove unassigned page"""
        data = {'page_id': self.page.id}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/remove-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PageActionAssignmentAPITests(APITestCase):
    """Test Page Action assignment API"""
    
    def setUp(self):
        """Set up test data"""
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.action = Action.objects.create(name='view', display_name='View')
    
    def test_assign_action_to_page(self):
        """POST /core/job_roles/pages/{id}/assign-action/ - Assign action"""
        data = {'action_id': self.action.id}
        response = self.client.post(
            f'/core/job_roles/pages/{self.page.id}/assign-action/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'Action assigned successfully')
        
        # Verify assignment exists
        self.assertTrue(
            PageAction.objects.filter(page=self.page, action=self.action).exists()
        )
    
    def test_assign_action_already_assigned(self):
        """POST /core/job_roles/pages/{id}/assign-action/ - Assign already assigned action"""
        PageAction.objects.create(page=self.page, action=self.action)
        
        data = {'action_id': self.action.id}
        response = self.client.post(
            f'/core/job_roles/pages/{self.page.id}/assign-action/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Action already assigned')
    
    def test_assign_action_missing_action_id(self):
        """POST /core/job_roles/pages/{id}/assign-action/ - Missing action_id"""
        response = self.client.post(
            f'/core/job_roles/pages/{self.page.id}/assign-action/',
            {}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_remove_action_from_page(self):
        """POST /core/job_roles/pages/{id}/remove-action/ - Remove action"""
        PageAction.objects.create(page=self.page, action=self.action)
        
        data = {'action_id': self.action.id}
        response = self.client.post(
            f'/core/job_roles/pages/{self.page.id}/remove-action/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Action removed successfully')
        
        # Verify assignment removed
        self.assertFalse(
            PageAction.objects.filter(page=self.page, action=self.action).exists()
        )


class UserActionDenialAPITests(APITestCase):
    """Test UserActionDenial API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        # Create user type
        self.user_type = UserType.objects.create(type_name='user', description='Regular user')
        
        # Create job role and page
        self.job_role = JobRole.objects.create(name='Accountant')
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.action = Action.objects.create(name='delete', display_name='Delete')
        self.page_action = PageAction.objects.create(page=self.page, action=self.action)
        
        # Link page to job role
        JobRolePage.objects.create(job_role=self.job_role, page=self.page)
        
        # Create user with job role
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123',
            user_type_name='user'
        )
        self.user.job_role = self.job_role
        self.user.save()
    
    def test_user_action_denial_list_get(self):
        """GET /core/job_roles/user-action-denials/ - List all denials"""
        response = self.client.get('/core/job_roles/user-action-denials/?page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_action_denial_create_post(self):
        """POST /core/job_roles/user-action-denials/ - Create denial"""
        data = {
            'user': self.user.id,
            'page_action': self.page_action.id
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify denial exists
        self.assertTrue(
            UserActionDenial.objects.filter(
                user=self.user,
                page_action=self.page_action
            ).exists()
        )
    
    def test_user_action_denial_create_without_page_access(self):
        """POST /core/job_roles/user-action-denials/ - Deny action on page user can't access"""
        # Create another page not assigned to user's job role
        other_page = Page.objects.create(name='hr_page', display_name='HR')
        other_action = Action.objects.create(name='view', display_name='View')
        other_page_action = PageAction.objects.create(page=other_page, action=other_action)
        
        data = {
            'user': self.user.id,
            'page_action': other_page_action.id
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('does not have access to page', str(response.data))
    
    def test_user_action_denial_create_user_without_job_role(self):
        """POST /core/job_roles/user-action-denials/ - User without job role"""
        # Create user without job role
        user2 = CustomUser.objects.create_user(
            email='test2@example.com',
            name='Test User 2',
            phone_number='0987654321',
            password='testpass123',
            user_type_name='user'
        )
        
        data = {
            'user': user2.id,
            'page_action': self.page_action.id
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('has no job role assigned', str(response.data))
    
    def test_user_action_denial_detail_get(self):
        """GET /core/job_roles/user-action-denials/{id}/ - Get denial details"""
        denial = UserActionDenial.objects.create(
            user=self.user,
            page_action=self.page_action
        )
        response = self.client.get(f'/core/job_roles/user-action-denials/{denial.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user'], self.user.id)
    
    def test_user_action_denial_delete(self):
        """DELETE /core/job_roles/user-action-denials/{id}/ - Remove denial"""
        denial = UserActionDenial.objects.create(
            user=self.user,
            page_action=self.page_action
        )
        response = self.client.delete(f'/core/job_roles/user-action-denials/{denial.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify denial removed
        self.assertFalse(UserActionDenial.objects.filter(id=denial.id).exists())
    
    def test_user_action_denial_filter_by_user(self):
        """GET /core/job_roles/user-action-denials/?user={id} - Filter by user"""
        UserActionDenial.objects.create(user=self.user, page_action=self.page_action)
        
        response = self.client.get(
            f'/core/job_roles/user-action-denials/?user={self.user.id}&page_size=100'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_action_denial_filter_by_page(self):
        """GET /core/job_roles/user-action-denials/?page={id} - Filter by page"""
        UserActionDenial.objects.create(user=self.user, page_action=self.page_action)
        
        response = self.client.get(
            f'/core/job_roles/user-action-denials/?page={self.page.id}&page_size=100'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_action_denial_filter_by_action(self):
        """GET /core/job_roles/user-action-denials/?action={id} - Filter by action"""
        UserActionDenial.objects.create(user=self.user, page_action=self.page_action)
        
        response = self.client.get(
            f'/core/job_roles/user-action-denials/?action={self.action.id}&page_size=100'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_action_denial_with_reason(self):
        """POST /core/job_roles/user-action-denials/ - Create denial with reason"""
        data = {
            'user': self.user.id,
            'page_action': self.page_action.id,
            'denial_reason': 'User is still in training and should not delete invoices yet'
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['denial_reason'], 'User is still in training and should not delete invoices yet')
        
        # Verify denial exists with reason
        denial = UserActionDenial.objects.get(
            user=self.user,
            page_action=self.page_action
        )
        self.assertEqual(denial.denial_reason, 'User is still in training and should not delete invoices yet')
    
    def test_user_action_denial_without_reason(self):
        """POST /core/job_roles/user-action-denials/ - Create denial without reason (optional)"""
        data = {
            'user': self.user.id,
            'page_action': self.page_action.id
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify denial exists without reason
        denial = UserActionDenial.objects.get(
            user=self.user,
            page_action=self.page_action
        )
        self.assertIsNone(denial.denial_reason)
    
    def test_user_action_denial_detail_includes_reason(self):
        """GET /core/job_roles/user-action-denials/{id}/ - Retrieve denial with reason"""
        denial = UserActionDenial.objects.create(
            user=self.user,
            page_action=self.page_action,
            denial_reason='Temporary restriction during audit period'
        )
        response = self.client.get(f'/core/job_roles/user-action-denials/{denial.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['denial_reason'], 'Temporary restriction during audit period')


# ============================================================================
# Edge Case and Integration Tests
# ============================================================================

class PermissionLogicIntegrationTests(TestCase):
    """Test the complete permission logic flow"""
    
    def setUp(self):
        """Set up comprehensive test scenario"""
        # Create user type
        self.user_type = UserType.objects.create(type_name='user')
        
        # Create job roles
        self.accountant_role = JobRole.objects.create(name='Accountant')
        self.manager_role = JobRole.objects.create(name='Manager')
        
        # Create pages
        self.invoice_page = Page.objects.create(
            name='invoice_page',
            display_name='Invoice Management'
        )
        self.report_page = Page.objects.create(
            name='report_page',
            display_name='Reports'
        )
        
        # Create actions
        self.view_action = Action.objects.create(name='view', display_name='View')
        self.create_action = Action.objects.create(name='create', display_name='Create')
        self.edit_action = Action.objects.create(name='edit', display_name='Edit')
        self.delete_action = Action.objects.create(name='delete', display_name='Delete')
        
        # Link actions to invoice page
        self.invoice_view = PageAction.objects.create(
            page=self.invoice_page, action=self.view_action
        )
        self.invoice_create = PageAction.objects.create(
            page=self.invoice_page, action=self.create_action
        )
        self.invoice_edit = PageAction.objects.create(
            page=self.invoice_page, action=self.edit_action
        )
        self.invoice_delete = PageAction.objects.create(
            page=self.invoice_page, action=self.delete_action
        )
        
        # Grant invoice page to accountant role
        JobRolePage.objects.create(
            job_role=self.accountant_role,
            page=self.invoice_page
        )
        
        # Grant report page to manager role
        JobRolePage.objects.create(
            job_role=self.manager_role,
            page=self.report_page
        )
        
        # Create users
        self.accountant_user = CustomUser.objects.create_user(
            email='accountant@example.com',
            name='Accountant User',
            phone_number='1111111111',
            password='pass123',
            user_type_name='user'
        )
        self.accountant_user.job_role = self.accountant_role
        self.accountant_user.save()
        
        self.manager_user = CustomUser.objects.create_user(
            email='manager@example.com',
            name='Manager User',
            phone_number='2222222222',
            password='pass123',
            user_type_name='user'
        )
        self.manager_user.job_role = self.manager_role
        self.manager_user.save()
    
    def test_user_has_page_access_via_job_role(self):
        """Test that user can access pages granted to their job role"""
        # Accountant should have access to invoice page
        job_role_pages = JobRolePage.objects.filter(
            job_role=self.accountant_user.job_role,
            page=self.invoice_page
        )
        self.assertTrue(job_role_pages.exists())
        
        # Manager should NOT have access to invoice page
        job_role_pages = JobRolePage.objects.filter(
            job_role=self.manager_user.job_role,
            page=self.invoice_page
        )
        self.assertFalse(job_role_pages.exists())
    
    def test_user_action_denial_removes_specific_permission(self):
        """Test that action denial removes permission for specific user"""
        # Deny delete action for accountant on invoice page
        UserActionDenial.objects.create(
            user=self.accountant_user,
            page_action=self.invoice_delete
        )
        
        # Verify denial exists
        denials = UserActionDenial.objects.filter(
            user=self.accountant_user,
            page_action__page=self.invoice_page,
            page_action__action=self.delete_action
        )
        self.assertTrue(denials.exists())
        
        # User should still have other actions
        denials_view = UserActionDenial.objects.filter(
            user=self.accountant_user,
            page_action__action=self.view_action
        )
        self.assertFalse(denials_view.exists())
    
    def test_multiple_users_different_denials_same_page(self):
        """Test different users can have different action denials on same page"""
        # Create another accountant
        accountant2 = CustomUser.objects.create_user(
            email='accountant2@example.com',
            name='Accountant 2',
            phone_number='3333333333',
            password='pass123',
            user_type_name='user'
        )
        accountant2.job_role = self.accountant_role
        accountant2.save()
        
        # Deny delete for user 1
        UserActionDenial.objects.create(
            user=self.accountant_user,
            page_action=self.invoice_delete
        )
        
        # Deny edit for user 2
        UserActionDenial.objects.create(
            user=accountant2,
            page_action=self.invoice_edit
        )
        
        # Verify each user has different denials
        user1_denials = UserActionDenial.objects.filter(
            user=self.accountant_user
        ).values_list('page_action__action__name', flat=True)
        self.assertIn('delete', user1_denials)
        self.assertNotIn('edit', user1_denials)
        
        user2_denials = UserActionDenial.objects.filter(
            user=accountant2
        ).values_list('page_action__action__name', flat=True)
        self.assertIn('edit', user2_denials)
        self.assertNotIn('delete', user2_denials)
    
    def test_reusable_actions_across_pages(self):
        """Test that same action can be used by multiple pages"""
        # Link view action to report page
        PageAction.objects.create(page=self.report_page, action=self.view_action)
        
        # Verify view action is linked to both pages
        pages_with_view = PageAction.objects.filter(
            action=self.view_action
        ).values_list('page__name', flat=True)
        
        self.assertIn('invoice_page', pages_with_view)
        self.assertIn('report_page', pages_with_view)
    
    def test_cascading_delete_job_role_page(self):
        """Test that deleting JobRolePage doesn't affect other relationships"""
        job_role_page = JobRolePage.objects.get(
            job_role=self.accountant_role,
            page=self.invoice_page
        )
        job_role_page.delete()
        
        # JobRole and Page should still exist
        self.assertTrue(JobRole.objects.filter(id=self.accountant_role.id).exists())
        self.assertTrue(Page.objects.filter(id=self.invoice_page.id).exists())
        
        # User should still exist but have no page access via this role
        self.assertTrue(CustomUser.objects.filter(id=self.accountant_user.id).exists())
        remaining_access = JobRolePage.objects.filter(
            job_role=self.accountant_role,
            page=self.invoice_page
        )
        self.assertFalse(remaining_access.exists())


class CRUDComprehensiveTests(APITestCase):
    """Comprehensive CRUD operation tests"""
    
    def test_job_role_full_crud_cycle(self):
        """Test complete CRUD cycle for JobRole"""
        # CREATE
        create_data = {'name': 'Analyst', 'description': 'Data analyst'}
        create_response = self.client.post('/core/job_roles/job-roles/', create_data)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        job_role_id = create_response.data['id']
        
        # READ (detail)
        read_response = self.client.get(f'/core/job_roles/job-roles/{job_role_id}/')
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data['name'], 'Analyst')
        
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
        
        # Verify deletion
        get_response = self.client.get(f'/core/job_roles/job-roles/{job_role_id}/')
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_page_full_crud_cycle(self):
        """Test complete CRUD cycle for Page"""
        # CREATE
        create_data = {
            'name': 'test_page',
            'display_name': 'Test Page',
            'description': 'Test description'
        }
        create_response = self.client.post('/core/job_roles/pages/', create_data)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        page_id = create_response.data['id']
        
        # READ
        read_response = self.client.get(f'/core/job_roles/pages/{page_id}/')
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        
        # UPDATE
        update_data = {'display_name': 'Updated Test Page'}
        update_response = self.client.patch(f'/core/job_roles/pages/{page_id}/', update_data)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        
        # DELETE
        delete_response = self.client.delete(f'/core/job_roles/pages/{page_id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
