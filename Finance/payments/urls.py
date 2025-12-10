"""
Payment URL Configuration
"""

from django.urls import path
from Finance.payments import views

app_name = 'payments'

urlpatterns = [
    # Payment CRUD endpoints
    path('', views.payment_list, name='payment-list'),
    path('<int:pk>/', views.payment_detail, name='payment-detail'),
    
    # Payment allocation management
    path('<int:payment_pk>/allocations/', views.payment_allocations, name='payment-allocations'),
    path('<int:payment_pk>/allocations/<int:allocation_pk>/', views.payment_allocation_detail, name='payment-allocation-detail'),
    
    # Utility endpoints
    path('<int:payment_pk>/available-invoices/', views.available_invoices_for_payment, name='payment-available-invoices'),
    
    # Approval workflow endpoints
    path('<int:pk>/submit-for-approval/', views.payment_submit_for_approval, name='payment-submit-for-approval'),
    path('<int:pk>/approval-action/', views.payment_approval_action, name='payment-approval-action'),
    path('<int:pk>/post-to-gl/', views.payment_post_to_gl, name='payment-post-to-gl'),
    path('pending-approvals/', views.payment_pending_approvals, name='payment-pending-approvals'),
]
