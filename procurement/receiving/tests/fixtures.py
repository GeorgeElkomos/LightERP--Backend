"""
Test fixtures and helper functions for Receiving tests.

This module provides common test data setup to avoid code duplication
across test files.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model

from procurement.catalog.models import catalogItem, UnitOfMeasure
from Finance.BusinessPartner.models import Supplier
from Finance.core.models import Currency
from procurement.po.models import POHeader, POLineItem
from procurement.receiving.models import GoodsReceipt, GoodsReceiptLine

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


def create_confirmed_po(supplier, currency, uom, user, po_type='Catalog'):
    """Create a confirmed PO ready for receiving"""
    po = POHeader.objects.create(
        po_type=po_type,
        po_date=date.today(),
        receiving_date=date.today() + timedelta(days=7),
        supplier_name=supplier.business_partner,  # Use business_partner, not supplier
        currency=currency,
        description='Test PO for receiving',
        status='CONFIRMED',
        created_by=user
    )
    
    # Add line items
    POLineItem.objects.create(
        po_header=po,
        line_number=1,
        line_type=po_type,
        item_name='Test Laptop',
        item_description='HP Laptop 15"',
        quantity=Decimal('10.000'),
        unit_of_measure=uom,
        unit_price=Decimal('1200.00'),
        line_total=Decimal('12000.00')
    )
    
    POLineItem.objects.create(
        po_header=po,
        line_number=2,
        line_type=po_type,
        item_name='Wireless Mouse',
        item_description='Logitech Mouse',
        quantity=Decimal('20.000'),
        unit_of_measure=uom,
        unit_price=Decimal('25.00'),
        line_total=Decimal('500.00')
    )
    
    # Update total
    po.total_amount = Decimal('12500.00')
    po.save()
    
    return po


def create_valid_grn_manual_data(po, uom):
    """Create valid GRN data with manual line entry"""
    po_line = po.line_items.first()
    
    return {
        'po_header_id': po.id,
        'receipt_date': str(date.today()),
        'grn_type': po.po_type,
        'notes': 'Test GRN',
        'lines': [
            {
                'line_number': 1,
                'po_line_item_id': po_line.id,
                'item_name': po_line.item_name,
                'item_description': po_line.item_description,
                'quantity_ordered': str(po_line.quantity),
                'quantity_received': '5.000',
                'unit_of_measure_id': uom.id,
                'unit_price': str(po_line.unit_price),
                'is_gift': False
            }
        ]
    }


def create_valid_grn_from_po_data(po):
    """Create valid GRN data using lines_from_po"""
    po_line = po.line_items.first()
    
    return {
        'po_header_id': po.id,
        'receipt_date': str(date.today()),
        'grn_type': po.po_type,
        'notes': 'Test GRN from PO',
        'lines_from_po': [
            {
                'po_line_item_id': po_line.id,
                'quantity_to_receive': '5.000'
            }
        ]
    }


def create_grn_with_lines(po, user, receipt_date=None):
    """Create a GRN with line items for testing"""
    if receipt_date is None:
        receipt_date = date.today()
    
    grn = GoodsReceipt.objects.create(
        po_header=po,
        receipt_date=receipt_date,
        supplier=Supplier.objects.get(business_partner_id=po.supplier_name_id),
        grn_type=po.po_type,
        received_by=user,
        notes='Test GRN',
        created_by=user
    )
    
    # Add lines from PO
    for po_line in po.line_items.all():
        grn_line = GoodsReceiptLine(
            goods_receipt=grn,
            line_number=po_line.line_number
        )
        grn_line.populate_from_po_line(po_line, quantity_to_receive=Decimal('5.000'))
        grn_line.save()
    
    # Refresh to get calculated totals
    grn.refresh_from_db()
    
    return grn
