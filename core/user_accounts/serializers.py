"""
User Account Serializers

Task 1a Update:
- Removed job_role FK references (now uses UserJobRole M2M in job_roles app)
- Added primary_role computed field for display
- Role assignment now happens via /job-roles/users/{id}/assign-roles/
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator, RegexValidator
from .models import UserAccount
import re


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for public user registration"""
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

    class Meta:
        model = UserAccount
        fields = ['email', 'name', 'phone_number', 'password', 'confirm_password']

    @staticmethod
    def validate_email(value):
        """Validate email format"""
        validator = EmailValidator(message="Enter a valid email address")
        validator(value)

        if UserAccount.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")

        return value

    @staticmethod
    def validate_phone_number(value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value

    @staticmethod
    def validate_password(value):
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
        """Create new user"""
        validated_data.pop('confirm_password')

        user = UserAccount.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            phone_number=validated_data['phone_number'],
            password=validated_data['password']
        )
        return user


class AdminCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for admin to create new users.
    Role assignment is done separately via /job-roles/users/{id}/assign-roles/
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = UserAccount
        fields = ['email', 'name', 'phone_number', 'password']

    @staticmethod
    def validate_phone_number(value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value

    @staticmethod
    def validate_password(value):
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

    def create(self, validated_data):
        """Create new user"""
        user = UserAccount.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            phone_number=validated_data['phone_number'],
            password=validated_data['password']
        )
        return user


class AdminUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for admin to update user details.
    Role assignment is done via /job-roles/users/{id}/assign-roles/
    """
    class Meta:
        model = UserAccount
        fields = ['email', 'name', 'phone_number']
        read_only_fields = ['email']  # Email cannot be changed

    @staticmethod
    def validate_phone_number(value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users (admin view)"""
    roles_count = serializers.SerializerMethodField()

    class Meta:
        model = UserAccount
        fields = ['id', 'email', 'name', 'phone_number', 'roles_count']
        read_only_fields = ['id', 'email', 'roles_count']

    def get_roles_count(self, obj):
        """Count of active roles"""
        from core.job_roles.services import get_user_active_roles
        return len(get_user_active_roles(obj))


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (users viewing/updating their own profile)"""
    roles = serializers.SerializerMethodField()

    class Meta:
        model = UserAccount
        fields = ['id', 'email', 'name', 'phone_number', 'roles']
        read_only_fields = ['id', 'email', 'roles']

    @staticmethod
    def validate_phone_number(value):
        """Validate phone number format"""
        phone_regex = RegexValidator(
            regex=r'^(\+?\d{1,3})?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$',
            message="Enter a valid phone number"
        )
        phone_regex(value)
        return value


    def get_roles(self, obj):
        """Get list of all active role names"""
        from core.job_roles.services import get_user_active_roles
        roles = get_user_active_roles(obj)
        return [role.name for role in roles]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    @staticmethod
    def validate_new_password(value):
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
    """Serializer for users requesting a password reset that routes to admin."""
    email = serializers.EmailField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class AdminPasswordResetSerializer(serializers.Serializer):
    """Serializer used by admins to set a temporary password for a user."""
    user_id = serializers.IntegerField(required=True)
    temporary_password = serializers.CharField(required=True, min_length=8)

    @staticmethod
    def validate_temporary_password(value):
        """Validate temporary password requirements"""
        if len(value) < 8:
            raise serializers.ValidationError('Temporary password must be at least 8 characters long')
        return value