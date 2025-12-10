"""
Invoice URL Configuration

URL patterns for Invoice module API endpoints.
Uses function-based views matching the core module pattern.
"""

from django.urls import path
from Finance.Invoice import views
from Finance.payments import views as payment_views

app_name = 'invoice'

urlpatterns = [
    # ============================================================================
    # AP Invoice URLs
    # ============================================================================
    path('ap/', views.ap_invoice_list, name='ap-invoice-list'),
    path('ap/<int:pk>/', views.ap_invoice_detail, name='ap-invoice-detail'),
    path('ap/<int:pk>/post-to-gl/', views.ap_invoice_post_to_gl, name='ap-invoice-post-to-gl'),
    
    # Approval workflow URLs for AP invoices
    path('ap/<int:pk>/submit-for-approval/', views.ap_invoice_submit_for_approval, name='ap-invoice-submit-for-approval'),
    path('ap/pending-approvals/', views.ap_invoice_pending_approvals, name='ap-invoice-pending-approvals'),
    path('ap/<int:pk>/approval-action/', views.ap_invoice_approval_action, name='ap-invoice-approval-action'),
    
    path('ap/<int:invoice_pk>/payments/', payment_views.invoice_payment_info, name='ap-invoice-payments'),
    path('ap/<int:invoice_pk>/recalculate-payments/', payment_views.recalculate_invoice_payments, name='ap-invoice-recalculate'),
    
    # ============================================================================
    # AR Invoice URLs
    # ============================================================================
    path('ar/', views.ar_invoice_list, name='ar-invoice-list'),
    path('ar/<int:pk>/', views.ar_invoice_detail, name='ar-invoice-detail'),
    path('ar/<int:pk>/post-to-gl/', views.ar_invoice_post_to_gl, name='ar-invoice-post-to-gl'),
    
    # Approval workflow URLs for AR invoices
    path('ar/<int:pk>/submit-for-approval/', views.ar_invoice_submit_for_approval, name='ar-invoice-submit-for-approval'),
    path('ar/pending-approvals/', views.ar_invoice_pending_approvals, name='ar-invoice-pending-approvals'),
    path('ar/<int:pk>/approval-action/', views.ar_invoice_approval_action, name='ar-invoice-approval-action'),
    
    path('ar/<int:invoice_pk>/payments/', payment_views.invoice_payment_info, name='ar-invoice-payments'),
    path('ar/<int:invoice_pk>/recalculate-payments/', payment_views.recalculate_invoice_payments, name='ar-invoice-recalculate'),
    
    # ============================================================================
    # One-Time Supplier Invoice URLs
    # ============================================================================
    path('one-time-supplier/', views.one_time_supplier_invoice_list, name='one-time-supplier-list'),
    path('one-time-supplier/<int:pk>/', views.one_time_supplier_invoice_detail, name='one-time-supplier-detail'),
    path('one-time-supplier/<int:pk>/post-to-gl/', views.one_time_supplier_invoice_post_to_gl, name='one-time-supplier-post-to-gl'),
    
    # Approval workflow URLs for One-Time Supplier invoices
    path('one-time-supplier/<int:pk>/submit-for-approval/', views.one_time_supplier_invoice_submit_for_approval, name='one-time-supplier-submit-for-approval'),
    path('one-time-supplier/pending-approvals/', views.one_time_supplier_invoice_pending_approvals, name='one-time-supplier-pending-approvals'),
    path('one-time-supplier/<int:pk>/approval-action/', views.one_time_supplier_invoice_approval_action, name='one-time-supplier-approval-action'),
    
    path('one-time-supplier/<int:invoice_pk>/payments/', payment_views.invoice_payment_info, name='one-time-supplier-payments'),
    path('one-time-supplier/<int:invoice_pk>/recalculate-payments/', payment_views.recalculate_invoice_payments, name='one-time-supplier-recalculate'),
]
