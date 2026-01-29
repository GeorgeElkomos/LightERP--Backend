"""
Tests for User Account API Views.
Covers registration, login, profile management, and admin operations.
"""
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from core.base.test_utils import setup_core_data, setup_admin_permissions
from django.contrib.auth import get_user_model

User = get_user_model()


def setUpModule():
    """Run once for the entire module at the beginning"""
    setup_core_data()


class RegistrationAPITest(APITestCase):
    """Test user registration endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.url = '/auth/register/'
        self.valid_data = {
            'email': 'newuser@example.com',
            'name': 'New User',
            'phone_number': '+1234567890',
            'password': 'SecurePass123',
            'confirm_password': 'SecurePass123'
        }

    def test_register_user_success(self):
        """Test successful user registration"""
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'newuser@example.com')
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])

    def test_register_duplicate_email(self):
        """Test registration with duplicate email"""
        self.client.post(self.url, self.valid_data, format='json')
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class LoginAPITest(APITestCase):
    """Test user login endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.url = '/auth/login/'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )

    def test_login_success(self):
        """Test successful login"""
        data = {'email': 'testuser@example.com', 'password': 'TestPass123'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)

class TokenRefreshAPITest(APITestCase):
    """Test JWT token refresh endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.url = '/auth/token/refresh/'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )
        self.refresh = RefreshToken.for_user(self.user)

    def test_refresh_token_success(self):
        """Test successful token refresh"""
        data = {'refresh': str(self.refresh)}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

class LogoutAPITest(APITestCase):
    """Test logout endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.url = '/auth/logout/'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )
        self.refresh = RefreshToken.for_user(self.user)
        self.access_token = str(self.refresh.access_token)

    def test_logout_success(self):
        """Test successful logout"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        data = {'refresh': str(self.refresh)}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class UserProfileAPITest(APITestCase):
    """Test user profile endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.url = '/accounts/profile/'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

    def test_get_profile_success(self):
        """Test getting user profile"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'testuser@example.com')

class ChangePasswordAPITest(APITestCase):
    """Test password change endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.url = '/auth/change-password/'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='OldPass123'
        )
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

    def test_change_password_success(self):
        """Test successful password change"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        data = {
            'old_password': 'OldPass123',
            'new_password': 'NewPass456',
            'confirm_password': 'NewPass456'
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456'))

class PasswordResetAPITests(APITestCase):
    """Test password reset request and admin reset"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='target@example.com',
            name='Target User',
            phone_number='+4444444444',
            password='OldPass123'
        )
        self.super_admin = User.objects.create_superuser(
            email='admin@example.com',
            name='Admin',
            phone_number='+1111111111',
            password='SuperPass123'
        )
        setup_admin_permissions(self.super_admin)

    def test_password_reset_request_success(self):
        """Test user requesting a password reset"""
        url = '/accounts/password-reset-request/'
        data = {'email': 'target@example.com', 'reason': 'Forgot password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('submitted to the admin', response.data['message'])

    def test_admin_password_reset_success(self):
        """Test admin setting temporary password"""
        refresh = RefreshToken.for_user(self.super_admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
        url = '/accounts/admin/password-reset/'
        data = {'user_id': self.user.id, 'temporary_password': 'TempPass123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('TempPass123'))

class AdminUserManagementAPITest(APITestCase):
    """Test admin user management (list, create, update, delete)"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@example.com',
            name='Admin User',
            phone_number='+2222222222',
            password='AdminPass123'
        )
        setup_admin_permissions(self.admin)
        self.target_user = User.objects.create_user(
            email='target@example.com',
            name='Target User',
            phone_number='+4444444444',
            password='TargetPass123'
        )
        refresh = RefreshToken.for_user(self.admin)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def test_list_users(self):
        """Test listing all users as admin"""
        url = '/accounts/admin/users/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)

    def test_update_user(self):
        """Test updating a user as admin"""
        url = f'/accounts/admin/users/{self.target_user.id}/'
        response = self.client.patch(url, {'name': 'Updated Target'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.name, 'Updated Target')

    def test_delete_user(self):
        """Test soft deleting a user as admin"""
        url = f'/accounts/admin/users/{self.target_user.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        from core.base.models import StatusChoices
        self.assertEqual(self.target_user.status, StatusChoices.INACTIVE)

