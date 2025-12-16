from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator, RegexValidator
from .models import CustomUser, UserType
from core.job_roles.models import JobRole
import re


class UserTypeSerializer(serializers.ModelSerializer):
    """Serializer for UserType model"""
    class Meta:
        model = UserType
        fields = ['id', 'type_name', 'description']
        read_only_fields = ['id']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for public user registration - always creates 'user' type"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    job_role = serializers.PrimaryKeyRelatedField(
        queryset=JobRole.objects.all(), 
        required=False, 
        allow_null=True
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'name', 'phone_number', 'password', 'confirm_password', 'job_role']
    
    def validate_email(self, value):
        """Validate email format"""
        validator = EmailValidator(message="Enter a valid email address")
        validator(value)
        
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value
    
    def validate_password(self, value):
        """Validate password strength"""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number")
        
        validate_password(value)
        return value
    
    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        
        return attrs
    
    def create(self, validated_data):
        """Create new user with default 'user' type"""
        validated_data.pop('confirm_password')
        job_role = validated_data.pop('job_role', None)
        
        # Always create public registrations as 'user' type
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            job_role=job_role,
            user_type_name='user'
        )
        return user


class AdminUserCreationSerializer(serializers.ModelSerializer):
    """
    Serializer for admin/super_admin to create users with specific types.
    Used by admin endpoints with proper permission checks.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    job_role = serializers.PrimaryKeyRelatedField(
        queryset=JobRole.objects.all(), 
        required=False, 
        allow_null=True
    )
    
    user_type = serializers.PrimaryKeyRelatedField(
        queryset=UserType.objects.all(),
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'name', 'phone_number', 'password', 'confirm_password', 'job_role', 'user_type']
    
    def validate_email(self, value):
        """Validate email format"""
        validator = EmailValidator(message="Enter a valid email address")
        validator(value)
        
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value
    
    def validate_password(self, value):
        """Validate password strength"""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number")
        
        validate_password(value)
        return value
    
    def validate(self, attrs):
        """Validate passwords match and set default user_type"""
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        
        # Default to 'user' if not specified
        if 'user_type' not in attrs or attrs['user_type'] is None:
            attrs['user_type'] = UserType.objects.get(type_name='user')
        
        return attrs
    
    def validate_user_type(self, value):
        """
        Validate user_type based on requesting admin's permissions.
        This will be called by the view after checking permissions.
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            # Regular admins cannot create other admins or super_admins
            if not request.user.is_super_admin() and value.type_name in ['admin', 'super_admin']:
                raise serializers.ValidationError(
                    "Only super admins can create admin or super_admin users"
                )
        return value
    
    def create(self, validated_data):
        """Create new user with specified type"""
        validated_data.pop('confirm_password')
        job_role = validated_data.pop('job_role', None)
        user_type = validated_data.pop('user_type', None)
        
        user_type_name = user_type.type_name if user_type else 'user'
        
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            job_role=job_role,
            user_type_name=user_type_name
        )
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for admin/super_admin to update user details including user_type.
    Permission checks happen in the view.
    """
    user_type = serializers.PrimaryKeyRelatedField(
        queryset=UserType.objects.all(),
        required=False
    )
    
    job_role = serializers.PrimaryKeyRelatedField(
        queryset=JobRole.objects.all(), 
        required=False, 
        allow_null=True
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'name', 'phone_number', 'user_type', 'job_role']
        read_only_fields = ['email']  # Email cannot be changed
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value
    
    def validate_user_type(self, value):
        """
        Validate user_type changes based on requesting admin's permissions.
        This will be enhanced by view-level checks.
        """
        request = self.context.get('request')
        instance = self.instance
        
        if request and hasattr(request, 'user') and instance:
            # Regular admins cannot change user_type to admin or super_admin
            if not request.user.is_super_admin() and value.type_name in ['admin', 'super_admin']:
                raise serializers.ValidationError(
                    "Only super admins can promote users to admin or super_admin"
                )
            
            # Cannot change super_admin type (model also protects this)
            if instance.is_super_admin():
                raise serializers.ValidationError(
                    "Cannot change user type of super admin"
                )
        
        return value


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users (admin view)"""
    user_type = serializers.CharField(source='user_type.type_name', read_only=True)
    job_role_name = serializers.CharField(source='job_role.name', read_only=True, allow_null=True)
    
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'name', 'phone_number', 'user_type', 'job_role_name']
        read_only_fields = ['id', 'email', 'user_type', 'job_role_name']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (users viewing/updating their own profile)"""
    user_type = serializers.CharField(source='user_type.type_name', read_only=True)
    job_role_name = serializers.CharField(source='job_role.name', read_only=True, allow_null=True)
    
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'name', 'phone_number', 'user_type', 'job_role_name']
        read_only_fields = ['id', 'user_type', 'email', 'job_role_name']
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate_new_password(self, value):
        """Validate new password strength"""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number")
        
        validate_password(value)
        return value
    
    def validate(self, attrs):
        """Validate that new passwords match"""
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for users requesting a password reset that routes to super admin."""
    email = serializers.EmailField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class SuperAdminPasswordResetSerializer(serializers.Serializer):
    """Serializer used by super admins to set a temporary password for a user."""
    user_id = serializers.IntegerField(required=True)
    temporary_password = serializers.CharField(required=True, min_length=8)

    def validate_temporary_password(self, value):
        """Validate temporary password requirements"""
        if len(value) < 8:
            raise serializers.ValidationError('Temporary password must be at least 8 characters long')
        return value