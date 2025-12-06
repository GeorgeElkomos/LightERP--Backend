"""
Comprehensive tests for AR Invoice API endpoints.

Tests all endpoints:
- POST   /finance/invoice/ar/              - Create AR invoice
- GET    /finance/invoice/ar/              - List AR invoices
- GET    /finance/invoice/ar/{id}/         - Get AR invoice detail
- PUT    /finance/invoice/ar/{id}/         - Update AR invoice (not implemented)
- DELETE /finance/invoice/ar/{id}/         - Delete AR invoice
- POST   /finance/invoice/ar/{id}/approve/ - Approve/Reject invoice
- POST   /finance/invoice/ar/{id}/post-to-gl/ - Post to GL

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

from Finance.Invoice.models import AR_Invoice, Invoice
from Finance.BusinessPartner.models import Customer
from Finance.core.models import Currency, Country
from Finance.GL.models import XX_SegmentType as SegmentType, XX_Segment, XX_Segment_combination, JournalEntry


class ARInvoiceCreateTests(TestCase):
    """Test AR Invoice creation endpoint"""
    
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
        
        # Create customer
        self.customer = Customer.objects.create(
            name='Test Customer Inc'
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
        self.segment_100 = XX_Segment.objects.create(
            segment_type=self.segment_type_1,
            code='100',
            alias='Main Company',
            node_type='detail'
        )
        self.segment_1200 = XX_Segment.objects.create(
            segment_type=self.segment_type_2,
            code='1200',
            alias='Accounts Receivable',
            node_type='detail'
        )
        self.segment_4000 = XX_Segment.objects.create(
            segment_type=self.segment_type_2,
            code='4000',
            alias='Sales Revenue',
            node_type='detail'
        )
        
        # Valid request data
        self.valid_data = {
            "date": str(date.today()),
            "currency_id": self.currency.id,
            "country_id": self.country.id,
            "customer_id": self.customer.id,
            "gl_distributions_id": self.journal_entry.id,
            "tax_amount": "100.00",
            "items": [
                {
                    "name": "Software License",
                    "description": "Annual subscription",
                    "quantity": "5",
                    "unit_price": "500.00"
                }
            ],
            "journal_entry": {
                "date": str(date.today()),
                "currency_id": self.currency.id,
                "memo": "Software sales",
                "lines": [
                    {
                        "amount": "2600.00",
                        "type": "DEBIT",
                        "segments": [
                            {"segment_type_id": self.segment_type_1.id, "segment_code": "100"},
                            {"segment_type_id": self.segment_type_2.id, "segment_code": "1200"}
                        ]
                    },
                    {
                        "amount": "2600.00",
                        "type": "CREDIT",
                        "segments": [
                            {"segment_type_id": self.segment_type_1.id, "segment_code": "100"},
                            {"segment_type_id": self.segment_type_2.id, "segment_code": "4000"}
                        ]
                    }
                ]
            }
        }
    
    def test_create_ar_invoice_success(self):
        """Test successful AR invoice creation"""
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('invoice_id', response.data)
        
        # Verify invoice was created
        ar_invoice = AR_Invoice.objects.get(invoice_id=response.data['invoice_id'])
        self.assertEqual(ar_invoice.customer_id, self.customer.id)
        self.assertEqual(ar_invoice.approval_status, 'DRAFT')
        
        # Verify items were created
        self.assertEqual(ar_invoice.invoice.items.count(), 1)
        
        # Verify journal entry was created
        self.assertIsNotNone(ar_invoice.gl_distributions)
    
    def test_create_ar_invoice_missing_customer(self):
        """Test creation fails with missing customer_id"""
        data = self.valid_data.copy()
        del data['customer_id']
        
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('customer_id', response.data)
    
    def test_create_ar_invoice_invalid_customer(self):
        """Test creation fails with non-existent customer"""
        data = self.valid_data.copy()
        data['customer_id'] = 99999
        
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_create_ar_invoice_multiple_items(self):
        """Test creation with multiple items"""
        data = self.valid_data.copy()
        data['items'] = [
            {
                "name": "Software License",
                "description": "Annual subscription",
                "quantity": "5",
                "unit_price": "500.00"
            },
            {
                "name": "Support Package",
                "description": "Premium support",
                "quantity": "1",
                "unit_price": "1000.00"
            }
        ]
        # Update totals: 2500 + 1000 + 100 tax = 3600
        data['journal_entry']['lines'][0]['amount'] = "3600.00"
        data['journal_entry']['lines'][1]['amount'] = "3600.00"
        
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ARInvoiceListTests(TestCase):
    """Test AR Invoice list endpoint"""
    
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
        
        # Create customers
        self.customer1 = Customer.objects.create(
            name='Customer 1'
        )
        self.customer2 = Customer.objects.create(
            name='Customer 2'
        )
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(date=date.today(), currency=self.currency, memo='Test Journal Entry')
        
        # Create invoices
        self.ar1 = AR_Invoice.objects.create(
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal_entry,
            customer=self.customer1,
            approval_status='DRAFT'
        )
        
        
        self.ar2 = AR_Invoice.objects.create(
            date=date.today() - timedelta(days=10),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('2000.00'),
            total=Decimal('2000.00'),
            gl_distributions=journal_entry,
            customer=self.customer2,
            approval_status='APPROVED'
        )
    
    def test_list_all_ar_invoices(self):
        """Test listing all AR invoices"""
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_filter_by_customer(self):
        """Test filtering by customer_id"""
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.get(url, {'customer_id': self.customer1.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['customer_id'], self.customer1.id)
    
    def test_filter_by_approval_status(self):
        """Test filtering by approval_status"""
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.get(url, {'approval_status': 'DRAFT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['approval_status'], 'DRAFT')
    
    def test_filter_by_date_range(self):
        """Test filtering by date range"""
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.get(url, {
            'date_from': str(date.today() - timedelta(days=5)),
            'date_to': str(date.today())
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_filter_multiple_criteria(self):
        """Test filtering with multiple criteria"""
        url = reverse('finance:invoice:ar-invoice-list')
        response = self.client.get(url, {
            'customer_id': self.customer1.id,
            'approval_status': 'DRAFT',
            'currency_id': self.currency.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ARInvoiceDetailTests(TestCase):
    """Test AR Invoice detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        journal_entry = JournalEntry.objects.create(date=date.today(), currency=currency, memo='Test Journal Entry')
        customer = Customer.objects.create(name='Test Customer')
        
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal_entry,
            customer=customer,
            approval_status='DRAFT'
        )
    
    def test_get_ar_invoice_detail(self):
        """Test retrieving AR invoice detail"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': self.ar_invoice.invoice_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invoice_id'], self.ar_invoice.invoice_id)
    
    def test_get_nonexistent_ar_invoice(self):
        """Test retrieving non-existent invoice returns 404"""
        url = reverse('finance:invoice:ar-invoice-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ARInvoiceDeleteTests(TestCase):
    """Test AR Invoice deletion endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        customer = Customer.objects.create(name='Test Customer')
        
        # Create journal entries
        journal_deletable = JournalEntry.objects.create(date=date.today(), currency=currency, memo='Test', posted=False)
        
        # Create invoice without posted journal (can be deleted)
        self.ar_deletable = AR_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal_deletable,
            customer=customer
        )
        
        # Create invoice with posted journal (cannot be deleted)
        journal = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test',
            posted=True
        )
        self.ar_posted = AR_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('2000.00'),
            total=Decimal('2000.00'),
            gl_distributions=journal,
            customer=customer
        )
    
    def test_delete_ar_invoice_success(self):
        """Test successful deletion of AR invoice"""
        url = reverse('finance:invoice:ar-invoice-detail', 
                     kwargs={'pk': self.ar_deletable.invoice_id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AR_Invoice.objects.filter(
            invoice_id=self.ar_deletable.invoice_id
        ).exists())
    
    def test_delete_ar_invoice_with_posted_journal(self):
        """Test deletion fails for invoice with posted journal"""
        url = reverse('finance:invoice:ar-invoice-detail', 
                     kwargs={'pk': self.ar_posted.invoice_id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(AR_Invoice.objects.filter(
            invoice_id=self.ar_posted.invoice_id
        ).exists())


class ARInvoiceApproveTests(TestCase):
    """Test AR Invoice approve/reject endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        journal_entry = JournalEntry.objects.create(date=date.today(), currency=currency, memo='Test Journal Entry')
        customer = Customer.objects.create(name='Test Customer')
        
        self.ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal_entry,
            customer=customer,
            approval_status='DRAFT'
        )
    
    def test_approve_ar_invoice(self):
        """Test approving AR invoice"""
        url = reverse('finance:invoice:ar-invoice-approve', 
                     kwargs={'pk': self.ar_invoice.invoice_id})
        response = self.client.post(url, {'action': 'APPROVED'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ar_invoice.refresh_from_db()
        self.assertEqual(self.ar_invoice.approval_status, 'APPROVED')
    
    def test_reject_ar_invoice(self):
        """Test rejecting AR invoice"""
        url = reverse('finance:invoice:ar-invoice-approve', 
                     kwargs={'pk': self.ar_invoice.invoice_id})
        response = self.client.post(url, {'action': 'REJECTED'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ar_invoice.refresh_from_db()
        self.assertEqual(self.ar_invoice.approval_status, 'REJECTED')
    
    def test_approve_case_insensitive(self):
        """Test action is case insensitive"""
        url = reverse('finance:invoice:ar-invoice-approve', 
                     kwargs={'pk': self.ar_invoice.invoice_id})
        response = self.client.post(url, {'action': 'approved'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ar_invoice.refresh_from_db()
        self.assertEqual(self.ar_invoice.approval_status, 'APPROVED')


class ARInvoicePostToGLTests(TestCase):
    """Test AR Invoice post to GL endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        customer = Customer.objects.create(name='Test Customer')
        
        # Approved invoice with unposted journal
        self.journal = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test',
            posted=False
        )
        self.ar_approved = AR_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal,
            customer=customer,
            approval_status='APPROVED'
        )
    
    def test_post_to_gl_success(self):
        """Test successful posting to GL"""
        url = reverse('finance:invoice:ar-invoice-post-to-gl', 
                     kwargs={'pk': self.ar_approved.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.journal.refresh_from_db()
        self.assertTrue(self.journal.posted)
        self.assertIn('journal_entry_id', response.data)
    
    def test_post_to_gl_not_approved(self):
        """Test posting fails for non-approved invoice"""
        self.ar_approved.approval_status = 'DRAFT'
        self.ar_approved.save()
        
        url = reverse('finance:invoice:ar-invoice-post-to-gl', 
                     kwargs={'pk': self.ar_approved.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_post_to_gl_already_posted(self):
        """Test posting already posted journal"""
        self.journal.posted = True
        self.journal.save()
        
        url = reverse('finance:invoice:ar-invoice-post-to-gl', 
                     kwargs={'pk': self.ar_approved.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
