from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator, RegexValidator
from .models import CustomUser, UserType
import re


class UserTypeSerializer(serializers.ModelSerializer):
    """Serializer for UserType model"""
    class Meta:
        model = UserType
        fields = ['id', 'type_name', 'description']
        read_only_fields = ['id']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration (public endpoint)"""
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
        model = CustomUser
        fields = ['email', 'name', 'phone_number', 'password', 'confirm_password']
    
    def validate_email(self, value):
        """Validate email format"""
        validator = EmailValidator(message="Enter a valid email address")
        validator(value)
        
        # Check if email already exists
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
        
        # Use Django's built-in password validators
        validate_password(value)
        return value
    
    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        return attrs
    
    def create(self, validated_data):
        """Create new user with user type"""
        validated_data.pop('confirm_password')
        
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            phone_number=validated_data['phone_number'],
            password=validated_data['password']
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (users updating their own profile)"""
    user_type = serializers.CharField(source='user_type.type_name', read_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'name', 'phone_number', 'user_type']
        read_only_fields = ['id', 'email', 'user_type']
    
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
