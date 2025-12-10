"""
AR Invoice Model - Accounts Receivable

Represents invoices to customers that the company expects to receive payment for.
"""

from django.db import models
from Finance.BusinessPartner.models import Customer
from .parent_model import Invoice
from .mixins import InvoiceChildManagerMixin, InvoiceChildModelMixin


class AR_InvoiceManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for AR_Invoice - uses Invoice-specific pattern!"""
    parent_model = Invoice
    bp_source_field = 'customer'  # ← Auto-extracts business_partner from customer
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-AR'
    }
    
    def active(self):
        """Get all active (not fully paid) AR invoices."""
        return self.exclude(invoice__payment_status='PAID')


class AR_Invoice(InvoiceChildModelMixin, models.Model):
    """
    Accounts Receivable Invoice - represents invoices to customers.
    
    ALL Invoice fields are automatically available as properties!
    
    Usage:
        ar_invoice = AR_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            total=5500.00,
            customer=customer  # business_partner auto-set!
        )
        
        # Update customer - business_partner auto-syncs
        ar_invoice.customer = new_customer
        ar_invoice.save()
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    bp_source_field = 'customer'  # ← Auto-syncs business_partner from customer
    
    invoice = models.OneToOneField(
        Invoice, 
        on_delete=models.CASCADE, 
        primary_key=True,
        related_name="ar_invoice"
    )
    
    # AR-specific fields
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.PROTECT,
        related_name="ar_invoices"
    )
    
    # Custom manager
    objects = AR_InvoiceManager()
    
    class Meta:
        db_table = 'ar_invoice'
        verbose_name = 'AR Invoice'
        verbose_name_plural = 'AR Invoices'
    
    def __str__(self):
        return f"AR Invoice: {self.customer.name} - ${self.invoice.total}"
