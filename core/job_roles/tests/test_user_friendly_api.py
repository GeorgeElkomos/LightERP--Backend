"""
Tests for user-friendly API enhancements.
Tests verify that endpoints accept human-readable identifiers (names, emails)
in addition to IDs.
"""
from django.test import TestCase
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


class UserFriendlyJobRoleAPITests(APITestCase):
    """Test job role API endpoints with name-based lookups"""
    
    def setUp(self):
        """Set up test data"""
        # Create user type
        self.user_type = UserType.objects.create(type_name='user', description='Regular user')
        
        # Create admin user
        admin_type = UserType.objects.create(type_name='super_admin', description='Super Admin')
        self.admin_user = CustomUser.objects.create_user(
            email='admin@example.com',
            name='Admin User',
            phone_number='1111111111',
            password='admin123',
            user_type_name='super_admin'
        )
        
        # Create test data
        self.job_role = JobRole.objects.create(name='Accountant', description='Accounting role')
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.action = Action.objects.create(name='view', display_name='View')
        
        # Create test user
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='2222222222',
            password='test123',
            user_type_name='user'
        )
    
    def test_assign_page_to_job_role_by_name(self):
        """POST /job-roles/{id}/assign-page/ - Assign page using page_name"""
        data = {'page_name': 'invoice_page'}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        
        # Verify assignment exists
        self.assertTrue(
            JobRolePage.objects.filter(job_role=self.job_role, page=self.page).exists()
        )
    
    def test_assign_page_to_job_role_by_id(self):
        """POST /job-roles/{id}/assign-page/ - Assign page using page_id (backward compatible)"""
        data = {'page_id': self.page.id}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/assign-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_remove_page_from_job_role_by_name(self):
        """POST /job-roles/{id}/remove-page/ - Remove page using page_name"""
        JobRolePage.objects.create(job_role=self.job_role, page=self.page)
        
        data = {'page_name': 'invoice_page'}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/remove-page/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify assignment removed
        self.assertFalse(
            JobRolePage.objects.filter(job_role=self.job_role, page=self.page).exists()
        )
    
    def test_remove_multiple_pages_by_names(self):
        """POST /job-roles/{id}/remove-page/ - Remove multiple pages using page_names"""
        page2 = Page.objects.create(name='reports_page', display_name='Reports')
        JobRolePage.objects.create(job_role=self.job_role, page=self.page)
        JobRolePage.objects.create(job_role=self.job_role, page=page2)
        
        data = {'page_names': ['invoice_page', 'reports_page']}
        response = self.client.post(
            f'/core/job_roles/job-roles/{self.job_role.id}/remove-page/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['removed_count'], 2)
    
    def test_assign_job_role_by_email_and_name(self):
        """POST /job-roles/assign/ - Assign role using user_email and job_role_name"""
        self.client.force_authenticate(user=self.admin_user)
        
        data = {
            'user_email': 'test@example.com',
            'job_role_name': 'Accountant'
        }
        response = self.client.post('/core/job_roles/job-roles/assign/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify assignment
        self.user.refresh_from_db()
        self.assertEqual(self.user.job_role, self.job_role)
    
    def test_create_job_role_with_page_names(self):
        """POST /job-roles/with-pages/ - Create job role with page_names"""
        page2 = Page.objects.create(name='reports_page', display_name='Reports')
        
        data = {
            'name': 'Manager',
            'description': 'Management role',
            'page_names': ['invoice_page', 'reports_page']
        }
        response = self.client.post('/core/job_roles/job-roles/with-pages/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify job role created
        job_role = JobRole.objects.get(name='Manager')
        self.assertEqual(job_role.job_role_pages.count(), 2)


class UserFriendlyPageAPITests(APITestCase):
    """Test page API endpoints with name-based lookups"""
    
    def setUp(self):
        """Set up test data"""
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.action = Action.objects.create(name='view', display_name='View')
    
    def test_assign_action_to_page_by_name(self):
        """POST /pages/{id}/assign-action/ - Assign action using action_name"""
        data = {'action_name': 'view'}
        response = self.client.post(
            f'/core/job_roles/pages/{self.page.id}/assign-action/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify assignment exists
        self.assertTrue(
            PageAction.objects.filter(page=self.page, action=self.action).exists()
        )
    
    def test_assign_action_to_page_by_id(self):
        """POST /pages/{id}/assign-action/ - Assign action using action_id (backward compatible)"""
        data = {'action_id': self.action.id}
        response = self.client.post(
            f'/core/job_roles/pages/{self.page.id}/assign-action/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_remove_action_from_page_by_name(self):
        """POST /pages/{id}/remove-action/ - Remove action using action_name"""
        PageAction.objects.create(page=self.page, action=self.action)
        
        data = {'action_name': 'view'}
        response = self.client.post(
            f'/core/job_roles/pages/{self.page.id}/remove-action/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify assignment removed
        self.assertFalse(
            PageAction.objects.filter(page=self.page, action=self.action).exists()
        )


class UserFriendlyPageActionAPITests(APITestCase):
    """Test PageAction creation with name-based lookups"""
    
    def setUp(self):
        """Set up test data"""
        self.page = Page.objects.create(name='invoice_page', display_name='Invoices')
        self.action = Action.objects.create(name='view', display_name='View')
    
    def test_create_page_action_with_action_name(self):
        """POST /page-actions/ - Create PageAction using action_name"""
        data = {
            'page': self.page.id,
            'action_name': 'view'
        }
        response = self.client.post('/core/job_roles/page-actions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify PageAction created
        self.assertTrue(
            PageAction.objects.filter(page=self.page, action=self.action).exists()
        )


class UserFriendlyUserActionDenialAPITests(APITestCase):
    """Test UserActionDenial creation with name/email-based lookups"""
    
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
    
    def test_create_denial_with_email_and_names(self):
        """POST /user-action-denials/ - Create denial using user_email, page_name, action_name"""
        data = {
            'user_email': 'test@example.com',
            'page_name': 'invoice_page',
            'action_name': 'delete'
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify denial exists
        self.assertTrue(
            UserActionDenial.objects.filter(
                user=self.user,
                page_action=self.page_action
            ).exists()
        )
    
    def test_create_denial_with_ids(self):
        """POST /user-action-denials/ - Create denial using IDs (backward compatible)"""
        data = {
            'user': self.user.id,
            'page_action': self.page_action.id
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_create_denial_invalid_email(self):
        """POST /user-action-denials/ - Fail with invalid user_email"""
        data = {
            'user_email': 'nonexistent@example.com',
            'page_name': 'invoice_page',
            'action_name': 'delete'
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('user_email', str(response.data))
    
    def test_create_denial_invalid_page_name(self):
        """POST /user-action-denials/ - Fail with invalid page_name"""
        data = {
            'user_email': 'test@example.com',
            'page_name': 'nonexistent_page',
            'action_name': 'delete'
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('page_name', str(response.data))
    
    def test_create_denial_invalid_action_name(self):
        """POST /user-action-denials/ - Fail with invalid action_name"""
        data = {
            'user_email': 'test@example.com',
            'page_name': 'invoice_page',
            'action_name': 'nonexistent_action'
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('action_name', str(response.data))
    
    def test_create_denial_with_reason_using_names(self):
        """POST /user-action-denials/ - Create denial with reason using names/email"""
        data = {
            'user_email': 'test@example.com',
            'page_name': 'invoice_page',
            'action_name': 'delete',
            'denial_reason': 'New employee still learning the system'
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['denial_reason'], 'New employee still learning the system')
        
        # Verify denial exists with reason
        denial = UserActionDenial.objects.get(
            user=self.user,
            page_action=self.page_action
        )
        self.assertEqual(denial.denial_reason, 'New employee still learning the system')
    
    def test_create_denial_with_reason_using_ids(self):
        """POST /user-action-denials/ - Create denial with reason using IDs"""
        data = {
            'user': self.user.id,
            'page_action': self.page_action.id,
            'denial_reason': 'Restricted access due to audit period'
        }
        response = self.client.post('/core/job_roles/user-action-denials/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['denial_reason'], 'Restricted access due to audit period')


class MixedInputTests(APITestCase):
    """Test that mixing IDs and names works correctly"""
    
    def setUp(self):
        """Set up test data"""
        self.user_type = UserType.objects.create(type_name='user')
        self.job_role = JobRole.objects.create(name='Manager')
        self.page1 = Page.objects.create(name='page1', display_name='Page 1')
        self.page2 = Page.objects.create(name='page2', display_name='Page 2')
    
    def test_create_job_role_with_mixed_ids_and_names(self):
        """POST /job-roles/with-pages/ - Create with both page_ids and page_names"""
        page3 = Page.objects.create(name='page3', display_name='Page 3')
        
        data = {
            'name': 'SuperManager',
            'description': 'Super management role',
            'page_ids': [self.page1.id],
            'page_names': ['page2', 'page3']
        }
        response = self.client.post('/core/job_roles/job-roles/with-pages/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify all 3 pages assigned
        job_role = JobRole.objects.get(name='SuperManager')
        self.assertEqual(job_role.job_role_pages.count(), 3)
