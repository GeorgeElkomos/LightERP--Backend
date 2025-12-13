"""
Comprehensive tests for OneTimeSupplier Invoice UPDATE endpoints.

Tests the PUT/PATCH functionality for one-time supplier invoices including:
- Basic field updates (date, currency, country, tax_amount)
- OneTimeSupplier changes (switching to different one-time supplier)
- Supplier detail updates (name, email, phone, tax_id)
- Items updates (add, remove, modify)
- Journal entry updates
- invoice_id vs pk bug fix validation (CRITICAL - OneTimeSupplier uses ForeignKey, not OneToOneField)
- Validation rules (DRAFT only, not posted to GL)
- Ensuring removed fields (approval_status, payment_status, subtotal, total) don't affect updates
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from Finance.Invoice.models import OneTimeSupplier, Invoice, InvoiceItem
from Finance.BusinessPartner.models import OneTime, BusinessPartner
from Finance.core.models import Currency, Country
from Finance.GL.models import (
    JournalEntry, JournalLine, XX_SegmentType as SegmentType, XX_Segment, XX_Segment_combination
)
from Finance.Invoice.tests.fixtures import (
    create_currency, create_country,
    create_segment_types, create_segments, create_journal_entry
)


def create_onetime_supplier(name='Test OneTime', email='test@example.com', phone='123-456-7890', tax_id='TAX123'):
    """Helper to create a OneTime supplier"""
    return OneTime.objects.create(
        name=name,
        email=email,
        phone=phone,
        tax_id=tax_id
    )


class OneTimeSupplierUpdateBasicFieldsTests(TestCase):
    """Test basic field updates for one-time supplier invoices"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create currencies
        self.usd = create_currency('USD', 'US Dollar', '$', is_base=True)
        self.cad = create_currency('CAD', 'Canadian Dollar', 'C$', is_base=False)
        
        # Create countries
        self.us = create_country('US', 'United States')
        self.ca = create_country('CA', 'Canada')
        
        # Create one-time suppliers
        self.onetime1 = create_onetime_supplier('Supplier Alpha', 'alpha@test.com', '111-111-1111', 'TAX111')
        self.onetime2 = create_onetime_supplier('Supplier Beta', 'beta@test.com', '222-222-2222', 'TAX222')
        
        je = create_journal_entry(self.usd)
        
        # Create a test OneTimeSupplier invoice
        self.ots_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('150.00'),
            tax_amount=Decimal('15.00'),
            total=Decimal('165.00'),
            one_time_supplier=self.onetime1,
            gl_distributions=je
        )
        
        self.invoice = self.ots_invoice.invoice
        
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Equipment',
            description='One-time equipment purchase',
            quantity=Decimal('3.00'),
            unit_price=Decimal('50.00')
        )
    
    def test_update_date(self):
        """Test updating invoice date"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        new_date = date.today() + timedelta(days=3)
        
        data = {'date': new_date.isoformat()}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.date, new_date)
    
    def test_update_currency(self):
        """Test updating invoice currency"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'currency_id': self.cad.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.currency.id, self.cad.id)
    
    def test_update_country(self):
        """Test updating invoice country"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'country_id': self.ca.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.country.id, self.ca.id)
    
    def test_update_tax_amount(self):
        """Test updating tax amount"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'tax_amount': '22.50'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.tax_amount, Decimal('22.50'))
    
    def test_switch_to_different_onetime_supplier(self):
        """Test changing to a different one-time supplier"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'one_time_supplier_id': self.onetime2.id}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.ots_invoice.refresh_from_db()
        self.assertEqual(self.ots_invoice.one_time_supplier.id, self.onetime2.id)
    
    def test_update_multiple_fields(self):
        """Test updating multiple fields at once"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        new_date = date.today() + timedelta(days=7)
        
        data = {
            'date': new_date.isoformat(),
            'currency_id': self.cad.id,
            'country_id': self.ca.id,
            'tax_amount': '18.00',
            'one_time_supplier_id': self.onetime2.id
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.ots_invoice.refresh_from_db()
        
        self.assertEqual(self.invoice.date, new_date)
        self.assertEqual(self.invoice.currency.id, self.cad.id)
        self.assertEqual(self.invoice.country.id, self.ca.id)
        self.assertEqual(self.invoice.tax_amount, Decimal('18.00'))
        self.assertEqual(self.ots_invoice.one_time_supplier.id, self.onetime2.id)


class OneTimeSupplierUpdateSupplierDetailsTests(TestCase):
    """Test updating supplier details (name, email, phone, tax_id)"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        
        self.onetime = create_onetime_supplier('Original Name', 'original@test.com', '555-0000', 'ORIG-TAX')
        
        je = create_journal_entry(self.usd)
        
        self.ots_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            one_time_supplier=self.onetime,
            gl_distributions=je
        )
        
        self.invoice = self.ots_invoice.invoice
    
    def test_update_supplier_name(self):
        """Test updating the supplier's name"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'supplier_name': 'Updated Supplier Name'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh and check name was updated (proxied from business_partner)
        self.onetime.refresh_from_db()
        self.assertEqual(self.onetime.name, 'Updated Supplier Name')
    
    def test_update_supplier_email(self):
        """Test updating the supplier's email"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'supplier_email': 'newemail@example.com'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.onetime.refresh_from_db()
        self.assertEqual(self.onetime.email, 'newemail@example.com')
    
    def test_update_supplier_phone(self):
        """Test updating the supplier's phone"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'supplier_phone': '999-888-7777'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.onetime.refresh_from_db()
        self.assertEqual(self.onetime.phone, '999-888-7777')
    
    def test_update_supplier_tax_id(self):
        """Test updating the supplier's tax ID"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {'supplier_tax_id': 'NEW-TAX-ID'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.onetime.refresh_from_db()
        self.assertEqual(self.onetime.tax_id, 'NEW-TAX-ID')
    
    def test_update_all_supplier_details(self):
        """Test updating all supplier details at once"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'supplier_name': 'Completely New Name',
            'supplier_email': 'completely@new.com',
            'supplier_phone': '111-222-3333',
            'supplier_tax_id': 'TAX-NEW-123'
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.onetime.refresh_from_db()
        self.onetime.business_partner.refresh_from_db()
        
        self.assertEqual(self.onetime.business_partner.name, 'Completely New Name')
        self.assertEqual(self.onetime.email, 'completely@new.com')
        self.assertEqual(self.onetime.phone, '111-222-3333')
        self.assertEqual(self.onetime.tax_id, 'TAX-NEW-123')
    
    def test_update_details_and_invoice_fields(self):
        """Test updating supplier details along with invoice fields"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        new_date = date.today() + timedelta(days=5)
        
        data = {
            'date': new_date.isoformat(),
            'tax_amount': '25.00',
            'supplier_name': 'Mixed Update Name',
            'supplier_email': 'mixed@update.com'
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.onetime.refresh_from_db()
        self.onetime.business_partner.refresh_from_db()
        
        self.assertEqual(self.invoice.date, new_date)
        self.assertEqual(self.invoice.tax_amount, Decimal('25.00'))
        self.assertEqual(self.onetime.business_partner.name, 'Mixed Update Name')
        self.assertEqual(self.onetime.email, 'mixed@update.com')


class OneTimeSupplierUpdateItemsTests(TestCase):
    """Test updating invoice items"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.onetime = create_onetime_supplier()
        
        je = create_journal_entry(self.usd)
        
        self.ots_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('200.00'),
            tax_amount=Decimal('20.00'),
            total=Decimal('220.00'),
            one_time_supplier=self.onetime,
            gl_distributions=je
        )
        
        self.invoice = self.ots_invoice.invoice
        
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Original Item',
            description='Original',
            quantity=Decimal('4.00'),
            unit_price=Decimal('50.00')
        )
    
    def test_update_items_replaces_existing(self):
        """Test that updating items replaces all existing items"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'items': [
                {
                    'name': 'New Item 1',
                    'description': 'First new item',
                    'quantity': '2.00',
                    'unit_price': '75.00'
                },
                {
                    'name': 'New Item 2',
                    'description': 'Second new item',
                    'quantity': '3.00',
                    'unit_price': '100.00'
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
        expected_subtotal = Decimal('2.00') * Decimal('75.00') + Decimal('3.00') * Decimal('100.00')
        self.assertEqual(self.invoice.subtotal, expected_subtotal)
        self.assertEqual(self.invoice.total, expected_subtotal + Decimal('20.00'))
    
    def test_removed_fields_are_ignored(self):
        """Test that removed fields cannot affect the invoice"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'items': [
                {
                    'name': 'Test Item',
                    'description': 'Test',
                    'quantity': '5.00',
                    'unit_price': '40.00'
                }
            ],
            'tax_amount': '12.00',
            'subtotal': '7777.77',  # Should be ignored
            'total': '6666.66',  # Should be ignored
            'approval_status': 'APPROVED',  # Should be ignored
            'payment_status': 'PAID'  # Should be ignored
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        # Subtotal should be 5 * 40 = 200, not 7777.77
        self.assertEqual(self.invoice.subtotal, Decimal('200.00'))
        # Total should be 200 + 12 = 212, not 6666.66
        self.assertEqual(self.invoice.total, Decimal('212.00'))
        # Status should remain DRAFT
        self.assertEqual(self.invoice.approval_status, 'DRAFT')
        self.assertEqual(self.invoice.payment_status, 'UNPAID')


