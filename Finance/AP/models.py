"""
Accounts Payable Models
Handles Vendors, Bills, Payments to vendors
"""
from django.db import models
from Finance.core.models import Currency, TaxRate, Country
#from Finance.GL.models import


class Supplier(models.Model):
    """
    Supplier/Vendor master data
    Note: Supplier and Vendor refer to the same entity
    """
    # Basic Information
    name = models.CharField(max_length=128, help_text="Legal name of supplier/vendor")
    legal_name = models.CharField(max_length=255, blank=True, help_text="Full legal entity name (if different from name)")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, null=True, blank=True, related_name="suppliers")
    vat_number = models.CharField(max_length=50, blank=True, help_text="VAT/Tax registration number (TRN)")
    tax_id = models.CharField(max_length=50, blank=True, help_text="Alternative tax ID")
    
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True) 
    # Notes
    notes = models.TextField(blank=True, help_text="Internal notes about this vendor")
    
    class Meta:
        db_table = 'supplier'  # NEW table name
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
    
    def __str__(self):
        return f"{self.name}"
    

    @property
    def can_delete(self):
        """
        Check if supplier can be safely deleted.
        Returns False if supplier has any related records (invoices, bills, POs, etc.)
        """
        # Check for related invoices
        if self.apinvoice_set.exists():
            return False
        
        # Check for related vendor bills
        if hasattr(self, 'vendorbill_set') and self.vendorbill_set.exists():
            return False
        
        # Check for related purchase orders
        if hasattr(self, 'poheader_set') and self.poheader_set.exists():
            return False
        
        # Check for related payments
        if hasattr(self, 'appayment_set') and self.appayment_set.exists():
            return False
        
        # Check for related RFx awards
        if hasattr(self, 'awarded_rfx_events') and self.awarded_rfx_events.exists():
            return False
        
        # Check for related quotes
        if hasattr(self, 'quotes') and self.quotes.exists():
            return False
        
        return True
    
    def get_deletion_blockers(self):
        """
        Get a list of reasons why this supplier cannot be deleted.
        Returns a list of strings describing the blocking relationships.
        """
        blockers = []
        
        # Check invoices
        invoice_count = self.apinvoice_set.count()
        if invoice_count > 0:
            blockers.append(f"{invoice_count} AP Invoice(s)")
        
        # Check vendor bills
        if hasattr(self, 'vendorbill_set'):
            bill_count = self.vendorbill_set.count()
            if bill_count > 0:
                blockers.append(f"{bill_count} Vendor Bill(s)")
        
        # Check purchase orders
        if hasattr(self, 'poheader_set'):
            po_count = self.poheader_set.count()
            if po_count > 0:
                blockers.append(f"{po_count} Purchase Order(s)")
        
        # Check payments
        if hasattr(self, 'appayment_set'):
            payment_count = self.appayment_set.count()
            if payment_count > 0:
                blockers.append(f"{payment_count} Payment(s)")
        
        # Check RFx awards
        if hasattr(self, 'awarded_rfx_events'):
            award_count = self.awarded_rfx_events.count()
            if award_count > 0:
                blockers.append(f"{award_count} RFx Award(s)")
        
        # Check quotes
        if hasattr(self, 'quotes'):
            quote_count = self.quotes.count()
            if quote_count > 0:
                blockers.append(f"{quote_count} Quote(s)")
        
        return blockers


class APInvoice(models.Model):
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
    
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
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
    
    class Meta:
        db_table = 'ap_apinvoice'  # NEW table name
    
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
    
