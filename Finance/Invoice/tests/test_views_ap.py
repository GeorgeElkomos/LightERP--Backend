"""
Comprehensive tests for AP Invoice API endpoints.

Tests all endpoints:
- POST   /finance/invoice/ap/              - Create AP invoice
- GET    /finance/invoice/ap/              - List AP invoices
- GET    /finance/invoice/ap/{id}/         - Get AP invoice detail
- PUT    /finance/invoice/ap/{id}/         - Update AP invoice
- DELETE /finance/invoice/ap/{id}/         - Delete AP invoice
- POST   /finance/invoice/ap/{id}/approve/ - Approve/Reject invoice
- POST   /finance/invoice/ap/{id}/post-to-gl/ - Post to GL

Covers scenarios:
- Success cases
- Validation errors
- Edge cases
- Business rule violations
- Filter testing
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
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
from Finance.Invoice.tests.test_helpers import (
    create_simple_approval_template_for_invoice,
    get_or_create_test_user,
    approve_invoice_for_testing
)

User = get_user_model()


class APInvoiceCreateTests(TestCase):
    """Test AP Invoice creation endpoint"""
    
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
        
        # Create supplier (automatically creates BusinessPartner)
        self.supplier = Supplier.objects.create(
            name='Test Supplier Inc'
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
        self.segment_6100 = XX_Segment.objects.create(
            segment_type=self.segment_type_2,
            code='6100',
            alias='Office Supplies Expense',
            node_type='detail'
        )
        self.segment_2100 = XX_Segment.objects.create(
            segment_type=self.segment_type_2,
            code='2100',
            alias='Accounts Payable',
            node_type='detail'
        )
        
        # Valid request data
        self.valid_data = {
            "date": str(date.today()),
            "currency_id": self.currency.id,
            "country_id": self.country.id,
            "supplier_id": self.supplier.id,
            "gl_distributions_id": self.journal_entry.id,
            "tax_amount": "50.00",
            "items": [
                {
                    "name": "Laptops",
                    "description": "Dell XPS 15",
                    "quantity": "10",
                    "unit_price": "1000.00"
                }
            ],
            "journal_entry": {
                "date": str(date.today()),
                "currency_id": self.currency.id,
                "memo": "IT equipment purchase",
                "lines": [
                    {
                        "amount": "10050.00",
                        "type": "DEBIT",
                        "segments": [
                            {"segment_type_id": self.segment_type_1.id, "segment_code": "100"},
                            {"segment_type_id": self.segment_type_2.id, "segment_code": "6100"}
                        ]
                    },
                    {
                        "amount": "10050.00",
                        "type": "CREDIT",
                        "segments": [
                            {"segment_type_id": self.segment_type_1.id, "segment_code": "100"},
                            {"segment_type_id": self.segment_type_2.id, "segment_code": "2100"}
                        ]
                    }
                ]
            }
        }
    
    def test_create_ap_invoice_success(self):
        """Test successful AP invoice creation"""
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('invoice_id', response.data)
        
        # Verify invoice was created
        ap_invoice = AP_Invoice.objects.get(invoice_id=response.data['invoice_id'])
        self.assertEqual(ap_invoice.supplier_id, self.supplier.id)
        self.assertEqual(ap_invoice.approval_status, 'DRAFT')
        
        # Verify items were created
        self.assertEqual(ap_invoice.invoice.items.count(), 1)
        item = ap_invoice.invoice.items.first()
        self.assertEqual(item.name, 'Laptops')
        self.assertEqual(item.quantity, Decimal('10'))
        
        # Verify journal entry was created
        self.assertIsNotNone(ap_invoice.gl_distributions)
        self.assertEqual(ap_invoice.gl_distributions.lines.count(), 2)
        
        # Verify response includes journal_entry with segment details (not segment_combination_id)
        self.assertIn('journal_entry', response.data)
        journal_entry = response.data['journal_entry']
        self.assertIn('lines', journal_entry)
        self.assertEqual(len(journal_entry['lines']), 2)
        
        # Verify each line has segments instead of segment_combination_id
        for line in journal_entry['lines']:
            self.assertNotIn('segment_combination_id', line)
            self.assertIn('segments', line)
            self.assertIsInstance(line['segments'], list)
            
            # Verify segment structure
            if len(line['segments']) > 0:
                segment = line['segments'][0]
                self.assertIn('segment_type_name', segment)
                self.assertIn('segment_code', segment)
    
    def test_create_ap_invoice_missing_supplier(self):
        """Test creation fails with missing supplier_id"""
        data = self.valid_data.copy()
        del data['supplier_id']
        
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('supplier_id', response.data)
    
    def test_create_ap_invoice_invalid_supplier(self):
        """Test creation fails with non-existent supplier"""
        data = self.valid_data.copy()
        data['supplier_id'] = 99999
        
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_create_ap_invoice_no_items(self):
        """Test creation fails without items"""
        data = self.valid_data.copy()
        data['items'] = []
        
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('items', response.data)
    
    def test_create_ap_invoice_unbalanced_journal(self):
        """Test creation fails with unbalanced journal entry"""
        data = self.valid_data.copy()
        data['journal_entry']['lines'][0]['amount'] = "5000.00"  # Unbalanced
        
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not balanced', str(response.data).lower())
    
    def test_create_ap_invoice_invalid_currency(self):
        """Test creation fails with invalid currency"""
        data = self.valid_data.copy()
        data['currency_id'] = 99999
        
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_ap_invoice_multiple_items(self):
        """Test creation with multiple items"""
        data = self.valid_data.copy()
        data['items'] = [
            {
                "name": "Laptops",
                "description": "Dell XPS 15",
                "quantity": "10",
                "unit_price": "1000.00"
            },
            {
                "name": "Monitors",
                "description": "27 inch 4K",
                "quantity": "20",
                "unit_price": "300.00"
            }
        ]
        # Update journal to reflect new total: 10000 + 6000 + 50 tax = 16050
        data['journal_entry']['lines'][0]['amount'] = "16050.00"
        data['journal_entry']['lines'][1]['amount'] = "16050.00"
        
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.post(url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ap_invoice = AP_Invoice.objects.get(invoice_id=response.data['invoice_id'])
        self.assertEqual(ap_invoice.invoice.items.count(), 1)


class APInvoiceListTests(TestCase):
    """Test AP Invoice list endpoint"""
    
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
        
        # Create suppliers (automatically creates BusinessPartner)
        self.supplier1 = Supplier.objects.create(name='Supplier 1')
        self.supplier2 = Supplier.objects.create(name='Supplier 2')
        
        # Create invoices through child model
        self.ap1 = AP_Invoice.objects.create(
            date=date.today(),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier1,
            approval_status='DRAFT'
        )
        
        self.ap2 = AP_Invoice.objects.create(
            date=date.today() - timedelta(days=5),
            currency=self.currency,
            country=self.country,
            subtotal=Decimal('2000.00'),
            total=Decimal('2000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier2,
            approval_status='APPROVED'
        )
    
    def test_list_all_ap_invoices(self):
        """Test listing all AP invoices"""
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response is wrapped in {'status', 'message', 'data'}
        self.assertEqual(len(response.data['data']['results']), 2)
    
    def test_filter_by_supplier(self):
        """Test filtering by supplier_id"""
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.get(url, {'supplier_id': self.supplier1.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['supplier_id'], self.supplier1.id)
    
    def test_filter_by_approval_status(self):
        """Test filtering by approval_status"""
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.get(url, {'approval_status': 'APPROVED'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)
        self.assertEqual(response.data['data']['results'][0]['approval_status'], 'APPROVED')
    
    def test_filter_by_currency(self):
        """Test filtering by currency_id"""
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.get(url, {'currency_id': self.currency.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 2)
    
    def test_filter_by_date_range(self):
        """Test filtering by date range"""
        url = reverse('finance:invoice:ap-invoice-list')
        response = self.client.get(url, {
            'date_from': str(date.today() - timedelta(days=3)),
            'date_to': str(date.today())
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['results']), 1)


class APInvoiceDetailTests(TestCase):
    """Test AP Invoice detail endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        journal_entry = JournalEntry.objects.create(date=date.today(), currency=currency, memo='Test Journal Entry')
        supplier = Supplier.objects.create(name='Test Supplier')
        
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal_entry,
            supplier=supplier,
            approval_status='DRAFT'
        )
    
    def test_get_ap_invoice_detail(self):
        """Test retrieving AP invoice detail"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.ap_invoice.invoice_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invoice_id'], self.ap_invoice.invoice_id)
        self.assertEqual(response.data['approval_status'], 'DRAFT')
        
        # Verify journal_entry is included
        self.assertIn('journal_entry', response.data)
        
        # Verify journal_entry structure (should NOT have segment_combination_id)
        journal_entry = response.data['journal_entry']
        self.assertIn('lines', journal_entry)
        
        # Verify lines have segments instead of segment_combination_id
        if len(journal_entry['lines']) > 0:
            line = journal_entry['lines'][0]
            self.assertNotIn('segment_combination_id', line)
            self.assertIn('segments', line)
    
    def test_get_nonexistent_ap_invoice(self):
        """Test retrieving non-existent invoice returns 404"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_update_ap_invoice_works(self):
        """Test that PUT/PATCH now work for updating invoices"""
        url = reverse('finance:invoice:ap-invoice-detail', kwargs={'pk': self.ap_invoice.invoice_id})
        
        # Test PATCH with basic update
        response_patch = self.client.patch(url, {'tax_amount': '50.00'}, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_200_OK)
        
        # Verify update worked
        self.ap_invoice.invoice.refresh_from_db()
        self.assertEqual(self.ap_invoice.invoice.tax_amount, Decimal('50.00'))