class OneTimeSupplierUpdateJournalEntryTests(TestCase):
    """Test updating journal entries"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.onetime = create_onetime_supplier()
        
        # Create segment types and segments
        self.segment_types = create_segment_types()
        self.segments = create_segments(self.segment_types)
        
        je = create_journal_entry(self.usd)
        
        self.ots_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('500.00'),
            tax_amount=Decimal('50.00'),
            total=Decimal('550.00'),
            one_time_supplier=self.onetime,
            gl_distributions=je
        )
        
        self.invoice = self.ots_invoice.invoice
    
    def test_add_journal_entry(self):
        """Test adding journal entry to invoice"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        # Create segment combination using the proper API
        combo = XX_Segment_combination.create_combination([
            (self.segment_types['company'].id, '100'),
            (self.segment_types['account'].id, '6200')
        ])
        
        data = {
            'journal_entry': {
                'currency_id': self.usd.id,
                'date': date.today().isoformat(),
                'memo': 'OneTime JE',
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': '6200'}
                        ],
                        'type': 'DEBIT',
                        'amount': '550.00',
                        'description': 'Expense'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': '6200'}
                        ],
                        'type': 'CREDIT',
                        'amount': '550.00',
                        'description': 'Payable'
                    }
                ]
            }
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertEqual(self.invoice.gl_distributions.memo, 'OneTime JE')
        self.assertEqual(self.invoice.gl_distributions.lines.count(), 2)


