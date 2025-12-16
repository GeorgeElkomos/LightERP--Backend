"""
API Views for User Account management and authentication.
Provides REST API endpoints for registration, login, profile management, and user administration.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied

from .models import CustomUser, UserType
from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    AdminUserCreationSerializer,
    AdminUserUpdateSerializer,
    UserListSerializer,
    PasswordResetRequestSerializer,
    SuperAdminPasswordResetSerializer,
)


# ============================================================================
# Public Authentication Views
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Public endpoint for user registration.
    Creates a new user account with 'user' type and returns JWT tokens.
    
    POST /auth/register/
    - Request body: { "email", "name", "phone_number", "password", "confirm_password" }
    - Returns: User data and JWT tokens
    """
    serializer = UserRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'user_type': user.user_type.type_name
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        }, status=status.HTTP_201_CREATED)
    
    # Log validation errors for debugging
    try:
        print('\n' + '='*60)
        print('REGISTER VALIDATION ERRORS:')
        print(serializer.errors)
        print('='*60 + '\n')
    except Exception:
        pass

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Public endpoint for user login.
    Authenticates user and returns JWT tokens.
    
    POST /auth/login/
    - Request body: { "email": "...", "password": "..." }
    - Returns: User data and JWT tokens
    """
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'error': 'Please provide both email and password'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Authenticate user
    user = authenticate(request, username=email, password=password)
    
    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'user_type': user.user_type.type_name
        },
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Authenticated endpoint for logout.
    Blacklists the refresh token.
    
    POST /auth/logout/
    - Request body: { "refresh": "..." }
    - Returns: Success message
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================================================
# User Profile Views (Self-Management)
# ============================================================================

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Authenticated endpoint for viewing and updating own profile.
    Users can only view/update their own profile (name, phone_number).
    Cannot change email, user_type, or job_role.
    
    GET /core/user_accounts/profile/
    - Returns: Current user's profile data
    
    PUT/PATCH /core/user_accounts/profile/
    - Request body: { "name", "phone_number" }
    - Returns: Updated profile data
    """
    user = request.user
    
    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UserProfileSerializer(user, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profile updated successfully',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Authenticated endpoint for changing own password.
    
    POST /auth/change-password/
    - Request body: { "old_password", "new_password", "confirm_password" }
    - Returns: Success message
    """
    serializer = ChangePasswordSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    
    # Check old password
    if not user.check_password(serializer.validated_data['old_password']):
        return Response(
            {'error': 'Old password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password
    user.set_password(serializer.validated_data['new_password'])
    user.save()
    
    return Response({
        'message': 'Password changed successfully'
    }, status=status.HTTP_200_OK)


# ============================================================================
# Admin User Management Views
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def admin_user_list(request):
    """
    Admin endpoint for listing and creating users.
    
    Permissions:
    - Super Admin: Can view all users and create users with any type
    - Admin: Can view and create only 'user' type users
    - User: No access (403)
    
    GET /admin/users/
    - Returns: List of users based on permissions
    
    POST /admin/users/
    - Request body: AdminUserCreationSerializer fields
    - Returns: Created user data
    """
    # Permission check
    if not request.user.is_admin():
        return Response(
            {'error': 'Admin privileges required'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        # Super admin sees all users
        if request.user.is_super_admin():
            users = CustomUser.objects.all()
        # Regular admin only sees non-admin users
        else:
            user_type = UserType.objects.get(type_name='user')
            users = CustomUser.objects.filter(user_type=user_type)
        
        serializer = UserListSerializer(users, many=True)
        return Response({
            'count': users.count(),
            'users': serializer.data
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = AdminUserCreationSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            user = serializer.save()
            
            return Response({
                'message': 'User created successfully',
                'user': UserListSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def admin_user_detail(request, user_id):
    """
    Admin endpoint for viewing, updating, and deleting specific users.
    
    Permissions:
    - Super Admin: Full CRUD on all users except cannot delete/demote self or other super admins
    - Admin: Full CRUD on 'user' type only, cannot touch admins or super admins
    - User: No access (403)
    
    GET /admin/users/<id>/
    - Returns: User details
    
    PUT/PATCH /admin/users/<id>/
    - Request body: AdminUserUpdateSerializer fields
    - Returns: Updated user data
    
    DELETE /admin/users/<id>/
    - Returns: Success message
    """
    # Permission check
    if not request.user.is_admin():
        return Response(
            {'error': 'Admin privileges required'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get target user
    try:
        target_user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Permission check: Regular admins can only manage regular users
    if not request.user.is_super_admin():
        if target_user.is_admin():
            return Response(
                {'error': 'You do not have permission to manage admin users'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    # Super admin cannot modify other super admins (except themselves for profile updates)
    if request.user.is_super_admin() and target_user.is_super_admin():
        if request.user.id != target_user.id:
            return Response(
                {'error': 'Cannot modify other super admin users'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    if request.method == 'GET':
        serializer = UserListSerializer(target_user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = AdminUserUpdateSerializer(
            target_user,
            data=request.data,
            partial=partial,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'User updated successfully',
                'user': UserListSerializer(target_user).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Cannot delete super admin (model also protects this)
        if target_user.is_super_admin():
            return Response(
                {'error': 'Cannot delete super admin user'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cannot delete self
        if request.user.id == target_user.id:
            return Response(
                {'error': 'Cannot delete your own account'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            target_user.delete()
            return Response({
                'message': f'User {target_user.email} deleted successfully'
            }, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )


# ============================================================================
# Password Reset Flow
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Public endpoint: User submits password reset request which is routed to super admin.
    Always returns a generic success message to avoid leaking account existence.
    
    POST /auth/password-reset-request/
    - Request body: { "email", "reason"? }
    - Returns: Generic success message
    """
    serializer = PasswordResetRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    reason = serializer.validated_data.get('reason', '')

    # Security: check existence silently
    user_exists = CustomUser.objects.filter(email=email).exists()

    if user_exists:
        # Log request for manual/administrative handling
        print(f"\n{'='*60}")
        print(f"PASSWORD RESET REQUEST")
        print(f"Email: {email}")
        print(f"Reason: {reason}")
        print(f"Status: Pending Super Admin Review")
        print(f"{'='*60}\n")

    return Response({
        'message': 'If an account exists with this email, a password reset request has been submitted to the super admin.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def superadmin_password_reset(request):
    """
    Super admin endpoint to set a temporary password for a user.
    Requires authenticated super admin user.
    
    POST /admin/password-reset/
    - Request body: { "user_id", "temporary_password" }
    - Returns: Success message with temporary password
    """
    # Permission check
    if not request.user.is_super_admin():
        return Response(
            {'error': 'Super admin privileges required'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = SuperAdminPasswordResetSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_id = serializer.validated_data['user_id']
    temporary_password = serializer.validated_data['temporary_password']

    try:
        user = CustomUser.objects.get(pk=user_id)

        user.set_password(temporary_password)
        user.save()

        # Logging for audit (replace with proper audit logging/email in production)
        print(f"\n{'='*60}")
        print(f"TEMPORARY PASSWORD SET BY SUPER ADMIN")
        print(f"User: {user.email}")
        print(f"Temporary Password: {temporary_password}")
        print(f"Admin: {request.user.email}")
        print(f"NOTE: User should change this password after logging in")
        print(f"{'='*60}\n")

        return Response({
            'message': f'Temporary password set successfully for {user.email}',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name
            },
            'temporary_password': temporary_password,
            'note': 'User should change this password after logging in'
        }, status=status.HTTP_200_OK)

    except CustomUser.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except PermissionDenied as e:
        return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)