"""
Accounts Payable - Admin Configuration
"""
from django.contrib import admin


# @admin.register(Vendor)
# class VendorAdmin(admin.ModelAdmin):
#     list_display = ['code', 'name', 'company', 'email', 'phone', 'is_active']
#     list_filter = ['company', 'is_active']
#     search_fields = ['code', 'name', 'email']


# @admin.register(Bill)
# class BillAdmin(admin.ModelAdmin):
#     list_display = ['bill_number', 'vendor', 'bill_date', 'due_date', 'total_amount', 'balance', 'status']
#     list_filter = ['company', 'status', 'bill_date']
#     search_fields = ['bill_number', 'vendor__name']
#     readonly_fields = ['balance']
