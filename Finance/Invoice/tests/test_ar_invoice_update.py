"""
Comprehensive tests for AR Invoice UPDATE endpoints.

Tests the PUT/PATCH functionality for AR invoices including:
- Basic field updates (date, currency, country, tax_amount)
- Customer changes
- Items updates (add, remove, modify)
- Journal entry updates
- invoice_id vs pk bug fix validation
- Validation rules (DRAFT only, not posted to GL)
- Ensuring removed fields (approval_status, payment_status, subtotal, total) don't affect updates
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from Finance.Invoice.models import AR_Invoice, Invoice, InvoiceItem
from Finance.BusinessPartner.models import Customer
from Finance.core.models import Currency, Country
from Finance.GL.models import (
    JournalEntry, JournalLine, XX_SegmentType as SegmentType, XX_Segment, XX_Segment_combination
)
from Finance.Invoice.tests.fixtures import (
    create_currency, create_country, create_customer,
    create_segment_types, create_segments, create_journal_entry
)


class ARInvoiceUpdateBasicFieldsTests(TestCase):
    """Test basic field updates for AR invoices"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create currencies
        self.usd = create_currency('USD', 'US Dollar', '$', is_base=True)
        self.gbp = create_currency('GBP', 'British Pound', '£', is_base=False)
        
        # Create countries
        self.us = create_country('US', 'United States')
        self.uk = create_country('GB', 'United Kingdom')
        
        # Create customers
        self.customer1 = create_customer('Customer One')
        self.customer2 = create_customer('Customer Two')
        
        # Create journal entry
        je = create_journal_entry(self.usd)
        
        # Create a test AR invoice
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('200.00'),
            tax_amount=Decimal('20.00'),
            total=Decimal('220.00'),
            gl_distributions=je,
            customer=self.customer1
        )
        
        self.invoice = self.ar_invoice.invoice
        
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Service 1',
            description='Consulting service',
            quantity=Decimal('4.00'),
            unit_price=Decimal('50.00')
        )
    
    def test_update_date(self):
        """Test updating invoice date"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        new_date = date.today() + timedelta(days=14)
        
        data = {'date': new_date.isoformat()}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.date, new_date)
    
    def test_update_currency(self):
        """Test updating invoice currency"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'currency_id': self.gbp.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.currency.id, self.gbp.id)
    
    def test_update_country(self):
        """Test updating invoice country"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'country_id': self.uk.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.country.id, self.uk.id)
    
    def test_update_tax_amount(self):
        """Test updating tax amount"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'tax_amount': '30.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.tax_amount, Decimal('30.00'))
    
    def test_update_customer(self):
        """Test changing customer"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'customer_id': self.customer2.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.ar_invoice.refresh_from_db()
        self.assertEqual(self.ar_invoice.customer.id, self.customer2.id)
    
    def test_update_multiple_fields(self):
        """Test updating multiple fields at once"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        new_date = date.today() + timedelta(days=30)
        
        data = {
            'date': new_date.isoformat(),
            'currency_id': self.gbp.id,
            'country_id': self.uk.id,
            'tax_amount': '35.00',
            'customer_id': self.customer2.id
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.ar_invoice.refresh_from_db()
        
        self.assertEqual(self.invoice.date, new_date)
        self.assertEqual(self.invoice.currency.id, self.gbp.id)
        self.assertEqual(self.invoice.country.id, self.uk.id)
        self.assertEqual(self.invoice.tax_amount, Decimal('35.00'))
        self.assertEqual(self.ar_invoice.customer.id, self.customer2.id)


class ARInvoiceUpdateItemsTests(TestCase):
    """Test updating invoice items"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.customer = create_customer()
        
        # Create test invoice with items
        je = create_journal_entry(self.usd)
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('500.00'),
            tax_amount=Decimal('50.00'),
            total=Decimal('550.00'),
            gl_distributions=je,
            customer=self.customer
        )
        
        self.invoice = self.ar_invoice.invoice
        
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Original Service',
            description='Original service description',
            quantity=Decimal('10.00'),
            unit_price=Decimal('50.00')
        )
    
    def test_update_items_replaces_existing(self):
        """Test that updating items replaces all existing items"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'items': [
                {
                    'name': 'Service A',
                    'description': 'New service A',
                    'quantity': '5.00',
                    'unit_price': '100.00'
                },
                {
                    'name': 'Service B',
                    'description': 'New service B',
                    'quantity': '3.00',
                    'unit_price': '150.00'
                }
            ]
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check items were replaced
        items = InvoiceItem.objects.filter(invoice=self.invoice)
        self.assertEqual(items.count(), 2)
        
        # Check subtotal and total were recalculated
        self.invoice.refresh_from_db()
        expected_subtotal = Decimal('5.00') * Decimal('100.00') + Decimal('3.00') * Decimal('150.00')
        self.assertEqual(self.invoice.subtotal, expected_subtotal)
        self.assertEqual(self.invoice.total, expected_subtotal + Decimal('50.00'))
    
    def test_update_items_with_tax_change(self):
        """Test updating items and tax together"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'items': [
                {
                    'name': 'Product X',
                    'description': 'Test product',
                    'quantity': '8.00',
                    'unit_price': '75.00'
                }
            ],
            'tax_amount': '60.00'
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        # Subtotal should be 8 * 75 = 600
        self.assertEqual(self.invoice.subtotal, Decimal('600.00'))
        # Total should be 600 + 60 = 660
        self.assertEqual(self.invoice.total, Decimal('660.00'))
    
    def test_removed_fields_are_ignored(self):
        """Test that removed fields cannot override calculated values"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'items': [
                {
                    'name': 'Test Item',
                    'description': 'Test',
                    'quantity': '4.00',
                    'unit_price': '25.00'
                }
            ],
            'tax_amount': '10.00',
            'subtotal': '9999.99',  # Should be ignored
            'total': '8888.88',  # Should be ignored
            'approval_status': 'APPROVED',  # Should be ignored
            'payment_status': 'PAID'  # Should be ignored
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        # Values should be calculated, not from provided data
        self.assertEqual(self.invoice.subtotal, Decimal('100.00'))
        self.assertEqual(self.invoice.total, Decimal('110.00'))
        self.assertEqual(self.invoice.approval_status, 'DRAFT')
        self.assertEqual(self.invoice.payment_status, 'UNPAID')


