"""
Accounts Receivable - URL Configuration
Handles AR-specific views and endpoints
"""
from django.urls import path
from . import views

app_name = 'ar'

urlpatterns = [
    # Example: Customer management, Invoices, Receipts
    # path('customers/', views.customer_list, name='customer_list'),
    # path('invoices/', views.invoice_list, name='invoice_list'),
]
