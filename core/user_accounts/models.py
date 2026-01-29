"""
User Account Models
Handles user authentication and permissions.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from core.base.models import SoftDeleteMixin, AuditMixin

class UserAccountManager(BaseUserManager):
    """
    Custom user manager for UserAccount model.
    Handles user creation with optional job role assignment via M2M.
    """
    
    def create_user(self, email, name, phone_number, password=None, **extra_fields):
        """
        Create and save a user.

        Args:
            email: User's email address (used for authentication)
            name: User's full name
            phone_number: User's phone number
            password: User's password (will be hashed)
            **extra_fields: Additional fields to set on the user
            
        Returns:
            UserAccount: The created user instance
        """
        if not email:
            raise ValueError('Email is required')
        if not name:
            raise ValueError('Name is required')
        if not phone_number:
            raise ValueError('Phone number is required')
        
        email = self.normalize_email(email)
        
        user = self.model(
            email=email,
            name=name,
            phone_number=phone_number,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, name, phone_number, password=None, **extra_fields):
        """
        Create and save an admin user with admin job role.
        Required by Django for the createsuperuser management command.

        The admin job role should exist in the database with full permissions.
        The role is assigned via UserJobRole M2M after user creation.
        """
        user = self.create_user(
            email=email,
            name=name,
            phone_number=phone_number,
            password=password,
            **extra_fields
        )
        
        # Try to assign admin role via M2M
        from core.job_roles.models import JobRole, UserJobRole
        
        # Ensure admin role exists using strict code
        admin_role, _ = JobRole.objects.get_or_create(
            code='admin',
            defaults={
                'name': 'Admin',
                'description': 'System Administrator with full access'
            }
        )
        
        UserJobRole.objects.create(
            user=user,
            job_role=admin_role,
            effective_start_date=timezone.now().date()
        )

        return user


class UserAccount(SoftDeleteMixin, AuditMixin, AbstractBaseUser):
    """
    Custom user model with email authentication and role-based permissions.

    Permissions are controlled via UserJobRole M2M relationship:
    - Users can have MULTIPLE job roles
    - Roles can have effective dates
    - User permissions = union of all active roles

    Note: Users with the 'admin' job role have access to everything.
    """
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)

    # Manager
    objects = UserAccountManager()
    
    # Django authentication settings
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'phone_number']
    
    class Meta:
        db_table = 'user_account'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.name} ({self.email})"

    def is_admin(self):
        """
        Check if user has the admin job role.
        Checks the currently effective roles via the job_roles service.
        """
        from core.job_roles.services import get_user_active_roles
        effective_roles = get_user_active_roles(self)
        return any(role.code == 'admin' for role in effective_roles)

    def deactivate(self):
        """
        Soft delete user.
        - Prevent deleting admin users
        - Set status to INACTIVE (via super)
        """
        if self.is_admin():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Cannot deactivate admin user")

        super().deactivate()

    def delete(self, *args, **kwargs):
        """Prevent deletion of admin users"""
        if self.is_admin():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Cannot delete admin user")
        return super().delete(*args, **kwargs)
