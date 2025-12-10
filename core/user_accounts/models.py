from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.core.exceptions import PermissionDenied
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver


class Role(models.Model):
    """Role model for user roles"""
    name = models.CharField(max_length=100, unique=True)
    
    class Meta:
        db_table = 'roles'
    
    def __str__(self):
        return self.name


class UserType(models.Model):
    """User type model with three types: user, admin, and super_admin"""
    type_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'user_types'
    
    def __str__(self):
        return self.type_name


class CustomUserManager(BaseUserManager):
    """Custom user manager for CustomUser model"""
    
    USER_TYPE_DESCRIPTIONS = {
        'user': 'Regular user with basic permissions',
        'admin': 'Administrator with elevated permissions',
        'super_admin': 'Super administrator with full system access'
    }
    
    def create_user(self, email, name, phone_number, password=None, user_type_name='user', **extra_fields):
        """Create and save a user with any user type"""
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
        """Create and save a super admin user (required by Django for createsuperuser command)"""
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
    user_type = models.ForeignKey(UserType, on_delete=models.PROTECT, related_name='users')
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users', null=True, blank=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'phone_number']
    
    class Meta:
        db_table = 'custom_users'
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def is_super_admin(self):
        """Check if user is super admin"""
        return self.user_type.type_name == 'super_admin'
    
    def is_admin(self):
        """Check if user is admin or super admin"""
        return self.user_type.type_name in ['admin', 'super_admin']
    
    def delete(self, *args, **kwargs):
        """Override delete to prevent deletion of super admin"""
        if self.is_super_admin():
            raise PermissionDenied("Cannot delete the super admin user")
        return super().delete(*args, **kwargs)
    
    def save(self, *args, **kwargs):
        """Override save to protect super admin properties"""
        if self.pk:  # Only for existing users
            try:
                old_user = CustomUser.objects.get(pk=self.pk)
                
                # Prevent changing user_type of super admin
                if old_user.is_super_admin() and old_user.user_type_id != self.user_type_id:
                    raise PermissionDenied("Cannot change user type of super admin")
            except CustomUser.DoesNotExist:
                pass
        
        return super().save(*args, **kwargs)


# Signals for additional protection
@receiver(pre_delete, sender=CustomUser)
def prevent_super_admin_deletion(sender, instance, **kwargs):
    """Signal to prevent deletion of super admin"""
    if instance.is_super_admin():
        raise PermissionDenied("Cannot delete the super admin user")


@receiver(pre_save, sender=CustomUser)
def prevent_super_admin_modification(sender, instance, **kwargs):
    """Signal to prevent unauthorized modification of super admin"""
    if instance.pk:  # Only for updates
        try:
            old_user = CustomUser.objects.get(pk=instance.pk)
            
            # Prevent changing user_type of super admin
            if old_user.is_super_admin() and old_user.user_type_id != instance.user_type_id:
                raise PermissionDenied("Cannot change user type of super admin")
        except CustomUser.DoesNotExist:
            pass
