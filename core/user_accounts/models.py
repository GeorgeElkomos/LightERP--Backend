"""
User Account Models
Handles user authentication and permissions.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.core.exceptions import PermissionDenied


class UserType(models.Model):
    """
    User type model with three types: user, admin, and super_admin.
    Defines the level of access and permissions for users.
    """
    type_name = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    
    class Meta:
        db_table = 'user_types'
        verbose_name = 'User Type'
        verbose_name_plural = 'User Types'
    
    def __str__(self):
        return self.type_name


class CustomUserManager(BaseUserManager):
    """
    Custom user manager for CustomUser model.
    Handles user creation with different user types and permissions.
    """
    
    USER_TYPE_DESCRIPTIONS = {
        'user': 'Regular user with basic permissions',
        'admin': 'Administrator with elevated permissions',
        'super_admin': 'Super administrator with full system access'
    }
    
    def create_user(self, email, name, phone_number, password=None, user_type_name='user', **extra_fields):
        """
        Create and save a user with any user type.
        
        Args:
            email: User's email address (used for authentication)
            name: User's full name
            phone_number: User's phone number
            password: User's password (will be hashed)
            user_type_name: Type of user ('user', 'admin', 'super_admin')
            **extra_fields: Additional fields to set on the user
            
        Returns:
            CustomUser: The created user instance
        """
        if not email:
            raise ValueError('Email is required')
        if not name:
            raise ValueError('Name is required')
        if not phone_number:
            raise ValueError('Phone number is required')
        
        email = self.normalize_email(email)
        
        # Get or create the specified user type
        user_type, _ = UserType.objects.get_or_create(
            type_name=user_type_name,
            defaults={'description': self.USER_TYPE_DESCRIPTIONS.get(user_type_name, '')}
        )
        
        user = self.model(
            email=email,
            name=name,
            phone_number=phone_number,
            user_type=user_type,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, name, phone_number, password=None, **extra_fields):
        """
        Create and save a super admin user.
        Required by Django for the createsuperuser management command.
        """
        return self.create_user(
            email=email,
            name=name,
            phone_number=phone_number,
            password=password,
            user_type_name='super_admin',
            **extra_fields
        )


class CustomUser(AbstractBaseUser):
    """Simplified custom user model with email authentication"""
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    
    # Relationships
    user_type = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name='users'
    )

    job_role = models.ForeignKey(
        'job_roles.JobRole',
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True,
        help_text="Job role determines page access permissions"
    )
    
    # Manager
    objects = CustomUserManager()
    
    # Django authentication settings
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'phone_number']
    
    class Meta:
        db_table = 'custom_users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def is_super_admin(self):
        """
        Check if user is a super admin.
        
        Returns:
            bool: True if user is super admin, False otherwise
        """
        return self.user_type.type_name == 'super_admin'
    
    def is_admin(self):
        """
        Check if user is an admin or super admin.
        
        Returns:
            bool: True if user is admin or super admin, False otherwise
        """
        return self.user_type.type_name in ['admin', 'super_admin']
    
    def delete(self, *args, **kwargs):
        """
        Override delete to prevent deletion of super admin.
        Similar to ProtectedDeleteMixin pattern in Finance.core.models.
        """
        if self.is_super_admin():
            raise PermissionDenied(
                "Cannot delete super admin user. Super admin is protected from deletion."
            )
        return super().delete(*args, **kwargs)
    
    def save(self, *args, **kwargs):
        """
        Override save to protect super admin properties.
        Prevents changing user_type of existing super admin users.
        """
        if self.pk:  # Only for existing users (updates)
            try:
                old_user = CustomUser.objects.get(pk=self.pk)
                
                # Prevent changing user_type of super admin
                if old_user.is_super_admin() and old_user.user_type_id != self.user_type_id:
                    raise PermissionDenied(
                        "Cannot change user type of super admin. Super admin type is protected."
                    )
            except CustomUser.DoesNotExist:
                pass
        
        return super().save(*args, **kwargs)
