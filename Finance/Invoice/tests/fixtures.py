"""
Test fixtures and helper functions for Invoice tests.

This module provides common test data setup to avoid code duplication
across test files.
"""

from decimal import Decimal
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import Supplier, Customer
from Finance.GL.models import XX_SegmentType, XX_Segment, JournalEntry
from datetime import date


def create_journal_entry(currency=None, memo='Test Journal Entry'):
    """Create a test journal entry"""
    if currency is None:
        currency = create_currency()
    return JournalEntry.objects.create(
        date=date.today(),
        currency=currency,
        memo=memo
    )


def create_currency(code='USD', name='US Dollar', symbol='$', is_base=True):
    """Create a test currency"""
    return Currency.objects.create(
        code=code,
        name=name,
        symbol=symbol,
        is_base_currency=is_base,
        exchange_rate_to_base_currency=Decimal('1.00') if is_base else Decimal('1.00')
    )


def create_country(code='US', name='United States'):
    """Create a test country"""
    return Country.objects.create(
        code=code,
        name=name
    )


def create_supplier(name='Test Supplier'):
    """Create a test supplier (creates BusinessPartner automatically)"""
    return Supplier.objects.create(
        name=name
    )


def create_customer(name='Test Customer'):
    """Create a test customer (creates BusinessPartner automatically)"""
    return Customer.objects.create(
        name=name
    )


def create_segment_types():
    """Create standard segment types for testing"""
    company = XX_SegmentType.objects.create(
        segment_name='Company',
        description='Company code'
    )
    account = XX_SegmentType.objects.create(
        segment_name='Account',
        description='Account number'
    )
    return {'company': company, 'account': account}


def create_segments(segment_types):
    """Create standard segments for testing"""
    segments = {}
    
    # Company segments
    segments['100'] = XX_Segment.objects.create(
        segment_type=segment_types['company'],
        code='100',
        alias='Main Company',
        node_type='detail'
    )
    
    # Account segments
    segments['1200'] = XX_Segment.objects.create(
        segment_type=segment_types['account'],
        code='1200',
        alias='Accounts Receivable',
        node_type='detail'
    )
    segments['2100'] = XX_Segment.objects.create(
        segment_type=segment_types['account'],
        code='2100',
        alias='Accounts Payable',
        node_type='detail'
    )
    segments['4000'] = XX_Segment.objects.create(
        segment_type=segment_types['account'],
        code='4000',
        alias='Sales Revenue',
        node_type='detail'
    )
    segments['6100'] = XX_Segment.objects.create(
        segment_type=segment_types['account'],
        code='6100',
        alias='Office Supplies Expense',
        node_type='detail'
    )
    segments['6200'] = XX_Segment.objects.create(
        segment_type=segment_types['account'],
        code='6200',
        alias='Travel Expense',
        node_type='detail'
    )
    
    return segments
    
    return segments


def setup_test_data():
    """
    Create all standard test data needed for invoice tests.
    
    Returns:
        dict: Dictionary containing all created objects
    """
    data = {}
    
    # Create currency and country
    data['currency'] = create_currency()
    data['country'] = create_country()
    
    # Create segment types and segments
    data['segment_types'] = create_segment_types()
    data['segments'] = create_segments(data['segment_types'])
    
    # Create supplier and customer
    data['supplier'] = create_supplier()
    data['customer'] = create_customer()
    
    return data
