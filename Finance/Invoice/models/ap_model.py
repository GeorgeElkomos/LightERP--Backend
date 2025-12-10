"""
AP Invoice Model - Accounts Payable

Represents invoices from suppliers that the company needs to pay.
"""

from django.db import models
from Finance.BusinessPartner.models import Supplier
from .parent_model import Invoice
from .mixins import InvoiceChildManagerMixin, InvoiceChildModelMixin


class AP_InvoiceManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for AP_Invoice - uses Invoice-specific pattern!"""
    parent_model = Invoice
    bp_source_field = 'supplier'  # ← Auto-extracts business_partner from supplier
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-AP'
    }
    
    def active(self):
        """Get all active (not fully paid) AP invoices."""
        return self.exclude(invoice__payment_status='PAID')


class AP_Invoice(InvoiceChildModelMixin, models.Model):
    """
    Accounts Payable Invoice - represents invoices from suppliers.
    
    ALL Invoice fields are automatically available as properties!
    No need to manually define them - they're auto-generated!
    
    Usage:
        ap_invoice = AP_Invoice.objects.create(
            date=date.today(),
            currency=currency,
            total=1100.00,
            supplier=supplier  # business_partner auto-set!
        )
        
        # Update supplier - business_partner auto-syncs
        ap_invoice.supplier = new_supplier
        ap_invoice.save()
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    bp_source_field = 'supplier'  # ← Auto-syncs business_partner from supplier
    
    invoice = models.OneToOneField(
        Invoice, 
        on_delete=models.CASCADE, 
        primary_key=True,
        related_name="ap_invoice"
    )
    
    # AP-specific fields
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.PROTECT,
        related_name="ap_invoices"
    )
    
    # Custom manager
    objects = AP_InvoiceManager()
    
    class Meta:
        db_table = 'ap_invoice'
        verbose_name = 'AP Invoice'
        verbose_name_plural = 'AP Invoices'
    
    def __str__(self):
        return f"AP Invoice: {self.supplier.name} - ${self.invoice.total}"