class ARInvoiceUpdateJournalEntryTests(TestCase):
    """Test updating journal entries"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.customer = create_customer()
        
        # Create segment types and segments
        self.segment_types = create_segment_types()
        self.segments = create_segments(self.segment_types)
        
        # Create journal entry
        self.je = create_journal_entry(self.usd)
        
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('100.00'),
            total=Decimal('1100.00'),
            gl_distributions=self.je,
            customer=self.customer
        )
        
        self.invoice = self.ar_invoice.invoice
    
    def test_add_journal_entry_to_invoice(self):
        """Test adding journal entry to invoice without one"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        # Create segment combination using proper API
        from Finance.GL.models import XX_Segment_combination, segment_combination_detials
        combo = XX_Segment_combination.create_combination([
            (self.segment_types['company'].id, self.segments['100'].code),
            (self.segment_types['account'].id, self.segments['1200'].code)
        ])
        
        data = {
            'journal_entry': {
                'date': date.today().isoformat(),
                'currency_id': self.usd.id,
                'memo': 'AR Journal Entry',
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['1200'].code}
                        ],
                        'type': 'DEBIT',
                        'amount': '1100.00'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['1200'].code}
                        ],
                        'type': 'CREDIT',
                        'amount': '1100.00'
                    }
                ]
            }
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertEqual(self.invoice.gl_distributions.memo, 'AR Journal Entry')
        self.assertEqual(self.invoice.gl_distributions.lines.count(), 2)
    
    def test_replace_journal_entry(self):
        """Test replacing existing journal entry"""
        # Create initial journal entry
        je = JournalEntry.objects.create(
            date=date.today(),
            currency=self.usd,
            memo='Old JE'
        )
        self.invoice.gl_distributions = je
        self.invoice._allow_direct_save = True
        self.invoice.save()
        
        old_je_id = je.id
        
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'journal_entry': {
                'date': date.today().isoformat(),
                'currency_id': self.usd.id,
                'memo': 'New AR JE',
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['4000'].code}
                        ],
                        'type': 'DEBIT',
                        'amount': '500.00'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['4000'].code}
                        ],
                        'type': 'CREDIT',
                        'amount': '500.00'
                    }
                ]
            }
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertNotEqual(self.invoice.gl_distributions.id, old_je_id)
        self.assertEqual(self.invoice.gl_distributions.memo, 'New AR JE')


