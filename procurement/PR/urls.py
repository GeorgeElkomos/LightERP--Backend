"""
Purchase Requisition URL Configuration

URL patterns for PR module API endpoints.
Uses function-based views matching the Invoice pattern.
"""

from django.urls import path
from procurement.PR import views

app_name = 'pr'

urlpatterns = [
    # ============================================================================
    # Catalog PR URLs
    # ============================================================================
    path('catalog/', views.catalog_pr_list, name='catalog-pr-list'),
    path('catalog/<int:pk>/', views.catalog_pr_detail, name='catalog-pr-detail'),
    
    # Approval workflow URLs for Catalog PRs
    path('catalog/<int:pk>/submit-for-approval/', views.catalog_pr_submit_for_approval, name='catalog-pr-submit-for-approval'),
    path('catalog/pending-approvals/', views.catalog_pr_pending_approvals, name='catalog-pr-pending-approvals'),
    path('catalog/<int:pk>/approval-action/', views.catalog_pr_approval_action, name='catalog-pr-approval-action'),
    
    # Cancel Catalog PR
    path('catalog/<int:pk>/cancel/', views.catalog_pr_cancel, name='catalog-pr-cancel'),
    
    # ============================================================================
    # Non-Catalog PR URLs
    # ============================================================================
    path('non-catalog/', views.noncatalog_pr_list, name='noncatalog-pr-list'),
    path('non-catalog/<int:pk>/', views.noncatalog_pr_detail, name='noncatalog-pr-detail'),
    
    # Approval workflow URLs for Non-Catalog PRs
    path('non-catalog/<int:pk>/submit-for-approval/', views.noncatalog_pr_submit_for_approval, name='noncatalog-pr-submit-for-approval'),
    path('non-catalog/pending-approvals/', views.noncatalog_pr_pending_approvals, name='noncatalog-pr-pending-approvals'),
    path('non-catalog/<int:pk>/approval-action/', views.noncatalog_pr_approval_action, name='noncatalog-pr-approval-action'),
    
    # Cancel Non-Catalog PR
    path('non-catalog/<int:pk>/cancel/', views.noncatalog_pr_cancel, name='noncatalog-pr-cancel'),
    
    # ============================================================================
    # Service PR URLs
    # ============================================================================
    path('service/', views.service_pr_list, name='service-pr-list'),
    path('service/<int:pk>/', views.service_pr_detail, name='service-pr-detail'),
    
    # Approval workflow URLs for Service PRs
    path('service/<int:pk>/submit-for-approval/', views.service_pr_submit_for_approval, name='service-pr-submit-for-approval'),
    path('service/pending-approvals/', views.service_pr_pending_approvals, name='service-pr-pending-approvals'),
    path('service/<int:pk>/approval-action/', views.service_pr_approval_action, name='service-pr-approval-action'),
    
    # Cancel Service PR
    path('service/<int:pk>/cancel/', views.service_pr_cancel, name='service-pr-cancel'),
]
