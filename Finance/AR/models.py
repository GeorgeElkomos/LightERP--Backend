"""
Accounts Receivable Models
Handles Customers, Invoices, Receipts from customers
"""
from django.db import models
# from Finance.core.models import Company, Currency
# from Finance.GL.models import Account  # Cross-reference to GL


# class Customer(models.Model):
#     """Customer Master"""
#     company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customers')
#     code = models.CharField(max_length=20)
#     name = models.CharField(max_length=200)
#     contact_person = models.CharField(max_length=100, blank=True)
#     email = models.EmailField(blank=True)
#     phone = models.CharField(max_length=50, blank=True)
#     address = models.TextField(blank=True)
#     credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
#     payment_terms = models.CharField(max_length=100, blank=True)
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         unique_together = ['company', 'code']
#         ordering = ['name']
    
#     def __str__(self):
#         return f"{self.code} - {self.name}"


# class Invoice(models.Model):
#     """Customer Invoices"""
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('SENT', 'Sent'),
#         ('PARTIAL', 'Partially Paid'),
#         ('PAID', 'Paid'),
#         ('CANCELLED', 'Cancelled'),
#     ]
    
#     company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoices')
#     customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
#     invoice_number = models.CharField(max_length=50)
#     invoice_date = models.DateField()
#     due_date = models.DateField()
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
#     total_amount = models.DecimalField(max_digits=15, decimal_places=2)
#     received_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
#     description = models.TextField(blank=True)
    
#     # Link to GL Account for AR
#     ar_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='ar_invoices')
    
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         ordering = ['-invoice_date']
    
#     def __str__(self):
#         return f"{self.invoice_number} - {self.customer.name}"
    
#     @property
#     def balance(self):
#         return self.total_amount - self.received_amount
