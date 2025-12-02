"""
Accounts Payable Models
Handles Vendors, Bills, Payments to vendors
"""
from django.db import models
# from Finance.core.models import Company, Currency
# from Finance.GL.models import Account  # Cross-reference to GL


# class Vendor(models.Model):
#     """Vendor/Supplier Master"""
#     company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='vendors')
#     code = models.CharField(max_length=20)
#     name = models.CharField(max_length=200)
#     contact_person = models.CharField(max_length=100, blank=True)
#     email = models.EmailField(blank=True)
#     phone = models.CharField(max_length=50, blank=True)
#     address = models.TextField(blank=True)
#     payment_terms = models.CharField(max_length=100, blank=True)
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         unique_together = ['company', 'code']
#         ordering = ['name']
    
#     def __str__(self):
#         return f"{self.code} - {self.name}"


# class Bill(models.Model):
#     """Vendor Bills/Invoices"""
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('SUBMITTED', 'Submitted'),
#         ('APPROVED', 'Approved'),
#         ('PAID', 'Paid'),
#         ('CANCELLED', 'Cancelled'),
#     ]
    
#     company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bills')
#     vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='bills')
#     bill_number = models.CharField(max_length=50)
#     bill_date = models.DateField()
#     due_date = models.DateField()
#     currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
#     total_amount = models.DecimalField(max_digits=15, decimal_places=2)
#     paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
#     description = models.TextField(blank=True)
    
#     # Link to GL Account for AP
#     ap_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='ap_bills')
    
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         ordering = ['-bill_date']
    
#     def __str__(self):
#         return f"{self.bill_number} - {self.vendor.name}"
    
#     @property
#     def balance(self):
#         return self.total_amount - self.paid_amount
