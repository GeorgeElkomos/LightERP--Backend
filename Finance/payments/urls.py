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

    # ========================================================================
    # Payment Plan & Installment URLs
    # ========================================================================
    
    # Invoice Payment Plans
    path('invoices/<int:invoice_pk>/payment-plans/', views.invoice_payment_plans_list, name='invoice-payment-plans-list'),
    path('invoices/<int:invoice_pk>/suggest-payment-plan/', views.invoice_suggest_payment_plan, name='invoice-suggest-payment-plan'),
    
    # Payment Plan Detail & Operations
    path('payment-plans/<int:pk>/', views.payment_plan_detail, name='payment-plan-detail'),
    path('payment-plans/<int:pk>/process-payment/', views.payment_plan_process_payment, name='payment-plan-process-payment'),
    path('payment-plans/<int:pk>/update-status/', views.payment_plan_update_status, name='payment-plan-update-status'),
    path('payment-plans/<int:pk>/cancel/', views.payment_plan_cancel, name='payment-plan-cancel'),
    path('payment-plans/<int:pk>/summary/', views.payment_plan_summary, name='payment-plan-summary'),
    path('payment-plans/<int:pk>/overdue-installments/', views.payment_plan_overdue_installments, name='payment-plan-overdue-installments'),
    
    # Payment Plan Installments
    path('payment-plans/<int:payment_plan_pk>/installments/', views.payment_plan_installments_list, name='payment-plan-installments-list'),
    
    # Installment Detail & Operations
    path('installments/<int:pk>/', views.installment_detail, name='installment-detail'),
    path('installments/<int:pk>/update-status/', views.installment_update_status, name='installment-update-status'),
    
    # Utility Lists
    path('payment-plans/overdue/', views.payment_plans_overdue_list, name='payment-plans-overdue-list'),
    path('installments/due-soon/', views.installments_due_soon, name='installments-due-soon'),
    path('business-partners/<int:bp_pk>/payment-plans/', views.business_partner_payment_plans, name='business-partner-payment-plans'),
]
