"""
Accounts Receivable - Admin Configuration
"""
from django.contrib import admin


# @admin.register(Customer)
# class CustomerAdmin(admin.ModelAdmin):
#     list_display = ['code', 'name', 'company', 'email', 'phone', 'credit_limit', 'is_active']
#     list_filter = ['company', 'is_active']
#     search_fields = ['code', 'name', 'email']


# @admin.register(Invoice)
# class InvoiceAdmin(admin.ModelAdmin):
#     list_display = ['invoice_number', 'customer', 'invoice_date', 'due_date', 'total_amount', 'balance', 'status']
#     list_filter = ['company', 'status', 'invoice_date']
#     search_fields = ['invoice_number', 'customer__name']
#     readonly_fields = ['balance']
