"""
Test fixtures and helper functions for catalog tests.
"""
from django.contrib.auth import get_user_model
from procurement.catalog.models import UnitOfMeasure, catalogItem

User = get_user_model()


def get_or_create_test_user(email='testuser@example.com', name='Test User'):
    """Get or create a test user for tests"""
    
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'name': name,
            'phone_number': '1234567890',
        }
    )
    
    if created:
        user.set_password('testpass123')
        user.save()
    
    return user


def create_unit_of_measure(code='PCS', name='Pieces', uom_type='QUANTITY', is_active=True, description=''):
    """Create a Unit of Measure for testing"""
    return UnitOfMeasure.objects.create(
        code=code.upper(),
        name=name,
        uom_type=uom_type,
        is_active=is_active,
        description=description
    )


def create_catalog_item(code='ITEM001', name='Test Item', description='Test item description'):
    """Create a catalog item for testing"""
    return catalogItem.objects.create(
        code=code.upper(),
        name=name,
        description=description
    )


def create_valid_uom_data(code='MTR', name='Meters', uom_type='LENGTH'):
    """Create valid UoM data for POST requests"""
    return {
        'code': code,
        'name': name,
        'uom_type': uom_type,
        'description': 'Test unit of measure',
        'is_active': True
    }


def create_valid_catalog_item_data(code='LAPTOP01', name='Laptop Computer'):
    """Create valid catalog item data for POST requests"""
    return {
        'code': code,
        'name': name,
        'description': 'High-performance laptop for business use'
    }
