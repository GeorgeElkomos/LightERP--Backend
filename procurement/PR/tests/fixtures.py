"""
Test fixtures and helper functions for PR tests.

This module provides common test data setup to avoid code duplication
across test files.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model

from procurement.catalog.models import catalogItem, UnitOfMeasure
from core.approval.models import ApprovalWorkflowTemplate, ApprovalWorkflowStageTemplate

User = get_user_model()


def create_unit_of_measure(code='EA', name='Each', uom_type='QUANTITY'):
    """Create a test unit of measure"""
    uom, _ = UnitOfMeasure.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'uom_type': uom_type
        }
    )
    return uom


def create_catalog_item(name='Laptop', description='Standard Laptop', code=None, uom=None):
    """Create a test catalog item"""
    if code is None:
        import random
        code = f'ITEM{random.randint(1000, 9999)}'
    
    item, _ = catalogItem.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'description': description
        }
    )
    return item


def get_or_create_test_user(email='testuser@example.com', name='Test User'):
    """Get or create a test user for tests"""
    from core.user_accounts.models import UserType
    
    # Get or create a basic user type
    user_type, _ = UserType.objects.get_or_create(
        type_name='employee',
        defaults={
            'description': 'Regular employee'
        }
    )
    
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'name': name,
            'phone_number': '1234567890',
            'user_type': user_type
        }
    )
    
    if created:
        user.set_password('testpass123')
        user.save()
    
    return user


def create_simple_approval_template_for_pr(name='PR Approval Template'):
    """Create a simple single-stage approval template for all PR types"""
    from django.contrib.contenttypes.models import ContentType
    from procurement.PR.models import Catalog_PR, NonCatalog_PR, Service_PR
    
    templates = []
    pr_models = [
        (Catalog_PR, 'CAT_PR_APPR'),
        (NonCatalog_PR, 'NC_PR_APPR'),
        (Service_PR, 'SRV_PR_APPR')
    ]
    
    for pr_model, template_code in pr_models:
        pr_content_type = ContentType.objects.get_for_model(pr_model)
        
        template, created = ApprovalWorkflowTemplate.objects.get_or_create(
            code=template_code,
            defaults={
                'name': f'{pr_model.__name__} Approval',
                'content_type': pr_content_type,
                'description': f'Simple {pr_model.__name__} approval template for testing',
                'is_active': True
            }
        )
        
        if created:
            # Create a single approval stage
            user = get_or_create_test_user()
            
            stage = ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=template,
                name='Manager Approval',
                order_index=1,
                decision_policy='ANY'
            )
        
        templates.append(template)
    
    return templates


def approve_pr_for_testing(pr_instance):
    """
    Approve a PR instance for testing purposes.
    Submits and auto-approves without going through full workflow.
    """
    from core.approval.managers import ApprovalManager
    
    # Create approval template if doesn't exist
    create_simple_approval_template_for_pr()
    
    # Get test user
    user = get_or_create_test_user()
    
    # Get the child instance if passed the parent PR
    if pr_instance.__class__.__name__ == 'PR':
        from procurement.PR.models import Catalog_PR, NonCatalog_PR, Service_PR
        # Determine which child model to use based on type_of_pr
        if pr_instance.type_of_pr == 'Catalog':
            pr_instance = Catalog_PR.objects.get(pr=pr_instance)
        elif pr_instance.type_of_pr == 'Non-Catalog':
            pr_instance = NonCatalog_PR.objects.get(pr=pr_instance)
        elif pr_instance.type_of_pr == 'Service':
            pr_instance = Service_PR.objects.get(pr=pr_instance)
    
    # Submit for approval
    workflow = pr_instance.submit_for_approval()
    
    # Approve using process_action
    ApprovalManager.process_action(pr_instance, user, "approve", "Auto-approved for testing")
    
    return pr_instance


def create_valid_catalog_pr_data(catalog_item=None, uom=None):
    """Create valid data for Catalog PR creation"""
    if catalog_item is None:
        catalog_item = create_catalog_item()
    if uom is None:
        uom = create_unit_of_measure()
    
    return {
        "date": str(date.today()),
        "required_date": str(date.today() + timedelta(days=10)),
        "requester_name": "John Doe",
        "requester_department": "IT",
        "requester_email": "john.doe@company.com",
        "priority": "MEDIUM",
        "description": "Test catalog PR",
        "notes": "Test notes",
        "items": [
            {
                "item_name": "Test Laptop",
                "item_description": "High-performance laptop",
                "catalog_item_id": catalog_item.id,
                "quantity": "5",
                "unit_of_measure_id": uom.id,
                "estimated_unit_price": "1200.00",
                "notes": "Urgent need"
            }
        ]
    }


def create_valid_noncatalog_pr_data(uom=None):
    """Create valid data for Non-Catalog PR creation"""
    if uom is None:
        uom = create_unit_of_measure()
    
    return {
        "date": str(date.today()),
        "required_date": str(date.today() + timedelta(days=10)),
        "requester_name": "Jane Smith",
        "requester_department": "Engineering",
        "requester_email": "jane.smith@company.com",
        "priority": "HIGH",
        "description": "Custom equipment not in catalog",
        "notes": "Special order",
        "items": [
            {
                "item_name": "Custom CNC Machine Part",
                "item_description": "Specialized component",
                "quantity": "3",
                "unit_of_measure_id": uom.id,
                "estimated_unit_price": "5000.00",
                "notes": "Contact supplier XYZ"
            }
        ]
    }


def create_valid_service_pr_data(uom=None):
    """Create valid data for Service PR creation"""
    if uom is None:
        uom, _ = UnitOfMeasure.objects.get_or_create(
            code='SRV',
            defaults={
                'name': 'Service',
                'uom_type': 'QUANTITY'
            }
        )
    
    return {
        "date": str(date.today()),
        "required_date": str(date.today() + timedelta(days=10)),
        "requester_name": "Bob Johnson",
        "requester_department": "Facilities",
        "requester_email": "bob.johnson@company.com",
        "priority": "URGENT",
        "description": "Annual HVAC maintenance",
        "notes": "Schedule for weekend",
        "items": [
            {
                "item_name": "HVAC Maintenance Service",
                "item_description": "Complete system inspection",
                "quantity": "1",
                "unit_of_measure_id": uom.id,
                "estimated_unit_price": "15000.00",
                "notes": "Includes parts and labor"
            }
        ]
    }
