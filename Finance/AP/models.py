"""
Accounts Payable Models
Handles Vendors, Bills, Payments to vendors
"""
from django.db import models
from Finance.core.models import Currency, TaxRate,ExchangeRate, country
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
    country = models.ForeignKey(country, on_delete=models.PROTECT, null=True, blank=True, related_name="suppliers")
    vat_number = models.CharField(max_length=50, blank=True, help_text="VAT/Tax registration number (TRN)")
    tax_id = models.CharField(max_length=50, blank=True, help_text="Alternative tax ID")
    
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True) 
    # Notes
    notes = models.TextField(blank=True, help_text="Internal notes about this vendor")
    
    class Meta:
        ordering = ['code']
        db_table = 'supplier'  # NEW table name
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    

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
    number = models.CharField(max_length=32, unique=True)
    date = models.DateField()
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="ap_invoices")
    country = models.ForeignKey(country, on_delete=models.PROTECT, null=True, blank=True, related_name="ap_invoices", help_text="Tax country for this invoice (defaults to supplier country)")
    #period = models.ForeignKey('periods.FiscalPeriod', on_delete=models.PROTECT, null=True, blank=True, related_name='ap_invoices', help_text="Fiscal period for this invoice")
    
    # 3-Way Match fields (PO → GR → Invoice matching)
    # po_header = models.ForeignKey(
    #     'purchase_orders.POHeader',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='ap_invoices',
    #     help_text="Purchase Order linked to this invoice"
    # )
    # goods_receipt = models.ForeignKey(
    #     'receiving.GoodsReceipt',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='ap_invoices',
    #     help_text="Goods Receipt linked to this invoice"
    # )
    
    # # 3-Way Match Status
    # MATCH_NOT_REQUIRED = 'NOT_REQUIRED'
    # MATCH_PENDING = 'PENDING'
    # MATCH_MATCHED = 'MATCHED'
    # MATCH_VARIANCE = 'VARIANCE'
    # MATCH_FAILED = 'FAILED'
    # MATCH_STATUSES = [
    #     (MATCH_NOT_REQUIRED, 'Not Required'),
    #     (MATCH_PENDING, 'Pending Match'),
    #     (MATCH_MATCHED, 'Matched'),
    #     (MATCH_VARIANCE, 'Variance Detected'),
    #     (MATCH_FAILED, 'Match Failed'),
    # ]
    # three_way_match_status = models.CharField(
    #     max_length=20,
    #     choices=MATCH_STATUSES,
    #     default=MATCH_NOT_REQUIRED,
    #     help_text="3-way match validation status"
    # )
    # match_variance_amount = models.DecimalField(
    #     max_digits=14,
    #     decimal_places=2,
    #     null=True,
    #     blank=True,
    #     help_text="Variance amount between invoice and PO (if any)"
    # )
    # match_variance_notes = models.TextField(
    #     blank=True,
    #     help_text="Notes about match variances"
    # )
    # match_performed_at = models.DateTimeField(
    #     null=True,
    #     blank=True,
    #     help_text="When 3-way match was last performed"
    # )
    
    # Approval workflow
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
    
    # Posting status - separates draft/posted state
    is_posted = models.BooleanField(default=False, help_text="Whether invoice is posted to GL")
    posted_at = models.DateTimeField(null=True, blank=True)
    
    # Payment status - separates payment state
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUSES, 
        default=UNPAID,
        help_text="Payment status of the invoice"
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Cancellation flag
    is_cancelled = models.BooleanField(default=False, help_text="Whether invoice is cancelled")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    gl_journal = models.OneToOneField(
        "finance.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="ap_source_new")  # Changed related_name to avoid conflict
    
    # FX tracking fields
    exchange_rate = models.DecimalField(
        max_digits=18, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Exchange rate used when posting (invoice currency to base currency)"
    )
    base_currency_total = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Total amount in base currency"
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
    
    def has_distributions(self):
        """Check if invoice has GL distribution lines (DEPRECATED - Always returns True)"""
        # Note: GL distribution lines are now deprecated
        # Distributions are created when invoice is posted to GL via JournalEntry
        # This method returns True to avoid validation errors
        return True
    
    def validate_distributions(self):
        """
        Validate GL distribution lines (DEPRECATED - Always returns valid)
        
        Returns:
            dict: {'valid': True, 'errors': [], 'warnings': []}
        """
        # Note: GL distribution lines are now deprecated
        # Distributions are created when invoice is posted to GL
        # This method returns valid to avoid blocking invoice creation
        return {
            'valid': True,
            'errors': [],
            'warnings': ['GL distributions are created when invoice is posted to GL']
        }
    
    def create_distributions_from_items(self, default_account=None):
        """
        Create GL distribution lines from items (DEPRECATED - No-op)
        
        Args:
            default_account: Default expense account (ignored)
            
        Returns:
            list: Empty list (no distributions created)
        """
        # Note: GL distribution lines are now deprecated
        # Distributions are created when invoice is posted to GL via JournalEntry
        # This method returns empty list to avoid errors but doesn't create anything
        print("DEBUG: create_distributions_from_items called (deprecated - no-op)")
        return []
    
    def calculate_total(self):
        """Calculate invoice total - returns stored total since items removed"""
        from decimal import Decimal
        
        # APItem model removed - return stored total directly
        return self.total or Decimal('0.00')
    
    # def perform_three_way_match(self):
    #     """
    #     Perform 3-way match between PO, Goods Receipt, and Invoice
        
    #     Returns:
    #         dict: {
    #             'status': 'MATCHED'|'VARIANCE'|'FAILED',
    #             'variances': [list of variance details],
    #             'total_variance': Decimal (total variance amount),
    #             'can_auto_approve': bool,
    #             'messages': [list of messages]
    #         }
    #     """
    #     from decimal import Decimal
    #     from django.utils import timezone
        
    #     result = {
    #         'status': self.MATCH_MATCHED,
    #         'variances': [],
    #         'total_variance': Decimal('0.00'),
    #         'can_auto_approve': False,
    #         'messages': []
    #     }
        
    #     # Validation: Must have PO and GR
    #     if not self.po_header:
    #         result['status'] = self.MATCH_FAILED
    #         result['messages'].append('Invoice must be linked to a Purchase Order')
    #         return result
        
    #     if not self.goods_receipt:
    #         result['status'] = self.MATCH_FAILED
    #         result['messages'].append('Invoice must be linked to a Goods Receipt')
    #         return result
        
    #     # Validate that GR belongs to the PO
    #     if self.goods_receipt.po_header_id != self.po_header.id:
    #         result['status'] = self.MATCH_FAILED
    #         result['messages'].append('Goods Receipt does not match the Purchase Order')
    #         return result
        
    #     # Validate supplier matches
    #     if self.supplier_id != self.po_header.supplier_id:
    #         result['status'] = self.MATCH_FAILED
    #         result['messages'].append('Invoice supplier does not match PO supplier')
    #         return result
        
    #     # Compare invoice total vs PO total
    #     po_total = self.po_header.total_amount or Decimal('0.00')
    #     invoice_total = self.total or Decimal('0.00')
        
    #     # Calculate variance
    #     variance = invoice_total - po_total
    #     variance_pct = (variance / po_total * 100) if po_total > 0 else Decimal('0.00')
        
    #     # Tolerance thresholds (configurable in production)
    #     TOLERANCE_AMOUNT = Decimal('100.00')  # $100
    #     TOLERANCE_PCT = Decimal('5.00')  # 5%
        
    #     if abs(variance) > Decimal('0.01'):  # More than 1 cent
    #         result['variances'].append({
    #             'type': 'price',
    #             'field': 'total',
    #             'po_value': float(po_total),
    #             'invoice_value': float(invoice_total),
    #             'variance': float(variance),
    #             'variance_pct': float(variance_pct)
    #         })
    #         result['total_variance'] = abs(variance)
            
    #         # Check if within tolerance
    #         if abs(variance) <= TOLERANCE_AMOUNT or abs(variance_pct) <= TOLERANCE_PCT:
    #             result['status'] = self.MATCH_VARIANCE
    #             result['can_auto_approve'] = True
    #             result['messages'].append(
    #                 f'Variance of {variance:.2f} ({variance_pct:.2f}%) is within acceptable tolerance'
    #             )
    #         else:
    #             result['status'] = self.MATCH_VARIANCE
    #             result['can_auto_approve'] = False
    #             result['messages'].append(
    #                 f'Variance of {variance:.2f} ({variance_pct:.2f}%) exceeds tolerance - manual approval required'
    #             )
    #     else:
    #         result['status'] = self.MATCH_MATCHED
    #         result['can_auto_approve'] = True
    #         result['messages'].append('Invoice matches PO exactly')
        
    #     # Update match fields
    #     self.three_way_match_status = result['status']
    #     self.match_variance_amount = result['total_variance']
    #     self.match_variance_notes = '; '.join(result['messages'])
    #     self.match_performed_at = timezone.now()
        
    #     # Auto-approve if within tolerance
    #     if result['can_auto_approve'] and self.approval_status == 'PENDING_APPROVAL':
    #         self.approval_status = 'APPROVED'
    #         result['messages'].append('Invoice auto-approved based on 3-way match')
        
    #     self.save()
        
    #     return result
    
    # def paid_amount(self):
    #     """Return total amount paid via allocations (converted to invoice currency)"""
    #     from decimal import Decimal
        
    #     paid = Decimal('0.00')
    #     for alloc in self.payment_allocations.all():
    #         alloc_amount = alloc.amount
            
    #         # Check if payment currency differs from invoice currency
    #         if alloc.payment and alloc.payment.currency_id != self.currency_id:
    #             # Convert payment amount to invoice currency
    #             if alloc.current_exchange_rate and alloc.current_exchange_rate != Decimal("0"):
    #                 # Payment amount in invoice currency = payment amount / exchange rate
    #                 # (exchange rate is FROM invoice TO payment, so divide to go back)
    #                 alloc_amount = alloc.amount / alloc.current_exchange_rate
    #             else:
    #                 # No exchange rate available, try to fetch on the fly
    #                 try:
    #                     from finance.fx_services import get_exchange_rate
    #                     rate = get_exchange_rate(
    #                         from_currency=alloc.payment.currency,
    #                         to_currency=self.currency,
    #                         rate_date=alloc.payment.date,
    #                         rate_type="SPOT"
    #                     )
    #                     # Payment currency to invoice currency
    #                     alloc_amount = alloc.amount * rate
    #                 except:
    #                     pass  # Keep original amount if conversion fails
            
    #         paid += alloc_amount
        
    #     return paid
    
    # def outstanding_amount(self):
    #     """Return unpaid balance (in invoice currency)"""
    #     return self.calculate_total() - self.paid_amount()