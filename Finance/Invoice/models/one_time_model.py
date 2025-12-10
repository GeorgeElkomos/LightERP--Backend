"""
One-Time Supplier Model

Represents invoices from ad-hoc suppliers without master data.
Useful for one-off purchases where creating a full supplier record isn't necessary.
"""

from django.db import models
from Finance.BusinessPartner.models import OneTime
from .parent_model import Invoice
from .mixins import InvoiceChildManagerMixin, InvoiceChildModelMixin


class OneTimeSupplierManager(InvoiceChildManagerMixin, models.Manager):
    """Manager for OneTimeSupplier - uses Invoice-specific pattern!"""
    parent_model = Invoice
    bp_source_field = 'one_time_supplier'  # ← Auto-extracts business_partner from one_time_supplier
    parent_defaults = {
        'approval_status': 'DRAFT',
        'payment_status': 'UNPAID',
        'prefix_code': 'Inv-OT'
    }


class OneTimeSupplier(InvoiceChildModelMixin, models.Model):
    """
    One-Time Supplier - for ad-hoc suppliers without master data.
    
    ALL Invoice fields are automatically available as properties!
    
    Usage:
        one_time = OneTimeSupplier.objects.create(
            date=date.today(),
            currency=currency,
            total=275.00,
            one_time_supplier=one_time_supplier_instance
        )
        
        # Update one_time_supplier - business_partner auto-syncs
        one_time.one_time_supplier = new_one_time
        one_time.save()
    """
    
    # Configuration for generic pattern
    parent_model = Invoice
    parent_field_name = 'invoice'
    bp_source_field = 'one_time_supplier'  # ← Auto-syncs business_partner from one_time_supplier
    
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE,
        related_name="OneTimeSuppliers"
    )
    
    # One-time supplier specific field
    one_time_supplier = models.ForeignKey(
        OneTime, 
        on_delete=models.PROTECT,
        related_name="one_time_suppliers_invoices"
    )
    
    # Custom manager
    objects = OneTimeSupplierManager()
    
    class Meta:
        db_table = 'OneTimeSupplier'
        verbose_name = 'One-Time Supplier'
        verbose_name_plural = 'One-Time Suppliers'
    
    def __str__(self):
        return f"One-Time: {self.one_time_supplier.name} - ${self.invoice.total}"
