"""
Test fixtures and helper functions for PO tests.

This module provides common test data setup to avoid code duplication
across test files.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model

from procurement.catalog.models import catalogItem, UnitOfMeasure
from Finance.BusinessPartner.models import Supplier
from Finance.core.models import Currency, Country, TaxRate
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


def create_catalog_item(name='Laptop', description='Standard Laptop', code=None):
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


def create_supplier(name='Test Supplier', code=None):
    """Create a test supplier"""
    if code is None:
        import random
        code = f'SUP{random.randint(1000, 9999)}'
    
    unique_name = f'{name} {code}'
    
    supplier = Supplier.objects.create(
        name=unique_name,
        email=f'{code.lower()}@supplier.com',
        phone='1234567890',
        website=f'https://www.{code.lower()}.com'
    )
    return supplier


def create_currency(code='USD', name='US Dollar'):
    """Create a test currency"""
    currency, _ = Currency.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'symbol': '$'
        }
    )
    return currency


def create_country(code='AE', name='United Arab Emirates'):
    """Create a test country"""
    country, _ = Country.objects.get_or_create(
        code=code,
        defaults={
            'name': name
        }
    )
    return country


def create_tax_rate(country=None, category='STANDARD', rate=Decimal('5.00'), name=None):
    """Create a test tax rate"""
    if country is None:
        country = create_country()
    
    if name is None:
        name = f'{country.code} {category} VAT'
    
    # Use filter + create instead of get_or_create to allow multiple rates
    # Only check if exact match exists
    existing = TaxRate.objects.filter(
        country=country,
        category=category,
        rate=rate
    ).first()
    
    if existing:
        return existing
    
    # If no exact match, create new one
    try:
        tax_rate = TaxRate.objects.create(
            country=country,
            category=category,
            name=name,
            rate=rate,
            is_active=True
        )
        return tax_rate
    except Exception:
        # If constraint fails, return existing one
        return TaxRate.objects.get(country=country, category=category)


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


def create_simple_approval_template_for_po(name='PO Approval Template'):
    """Create a simple single-stage approval template for POs"""
    from django.contrib.contenttypes.models import ContentType
    from procurement.po.models import POHeader
    
    po_content_type = ContentType.objects.get_for_model(POHeader)
    
    template, created = ApprovalWorkflowTemplate.objects.get_or_create(
        code='PO_APPR',
        defaults={
            'name': 'PO Approval',
            'content_type': po_content_type,
            'description': 'Simple PO approval template for testing',
            'is_active': True
        }
    )
    
    if created:
        # Create a single approval stage
        stage = ApprovalWorkflowStageTemplate.objects.create(
            workflow_template=template,
            name='Manager Approval',
            order_index=1,
            decision_policy='ANY',
            allow_reject=True,
            allow_delegate=True
        )
    
    return template


def approve_po_for_testing(po_instance):
    """
    Approve a PO instance for testing purposes.
    Submits and auto-approves without going through full workflow.
    """
    from core.approval.managers import ApprovalManager
    
    # Create approval template if doesn't exist
    create_simple_approval_template_for_po()
    
    # Get test user
    user = get_or_create_test_user()
    
    # Submit for approval
    po_instance.submit_for_approval(submitted_by=user)
    
    # Approve using process_action
    ApprovalManager.process_action(po_instance, user, "approve", "Auto-approved for testing")
    
    return po_instance


def create_valid_po_data(supplier=None, currency=None, uom=None, tax_rate=None, po_type='Catalog', delivery_amount='50.00'):
    """Create valid data for PO creation (manual entry)"""
    if supplier is None:
        supplier = create_supplier()
    if currency is None:
        currency = create_currency()
    if uom is None:
        uom = create_unit_of_measure()
    if tax_rate is None:
        tax_rate = create_tax_rate()  # Creates 5% tax rate by default
    
    return {
        "po_date": str(date.today()),
        "po_type": po_type,
        "supplier_id": supplier.id,
        "currency_id": currency.id,
        "tax_rate_id": tax_rate.id,
        "delivery_amount": delivery_amount,
        "receiving_date": str(date.today() + timedelta(days=10)),
        "receiving_address": "123 Main St, City",
        "receiver_email": "receiver@company.com",
        "receiver_contact": "John Doe",
        "receiver_phone": "555-1234",
        "description": "Test PO",
        "items": [
            {
                "line_number": 1,
                "line_type": po_type,
                "item_name": "Test Laptop",
                "item_description": "High-performance laptop",
                "quantity": "10",
                "unit_of_measure_id": uom.id,
                "unit_price": "1200.00",
                "line_notes": ""
            }
        ]
    }


def create_approved_pr_with_items():
    """
    Create an approved PR with items for PO conversion testing.
    Returns (pr_instance, pr_items)
    """
    from procurement.PR.models import Catalog_PR, PRItem
    from procurement.PR.tests.fixtures import (
        create_simple_approval_template_for_pr,
        approve_pr_for_testing
    )
    
    # Create test data
    uom = create_unit_of_measure()
    catalog_item = create_catalog_item()
    user = get_or_create_test_user()
    
    # Create approval template
    create_simple_approval_template_for_pr()
    
    # Create Catalog PR
    catalog_pr = Catalog_PR.objects.create(
        date=date.today(),
        required_date=date.today() + timedelta(days=10),
        requester_name="Test Requester",
        requester_department="IT",
        requester_email="requester@company.com",
        priority="MEDIUM",
        description="Test PR for PO conversion",
        notes=""
    )
    
    # Create PR items
    item1 = PRItem.objects.create(
        pr=catalog_pr.pr,
        line_number=1,
        item_name="Laptop",
        item_description="High-performance laptop",
        catalog_item=catalog_item,
        quantity=Decimal('10.000'),
        unit_of_measure=uom,
        estimated_unit_price=Decimal('1200.00'),
        notes=""
    )
    
    item2 = PRItem.objects.create(
        pr=catalog_pr.pr,
        line_number=2,
        item_name="Mouse",
        item_description="Wireless mouse",
        catalog_item=catalog_item,
        quantity=Decimal('20.000'),
        unit_of_measure=uom,
        estimated_unit_price=Decimal('50.00'),
        notes=""
    )
    
    # Generate PR number
    catalog_pr.pr.generate_pr_number()
    catalog_pr.pr._allow_direct_save = True
    catalog_pr.pr.save()
    
    # Approve the PR
    approve_pr_for_testing(catalog_pr)
    
    return catalog_pr, [item1, item2]


def create_valid_po_from_pr_data(pr_items, supplier=None, currency=None, tax_rate=None, delivery_amount='75.00'):
    """Create valid data for PO creation from PR items"""
    if supplier is None:
        supplier = create_supplier()
    if currency is None:
        currency = create_currency()
    if tax_rate is None:
        tax_rate = create_tax_rate()  # Creates 5% tax rate by default
    
    pr_type = pr_items[0].pr.type_of_pr
    
    return {
        "po_date": str(date.today()),
        "po_type": pr_type,
        "supplier_id": supplier.id,
        "currency_id": currency.id,
        "tax_rate_id": tax_rate.id,
        "delivery_amount": delivery_amount,
        "receiving_date": str(date.today() + timedelta(days=10)),
        "receiving_address": "123 Main St, City",
        "receiver_email": "receiver@company.com",
        "receiver_contact": "John Doe",
        "receiver_phone": "555-1234",
        "description": f"Converting PR items",
        "items_from_pr": [
            {
                "pr_item_id": pr_items[0].id,
                "quantity_to_convert": str(pr_items[0].quantity),
                "unit_price": "1250.00",  # Slightly different from PR estimate
                "line_notes": "First item"
            },
            {
                "pr_item_id": pr_items[1].id,
                "unit_price": "55.00",  # Uses remaining quantity
                "line_notes": "Second item"
            }
        ]
    }
