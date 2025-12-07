"""
Comprehensive tests for One-Time Supplier Invoice API endpoints.

Tests all endpoints:
- POST   /finance/invoice/one-time-supplier/              - Create one-time invoice
- GET    /finance/invoice/one-time-supplier/              - List one-time invoices
- GET    /finance/invoice/one-time-supplier/{id}/         - Get detail
- PUT    /finance/invoice/one-time-supplier/{id}/         - Update (not implemented)
- DELETE /finance/invoice/one-time-supplier/{id}/         - Delete invoice
- POST   /finance/invoice/one-time-supplier/{id}/approve/ - Approve/Reject
- POST   /finance/invoice/one-time-supplier/{id}/post-to-gl/ - Post to GL

Covers scenarios:
- Success cases
- Validation errors
- Edge cases
- Business rule violations
- Filter testing
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta

from Finance.Invoice.models import OneTimeSupplier, Invoice
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import OneTime
from Finance.GL.models import JournalEntry, XX_SegmentType as SegmentType, XX_Segment


class OneTimeSupplierInvoiceCreateTests(TestCase):
    """Test One-Time Supplier Invoice creation endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True,
            exchange_rate_to_base_currency=Decimal('1.00')
        )
        
        # Create country
        self.country = Country.objects.create(
            code='US',
            name='United States'
        )
        
        # Create shared journal entry for all invoices
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Journal Entry'
        )
        
        # Create segment types
        self.segment_type_1 = SegmentType.objects.create(
            segment_name='Company',
            description='Company code'
        )
        self.segment_type_2 = SegmentType.objects.create(
            segment_name='Account',
            description='Account number'
        )
        
        # Create segments
        XX_Segment.objects.create(
            segment_type=self.segment_type_1,
            code='100',
            alias='Main Company',
            node_type='child'
        )
        XX_Segment.objects.create(
            segment_type=self.segment_type_2,
            code='6200',
            alias='Travel Expense',
            node_type='child'
        )
        XX_Segment.objects.create(
            segment_type=self.segment_type_2,
            code='2100',
            alias='Accounts Payable',
            node_type='child'
        )
        
        # Valid request data
        self.valid_data = {
            "date": str(date.today()),
            "currency_id": self.currency.id,
            "country_id": self.country.id,
            "supplier_name": "ABC Catering Services",
            "supplier_address": "123 Main St, New York, NY",
            "gl_distributions_id": self.journal_entry.id,
            "supplier_email": "contact@abccatering.com",
            "supplier_phone": "+1-555-1234",
            "supplier_tax_id": "12-3456789",
            "tax_amount": "25.00",
            "items": [
                {
                    "name": "Catering Services",
                    "description": "Office event catering",
                    "quantity": "1",
                    "unit_price": "500.00"
                }
            ],
            "journal_entry": {
                "date": str(date.today()),
                "currency_id": self.currency.id,
                "memo": "One-time catering expense",
                "lines": [
                    {
                        "amount": "525.00",
                        "type": "DEBIT",
                        "segments": [
                            {"segment_type_id": self.segment_type_1.id, "segment_code": "100"},
                            {"segment_type_id": self.segment_type_2.id, "segment_code": "6200"}
                        ]
                    },
                    {
                        "amount": "525.00",
                        "type": "CREDIT",
                        "segments": [
                            {"segment_type_id": self.segment_type_1.id, "segment_code": "100"},
                            {"segment_type_id": self.segment_type_2.id, "segment_code": "2100"}
                        ]
                    }
                ]
            }
        }
    
    def test_create_one_time_invoice_success(self):
        """Test successful one-time supplier invoice creation"""
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('supplier_name', response.data)
        self.assertEqual(response.data['supplier_name'], 'ABC Catering Services')
        
        # Verify invoice was created
        invoice = OneTimeSupplier.objects.get(invoice_id=response.data['id'])
        self.assertEqual(invoice.one_time_supplier.name, 'ABC Catering Services')
        self.assertEqual(invoice.one_time_supplier.email, 'contact@abccatering.com')
    
    def test_create_one_time_invoice_minimal_data(self):
        """Test creation with minimal supplier info (only name required)"""
        data = self.valid_data.copy()
        data['supplier_name'] = 'Quick Fix Repairs'
        # Remove optional fields
        del data['supplier_address']
        del data['supplier_email']
        del data['supplier_phone']
        del data['supplier_tax_id']
        
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = OneTimeSupplier.objects.get(invoice_id=response.data['id'])
        self.assertEqual(invoice.one_time_supplier.name, 'Quick Fix Repairs')
        self.assertIn(invoice.one_time_supplier.email, ['', None])  # Optional field
    
    def test_create_one_time_invoice_missing_supplier_name(self):
        """Test creation fails without supplier_name or one_time_supplier_id"""
        data = self.valid_data.copy()
        del data['supplier_name']
        
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_create_one_time_invoice_no_items(self):
        """Test creation fails without items"""
        data = self.valid_data.copy()
        data['items'] = []
        
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_one_time_invoice_long_supplier_name(self):
        """Test creation with very long supplier name"""
        data = self.valid_data.copy()
        data['supplier_name'] = 'A' * 300  # Very long name
        
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.post(url, data, format='json')
        
        # Should either succeed or fail gracefully
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])


