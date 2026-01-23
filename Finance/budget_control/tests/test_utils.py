"""
Test fixtures and utilities for budget control module tests
"""
from django.contrib.auth import get_user_model
from Finance.core.models import Currency

User = get_user_model()


def create_test_user(username='testuser', email='test@example.com', password='testpass123', **kwargs):
    """
    Create a test user with all required fields for CustomUser model.
    
    Args:
        username: Username for the user
        email: Email address
        password: Password for authentication
        **kwargs: Additional fields (name, phone_number, is_staff, etc.)
    
    Returns:
        User: Created user instance
    """
    # Set defaults for required fields
    name = kwargs.pop('name', f'{username} User')
    phone_number = kwargs.pop('phone_number', f'+1234567{username[-4:].zfill(4)}')
    user_type_name = kwargs.pop('user_type_name', 'user')
    
    # Remove unsupported fields (CustomUser doesn't have these Django User fields)
    unsupported_fields = ['is_staff', 'is_superuser', 'is_active', 'groups', 'user_permissions']
    for field in unsupported_fields:
        kwargs.pop(field, None)
    
    # Create user with all required fields
    user = User.objects.create_user(
        email=email,
        name=name,
        phone_number=phone_number,
        password=password,
        user_type_name=user_type_name,
        **kwargs
    )
    
    # Set username after creation (if your model has it)
    if hasattr(user, 'username'):
        user.username = username
        user.save()
    
    return user


def create_admin_user(username='admin', email='admin@example.com', password='admin123', **kwargs):
    """
    Create an admin test user.
    
    Args:
        username: Username for the admin
        email: Email address
        password: Password
        **kwargs: Additional fields
    
    Returns:
        User: Created admin user
    """
    kwargs['name'] = kwargs.get('name', 'Admin User')
    kwargs['phone_number'] = kwargs.get('phone_number', '+1234567890')
    kwargs['user_type_name'] = 'admin'
    kwargs['is_staff'] = True
    
    return create_test_user(username=username, email=email, password=password, **kwargs)


def create_super_admin_user(username='superadmin', email='superadmin@example.com', password='super123', **kwargs):
    """
    Create a super admin test user.
    
    Args:
        username: Username for the super admin
        email: Email address
        password: Password
        **kwargs: Additional fields
    
    Returns:
        User: Created super admin user
    """
    kwargs['name'] = kwargs.get('name', 'Super Admin User')
    kwargs['phone_number'] = kwargs.get('phone_number', '+1234567999')
    kwargs['user_type_name'] = 'super_admin'
    kwargs['is_staff'] = True
    kwargs['is_superuser'] = True
    
    return create_test_user(username=username, email=email, password=password, **kwargs)


def create_test_currency(code='USD', name='US Dollar', symbol='$', **kwargs):
    """
    Create a test currency.
    
    Args:
        code: Currency code (3 letters)
        name: Currency name
        symbol: Currency symbol
        **kwargs: Additional fields
    
    Returns:
        Currency: Created currency instance
    """
    currency, created = Currency.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'symbol': symbol,
            'is_active': kwargs.get('is_active', True),
            'is_base_currency': kwargs.get('is_base_currency', False),
            'exchange_rate_to_base_currency': kwargs.get('exchange_rate_to_base_currency', 1)
        }
    )
    return currency