class ARInvoiceUpdateValidationTests(TestCase):
    """Test validation rules for updates"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.customer = create_customer()
        
        je = create_journal_entry(self.usd)
        
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('300.00'),
            tax_amount=Decimal('30.00'),
            total=Decimal('330.00'),
            customer=self.customer,
            gl_distributions=je
        )
        
        self.invoice = self.ar_invoice.invoice
    
    def test_cannot_update_approved_invoice(self):
        """Test that approved invoices cannot be updated"""
        self.invoice.approval_status = 'APPROVED'
        self.invoice._allow_direct_save = True
        self.invoice.save()
        
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        data = {'tax_amount': '40.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('DRAFT', str(response.data))
    
    def test_cannot_update_rejected_invoice(self):
        """Test that rejected invoices cannot be updated"""
        self.invoice.approval_status = 'REJECTED'
        self.invoice._allow_direct_save = True
        self.invoice.save()
        
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        data = {'tax_amount': '40.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_cannot_update_posted_invoice(self):
        """Test that invoices posted to GL cannot be updated"""
        je = JournalEntry.objects.create(
            date=date.today(),
            currency=self.usd,
            memo='Posted JE',
            posted=True
        )
        self.invoice.gl_distributions = je
        self.invoice._allow_direct_save = True
        self.invoice.save()
        
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        data = {'tax_amount': '40.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('posted', str(response.data).lower())
    
    def test_put_and_patch_both_work(self):
        """Test that both PUT and PATCH work correctly"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        # Test PATCH (partial update)
        patch_data = {'tax_amount': '35.00'}
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.tax_amount, Decimal('35.00'))
        
        # Test PUT (full update)
        put_data = {
            'date': date.today().isoformat(),
            'currency_id': self.usd.id,
            'country_id': self.us.id,
            'tax_amount': '50.00',
            'customer_id': self.customer.id,
            'items': [
                {
                    'name': 'Item',
                    'description': 'Desc',
                    'quantity': '1.00',
                    'unit_price': '300.00'
                }
            ]
        }
        response = self.client.put(url, put_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ARInvoiceInvoiceIdBugTests(TestCase):
    """Test the invoice_id vs pk bug fix"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.customer = create_customer()
        
        # AR_Invoice has OneToOneField with primary_key=True, so pk should equal invoice_id
        # But test to ensure the filtering is correct
        je = create_journal_entry(self.usd)
        
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            customer=self.customer,
            gl_distributions=je
        )
        
        self.invoice = self.ar_invoice.invoice
        
        # Verify the relationship
        self.assertEqual(self.ar_invoice.pk, self.invoice.id)
    
    def test_detail_endpoint_uses_invoice_id(self):
        """Test that detail endpoint correctly filters by invoice_id"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invoice_id'], self.invoice.id)
    
    def test_update_endpoint_uses_invoice_id(self):
        """Test that update endpoint correctly filters by invoice_id"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'tax_amount': '15.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.tax_amount, Decimal('15.00'))


class ARInvoiceUpdateIntegrationTests(TestCase):
    """Integration tests combining multiple update scenarios"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.gbp = create_currency('GBP', 'British Pound', '£', is_base=False)
        self.us = create_country()
        self.customer1 = create_customer('Customer 1')
        self.customer2 = create_customer('Customer 2')
        
        self.segment_types = create_segment_types()
        self.segments = create_segments(self.segment_types)
        
        je = create_journal_entry(self.usd)
        
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('100.00'),
            total=Decimal('1100.00'),
            customer=self.customer1,
            gl_distributions=je
        )
        
        self.invoice = self.ar_invoice.invoice
        
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Original Service',
            description='Original',
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00')
        )
    
    def test_complete_invoice_update(self):
        """Test updating all aspects of an invoice at once"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.invoice.id})
        
        # Create segment combination using the proper API
        combo = XX_Segment_combination.create_combination([
            (self.segment_types['company'].id, '100'),
            (self.segment_types['account'].id, '4000')
        ])
        
        new_date = date.today() + timedelta(days=15)
        
        data = {
            'date': new_date.isoformat(),
            'currency_id': self.gbp.id,
            'country_id': None,
            'tax_amount': '80.00',
            'customer_id': self.customer2.id,
            'items': [
                {
                    'name': 'Consulting Service',
                    'description': 'Professional consulting',
                    'quantity': '20.00',
                    'unit_price': '50.00'
                },
                {
                    'name': 'Training Service',
                    'description': 'Technical training',
                    'quantity': '5.00',
                    'unit_price': '200.00'
                }
            ],
            'journal_entry': {
                'currency_id': self.gbp.id,
                'date': new_date.isoformat(),
                'memo': 'Complete AR update',
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': '4000'}
                        ],
                        'type': 'DEBIT',
                        'amount': '2080.00',
                        'description': 'Receivable'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': '4000'}
                        ],
                        'type': 'CREDIT',
                        'amount': '2080.00',
                        'description': 'Revenue'
                    }
                ]
            }
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all updates
        self.invoice.refresh_from_db()
        self.ar_invoice.refresh_from_db()
        
        self.assertEqual(self.invoice.date, new_date)
        self.assertEqual(self.invoice.currency.id, self.gbp.id)
        self.assertIsNone(self.invoice.country)
        self.assertEqual(self.invoice.tax_amount, Decimal('80.00'))
        self.assertEqual(self.ar_invoice.customer.id, self.customer2.id)
        
        # Check items
        items = InvoiceItem.objects.filter(invoice=self.invoice)
        self.assertEqual(items.count(), 2)
        
        # Check calculated totals
        expected_subtotal = Decimal('20.00') * Decimal('50.00') + Decimal('5.00') * Decimal('200.00')
        self.assertEqual(self.invoice.subtotal, expected_subtotal)
        self.assertEqual(self.invoice.total, expected_subtotal + Decimal('80.00'))
        
        # Check journal entry
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertEqual(self.invoice.gl_distributions.memo, 'Complete AR update')
