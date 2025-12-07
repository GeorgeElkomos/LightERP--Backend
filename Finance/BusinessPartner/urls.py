"""
URL Configuration for Business Partner API endpoints.
"""
from django.urls import path
from . import views
from Finance.payments import views as payment_views

app_name = 'businesspartner'

urlpatterns = [
    # Customer endpoints
    path('customers/', views.customer_list, name='customer-list'),
    path('customers/active/', views.customer_active_list, name='customer-active-list'),
    path('customers/<int:pk>/', views.customer_detail, name='customer-detail'),
    path('customers/<int:pk>/toggle-active/', views.customer_toggle_active, name='customer-toggle-active'),
    path('customers/<int:bp_pk>/payment-summary/', payment_views.business_partner_payment_summary, name='customer-payment-summary'),
    
    # Supplier endpoints
    path('suppliers/', views.supplier_list, name='supplier-list'),
    path('suppliers/active/', views.supplier_active_list, name='supplier-active-list'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier-detail'),
    path('suppliers/<int:pk>/toggle-active/', views.supplier_toggle_active, name='supplier-toggle-active'),
    path('suppliers/<int:bp_pk>/payment-summary/', payment_views.business_partner_payment_summary, name='supplier-payment-summary'),
]
