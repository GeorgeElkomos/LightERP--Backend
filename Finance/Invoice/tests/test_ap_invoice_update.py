"""
Comprehensive tests for AP Invoice UPDATE endpoints.

Tests the PUT/PATCH functionality for AP invoices including:
- Basic field updates (date, currency, country, tax_amount)
- Supplier changes
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

from Finance.Invoice.models import AP_Invoice, Invoice, InvoiceItem
from Finance.BusinessPartner.models import Supplier
from Finance.core.models import Currency, Country
from Finance.GL.models import (
    JournalEntry, JournalLine, XX_SegmentType as SegmentType, XX_Segment, XX_Segment_combination
)
from Finance.Invoice.tests.fixtures import (
    create_currency, create_country, create_supplier,
    create_segment_types, create_segments, create_journal_entry
)


class APInvoiceUpdateBasicFieldsTests(TestCase):
    """Test basic field updates for AP invoices"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create currencies
        self.usd = create_currency('USD', 'US Dollar', '$', is_base=True)
        self.eur = create_currency('EUR', 'Euro', '€', is_base=False)
        
        # Create countries
        self.us = create_country('US', 'United States')
        self.de = create_country('DE', 'Germany')
        
        # Create suppliers
        self.supplier1 = create_supplier('Supplier One')
        self.supplier2 = create_supplier('Supplier Two')
        
        # Create segment types and segments
        self.segment_types = create_segment_types()
        self.segments = create_segments(self.segment_types)
        
        # Create journal entry
        self.je = create_journal_entry(self.usd)
        
        # Create a test AP invoice (creates Invoice automatically)
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            gl_distributions=self.je,
            supplier=self.supplier1
        )
        
        self.invoice = self.ap_invoice.invoice
        
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Item 1',
            description='Test item 1',
            quantity=Decimal('2.00'),
            unit_price=Decimal('50.00')
        )
    
    def test_update_date(self):
        """Test updating invoice date"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        new_date = date.today() + timedelta(days=7)
        
        data = {'date': new_date.isoformat()}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.date, new_date)
    
    def test_update_currency(self):
        """Test updating invoice currency"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'currency_id': self.eur.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.currency.id, self.eur.id)
    
    def test_update_country(self):
        """Test updating invoice country"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'country_id': self.de.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.country.id, self.de.id)
    
    def test_update_country_to_null(self):
        """Test updating invoice country to null"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'country_id': None}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertIsNone(self.invoice.country)
    
    def test_update_tax_amount(self):
        """Test updating tax amount"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'tax_amount': '15.50'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.tax_amount, Decimal('15.50'))
    
    def test_update_supplier(self):
        """Test changing supplier"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {'supplier_id': self.supplier2.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.ap_invoice.refresh_from_db()
        self.assertEqual(self.ap_invoice.supplier.id, self.supplier2.id)
    
    def test_update_multiple_fields(self):
        """Test updating multiple fields at once"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        new_date = date.today() + timedelta(days=5)
        
        data = {
            'date': new_date.isoformat(),
            'currency_id': self.eur.id,
            'country_id': self.de.id,
            'tax_amount': '20.00',
            'supplier_id': self.supplier2.id
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.ap_invoice.refresh_from_db()
        
        self.assertEqual(self.invoice.date, new_date)
        self.assertEqual(self.invoice.currency.id, self.eur.id)
        self.assertEqual(self.invoice.country.id, self.de.id)
        self.assertEqual(self.invoice.tax_amount, Decimal('20.00'))
        self.assertEqual(self.ap_invoice.supplier.id, self.supplier2.id)


class APInvoiceUpdateItemsTests(TestCase):
    """Test updating invoice items"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.supplier = create_supplier()
        
        # Create test invoice with items
        je = create_journal_entry(self.usd)
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            gl_distributions=je,
            supplier=self.supplier
        )
        
        self.invoice = self.ap_invoice.invoice
        
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Item 1',
            description='Original item',
            quantity=Decimal('2.00'),
            unit_price=Decimal('50.00')
        )
    
    def test_update_items_replaces_existing(self):
        """Test that updating items replaces all existing items"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'items': [
                {
                    'name': 'New Item 1',
                    'description': 'First new item',
                    'quantity': '3.00',
                    'unit_price': '25.00'
                },
                {
                    'name': 'New Item 2',
                    'description': 'Second new item',
                    'quantity': '1.00',
                    'unit_price': '50.00'
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
        expected_subtotal = Decimal('3.00') * Decimal('25.00') + Decimal('1.00') * Decimal('50.00')
        self.assertEqual(self.invoice.subtotal, expected_subtotal)
        self.assertEqual(self.invoice.total, expected_subtotal + Decimal('10.00'))
    
    def test_update_items_recalculates_totals(self):
        """Test that subtotal and total are auto-calculated from items"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'items': [
                {
                    'name': 'Item A',
                    'description': 'Test',
                    'quantity': '5.00',
                    'unit_price': '20.00'
                }
            ],
            'tax_amount': '15.00'
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        # Subtotal should be 5 * 20 = 100
        self.assertEqual(self.invoice.subtotal, Decimal('100.00'))
        # Total should be 100 + 15 = 115
        self.assertEqual(self.invoice.total, Decimal('115.00'))
    
    def test_removed_fields_ignored(self):
        """Test that removed fields (subtotal, total, approval_status, payment_status) are ignored"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        # Try to set removed fields - they should be ignored
        data = {
            'items': [
                {
                    'name': 'Item X',
                    'description': 'Test',
                    'quantity': '2.00',
                    'unit_price': '30.00'
                }
            ],
            'subtotal': '999.99',  # Should be ignored
            'total': '888.88',  # Should be ignored
            'approval_status': 'APPROVED',  # Should be ignored
            'payment_status': 'PAID'  # Should be ignored
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        # Subtotal should be calculated from items (2 * 30 = 60), not 999.99
        self.assertEqual(self.invoice.subtotal, Decimal('60.00'))
        # Total should be 60 + 10 (tax) = 70, not 888.88
        self.assertEqual(self.invoice.total, Decimal('70.00'))
        # Status should remain DRAFT
        self.assertEqual(self.invoice.approval_status, 'DRAFT')
        self.assertEqual(self.invoice.payment_status, 'UNPAID')


class APInvoiceUpdateJournalEntryTests(TestCase):
    """Test updating journal entries"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.supplier = create_supplier()
        
        # Create segment types and segments
        self.segment_types = create_segment_types()
        self.segments = create_segments(self.segment_types)
        
        # Create journal entry
        self.je = create_journal_entry(self.usd)
        
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            gl_distributions=self.je,
            supplier=self.supplier
        )
        
        self.invoice = self.ap_invoice.invoice
        
        # Create initial journal entry
        je = JournalEntry.objects.create(
            date=date.today(),
            currency=self.usd,
            memo='Original JE'
        )
        self.invoice.gl_distributions = je
        self.ap_invoice.save()
    
    def test_update_journal_entry_replaces_existing(self):
        """Test that updating journal entry replaces the existing one"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        # Create segment combination using proper API
        from Finance.GL.models import XX_Segment_combination, segment_combination_detials
        combo = XX_Segment_combination.create_combination([
            (self.segment_types['company'].id, self.segments['100'].code),
            (self.segment_types['account'].id, self.segments['6100'].code)
        ])
        
        data = {
            'journal_entry': {
                'date': date.today().isoformat(),
                'memo': 'Updated Journal Entry',
                'currency_id': self.usd.id,
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['6100'].code}
                        ],
                        'type': 'DEBIT',
                        'amount': '100.00',
                        'description': 'Debit line'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['6100'].code}
                        ],
                        'type': 'CREDIT',
                        'amount': '100.00',
                        'description': 'Credit line'
                    }
                ]
            }
        }
        response = self.client.patch(url, data, format='json')
        
        if response.status_code != status.HTTP_200_OK:
            print(f"\nERROR Response: {response.status_code}")
            print(f"Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertEqual(self.invoice.gl_distributions.memo, 'Updated Journal Entry')
        self.assertEqual(self.invoice.gl_distributions.lines.count(), 2)
    
    def test_update_journal_entry_with_segment_details(self):
        """Test updating journal entry with full segment details"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'journal_entry': {
                'date': date.today().isoformat(),
                'currency_id': self.usd.id,
                'memo': 'JE with segment details',
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['6100'].code}
                        ],
                        'type': 'DEBIT',
                        'amount': '50.00'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['2100'].code}
                        ],
                        'type': 'CREDIT',
                        'amount': '50.00'
                    }
                ]
            }
        }
        response = self.client.patch(url, data, format='json')
        
        if response.status_code != status.HTTP_200_OK:
            print(f"\nERROR test_update_journal_entry_with_segment_details: {response.status_code}")
            print(f"Response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertEqual(self.invoice.gl_distributions.lines.count(), 2)


class APInvoiceUpdateValidationTests(TestCase):
    """Test validation rules for updates"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.supplier = create_supplier()
        
        # Create journal entry
        self.je = create_journal_entry(self.usd)
        
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            gl_distributions=self.je,
            supplier=self.supplier
        )
        
        self.invoice = self.ap_invoice.invoice
    
    def test_cannot_update_approved_invoice(self):
        """Test that approved invoices cannot be updated"""
        # Change status to APPROVED
        self.invoice.approval_status = 'APPROVED'
        self.invoice._allow_direct_save = True
        self.invoice.save()
        
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        data = {'tax_amount': '20.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('DRAFT', str(response.data))
    
    def test_cannot_update_posted_invoice(self):
        """Test that invoices posted to GL cannot be updated"""
        # Create and post journal entry
        je = JournalEntry.objects.create(
            date=date.today(),
            currency=self.usd,
            memo='Posted JE',
            posted=True
        )
        self.invoice.gl_distributions = je
        self.invoice._allow_direct_save = True
        self.invoice.save()
        
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        data = {'tax_amount': '20.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('posted', str(response.data).lower())
    
    def test_put_request_works(self):
        """Test that PUT request works (not just PATCH)"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        # PUT requires all fields
        data = {
            'date': date.today().isoformat(),
            'currency_id': self.usd.id,
            'country_id': self.us.id,
            'tax_amount': '15.00',
            'supplier_id': self.supplier.id,
            'items': [
                {
                    'name': 'Item 1',
                    'description': 'Test item',
                    'quantity': '1.00',
                    'unit_price': '100.00'
                }
            ]
        }
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class APInvoiceInvoiceIdBugTests(TestCase):
    """Test the invoice_id vs pk bug fix"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.supplier = create_supplier()
        
        # Create journal entry
        self.je = create_journal_entry(self.usd)
        
        # Create multiple invoices to ensure IDs are different
        for i in range(5):
            ap_inv = AP_Invoice.objects.create(
                date=date.today(),
                currency=self.usd,
                subtotal=Decimal('100.00'),
                tax_amount=Decimal('10.00'),
                total=Decimal('110.00'),
                gl_distributions=self.je,
                supplier=self.supplier
            )
            if i == 0:
                # Only keep reference to the first one
                self.ap_invoice = ap_inv
                self.test_invoice = ap_inv.invoice
    
    def test_detail_endpoint_uses_invoice_id(self):
        """Test that detail endpoint correctly filters by invoice_id"""
        # Use the invoice.id (not ap_invoice.pk) in URL
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.test_invoice.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invoice_id'], self.test_invoice.id)
    
    def test_update_endpoint_uses_invoice_id(self):
        """Test that update endpoint correctly filters by invoice_id"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.test_invoice.id})
        
        data = {'tax_amount': '25.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.test_invoice.refresh_from_db()
        self.assertEqual(self.test_invoice.tax_amount, Decimal('25.00'))
    
    def test_post_to_gl_uses_invoice_id(self):
        """Test that post_to_gl endpoint correctly filters by invoice_id"""
        # Create segment types and segments
        segment_types = create_segment_types()
        segments = create_segments(segment_types)
        
        # Create segment combination using proper API
        from Finance.GL.models import XX_Segment_combination, segment_combination_detials
        combo = XX_Segment_combination.create_combination([
            (segment_types['company'].id, segments['100'].code),
            (segment_types['account'].id, segments['2100'].code)
        ])
        
        # Create journal entry
        je = JournalEntry.objects.create(
            date=date.today(),
            currency=self.usd,
            memo='Test JE'
        )
        self.test_invoice.gl_distributions = je
        self.test_invoice._allow_direct_save = True
        self.test_invoice.save()
        
        url = reverse('finance:invoice:ap-invoice-post-to-gl', kwargs={'pk': self.test_invoice.id})
        response = self.client.post(url)
        
        # May get validation error, but should find the invoice
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class APInvoiceUpdateIntegrationTests(TestCase):
    """Integration tests combining multiple update scenarios"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.eur = create_currency('EUR', 'Euro', '€', is_base=False)
        self.us = create_country()
        self.supplier1 = create_supplier('Supplier 1')
        self.supplier2 = create_supplier('Supplier 2')
        
        self.segment_types = create_segment_types()
        self.segments = create_segments(self.segment_types)
        
        # Create journal entry
        self.je = create_journal_entry(self.usd)
        
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            gl_distributions=self.je,
            supplier=self.supplier1
        )
        
        self.invoice = self.ap_invoice.invoice
        
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Original Item',
            description='Original',
            quantity=Decimal('1.00'),
            unit_price=Decimal('100.00')
        )
    
    def test_complete_invoice_update(self):
        """Test updating all aspects of an invoice at once"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.invoice.id})
        
        # Create segment combination using proper API
        from Finance.GL.models import XX_Segment_combination, segment_combination_detials
        combo = XX_Segment_combination.create_combination([
            (self.segment_types['company'].id, self.segments['100'].code),
            (self.segment_types['account'].id, self.segments['6100'].code)
        ])
        
        new_date = date.today() + timedelta(days=10)
        
        data = {
            'date': new_date.isoformat(),
            'currency_id': self.eur.id,
            'country_id': None,
            'tax_amount': '25.50',
            'supplier_id': self.supplier2.id,
            'items': [
                {
                    'name': 'New Item 1',
                    'description': 'Updated item 1',
                    'quantity': '3.00',
                    'unit_price': '40.00'
                },
                {
                    'name': 'New Item 2',
                    'description': 'Updated item 2',
                    'quantity': '2.00',
                    'unit_price': '60.00'
                }
            ],
            'journal_entry': {
                'date': new_date.isoformat(),
                'currency_id': self.eur.id,
                'memo': 'Complete update JE',
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['6100'].code}
                        ],
                        'type': 'DEBIT',
                        'amount': '240.00'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': self.segments['100'].code},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': self.segments['6100'].code}
                        ],
                        'type': 'CREDIT',
                        'amount': '240.00'
                    }
                ]
            }
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all updates
        self.invoice.refresh_from_db()
        self.ap_invoice.refresh_from_db()
        
        self.assertEqual(self.invoice.date, new_date)
        self.assertEqual(self.invoice.currency.id, self.eur.id)
        self.assertIsNone(self.invoice.country)
        self.assertEqual(self.invoice.tax_amount, Decimal('25.50'))
        self.assertEqual(self.ap_invoice.supplier.id, self.supplier2.id)
        
        # Check items
        items = InvoiceItem.objects.filter(invoice=self.invoice)
        self.assertEqual(items.count(), 2)
        
        # Check calculated totals
        expected_subtotal = Decimal('3.00') * Decimal('40.00') + Decimal('2.00') * Decimal('60.00')
        self.assertEqual(self.invoice.subtotal, expected_subtotal)
        self.assertEqual(self.invoice.total, expected_subtotal + Decimal('25.50'))
        
        # Check journal entry
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertEqual(self.invoice.gl_distributions.memo, 'Complete update JE')

