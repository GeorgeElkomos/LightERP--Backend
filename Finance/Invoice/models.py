
from django.db import models
from Finance.core.models import Currency, TaxRate, Country
from Finance.BusinessPartner.models import Customer, Supplier
from Finance.GL.models import JournalEntry
#from Finance.GL.models import


class Genral_Invoice(models.Model):
    """Accounts Payable Invoice"""
    # Payment status choices
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    PAYMENT_STATUSES = [
        (UNPAID, "Unpaid"),
        (PARTIALLY_PAID, "Partially Paid"),
        (PAID, "Paid"),
    ]
    date = models.DateField()
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="ap_invoices")
    country = models.ForeignKey(Country, on_delete=models.PROTECT, null=True, blank=True, related_name="ap_invoices", help_text="Tax country for this invoice (defaults to supplier country)")
    APPROVAL_STATUSES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUSES,
        default='DRAFT',
        help_text="Approval workflow status"
    )
    
   
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUSES, 
        default=UNPAID,
        help_text="Payment status of the invoice"
    )
    
    # Stored total fields
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Invoice subtotal (before tax)"
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total tax amount"
    )
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Invoice total (subtotal + tax)"
    )
    gl_distributions=models.ForeignKey(JournalEntry, on_delete=models.PROTECT, null=False, blank=False, related_name="invoices", help_text="GL Journal Entry for this invoice")
    class Meta:
        db_table = 'invoice'  # NEW table name
    
    def save(self, *args, **kwargs):
        # Auto-set country from supplier if not explicitly set
        if not self.country and self.supplier and self.supplier.country:
            self.country = self.supplier.country
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"AP-{self.number}"
    
    def calculate_and_save_totals(self):
        """Calculate invoice totals - DEPRECATED since APItem model removed
        
        Invoice totals should be entered directly on the invoice fields:
        - subtotal, tax_amount, total
        Or calculated from GL distributions if needed.
        This method now just returns the current stored values.
        """
        from decimal import Decimal
        
        # No items to calculate from - return existing values
        return {
            'subtotal': self.subtotal or Decimal('0.00'),
            'tax_amount': self.tax_amount or Decimal('0.00'),
            'total': self.total or Decimal('0.00')
        }
    def convert_amount_to_base_currency(self, amount):

        """Convert given amount from invoice currency to base currency using exchange rate.
        
        Args:
            amount (Decimal): Amount in invoice currency to convert.


        Returns:            Decimal: Equivalent amount in base currency.
        """      
        from decimal import Decimal
        
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        if self.currency.is_base_currency:
            return amount
        
        if self.exchange_rate is None:
            raise ValueError("Exchange rate is not set for this invoice.")
        
        base_amount = amount * self.exchange_rate
        return base_amount
    

class AP_Invoice(models.Model):
    from Finance.Invoice.models import Genral_Invoice as BaseInvoice
    invoice = models.OneToOneField(BaseInvoice, on_delete=models.CASCADE, primary_key=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)


    def __str__(self):
        return f"APInvoice for {self.invoice}"
class AR_Invoice(models.Model):
    from Finance.Invoice.models import Genral_Invoice as BaseInvoice
    invoice = models.OneToOneField(BaseInvoice, on_delete=models.CASCADE, primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)


    def __str__(self):
        return f"ARInvoice for {self.invoice}"
class one_use_supplier(models.Model):
    invoice = models.ForeignKey(Genral_Invoice, on_delete=models.CASCADE)  
    supplier_name = models.CharField(max_length=255)
    supplier_address = models.TextField()