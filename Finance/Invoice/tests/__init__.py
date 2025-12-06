"""
Invoice Tests Package

This package contains comprehensive tests for the Invoice module:
- test_views_ap.py: AP Invoice endpoint tests
- test_views_ar.py: AR Invoice endpoint tests
- test_views_one_time.py: One-Time Supplier Invoice endpoint tests
- fixtures.py: Common test data setup helpers

Run all tests:
    python manage.py test Finance.Invoice.tests

Run specific test file:
    python manage.py test Finance.Invoice.tests.test_views_ap
    python manage.py test Finance.Invoice.tests.test_views_ar
    python manage.py test Finance.Invoice.tests.test_views_one_time
"""

from .fixtures import (
    create_currency,
    create_country,
    create_supplier,
    create_customer,
    create_segment_types,
    create_segments,
    setup_test_data
)

__all__ = [
    'create_currency',
    'create_country',
    'create_supplier',
    'create_customer',
    'create_segment_types',
    'create_segments',
    'setup_test_data',
]
