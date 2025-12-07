"""
API Tests for Payment Endpoints

Tests for Payment CRUD and allocation management REST API.
Based on patterns from test_payment_allocation.py
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from datetime import date

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import AP_Invoice, AR_Invoice
from Finance.BusinessPartner.models import Customer, Supplier, BusinessPartner
from Finance.core.models import Currency, Country
from Finance.GL.models import JournalEntry
from Finance.GL.models import JournalEntry


class PaymentAPITestCase(APITestCase):
    """Base test case with common setup"""
    
    def setUp(self):
        """Set up test data"""
        # Create currency
        self.usd = Currency.objects.create(
            name="US Dollar",
            code="USD",
            symbol="$",
            is_base_currency=True
        )
        
        # Create country
        self.country = Country.objects.create(
            name="United States",
            code="US"
        )
        
        # Create supplier with business partner
        self.supplier = Supplier.objects.create(
            name="Test Supplier Co",
            country=self.country
        )
        
        # Create customer with business partner
        self.customer = Customer.objects.create(
            name="Test Customer Co",
            country=self.country
        )
        
        # Create shared journal entry for invoices
        self.journal_entry = JournalEntry.objects.create(
            date=date.today(),
            currency=self.usd,
            memo='Test Journal Entry'
        )


class PaymentListAPITestCase(PaymentAPITestCase):
    """Tests for payment list endpoint (GET /payments/ and POST /payments/)"""
    
    def setUp(self):
        super().setUp()
        
        self.payment1 = Payment.objects.create(
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2024, 1, 1),
            approval_status='APPROVED'
        )
        
        self.payment2 = Payment.objects.create(
            business_partner=self.customer.business_partner,
            currency=self.usd,
            date=date(2024, 1, 2),
            approval_status='DRAFT'
        )
    
    def test_list_all_payments(self):
        """GET /payments/ should return all payments"""
        url = reverse('finance:payments:payment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_filter_by_business_partner(self):
        """GET /payments/?business_partner_id=X should filter by BP"""
        url = reverse('finance:payments:payment-list')
        response = self.client.get(url, {'business_partner_id': self.supplier.business_partner.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['business_partner_id'], self.supplier.business_partner.id)
    
    def test_create_payment_minimal(self):
        """POST /payments/ should create a new payment"""
        url = reverse('finance:payments:payment-list')
        data = {
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'date': '2024-01-15'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.count(), 3)
        self.assertEqual(response.data['business_partner_id'], self.supplier.business_partner.id)
        self.assertEqual(response.data['approval_status'], 'DRAFT')
    
    def test_create_payment_with_allocations(self):
        """POST /payments/ with allocations should create payment and allocations"""
        invoice = AP_Invoice.objects.create(
            date=date(2024, 1, 1),
            currency=self.usd,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        url = reverse('finance:payments:payment-list')
        data = {
            'business_partner_id': self.supplier.business_partner.id,
            'currency_id': self.usd.id,
            'date': '2024-01-15',
            'allocations': [
                {
                    'invoice_id': invoice.invoice.id,
                    'amount_allocated': '500.00'
                }
            ]
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(id=response.data['id'])
        self.assertEqual(payment.allocations.count(), 1)
        self.assertEqual(payment.get_total_allocated(), Decimal('500.00'))
        
        # Verify invoice paid_amount updated
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))


class PaymentDetailAPITestCase(PaymentAPITestCase):
    """Tests for payment detail endpoint (GET/PUT/DELETE /payments/{id}/)"""
    
    def setUp(self):
        super().setUp()
        
        self.payment = Payment.objects.create(
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2024, 1, 1),
            approval_status='DRAFT'
        )
    
    def test_get_payment_detail(self):
        """GET /payments/{id}/ should return payment details"""
        url = reverse('finance:payments:payment-detail', kwargs={'pk': self.payment.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.payment.id)
        self.assertEqual(response.data['business_partner_id'], self.supplier.business_partner.id)
    
    def test_update_payment(self):
        """PUT /payments/{id}/ should update payment"""
        url = reverse('finance:payments:payment-detail', kwargs={'pk': self.payment.id})
        data = {
            'date': '2024-01-20',
            'approval_status': 'APPROVED'
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.date, date(2024, 1, 20))
        self.assertEqual(self.payment.approval_status, 'APPROVED')
    
    def test_delete_payment(self):
        """DELETE /payments/{id}/ should delete payment"""
        url = reverse('finance:payments:payment-detail', kwargs={'pk': self.payment.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Payment.objects.count(), 0)
    
    def test_delete_payment_with_allocations_updates_invoices(self):
        """DELETE /payments/{id}/ should decrease invoice paid_amounts"""
        invoice = AP_Invoice.objects.create(
            date=date(2024, 1, 1),
            currency=self.usd,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        PaymentAllocation.objects.create(
            payment=self.payment,
            invoice=invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice.paid_amount, Decimal('500.00'))
        
        url = reverse('finance:payments:payment-detail', kwargs={'pk': self.payment.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify invoice updated - refresh parent Invoice
        from Finance.Invoice.models import Invoice
        invoice_obj = Invoice.objects.get(id=invoice.invoice.id)
        self.assertEqual(invoice_obj.paid_amount, Decimal('0.00'))


class PaymentAllocationAPITestCase(PaymentAPITestCase):
    """Tests for allocation management endpoints"""
    
    def setUp(self):
        super().setUp()
        
        self.payment = Payment.objects.create(
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2024, 1, 1)
        )
        
        self.invoice = AP_Invoice.objects.create(
            date=date(2024, 1, 1),
            currency=self.usd,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
    
    def test_list_allocations(self):
        """GET /payments/{id}/allocations/ should return allocations"""
        allocation = PaymentAllocation.objects.create(
            payment=self.payment,
            invoice=self.invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        url = reverse('finance:payments:payment-allocations', kwargs={'payment_pk': self.payment.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(Decimal(response.data[0]['amount_allocated']), Decimal('500.00'))
    
    def test_create_allocation(self):
        """POST /payments/{id}/allocations/ should create allocation"""
        url = reverse('finance:payments:payment-allocations', kwargs={'payment_pk': self.payment.id})
        data = {
            'invoice_id': self.invoice.invoice.id,
            'amount_allocated': '500.00'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PaymentAllocation.objects.count(), 1)
        
        # Verify invoice updated
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice.paid_amount, Decimal('500.00'))
    
    def test_update_allocation(self):
        """PUT /payments/{id}/allocations/{id}/ should update allocation"""
        allocation = PaymentAllocation.objects.create(
            payment=self.payment,
            invoice=self.invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        url = reverse('finance:payments:payment-allocation-detail', kwargs={
            'payment_pk': self.payment.id,
            'allocation_pk': allocation.id
        })
        data = {'amount_allocated': '750.00'}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify invoice updated - refresh parent Invoice
        from Finance.Invoice.models import Invoice
        invoice_obj = Invoice.objects.get(id=self.invoice.invoice.id)
        self.assertEqual(invoice_obj.paid_amount, Decimal('750.00'))
    
    def test_delete_allocation(self):
        """DELETE /payments/{id}/allocations/{id}/ should remove allocation"""
        allocation = PaymentAllocation.objects.create(
            payment=self.payment,
            invoice=self.invoice.invoice,
            amount_allocated=Decimal('500.00')
        )
        
        url = reverse('finance:payments:payment-allocation-detail', kwargs={
            'payment_pk': self.payment.id,
            'allocation_pk': allocation.id
        })
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PaymentAllocation.objects.count(), 0)
        
        # Verify invoice updated
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice.paid_amount, Decimal('0.00'))


class InvoicePaymentInfoAPITestCase(PaymentAPITestCase):
    """Tests for invoice payment info endpoint"""
    
    def setUp(self):
        super().setUp()
        
        self.invoice = AP_Invoice.objects.create(
            date=date(2024, 1, 1),
            currency=self.usd,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        self.payment = Payment.objects.create(
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2024, 1, 1)
        )
        
        PaymentAllocation.objects.create(
            payment=self.payment,
            invoice=self.invoice.invoice,
            amount_allocated=Decimal('600.00')
        )
    
    def test_get_invoice_payment_info(self):
        """GET /invoice/ap/{id}/payments/ should return payment info"""
        url = reverse('finance:invoice:ap-invoice-payments', kwargs={'invoice_pk': self.invoice.invoice.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invoice_id'], self.invoice.invoice.id)
        self.assertEqual(Decimal(response.data['total']), Decimal('1000.00'))
        self.assertEqual(Decimal(response.data['paid_amount']), Decimal('600.00'))
        self.assertEqual(Decimal(response.data['remaining_amount']), Decimal('400.00'))
        self.assertEqual(response.data['payment_status'], 'PARTIALLY_PAID')
        self.assertEqual(len(response.data['allocations']), 1)


class BusinessPartnerPaymentSummaryAPITestCase(PaymentAPITestCase):
    """Tests for business partner payment summary endpoint"""
    
    def setUp(self):
        super().setUp()
        
        # Create invoices
        self.invoice1 = AP_Invoice.objects.create(
            date=date(2024, 1, 1),
            currency=self.usd,
            country=self.country,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        self.invoice2 = AP_Invoice.objects.create(
            date=date(2024, 1, 2),
            currency=self.usd,
            country=self.country,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            gl_distributions=self.journal_entry,
            supplier=self.supplier
        )
        
        # Create payment with allocation
        self.payment = Payment.objects.create(
            business_partner=self.supplier.business_partner,
            currency=self.usd,
            date=date(2024, 1, 1)
        )
        
        PaymentAllocation.objects.create(
            payment=self.payment,
            invoice=self.invoice1.invoice,
            amount_allocated=Decimal('1000.00')
        )
    
    def test_get_payment_summary(self):
        """GET /bp/suppliers/{id}/payment-summary/ should return summary"""
        url = reverse('finance:businesspartner:supplier-payment-summary', kwargs={'bp_pk': self.supplier.business_partner.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['business_partner_id'], self.supplier.business_partner.id)
        self.assertEqual(response.data['total_payments'], 1)
        self.assertEqual(response.data['total_invoices'], 2)
        self.assertEqual(Decimal(response.data['total_invoice_amount']), Decimal('1500.00'))
        self.assertEqual(Decimal(response.data['total_paid_amount']), Decimal('1000.00'))
        self.assertEqual(Decimal(response.data['total_unpaid_amount']), Decimal('500.00'))
        self.assertEqual(response.data['paid_invoices_count'], 1)
        self.assertEqual(response.data['partially_paid_invoices_count'], 0)
        self.assertEqual(response.data['unpaid_invoices_count'], 1)
