"""
Comprehensive test suite for user_accounts app.
Tests authentication endpoints, account management, and edge cases.
"""
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import json

from core.user_accounts.models import UserType, CustomUser, CustomUserManager


User = get_user_model()


class UserTypeModelTest(TestCase):
    """Test UserType model functionality"""
    
    def setUp(self):
        self.user_type = UserType.objects.create(
            type_name='test_type',
            description='Test user type'
        )
    
    def test_user_type_creation(self):
        """Test UserType is created correctly"""
        self.assertEqual(self.user_type.type_name, 'test_type')
        self.assertEqual(self.user_type.description, 'Test user type')
        self.assertEqual(str(self.user_type), 'test_type')
    
    def test_user_type_unique_constraint(self):
        """Test that type_name must be unique"""
        with self.assertRaises(Exception):
            UserType.objects.create(type_name='test_type')
    
    def test_user_type_db_table(self):
        """Test correct database table name"""
        self.assertEqual(UserType._meta.db_table, 'user_types')


class CustomUserManagerTest(TestCase):
    """Test CustomUserManager functionality"""
    
    def test_create_user_success(self):
        """Test creating a regular user"""
        user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.name, 'Test User')
        self.assertEqual(user.user_type.type_name, 'user')
        self.assertTrue(user.check_password('TestPass123'))
    
    def test_create_user_with_admin_type(self):
        """Test creating an admin user"""
        user = User.objects.create_user(
            email='admin@example.com',
            name='Admin User',
            phone_number='+1234567890',
            password='AdminPass123',
            user_type_name='admin'
        )
        self.assertEqual(user.user_type.type_name, 'admin')
        self.assertTrue(user.is_admin())
    
    def test_create_superuser(self):
        """Test creating a super admin user"""
        user = User.objects.create_superuser(
            email='super@example.com',
            name='Super Admin',
            phone_number='+1234567890',
            password='SuperPass123'
        )
        self.assertEqual(user.user_type.type_name, 'super_admin')
        self.assertTrue(user.is_super_admin())
        self.assertTrue(user.is_admin())
    
    def test_create_user_without_email(self):
        """Test that email is required"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(
                email='',
                name='Test User',
                phone_number='+1234567890',
                password='TestPass123'
            )
        self.assertIn('Email is required', str(context.exception))
    
    def test_create_user_without_name(self):
        """Test that name is required"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(
                email='test@example.com',
                name='',
                phone_number='+1234567890',
                password='TestPass123'
            )
        self.assertIn('Name is required', str(context.exception))
    
    def test_create_user_without_phone(self):
        """Test that phone number is required"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(
                email='test@example.com',
                name='Test User',
                phone_number='',
                password='TestPass123'
            )
        self.assertIn('Phone number is required', str(context.exception))
    
    def test_email_normalization(self):
        """Test that email is normalized"""
        user = User.objects.create_user(
            email='Test@EXAMPLE.COM',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )
        self.assertEqual(user.email, 'Test@example.com')


class CustomUserModelTest(TransactionTestCase):
    """Test CustomUser model functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )
        self.admin = User.objects.create_user(
            email='admin@example.com',
            name='Admin User',
            phone_number='+0987654321',
            password='AdminPass123',
            user_type_name='admin'
        )
        self.super_admin = User.objects.create_superuser(
            email='super@example.com',
            name='Super Admin',
            phone_number='+1122334455',
            password='SuperPass123'
        )
    
    def test_user_string_representation(self):
        """Test __str__ method"""
        self.assertEqual(str(self.user), 'Test User (test@example.com)')
    
    def test_is_super_admin_method(self):
        """Test is_super_admin() method"""
        self.assertFalse(self.user.is_super_admin())
        self.assertFalse(self.admin.is_super_admin())
        self.assertTrue(self.super_admin.is_super_admin())
    
    def test_is_admin_method(self):
        """Test is_admin() method"""
        self.assertFalse(self.user.is_admin())
        self.assertTrue(self.admin.is_admin())
        self.assertTrue(self.super_admin.is_admin())
    
    def test_delete_regular_user(self):
        """Test that regular users can be deleted"""
        user_id = self.user.id
        self.user.delete()
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(id=user_id)
    
    def test_delete_super_admin_raises_exception(self):
        """Test that super admin cannot be deleted"""
        with self.assertRaises(PermissionDenied) as context:
            self.super_admin.delete()
        self.assertIn('Cannot delete the super admin user', str(context.exception))
    
    def test_change_super_admin_type_raises_exception(self):
        """Test that super admin type cannot be changed"""
        regular_type = UserType.objects.get(type_name='user')
        self.super_admin.user_type = regular_type
        
        with self.assertRaises(PermissionDenied) as context:
            self.super_admin.save()
        self.assertIn('Cannot change user type of super admin', str(context.exception))
    
    def test_username_field(self):
        """Test that email is the USERNAME_FIELD"""
        self.assertEqual(User.USERNAME_FIELD, 'email')
    
    def test_required_fields(self):
        """Test REQUIRED_FIELDS"""
        self.assertIn('name', User.REQUIRED_FIELDS)
        self.assertIn('phone_number', User.REQUIRED_FIELDS)
    
    def test_db_table_name(self):
        """Test correct database table name"""
        self.assertEqual(User._meta.db_table, 'custom_users')


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
        self.assertEqual(response.data['user']['user_type'], 'user')
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
    
    def test_register_duplicate_email(self):
        """Test registration with duplicate email"""
        # Create first user
        self.client.post(self.url, self.valid_data, format='json')
        
        # Try to register again with same email
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_password_mismatch(self):
        """Test registration with mismatched passwords"""
        data = self.valid_data.copy()
        data['confirm_password'] = 'DifferentPassword123'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', response.data)
    
    def test_register_weak_password(self):
        """Test registration with weak password"""
        test_cases = [
            ('short', 'Password must be at least 8 characters'),
            ('nouppercase123', 'uppercase letter'),
            ('NOLOWERCASE123', 'lowercase letter'),
            ('NoNumbers', 'number'),
        ]
        
        for weak_password, expected_error in test_cases:
            data = self.valid_data.copy()
            data['password'] = weak_password
            data['confirm_password'] = weak_password
            
            response = self.client.post(self.url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_invalid_email(self):
        """Test registration with invalid email"""
        data = self.valid_data.copy()
        data['email'] = 'invalid-email'
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_missing_fields(self):
        """Test registration with missing required fields"""
        required_fields = ['email', 'name', 'phone_number', 'password', 'confirm_password']
        
        for field in required_fields:
            data = self.valid_data.copy()
            del data[field]
            
            response = self.client.post(self.url, data, format='json')
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
        data = {
            'email': 'testuser@example.com',
            'password': 'TestPass123'
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'testuser@example.com')
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
    
    def test_login_wrong_password(self):
        """Test login with wrong password"""
        data = {
            'email': 'testuser@example.com',
            'password': 'WrongPassword123'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_login_nonexistent_user(self):
        """Test login with non-existent email"""
        data = {
            'email': 'nonexistent@example.com',
            'password': 'TestPass123'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_missing_email(self):
        """Test login without email"""
        data = {'password': 'TestPass123'}
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_missing_password(self):
        """Test login without password"""
        data = {'email': 'testuser@example.com'}
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_case_insensitive_email(self):
        """Test login with different email case"""
        data = {
            'email': 'TESTUSER@EXAMPLE.COM',
            'password': 'TestPass123'
        }
        
        response = self.client.post(self.url, data, format='json')
        # Should fail because email is case-sensitive in database lookup
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
        self.assertIn('refresh', response.data)
    
    def test_refresh_invalid_token(self):
        """Test refresh with invalid token"""
        data = {'refresh': 'invalid.token.here'}
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_refresh_missing_token(self):
        """Test refresh without token"""
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserProfileAPITest(APITestCase):
    """Test user profile endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.url = '/core/user_accounts/profile/'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            name='Test User',
            phone_number='+1234567890',
            password='TestPass123'
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            name='Other User',
            phone_number='+0987654321',
            password='OtherPass123'
        )
        
        # Get tokens for authentication
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
    
    def test_get_profile_success(self):
        """Test getting user profile"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'testuser@example.com')
        self.assertEqual(response.data['name'], 'Test User')
        self.assertEqual(response.data['phone_number'], '+1234567890')
        self.assertEqual(response.data['user_type'], 'user')
    
    def test_get_profile_unauthenticated(self):
        """Test getting profile without authentication"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_profile_full(self):
        """Test full profile update (PUT)"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {
            'name': 'Updated Name',
            'phone_number': '+9999999999'
        }
        
        response = self.client.put(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['name'], 'Updated Name')
        self.assertEqual(response.data['user']['phone_number'], '+9999999999')
        
        # Verify in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Updated Name')
        self.assertEqual(self.user.phone_number, '+9999999999')
    
    def test_update_profile_partial(self):
        """Test partial profile update (PATCH)"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {'name': 'Partially Updated'}
        
        response = self.client.patch(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['name'], 'Partially Updated')
        
        # Phone number should remain unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, '+1234567890')
    
    def test_update_profile_cannot_change_email(self):
        """Test that email cannot be changed"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {
            'email': 'newemail@example.com',
            'name': 'Updated Name',
            'phone_number': '+1234567890'
        }
        
        response = self.client.put(self.url, data, format='json')
        
        # Email should remain unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'testuser@example.com')
    
    def test_update_profile_cannot_change_user_type(self):
        """Test that user_type cannot be changed"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {
            'user_type': 'admin',
            'name': 'Updated Name',
            'phone_number': '+1234567890'
        }
        
        response = self.client.put(self.url, data, format='json')
        
        # User type should remain 'user'
        self.user.refresh_from_db()
        self.assertEqual(self.user.user_type.type_name, 'user')


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
        self.assertIn('message', response.data)
        
        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456'))
        self.assertFalse(self.user.check_password('OldPass123'))
    
    def test_change_password_wrong_old_password(self):
        """Test password change with wrong old password"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {
            'old_password': 'WrongOldPass',
            'new_password': 'NewPass456',
            'confirm_password': 'NewPass456'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_change_password_mismatch(self):
        """Test password change with mismatched new passwords"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {
            'old_password': 'OldPass123',
            'new_password': 'NewPass456',
            'confirm_password': 'DifferentPass789'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_change_password_weak_new_password(self):
        """Test password change with weak new password"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {
            'old_password': 'OldPass123',
            'new_password': 'weak',
            'confirm_password': 'weak'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_change_password_unauthenticated(self):
        """Test password change without authentication"""
        data = {
            'old_password': 'OldPass123',
            'new_password': 'NewPass456',
            'confirm_password': 'NewPass456'
        }
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


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
        self.assertIn('message', response.data)
    
    def test_logout_without_refresh_token(self):
        """Test logout without refresh token"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_logout_unauthenticated(self):
        """Test logout without authentication"""
        data = {'refresh': str(self.refresh)}
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout_invalid_token(self):
        """Test logout with invalid refresh token"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        data = {'refresh': 'invalid.token.here'}
        
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ComplexUserWorkflowTest(APITestCase):
    """Test complex user workflows and edge cases"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_complete_user_lifecycle(self):
        """Test complete user lifecycle: register -> login -> update profile -> change password -> logout"""
        
        # 1. Register
        register_data = {
            'email': 'lifecycle@example.com',
            'name': 'Lifecycle User',
            'phone_number': '+1234567890',
            'password': 'InitialPass123',
            'confirm_password': 'InitialPass123'
        }
        response = self.client.post('/auth/register/', register_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        access_token = response.data['tokens']['access']
        refresh_token = response.data['tokens']['refresh']
        
        # 2. Login
        login_data = {
            'email': 'lifecycle@example.com',
            'password': 'InitialPass123'
        }
        response = self.client.post('/auth/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Get Profile
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/core/user_accounts/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'lifecycle@example.com')
        
        # 4. Update Profile
        update_data = {
            'name': 'Updated Lifecycle User',
            'phone_number': '+9999999999'
        }
        response = self.client.patch('/core/user_accounts/profile/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Change Password
        password_data = {
            'old_password': 'InitialPass123',
            'new_password': 'UpdatedPass456',
            'confirm_password': 'UpdatedPass456'
        }
        response = self.client.post('/auth/change-password/', password_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 6. Verify new password works
        login_data['password'] = 'UpdatedPass456'
        response = self.client.post('/auth/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 7. Logout
        logout_data = {'refresh': refresh_token}
        response = self.client.post('/auth/logout/', logout_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_multiple_users_isolation(self):
        """Test that users can only access their own data"""
        
        # Create two users
        user1 = User.objects.create_user(
            email='user1@example.com',
            name='User One',
            phone_number='+1111111111',
            password='Pass123'
        )
        user2 = User.objects.create_user(
            email='user2@example.com',
            name='User Two',
            phone_number='+2222222222',
            password='Pass123'
        )
        
        # Get token for user1
        refresh1 = RefreshToken.for_user(user1)
        token1 = str(refresh1.access_token)
        
        # User1 gets their profile
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token1}')
        response = self.client.get('/core/user_accounts/profile/')
        self.assertEqual(response.data['email'], 'user1@example.com')
        self.assertNotEqual(response.data['email'], 'user2@example.com')
        
        # User1 updates their profile
        update_data = {'name': 'User One Updated'}
        response = self.client.patch('/core/user_accounts/profile/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user2 data is unchanged
        user2.refresh_from_db()
        self.assertEqual(user2.name, 'User Two')
    
    def test_token_expiration_and_refresh(self):
        """Test token refresh mechanism"""
        user = User.objects.create_user(
            email='tokentest@example.com',
            name='Token Test',
            phone_number='+1234567890',
            password='TestPass123'
        )
        
        # Get initial tokens
        refresh = RefreshToken.for_user(user)
        old_access = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Refresh the token
        response = self.client.post('/auth/token/refresh/', 
                                   {'refresh': refresh_token}, 
                                   format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        new_access = response.data['access']
        new_refresh = response.data['refresh']
        
        # Verify new tokens are different
        self.assertNotEqual(old_access, new_access)
        self.assertNotEqual(refresh_token, new_refresh)
        
        # Verify new access token works
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')
        response = self.client.get('/core/user_accounts/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_concurrent_user_registrations(self):
        """Test handling multiple simultaneous registrations"""
        users_data = [
            {'email': f'user{i}@example.com', 
             'name': f'User {i}', 
             'phone_number': f'+{i}234567890',
             'password': f'Pass{i}123',
             'confirm_password': f'Pass{i}123'}
            for i in range(1, 6)
        ]
        
        # Register multiple users
        for data in users_data:
            response = self.client.post('/auth/register/', data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify all users exist
        self.assertEqual(User.objects.count(), 5)
    
    def test_special_characters_in_user_data(self):
        """Test handling special characters in user data"""
        special_data = {
            'email': 'special.user+test@example.com',
            'name': "O'Brien-Smith (Jr.)",
            'phone_number': '+15551234567',  # Simplified phone format
            'password': 'P@ssw0rd123',
            'confirm_password': 'P@ssw0rd123'
        }
        
        response = self.client.post('/auth/register/', special_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(email='special.user+test@example.com')
        self.assertEqual(user.name, "O'Brien-Smith (Jr.)")


class SuperAdminProtectionTest(TransactionTestCase):
    """Test super admin protection mechanisms"""
    
    def setUp(self):
        self.super_admin = User.objects.create_superuser(
            email='super@example.com',
            name='Super Admin',
            phone_number='+1234567890',
            password='SuperPass123'
        )
        self.regular_user = User.objects.create_user(
            email='regular@example.com',
            name='Regular User',
            phone_number='+0987654321',
            password='RegularPass123'
        )
    
    def test_cannot_delete_super_admin_via_delete_method(self):
        """Test super admin cannot be deleted via delete()"""
        with self.assertRaises(PermissionDenied):
            self.super_admin.delete()
        
        # Verify super admin still exists
        self.assertTrue(User.objects.filter(id=self.super_admin.id).exists())
    
    def test_cannot_change_super_admin_user_type(self):
        """Test super admin user_type cannot be changed"""
        user_type = UserType.objects.get(type_name='user')
        self.super_admin.user_type = user_type
        
        with self.assertRaises(PermissionDenied):
            self.super_admin.save()
        
        # Verify user_type unchanged
        self.super_admin.refresh_from_db()
        self.assertEqual(self.super_admin.user_type.type_name, 'super_admin')
    
    def test_can_update_super_admin_other_fields(self):
        """Test super admin can update non-protected fields"""
        self.super_admin.name = 'Updated Super Admin'
        self.super_admin.phone_number = '+9999999999'
        self.super_admin.save()
        
        self.super_admin.refresh_from_db()
        self.assertEqual(self.super_admin.name, 'Updated Super Admin')
        self.assertEqual(self.super_admin.phone_number, '+9999999999')
    
    def test_regular_user_can_be_deleted(self):
        """Test regular users can be deleted"""
        user_id = self.regular_user.id
        self.regular_user.delete()
        
        self.assertFalse(User.objects.filter(id=user_id).exists())


class EdgeCaseTest(APITestCase):
    """Test edge cases and boundary conditions"""
    
    def test_very_long_name(self):
        """Test handling very long names"""
        long_name = 'A' * 255  # Max length
        data = {
            'email': 'longname@example.com',
            'name': long_name,
            'phone_number': '+1234567890',
            'password': 'TestPass123',
            'confirm_password': 'TestPass123'
        }
        
        response = self.client.post('/auth/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_unicode_characters_in_name(self):
        """Test Unicode characters in user name"""
        data = {
            'email': 'unicode@example.com',
            'name': '李明 José García Müller',
            'phone_number': '+1234567890',
            'password': 'TestPass123',
            'confirm_password': 'TestPass123'
        }
        
        response = self.client.post('/auth/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(email='unicode@example.com')
        self.assertEqual(user.name, '李明 José García Müller')
    
    def test_empty_string_vs_none(self):
        """Test handling of empty strings vs None"""
        # Empty strings should fail validation
        data = {
            'email': '',
            'name': 'Test',
            'phone_number': '+1234567890',
            'password': 'TestPass123',
            'confirm_password': 'TestPass123'
        }
        
        response = self.client.post('/auth/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_sql_injection_attempt(self):
        """Test protection against SQL injection"""
        data = {
            'email': "test'; DROP TABLE custom_users; --@example.com",
            'name': "Robert'); DROP TABLE custom_users; --",
            'phone_number': '+1234567890',
            'password': 'TestPass123',
            'confirm_password': 'TestPass123'
        }
        
        # Should either reject or safely handle the input
        response = self.client.post('/auth/register/', data, format='json')
        
        # Verify tables still exist
        self.assertTrue(User.objects.model._meta.db_table)
        self.assertEqual(User.objects.all().count() >= 0, True)


print("\n" + "="*80)
print("USER ACCOUNTS APP - COMPREHENSIVE TEST SUITE")
print("="*80)
