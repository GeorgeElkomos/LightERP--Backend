"""
Tests for Payment period integration.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from Finance.payments.models import Payment
from Finance.period.models import Period
from Finance.BusinessPartner.models import Customer, Supplier, Country
from Finance.core.models import Currency
from Finance.GL.models import XX_SegmentType, XX_Segment

User = get_user_model()


class PaymentPeriodIntegrationTest(APITestCase):
    """Test Payment integration with Period validation."""
    
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
        
        # Create segment types
        self.company_segment_type = XX_SegmentType.objects.create(
            segment_name='Company',
            is_required=True,
            has_hierarchy=False,
            length=10,
            display_order=1
        )
        self.account_segment_type = XX_SegmentType.objects.create(
            segment_name='Account',
            is_required=True,
            has_hierarchy=True,
            length=10,
            display_order=2
        )
        
        # Create segments
        XX_Segment.objects.create(
            segment_type=self.company_segment_type,
            code='100',
            alias='Main Company',
            node_type='child'
        )
        XX_Segment.objects.create(
            segment_type=self.account_segment_type,
            code='1000',
            alias='Cash',
            node_type='child'
        )
        XX_Segment.objects.create(
            segment_type=self.account_segment_type,
            code='1100',
            alias='Accounts Receivable',
            node_type='child'
        )
        XX_Segment.objects.create(
            segment_type=self.account_segment_type,
            code='2100',
            alias='Accounts Payable',
            node_type='child'
        )
        
        # Create country
        self.country = Country.objects.create(
            name='United States',
            code='US'
        )
        
        # Create customer (for AR payments/receipts)
        self.customer = Customer.objects.create(
            name='Test Customer'
        )
        
        # Create supplier (for AP payments)
        self.supplier = Supplier.objects.create(
            name='Test Supplier'
        )
        
        # Create January 2026 period with AR, AP, GL open
        self.jan_period = Period.objects.create(
            name='January 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            fiscal_year=2026,
            period_number=1
        )
        self.jan_period.ar_period.state = 'open'
        self.jan_period.ar_period.save()
        self.jan_period.ap_period.state = 'open'
        self.jan_period.ap_period.save()
        self.jan_period.gl_period.state = 'open'
        self.jan_period.gl_period.save()
        
        # Create February 2026 period with all closed
        self.feb_period = Period.objects.create(
            name='February 2026',
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            fiscal_year=2026,
            period_number=2
        )
        # February periods stay closed (default)
    
    def test_create_customer_payment_in_open_ar_period(self):
        """Test creating customer payment (receipt) when AR period is open."""
        data = {
            'date': '2026-01-15',
            'business_partner_id': self.customer.id,
            'currency_id': self.currency.id,
            'exchange_rate': '1.0000',
            'gl_entry': {
                'date': '2026-01-15',
                'currency_id': self.currency.id,
                'memo': 'Customer Payment Receipt',
                'lines': [
                    {
                        'amount': '1000.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1000'}
                        ]
                    },
                    {
                        'amount': '1000.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1100'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/payments/', data, format='json')
        if response.status_code != status.HTTP_201_CREATED:
            print(f"\n\nPayment Test Error Response: {response.status_code}")
            print(f"Response data: {response.data}\n\n")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
    
    def test_create_supplier_payment_in_open_ap_period(self):
        """Test creating supplier payment when AP period is open."""
        data = {
            'date': '2026-01-15',
            'business_partner_id': self.supplier.id,
            'currency_id': self.currency.id,
            'exchange_rate': '1.0000',
            'gl_entry': {
                'date': '2026-01-15',
                'currency_id': self.currency.id,
                'memo': 'Supplier Payment',
                'lines': [
                    {
                        'amount': '1000.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '2100'}
                        ]
                    },
                    {
                        'amount': '1000.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1000'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
    
    def test_create_customer_payment_in_closed_ar_period_fails(self):
        """Test creating customer payment fails when AR period is closed."""
        data = {
            'date': '2026-02-15',  # February AR period is closed
            'business_partner_id': self.customer.id,
            'currency_id': self.currency.id,
            'exchange_rate': '1.0000',
            'gl_entry': {
                'date': '2026-02-15',
                'currency_id': self.currency.id,
                'memo': 'Customer Payment Receipt',
                'lines': [
                    {
                        'amount': '1000.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1000'}
                        ]
                    },
                    {
                        'amount': '1000.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1100'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('closed', str(response.data).lower())
    
    def test_create_supplier_payment_in_closed_ap_period_fails(self):
        """Test creating supplier payment fails when AP period is closed."""
        data = {
            'date': '2026-02-15',  # February AP period is closed
            'business_partner_id': self.supplier.id,
            'currency_id': self.currency.id,
            'exchange_rate': '1.0000',
            'gl_entry': {
                'date': '2026-02-15',
                'currency_id': self.currency.id,
                'memo': 'Supplier Payment',
                'lines': [
                    {
                        'amount': '1000.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '2100'}
                        ]
                    },
                    {
                        'amount': '1000.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1000'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('closed', str(response.data).lower())
    
    def test_create_payment_no_period_fails(self):
        """Test creating payment fails when no period exists."""
        data = {
            'date': '2025-12-15',  # No period exists for this date
            'business_partner_id': self.customer.id,
            'currency_id': self.currency.id,
            'exchange_rate': '1.0000',
            'gl_entry': {
                'date': '2025-12-15',
                'currency_id': self.currency.id,
                'memo': 'Customer Payment Receipt',
                'lines': [
                    {
                        'amount': '1000.00',
                        'type': 'DEBIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1000'}
                        ]
                    },
                    {
                        'amount': '1000.00',
                        'type': 'CREDIT',
                        'segments': [
                            {'segment_type_id': self.company_segment_type.id, 'segment_code': '100'},
                            {'segment_type_id': self.account_segment_type.id, 'segment_code': '1100'}
                        ]
                    }
                ]
            }
        }
        
        response = self.client.post('/finance/payments/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('no accounting period found', str(response.data).lower())