class OneTimeSupplierInvoiceListTests(TestCase):
    """Test One-Time Supplier Invoice list endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )
        
        # Create country
        self.country = Country.objects.create(code='US', name='United States')
        
        # Create shared journal entry for all invoices
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.currency,
            memo='Test Journal Entry'
        )
        
        # Create OneTime business partners
        self.one_time_partner1 = OneTime.objects.create(
            name='ABC Catering',
            email='abc@example.com'
        )
        self.one_time_partner2 = OneTime.objects.create(
            name='XYZ Repairs',
            email='xyz@example.com'
        )
        
        # Create invoices through child model
        self.one_time1 = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            gl_distributions=self.journal_entry,
            one_time_supplier=self.one_time_partner1,
            approval_status='DRAFT'
        )
        
        self.one_time2 = OneTimeSupplier.objects.create(
            date=date.today() - timedelta(days=7),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            one_time_supplier=self.one_time_partner2,
            approval_status='APPROVED'
        )
    
    def test_list_all_one_time_invoices(self):
        """Test listing all one-time invoices"""
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_filter_by_supplier_name(self):
        """Test filtering by supplier name (contains)"""
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.get(url, {'supplier_name': 'Catering'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn('Catering', response.data[0]['supplier_name'])
    
    def test_filter_by_approval_status(self):
        """Test filtering by approval_status"""
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.get(url, {'approval_status': 'APPROVED'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['approval_status'], 'APPROVED')
    
    def test_filter_by_currency(self):
        """Test filtering by currency_id"""
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.get(url, {'currency_id': self.currency.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_filter_by_date_range(self):
        """Test filtering by date range"""
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.get(url, {
            'date_from': str(date.today() - timedelta(days=3)),
            'date_to': str(date.today())
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_filter_case_insensitive_supplier_name(self):
        """Test supplier name filtering is case insensitive"""
        url = reverse('finance:invoice:one-time-supplier-list')
        response = self.client.get(url, {'supplier_name': 'abc'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)


class OneTimeSupplierInvoiceDetailTests(TestCase):
    """Test One-Time Supplier Invoice detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test Journal Entry'
        )
        
        # Create OneTime business partner
        one_time_partner = OneTime.objects.create(
            name='Test Vendor',
            email='test@example.com'
        )
        
        self.one_time_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            gl_distributions=journal_entry,
            one_time_supplier=one_time_partner,
            approval_status='DRAFT'
        )
    
    def test_get_one_time_invoice_detail(self):
        """Test retrieving one-time invoice detail"""
        url = reverse('finance:invoice:one-time-supplier-detail', 
                     kwargs={'pk': self.one_time_invoice.invoice_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['supplier_name'], 'Test Vendor')
    
    def test_get_nonexistent_one_time_invoice(self):
        """Test retrieving non-existent invoice returns 404"""
        url = reverse('finance:invoice:one-time-supplier-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_update_one_time_invoice_not_implemented(self):
        """Test that PUT/PATCH returns not implemented"""
        url = reverse('finance:invoice:one-time-supplier-detail', 
                     kwargs={'pk': self.one_time_invoice.invoice_id})
        
        response_put = self.client.put(url, {}, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        
        response_patch = self.client.patch(url, {}, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_501_NOT_IMPLEMENTED)


class OneTimeSupplierInvoiceDeleteTests(TestCase):
    """Test One-Time Supplier Invoice deletion endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test Journal Entry'
        )
        
        # Create OneTime business partners
        deletable_partner = OneTime.objects.create(name='Deletable Vendor')
        posted_partner = OneTime.objects.create(name='Posted Vendor')
        
        # Invoice without posted journal (can be deleted)
        self.deletable = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            gl_distributions=journal_entry,
            one_time_supplier=deletable_partner
        )
        
        # Invoice with posted journal (cannot be deleted)
        self.journal_posted = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Posted',
            posted=True
        )
        self.posted = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_posted,
            one_time_supplier=posted_partner
        )
    
    def test_delete_one_time_invoice_success(self):
        """Test successful deletion"""
        url = reverse('finance:invoice:one-time-supplier-detail', 
                     kwargs={'pk': self.deletable.invoice_id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OneTimeSupplier.objects.filter(
            invoice_id=self.deletable.invoice_id
        ).exists())
    
    def test_delete_with_posted_journal(self):
        """Test deletion fails for invoice with posted journal"""
        url = reverse('finance:invoice:one-time-supplier-detail', 
                     kwargs={'pk': self.posted.invoice_id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('posted journal', str(response.data).lower())


class OneTimeSupplierInvoiceApproveTests(TestCase):
    """Test One-Time Supplier Invoice approve/reject endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test Journal Entry'
        )
        
        # Create OneTime business partner
        one_time_partner = OneTime.objects.create(name='Test Vendor')
        
        self.one_time_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            gl_distributions=journal_entry,
            one_time_supplier=one_time_partner,
            approval_status='DRAFT'
        )
    
    def test_approve_one_time_invoice(self):
        """Test approving one-time invoice"""
        url = reverse('finance:invoice:one-time-supplier-approve', 
                     kwargs={'pk': self.one_time_invoice.invoice_id})
        response = self.client.post(url, {'action': 'APPROVED'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('approved successfully', response.data['message'].lower())
        self.one_time_invoice.refresh_from_db()
        self.assertEqual(self.one_time_invoice.approval_status, 'APPROVED')
    
    def test_reject_one_time_invoice(self):
        """Test rejecting one-time invoice"""
        url = reverse('finance:invoice:one-time-supplier-approve', 
                     kwargs={'pk': self.one_time_invoice.invoice_id})
        response = self.client.post(url, {'action': 'REJECTED'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rejected successfully', response.data['message'].lower())
        self.one_time_invoice.refresh_from_db()
        self.assertEqual(self.one_time_invoice.approval_status, 'REJECTED')
    
    def test_approve_default_action(self):
        """Test default action is APPROVED"""
        url = reverse('finance:invoice:one-time-supplier-approve', 
                     kwargs={'pk': self.one_time_invoice.invoice_id})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.one_time_invoice.refresh_from_db()
        self.assertEqual(self.one_time_invoice.approval_status, 'APPROVED')
    
    def test_approve_invalid_action(self):
        """Test invalid action returns error"""
        url = reverse('finance:invoice:one-time-supplier-approve', 
                     kwargs={'pk': self.one_time_invoice.invoice_id})
        response = self.client.post(url, {'action': 'PENDING'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid action', response.data['error'])
    
    def test_approve_already_approved(self):
        """Test approving already approved invoice"""
        self.one_time_invoice.approval_status = 'APPROVED'
        self.one_time_invoice.save()
        
        url = reverse('finance:invoice:one-time-supplier-approve', 
                     kwargs={'pk': self.one_time_invoice.invoice_id})
        response = self.client.post(url, {'action': 'APPROVED'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OneTimeSupplierInvoicePostToGLTests(TestCase):
    """Test One-Time Supplier Invoice post to GL endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        
        # Create OneTime business partners
        test_partner = OneTime.objects.create(name='Test Vendor')
        draft_partner = OneTime.objects.create(name='Draft Vendor')
        
        # Approved invoice with unposted journal
        self.journal = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test Unposted',
            posted=False
        )
        self.approved_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            gl_distributions=self.journal,
            one_time_supplier=test_partner,
            approval_status='APPROVED'
        )
        
        # Draft invoice (not approved)
        journal2 = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Draft',
            posted=False
        )
        self.draft_invoice = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal2,
            one_time_supplier=draft_partner,
            approval_status='DRAFT'
        )
    
    def test_post_to_gl_success(self):
        """Test successful posting to GL"""
        url = reverse('finance:invoice:one-time-supplier-post-to-gl', 
                     kwargs={'pk': self.approved_invoice.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('posted successfully', response.data['message'].lower())
        self.journal.refresh_from_db()
        self.assertTrue(self.journal.posted)
    
    def test_post_to_gl_not_approved(self):
        """Test posting fails for non-approved invoice"""
        url = reverse('finance:invoice:one-time-supplier-post-to-gl', 
                     kwargs={'pk': self.draft_invoice.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('approved', response.data['error'].lower())
    
    def test_post_to_gl_already_posted(self):
        """Test posting already posted journal"""
        self.journal.posted = True
        self.journal.save()
        
        url = reverse('finance:invoice:one-time-supplier-post-to-gl', 
                     kwargs={'pk': self.approved_invoice.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already posted', response.data['message'].lower())
    
    # test_post_to_gl_no_journal removed - gl_distributions is NOT NULL field
    # All invoices must have a journal entry from creation

