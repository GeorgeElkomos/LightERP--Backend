"""
Invoice URL Configuration

URL patterns for Invoice module API endpoints.
Uses function-based views matching the core module pattern.
"""

from django.urls import path
from Finance.Invoice import views

app_name = 'invoice'

urlpatterns = [
    # ============================================================================
    # AP Invoice URLs
    # ============================================================================
    path('ap/', views.ap_invoice_list, name='ap-invoice-list'),
    path('ap/<int:pk>/', views.ap_invoice_detail, name='ap-invoice-detail'),
    path('ap/<int:pk>/approve/', views.ap_invoice_approve, name='ap-invoice-approve'),
    path('ap/<int:pk>/post-to-gl/', views.ap_invoice_post_to_gl, name='ap-invoice-post-to-gl'),
    
    # ============================================================================
    # AR Invoice URLs
    # ============================================================================
    path('ar/', views.ar_invoice_list, name='ar-invoice-list'),
    path('ar/<int:pk>/', views.ar_invoice_detail, name='ar-invoice-detail'),
    path('ar/<int:pk>/approve/', views.ar_invoice_approve, name='ar-invoice-approve'),
    path('ar/<int:pk>/post-to-gl/', views.ar_invoice_post_to_gl, name='ar-invoice-post-to-gl'),
    
    # ============================================================================
    # One-Time Supplier Invoice URLs
    # ============================================================================
    path('one-time-supplier/', views.one_time_supplier_invoice_list, name='one-time-supplier-list'),
    path('one-time-supplier/<int:pk>/', views.one_time_supplier_invoice_detail, name='one-time-supplier-detail'),
    path('one-time-supplier/<int:pk>/approve/', views.one_time_supplier_invoice_approve, name='one-time-supplier-approve'),
    path('one-time-supplier/<int:pk>/post-to-gl/', views.one_time_supplier_invoice_post_to_gl, name='one-time-supplier-post-to-gl'),
]