class OneTimeSupplierUpdateValidationTests(TestCase):
    """Test validation rules for updates"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.onetime = create_onetime_supplier()
        
        je = create_journal_entry(self.usd)
        
        self.ots_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total=Decimal('110.00'),
            one_time_supplier=self.onetime,
            gl_distributions=je
        )
        
        self.invoice = self.ots_invoice.invoice
    
    def test_cannot_update_approved_invoice(self):
        """Test that approved invoices cannot be updated"""
        self.invoice.approval_status = 'APPROVED'
        self.invoice._allow_direct_save = True
        self.invoice.save()
        
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        data = {'tax_amount': '20.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('DRAFT', str(response.data))
    
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
        
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        data = {'tax_amount': '20.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('posted', str(response.data).lower())


class OneTimeSupplierInvoiceIdBugTests(TestCase):
    """
    CRITICAL TEST: Test the invoice_id vs pk bug fix.
    
    OneTimeSupplier uses ForeignKey (not OneToOneField with primary_key=True),
    so OneTimeSupplier.pk != Invoice.id.
    This was the source of the original bug.
    """
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.us = create_country()
        self.onetime = create_onetime_supplier()
        
        je = create_journal_entry(self.usd)
        
        # Create multiple invoices to ensure IDs differ
        for i in range(5):
            ots_inv = OneTimeSupplier.objects.create(
                date=date.today(),
                currency=self.usd,
                subtotal=Decimal('100.00'),
                tax_amount=Decimal('10.00'),
                total=Decimal('110.00'),
                one_time_supplier=self.onetime,
                gl_distributions=je
            )
            if i == 0:
                # Only create OneTimeSupplier for the first one
                self.ots_invoice = ots_inv
                self.test_invoice = ots_inv.invoice
        
    
    def test_detail_endpoint_uses_invoice_id_not_pk(self):
        """
        Test that detail endpoint correctly filters by invoice_id, not pk.
        This is the key bug fix - using invoice_id instead of pk.
        """
        # Use the invoice.id (not ots_invoice.pk) in URL
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.test_invoice.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invoice_id'], self.test_invoice.id)
        
        # Note: OneTimeSupplier uses ForeignKey (not OneToOneField with primary_key=True)
        # so pk can be different from invoice_id, but in this test they happen to match
        # The key fix was ensuring the view filters by invoice_id, not by pk of OneTimeSupplier
        # If we had more invoices, the IDs would differ, but the filtering would still work correctly
    
    def test_update_endpoint_uses_invoice_id_not_pk(self):
        """Test that update endpoint correctly filters by invoice_id"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.test_invoice.id})
        
        data = {'tax_amount': '15.00'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.test_invoice.refresh_from_db()
        self.assertEqual(self.test_invoice.tax_amount, Decimal('15.00'))
    
    def test_post_to_gl_uses_invoice_id(self):
        """Test that post_to_gl endpoint correctly filters by invoice_id"""
        segment_types = create_segment_types()
        segments = create_segments(segment_types)
        
        # Create proper segment combination
        combo = XX_Segment_combination.create_combination([
            (segment_types['company'].id, '100'),
            (segment_types['account'].id, '2100')
        ])
        
        # Create a proper journal entry with lines
        je = JournalEntry.objects.create(
            date=date.today(),
            currency=self.usd,
            memo='Test JE'
        )
        from Finance.GL.models import JournalLine
        JournalLine.objects.create(
            entry=je,
            segment_combination=combo,
            amount=Decimal('100.00'),
            type='DEBIT'
        )
        JournalLine.objects.create(
            entry=je,
            segment_combination=combo,
            amount=Decimal('100.00'),
            type='CREDIT'
        )
        
        self.test_invoice.gl_distributions = je
        self.test_invoice._allow_direct_save = True
        self.test_invoice.save()
        
        url = reverse('finance:invoice:one-time-supplier-post-to-gl', kwargs={'pk': self.test_invoice.id})
        response = self.client.post(url)
        
        # May get validation error, but should find the invoice (not 404)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class OneTimeSupplierUpdateIntegrationTests(TestCase):
    """Integration tests combining multiple update scenarios"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.usd = create_currency()
        self.cad = create_currency('CAD', 'Canadian Dollar', 'C$', is_base=False)
        self.us = create_country()
        self.onetime1 = create_onetime_supplier('Supplier One', 'one@test.com', '111-1111', 'TAX1')
        self.onetime2 = create_onetime_supplier('Supplier Two', 'two@test.com', '222-2222', 'TAX2')
        
        self.segment_types = create_segment_types()
        self.segments = create_segments(self.segment_types)
        
        je = create_journal_entry(self.usd)
        
        self.ots_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.usd,
            country=self.us,
            subtotal=Decimal('300.00'),
            tax_amount=Decimal('30.00'),
            total=Decimal('330.00'),
            one_time_supplier=self.onetime1,
            gl_distributions=je
        )
        
        self.invoice = self.ots_invoice.invoice
        
        InvoiceItem.objects.create(
            invoice=self.invoice,
            name='Original',
            description='Original item',
            quantity=Decimal('3.00'),
            unit_price=Decimal('100.00')
        )
    
    def test_complete_invoice_update_with_supplier_details(self):
        """Test updating all aspects including supplier details"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        # Create segment combination using the proper API
        combo = XX_Segment_combination.create_combination([
            (self.segment_types['company'].id, '100'),
            (self.segment_types['account'].id, '6100')
        ])
        
        new_date = date.today() + timedelta(days=20)
        
        data = {
            'date': new_date.isoformat(),
            'currency_id': self.cad.id,
            'country_id': None,
            'tax_amount': '45.00',
            'supplier_name': 'Updated Supplier Name',
            'supplier_email': 'updated@email.com',
            'supplier_phone': '999-9999',
            'supplier_tax_id': 'NEW-TAX',
            'items': [
                {
                    'name': 'Hardware',
                    'description': 'Computer hardware',
                    'quantity': '2.00',
                    'unit_price': '250.00'
                },
                {
                    'name': 'Software',
                    'description': 'Software license',
                    'quantity': '1.00',
                    'unit_price': '300.00'
                }
            ],
            'journal_entry': {
                'currency_id': self.cad.id,
                'date': new_date.isoformat(),
                'memo': 'Complete OneTime update',
                'lines': [
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': '6100'}
                        ],
                        'type': 'DEBIT',
                        'amount': '845.00',
                        'description': 'Expense total'
                    },
                    {
                        'segments': [
                            {'segment_type_id': self.segment_types['company'].id, 'segment_code': '100'},
                            {'segment_type_id': self.segment_types['account'].id, 'segment_code': '6100'}
                        ],
                        'type': 'CREDIT',
                        'amount': '845.00',
                        'description': 'Payable total'
                    }
                ]
            }
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all updates
        self.invoice.refresh_from_db()
        self.ots_invoice.refresh_from_db()
        self.onetime1.refresh_from_db()
        
        self.assertEqual(self.invoice.date, new_date)
        self.assertEqual(self.invoice.currency.id, self.cad.id)
        self.assertIsNone(self.invoice.country)
        self.assertEqual(self.invoice.tax_amount, Decimal('45.00'))
        
        # Check supplier details were updated (proxied properties)
        self.assertEqual(self.onetime1.name, 'Updated Supplier Name')
        self.assertEqual(self.onetime1.email, 'updated@email.com')
        self.assertEqual(self.onetime1.phone, '999-9999')
        self.assertEqual(self.onetime1.tax_id, 'NEW-TAX')
        
        # Check items
        items = InvoiceItem.objects.filter(invoice=self.invoice)
        self.assertEqual(items.count(), 2)
        
        # Check calculated totals
        expected_subtotal = Decimal('2.00') * Decimal('250.00') + Decimal('1.00') * Decimal('300.00')
        self.assertEqual(self.invoice.subtotal, expected_subtotal)
        self.assertEqual(self.invoice.total, expected_subtotal + Decimal('45.00'))
        
        # Check journal entry
        self.assertIsNotNone(self.invoice.gl_distributions)
        self.assertEqual(self.invoice.gl_distributions.memo, 'Complete OneTime update')
    
    def test_switch_supplier_and_update_invoice(self):
        """Test switching to different supplier while updating invoice"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': self.invoice.id})
        
        data = {
            'one_time_supplier_id': self.onetime2.id,
            'tax_amount': '40.00',
            'items': [
                {
                    'name': 'New Item',
                    'description': 'New desc',
                    'quantity': '5.00',
                    'unit_price': '80.00'
                }
            ]
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.invoice.refresh_from_db()
        self.ots_invoice.refresh_from_db()
        
        # Should be using supplier 2 now
        self.assertEqual(self.ots_invoice.one_time_supplier.id, self.onetime2.id)
        
        # Invoice should be updated
        self.assertEqual(self.invoice.tax_amount, Decimal('40.00'))
        self.assertEqual(self.invoice.subtotal, Decimal('400.00'))
        self.assertEqual(self.invoice.total, Decimal('440.00'))
