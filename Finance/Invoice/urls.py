"""
Accounts Payable - URL Configuration
Handles AP-specific views and endpoints
"""
from django.urls import path
from . import views

app_name = 'invoice'

urlpatterns = [
    # Example: Vendor management, Bills, Payments
    # path('vendors/', views.vendor_list, name='vendor_list'),
    # path('bills/', views.bill_list, name='bill_list'),
]
