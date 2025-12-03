# """
# Accounts Payable Models
# Handles Vendors, Bills, Payments to vendors
# """
# from django.db import models
# from Finance.core.models import Currency, TaxRate, Country
# from Finance.BusinessPartner.models import Customer, Supplier
# #from Finance.GL.models import




# class ARInvoice(models.Model):
#     """Accounts Receivable Invoice"""
#     # Payment status choices
#     UNPAID = "UNPAID"
#     PARTIALLY_PAID = "PARTIALLY_PAID"
#     PAID = "PAID"
#     PAYMENT_STATUSES = [
#         (UNPAID, "Unpaid"),
#         (PARTIALLY_PAID, "Partially Paid"),
#         (PAID, "Paid"),
#     ]
    
#     customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
#     number = models.CharField(max_length=32, unique=True)
#     date = models.DateField()
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="ar_invoices")
#     country = models.ForeignKey(
#         Country, 
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         help_text="Tax country for this invoice (defaults to customer country)"
#     )
    
#     # Approval workflow
#     APPROVAL_STATUSES = [
#         ('DRAFT', 'Draft'),
#         ('PENDING_APPROVAL', 'Pending Approval'),
#         ('APPROVED', 'Approved'),
#         ('REJECTED', 'Rejected'),
#     ]
#     approval_status = models.CharField(
#         max_length=20,
#         choices=APPROVAL_STATUSES,
#         default='DRAFT',
#         help_text="Approval workflow status"
#     )

#     # Payment status - separates payment state
#     payment_status = models.CharField(
#         max_length=20, 
#         choices=PAYMENT_STATUSES, 
#         default=UNPAID,
#         help_text="Payment status of the invoice"
#     )
#     # Stored total fields
#     subtotal = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Invoice subtotal (before tax)"
#     )
#     tax_amount = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Total tax amount"
#     )
#     total = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Invoice total (subtotal + tax)"
#     )
    
#     class Meta:
#         db_table = 'ar_arinvoice'  # NEW table name
    
#     def save(self, *args, **kwargs):
#         # Auto-set country from customer if not explicitly set
#         if not self.country and self.customer and self.customer.country:
#             self.country = self.customer.country
#         super().save(*args, **kwargs)
    
#     def __str__(self):
#         return f"AR-{self.number}"
    
#     def calculate_and_save_totals(self):
#         """Calculate invoice totals from items and save to database"""
#         from decimal import Decimal
        
#         subtotal_amt = Decimal('0.00')
#         tax_amt = Decimal('0.00')
        
#         for item in self.items.all():
#             line_subtotal = item.quantity * item.unit_price
#             line_tax = Decimal('0.00')
#             if item.tax_rate:
#                 line_tax = line_subtotal * (item.tax_rate.rate / 100)
#             subtotal_amt += line_subtotal
#             tax_amt += line_tax
        
#         self.subtotal = subtotal_amt
#         self.tax_amount = tax_amt
#         self.total = subtotal_amt + tax_amt
#         self.save(update_fields=['subtotal', 'tax_amount', 'total'])
        
#         return {
#             'subtotal': self.subtotal,
#             'tax_amount': self.tax_amount,
#             'total': self.total
#         }
    
#     def calculate_total(self):
#         """Calculate invoice total from items (backward compatibility)"""
#         from decimal import Decimal
        
#         total = Decimal('0.00')
#         for item in self.items.all():
#             subtotal = item.quantity * item.unit_price
#             tax_amount = Decimal('0.00')
#             if item.tax_rate:
#                 tax_amount = subtotal * (item.tax_rate.rate / 100)
#             total += subtotal + tax_amount
#         return total
#     def convert_amount_to_base_currency(self, amount):

#         """Convert given amount from invoice currency to base currency using exchange rate.
        
#         Args:
#             amount (Decimal): Amount in invoice currency to convert.
#         Returns:            Decimal: Equivalent amount in base currency.
#         """ 
#         from decimal import Decimal
        
#         # Convert amount to Decimal if it isn't already
#         if not isinstance(amount, Decimal):
#             amount = Decimal(str(amount))
        
#         # If invoice currency is base currency, return amount as-is
#         if self.currency.is_base_currency:
#             return amount
        
#         # Use currency's method to convert to base currency
#         base_amount = self.currency.convert_to_base_currency(amount)
        
#         return base_amount



# class APInvoice(models.Model):
#     """Accounts Payable Invoice"""
#     # Payment status choices
#     UNPAID = "UNPAID"
#     PARTIALLY_PAID = "PARTIALLY_PAID"
#     PAID = "PAID"
#     PAYMENT_STATUSES = [
#         (UNPAID, "Unpaid"),
#         (PARTIALLY_PAID, "Partially Paid"),
#         (PAID, "Paid"),
#     ]
    
#     supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
#     date = models.DateField()
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="ap_invoices")
#     country = models.ForeignKey(Country, on_delete=models.PROTECT, null=True, blank=True, related_name="ap_invoices", help_text="Tax country for this invoice (defaults to supplier country)")
#     APPROVAL_STATUSES = [
#         ('DRAFT', 'Draft'),
#         ('PENDING_APPROVAL', 'Pending Approval'),
#         ('APPROVED', 'Approved'),
#         ('REJECTED', 'Rejected'),
#     ]
#     approval_status = models.CharField(
#         max_length=20,
#         choices=APPROVAL_STATUSES,
#         default='DRAFT',
#         help_text="Approval workflow status"
#     )
    
   
#     payment_status = models.CharField(
#         max_length=20, 
#         choices=PAYMENT_STATUSES, 
#         default=UNPAID,
#         help_text="Payment status of the invoice"
#     )
    
#     # Stored total fields
#     subtotal = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Invoice subtotal (before tax)"
#     )
#     tax_amount = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Total tax amount"
#     )
#     total = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Invoice total (subtotal + tax)"
#     )
    
#     class Meta:
#         db_table = 'ap_apinvoice'  # NEW table name
    
#     def save(self, *args, **kwargs):
#         # Auto-set country from supplier if not explicitly set
#         if not self.country and self.supplier and self.supplier.country:
#             self.country = self.supplier.country
#         super().save(*args, **kwargs)
    
#     def __str__(self):
#         return f"AP-{self.number}"
    
#     def calculate_and_save_totals(self):
#         """Calculate invoice totals - DEPRECATED since APItem model removed
        
#         Invoice totals should be entered directly on the invoice fields:
#         - subtotal, tax_amount, total
#         Or calculated from GL distributions if needed.
#         This method now just returns the current stored values.
#         """
#         from decimal import Decimal
        
#         # No items to calculate from - return existing values
#         return {
#             'subtotal': self.subtotal or Decimal('0.00'),
#             'tax_amount': self.tax_amount or Decimal('0.00'),
#             'total': self.total or Decimal('0.00')
#         }
#     def convert_amount_to_base_currency(self, amount):

#         """Convert given amount from invoice currency to base currency using exchange rate.
        
#         Args:
#             amount (Decimal): Amount in invoice currency to convert.


#         Returns:            Decimal: Equivalent amount in base currency.
#         """      
#         from decimal import Decimal
        
#         if not isinstance(amount, Decimal):
#             amount = Decimal(str(amount))
        
#         if self.currency.is_base_currency:
#             return amount
        
#         if self.exchange_rate is None:
#             raise ValueError("Exchange rate is not set for this invoice.")
        
#         base_amount = amount * self.exchange_rate
#         return base_amount
    