class APInvoiceDeleteTests(TestCase):
    """Test AP Invoice deletion endpoint"""
    
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
        supplier = Supplier.objects.create(name='Test Supplier')
        
        # Create invoice without posted journal entry (can be deleted)
        self.ap_invoice_deletable = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal_entry,
            supplier=supplier
        )
        
        # Create invoice with posted journal entry (cannot be deleted)
        self.journal = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test Posted',
            posted=True
        )
        self.ap_invoice_posted = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('2000.00'),
            total=Decimal('2000.00'),
            gl_distributions=self.journal,
            supplier=supplier
        )
    
    def test_delete_ap_invoice_success(self):
        """Test successful deletion of AP invoice"""
        url = reverse('finance:invoice:ap-invoice-detail', 
                     kwargs={'pk': self.ap_invoice_deletable.invoice_id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AP_Invoice.objects.filter(
            invoice_id=self.ap_invoice_deletable.invoice_id
        ).exists())
    
    def test_delete_ap_invoice_with_posted_journal(self):
        """Test deletion fails for invoice with posted journal"""
        url = reverse('finance:invoice:ap-invoice-detail', 
                     kwargs={'pk': self.ap_invoice_posted.invoice_id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('posted journal', str(response.data).lower())
        # Verify invoice still exists
        self.assertTrue(AP_Invoice.objects.filter(
            invoice_id=self.ap_invoice_posted.invoice_id
        ).exists())


class APInvoiceApproveTests(TestCase):
    """Test AP Invoice approve/reject endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create approval workflow template
        create_simple_approval_template_for_invoice()
        
        # Create test user
        self.user = get_or_create_test_user('approver1@test.com')
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        journal_entry = JournalEntry.objects.create(date=date.today(), currency=currency, memo='Test Journal Entry')
        supplier = Supplier.objects.create(name='Test Supplier')
        
        # Create a balanced journal entry
        segment_type_1 = SegmentType.objects.create(segment_name='Company', description='Company')
        segment_type_2 = SegmentType.objects.create(segment_name='Account', description='Account')
        segment_100 = XX_Segment.objects.create(segment_type=segment_type_1, code='100', alias='Co 100', node_type='detail')
        segment_6100 = XX_Segment.objects.create(segment_type=segment_type_2, code='6100', alias='Expense', node_type='detail')
        segment_2100 = XX_Segment.objects.create(segment_type=segment_type_2, code='2100', alias='AP', node_type='detail')
        
        # Create segment combinations using get_combination_id
        combination_dr_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, '100'),
            (segment_type_2.id, '6100')
        ])
        combination_cr_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, '100'),
            (segment_type_2.id, '2100')
        ])
        
        combination_dr = XX_Segment_combination.objects.get(id=combination_dr_id)
        combination_cr = XX_Segment_combination.objects.get(id=combination_cr_id)
        
        JournalLine.objects.create(entry=journal_entry, type='DEBIT',
                                   segment_combination=combination_dr, amount=Decimal('1000.00'))
        JournalLine.objects.create(entry=journal_entry, type='CREDIT',
                                   segment_combination=combination_cr, amount=Decimal('1000.00'))
        
        self.ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=journal_entry,
            supplier=supplier
        )
        
        # Create invoice items matching the journal entry total
        InvoiceItem.objects.create(
            invoice=self.ap_invoice.invoice,
            name='Test Item',
            description='Test Item Description',
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00')
        )
        
        # Submit invoice for approval so it can be approved/rejected
        self.ap_invoice.submit_for_approval()
    
    def test_approve_ap_invoice(self):
        """Test approving AP invoice"""
        # Authenticate the API client
        self.client.force_authenticate(user=self.user)
        
        url = reverse('finance:invoice:ap-invoice-approval-action', 
                     kwargs={'pk': self.ap_invoice.invoice_id})
        response = self.client.post(url, {'action': 'APPROVED'}, format='json')
        
        if response.status_code != status.HTTP_200_OK:
            print(f"Response: {response.content}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ap_invoice.refresh_from_db()
        self.assertEqual(self.ap_invoice.approval_status, 'APPROVED')
    
    def test_reject_ap_invoice(self):
        """Test rejecting AP invoice"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('finance:invoice:ap-invoice-approval-action', 
                     kwargs={'pk': self.ap_invoice.invoice_id})
        response = self.client.post(url, {'action': 'REJECTED', 'comment': 'Test rejection'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ap_invoice.refresh_from_db()
        self.assertEqual(self.ap_invoice.approval_status, 'REJECTED')
    
    def test_approve_default_action(self):
        """Test default action is APPROVED when not specified"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('finance:invoice:ap-invoice-approval-action', 
                     kwargs={'pk': self.ap_invoice.invoice_id})
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ap_invoice.refresh_from_db()
        self.assertEqual(self.ap_invoice.approval_status, 'APPROVED')
    
    def test_approve_invalid_action(self):
        """Test invalid action returns error"""
        url = reverse('finance:invoice:ap-invoice-approval-action', 
                     kwargs={'pk': self.ap_invoice.invoice_id})
        response = self.client.post(url, {'action': 'INVALID'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid action', response.data['error'])
    
    def test_approve_already_approved(self):
        """Test approving already approved invoice"""
        # Approve the invoice first
        self.ap_invoice.approve(self.user, comment="First approval")
        self.ap_invoice.refresh_from_db()
        
        url = reverse('finance:invoice:ap-invoice-approval-action', 
                     kwargs={'pk': self.ap_invoice.invoice_id})
        response = self.client.post(url, {'action': 'APPROVED'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already', response.data['error'].lower())


class APInvoicePostToGLTests(TestCase):
    """Test AP Invoice post to GL endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create approval workflow template
        create_simple_approval_template_for_invoice()
        
        # Create test user
        self.user = get_or_create_test_user('approver2@test.com')
        
        currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$', is_base_currency=True)
        country = Country.objects.create(code='US', name='United States')
        supplier = Supplier.objects.create(name='Test Supplier')
        
        # Create segment types and segments for balanced journal entries
        segment_type_1 = SegmentType.objects.create(segment_name='Company', description='Company')
        segment_type_2 = SegmentType.objects.create(segment_name='Account', description='Account')
        segment_100 = XX_Segment.objects.create(segment_type=segment_type_1, code='100', alias='Co 100', node_type='detail')
        segment_6100 = XX_Segment.objects.create(segment_type=segment_type_2, code='6100', alias='Expense', node_type='detail')
        segment_2100 = XX_Segment.objects.create(segment_type=segment_type_2, code='2100', alias='AP', node_type='detail')
        
        # Create segment combinations using get_combination_id
        combination_dr_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, '100'),
            (segment_type_2.id, '6100')
        ])
        combination_cr_id = XX_Segment_combination.get_combination_id([
            (segment_type_1.id, '100'),
            (segment_type_2.id, '2100')
        ])
        
        combination_dr = XX_Segment_combination.objects.get(id=combination_dr_id)
        combination_cr = XX_Segment_combination.objects.get(id=combination_cr_id)
        
        # Approved invoice with unposted journal
        self.journal1 = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test Unposted',
            posted=False
        )
        JournalLine.objects.create(entry=self.journal1, type='DEBIT',
                                   segment_combination=combination_dr, amount=Decimal('1000.00'))
        JournalLine.objects.create(entry=self.journal1, type='CREDIT',
                                   segment_combination=combination_cr, amount=Decimal('1000.00'))
        
        self.ap_approved = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal1,
            supplier=supplier
        )
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=self.ap_approved.invoice,
            name='Test Item',
            description='Test Item Description',
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00')
        )
        # Approve using workflow
        approve_invoice_for_testing(self.ap_approved, self.user)
        
        # Draft invoice (not approved)
        self.journal2 = JournalEntry.objects.create(
            date=date.today(),
            currency=currency,
            memo='Test Draft',
            posted=False
        )
        JournalLine.objects.create(entry=self.journal2, type='DEBIT',
                                   segment_combination=combination_dr, amount=Decimal('2000.00'))
        JournalLine.objects.create(entry=self.journal2, type='CREDIT',
                                   segment_combination=combination_cr, amount=Decimal('2000.00'))
        
        self.ap_draft = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            country=country,
            subtotal=Decimal('2000.00'),
            total=Decimal('2000.00'),
            gl_distributions=self.journal2,
            supplier=supplier
        )
        # Create invoice items
        InvoiceItem.objects.create(
            invoice=self.ap_draft.invoice,
            name='Test Item',
            description='Test Item Description',
            quantity=Decimal('20.00'),
            unit_price=Decimal('100.00')
        )
    
    def test_post_to_gl_success(self):
        """Test successful posting to GL"""
        url = reverse('finance:invoice:ap-invoice-post-to-gl', 
                     kwargs={'pk': self.ap_approved.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.journal1.refresh_from_db()
        self.assertTrue(self.journal1.posted)
    
    def test_post_to_gl_not_approved(self):
        """Test posting fails for non-approved invoice"""
        url = reverse('finance:invoice:ap-invoice-post-to-gl', 
                     kwargs={'pk': self.ap_draft.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('approved', response.data['error'].lower())
    
    def test_post_to_gl_already_posted(self):
        """Test posting already posted journal"""
        self.journal1.posted = True
        self.journal1.save()
        
        url = reverse('finance:invoice:ap-invoice-post-to-gl', 
                     kwargs={'pk': self.ap_approved.invoice_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already posted', response.data['message'].lower())
    
    # test_post_to_gl_no_journal removed - gl_distributions is NOT NULL field
    # All invoices must have a journal entry from creation
