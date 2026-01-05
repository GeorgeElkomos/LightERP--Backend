"""
Tests for Invoice models and period integration.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from decimal import Decimal

from Finance.Invoice.models import AR_Invoice, AP_Invoice, Invoice
from Finance.period.models import Period
from Finance.BusinessPartner.models import Customer, Supplier, Country
from Finance.core.models import Currency
from Finance.GL.models import XX_SegmentType, XX_Segment

User = get_user_model()


class ARInvoicePeriodIntegrationTest(APITestCase):
    """Test AR Invoice integration with Period validation."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            name='Test User',
            phone_number='1234567890',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        # Create country
        self.country = Country.objects.create(
            name='United States',
            code='US'
        )
        
        # Create customer
        self.customer = Customer.objects.create(
            name='Test Customer'
        )
        
        # Create segment types
        self.segment_type_company = XX_SegmentType.objects.create(
            segment_name='Company',
            description='Company code'
        )
        self.segment_type_account = XX_SegmentType.objects.create(
            segment_name='Account',
            description='Account number'
        )
        
        # Create segments
        self.segment_100 = XX_Segment.objects.create(
            segment_type=self.segment_type_company,
            code='100',
            alias='Main Company',
            node_type='detail'
        )
        self.segment_1100 = XX_Segment.objects.create(
            segment_type=self.segment_type_account,
            code='1100',
            alias='Accounts Receivable',
            node_type='detail'
        )
        self.segment_4000 = XX_Segment.objects.create(
            segment_type=self.segment_type_account,
            code='4000',
            alias='Revenue',
            node_type='detail'
        )
        
        # Create January 2026 period with AR open, GL open
        self.jan_period = Period.objects.create(
            name='January 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            fiscal_year=2026,
            period_number=1
        )
        self.jan_period.ar_period.state = 'open'
        self.jan_period.ar_period.save()
        self.jan_period.gl_period.state = 'open'
        self.jan_period.gl_period.save()
        
        # Create February 2026 period with AR closed
        self.feb_period = Period.objects.create(
            name='February 2026',
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            fiscal_year=2026,
            period_number=2
        )
        # February AR period stays closed (default)
    
    def test_create_ar_invoice_in_open_period(self):
        """Test creating AR invoice when AR period is open."""
        data = {
            'date': '2026-01-15',
            'currency_id': self.currency.id,
            'customer_id': self.customer.id,
            'subtotal': '1000.00',
            'tax_amount': '100.00',
            'total': '1100.00',
            'items': [
                {
                    'name': 'Test Item',
                    'description': 'Test Item Description',
                    'quantity': 1,
                    'unit_price': '1000.00',
                    'line_total': '1000.00'
                }
            ],
            'journal_entry': {
                'date': '2026-01-15',
                'currency_id': self.currency.id,
                'memo': 'AR Invoice',
                'lines': [
                    {
                        'amount': '1100.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': self.segment_type_company.id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_type_account.id, 'segment_code': '1100'}
                        ]
                    },
                    {
                        'amount': '1100.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': self.segment_type_company.id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_type_account.id, 'segment_code': '4000'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/invoice/ar/', data, format='json')
        if response.status_code != status.HTTP_201_CREATED:
            print(f"AR Invoice creation failed with status {response.status_code}")
            print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('invoice_id', response.data)
    
    def test_create_ar_invoice_in_closed_period_fails(self):
        """Test creating AR invoice fails when AR period is closed."""
        data = {
            'date': '2026-02-15',  # February period is closed
            'currency_id': self.currency.id,
            'customer_id': self.customer.id,
            'subtotal': '1000.00',
            'tax_amount': '100.00',
            'total': '1100.00',
            'items': [
                {
                    'name': 'Test Item',
                    'description': 'Test Item Description',
                    'quantity': 1,
                    'unit_price': '1000.00',
                    'line_total': '1000.00'
                }
            ],
            'journal_entry': {
                'date': '2026-02-15',
                'currency_id': self.currency.id,
                'memo': 'AR Invoice',
                'lines': [
                    {
                        'amount': '1100.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': 1, 'segment_code': '100'},
                            {'segment_type_id': 2, 'segment_code': '1100'}
                        ]
                    },
                    {
                        'amount': '1100.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': 1, 'segment_code': '100'},
                            {'segment_type_id': 2, 'segment_code': '4000'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/invoice/ar/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('closed', str(response.data).lower())
    
    def test_create_ar_invoice_no_period_fails(self):
        """Test creating AR invoice fails when no period exists."""
        data = {
            'date': '2025-12-15',  # No period exists for this date
            'currency_id': self.currency.id,
            'customer_id': self.customer.id,
            'subtotal': '1000.00',
            'tax_amount': '100.00',
            'total': '1100.00',
            'items': [
                {
                    'name': 'Test Item',
                    'description': 'Test Item Description',
                    'quantity': 1,
                    'unit_price': '1000.00',
                    'line_total': '1000.00'
                }
            ],
            'journal_entry': {
                'date': '2025-12-15',
                'currency_id': self.currency.id,
                'memo': 'AR Invoice',
                'lines': [
                    {
                        'amount': '1100.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': 1, 'segment_code': '100'},
                            {'segment_type_id': 2, 'segment_code': '1100'}
                        ]
                    },
                    {
                        'amount': '1100.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': 1, 'segment_code': '100'},
                            {'segment_type_id': 2, 'segment_code': '4000'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/invoice/ar/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('no accounting period found', str(response.data).lower())


class APInvoicePeriodIntegrationTest(APITestCase):
    """Test AP Invoice integration with Period validation."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test2@example.com',
            name='Test User 2',
            phone_number='1234567891',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        # Create country
        self.country = Country.objects.create(
            name='United States',
            code='US'
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            name='Test Supplier'
        )
        
        # Create segment types
        self.segment_type_company = XX_SegmentType.objects.create(
            segment_name='Company',
            description='Company code'
        )
        self.segment_type_account = XX_SegmentType.objects.create(
            segment_name='Account',
            description='Account number'
        )
        
        # Create segments
        self.segment_100 = XX_Segment.objects.create(
            segment_type=self.segment_type_company,
            code='100',
            alias='Main Company',
            node_type='detail'
        )
        self.segment_5000 = XX_Segment.objects.create(
            segment_type=self.segment_type_account,
            code='5000',
            alias='Expenses',
            node_type='detail'
        )
        self.segment_2100 = XX_Segment.objects.create(
            segment_type=self.segment_type_account,
            code='2100',
            alias='Accounts Payable',
            node_type='detail'
        )
        
        # Create January 2026 period with AP open, GL open
        self.jan_period = Period.objects.create(
            name='January 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            fiscal_year=2026,
            period_number=1
        )
        self.jan_period.ap_period.state = 'open'
        self.jan_period.ap_period.save()
        self.jan_period.gl_period.state = 'open'
        self.jan_period.gl_period.save()
        
        # Create February 2026 period with AP closed
        self.feb_period = Period.objects.create(
            name='February 2026',
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            fiscal_year=2026,
            period_number=2
        )
        # February AP period stays closed (default)
    
    def test_create_ap_invoice_in_open_period(self):
        """Test creating AP invoice when AP period is open."""
        data = {
            'date': '2026-01-15',
            'currency_id': self.currency.id,
            'supplier_id': self.supplier.id,
            'subtotal': '1000.00',
            'tax_amount': '100.00',
            'total': '1100.00',
            'items': [
                {
                    'name': 'Test Item',
                    'description': 'Test Item Description',
                    'quantity': 1,
                    'unit_price': '1000.00',
                    'line_total': '1000.00'
                }
            ],
            'journal_entry': {
                'date': '2026-01-15',
                'currency_id': self.currency.id,
                'memo': 'AP Invoice',
                'lines': [
                    {
                        'amount': '1100.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': self.segment_type_company.id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_type_account.id, 'segment_code': '5000'}
                        ]
                    },
                    {
                        'amount': '1100.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': self.segment_type_company.id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_type_account.id, 'segment_code': '2100'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/invoice/ap/', data, format='json')
        if response.status_code != status.HTTP_201_CREATED:
            print(f"AP Invoice creation failed with status {response.status_code}")
            print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('invoice_id', response.data)
    
    def test_create_ap_invoice_in_closed_period_fails(self):
        """Test creating AP invoice fails when AP period is closed."""
        data = {
            'date': '2026-02-15',  # February period is closed
            'currency_id': self.currency.id,
            'supplier_id': self.supplier.id,
            'subtotal': '1000.00',
            'tax_amount': '100.00',
            'total': '1100.00',
            'items': [
                {
                    'name': 'Test Item',
                    'description': 'Test Item Description',
                    'quantity': 1,
                    'unit_price': '1000.00',
                    'line_total': '1000.00'
                }
            ],
            'journal_entry': {
                'date': '2026-02-15',
                'currency_id': self.currency.id,
                'memo': 'AP Invoice',
                'lines': [
                    {
                        'amount': '1100.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': 1, 'segment_code': '100'},
                            {'segment_type_id': 2, 'segment_code': '5000'}
                        ]
                    },
                    {
                        'amount': '1100.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': 1, 'segment_code': '100'},
                            {'segment_type_id': 2, 'segment_code': '2100'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/invoice/ap/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('closed', str(response.data).lower())

