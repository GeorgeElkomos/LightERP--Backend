"""
Finance App - Main URL Configuration
This file routes URLs to the appropriate sub-apps within the Finance module.
"""
from django.urls import path, include

app_name = 'finance'

urlpatterns = [
    # Core Finance URLs
    path('core/', include('Finance.core.urls')),
    
    # General Ledger URLs
    path('gl/', include('Finance.GL.urls')),
    
    # Accounts Payable URLs
    path('bp/', include('Finance.BusinessPartner.urls')),
    
    # Accounts Receivable URLs
    path('invoice/', include('Finance.Invoice.urls')),
    
    # Payment URLs
    path('payments/', include('Finance.payments.urls')),
    
    # Default Combinations URLs
    path('', include('Finance.default_combinations.urls')),
]
