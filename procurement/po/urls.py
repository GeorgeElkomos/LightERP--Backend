"""
Purchase Order URL Configuration

URL patterns for PO module API endpoints.
Uses function-based views matching the PR/Invoice pattern.
"""

from django.urls import path
from procurement.po import views

app_name = 'po'

urlpatterns = [
    # ============================================================================
    # PO CRUD Operations
    # ============================================================================
    path('', views.po_list, name='po-list'),
    path('<int:pk>/', views.po_detail, name='po-detail'),
    
    # ============================================================================
    # PO Workflow Actions
    # ============================================================================
    # Submit for approval
    path('<int:pk>/submit-for-approval/', views.po_submit_for_approval, name='po-submit-for-approval'),
    
    # Pending approvals list
    path('pending-approvals/', views.po_pending_approvals, name='po-pending-approvals'),
    
    # Approve/Reject action
    path('<int:pk>/approval-action/', views.po_approval_action, name='po-approval-action'),
    
    # Confirm PO (send to vendor)
    path('<int:pk>/confirm/', views.po_confirm, name='po-confirm'),
    
    # Cancel PO
    path('<int:pk>/cancel/', views.po_cancel, name='po-cancel'),
    
    # ============================================================================
    # Goods Receiving
    # ============================================================================
    # Record goods receipt
    path('<int:pk>/record-receipt/', views.po_record_receipt, name='po-record-receipt'),
    
    # Get receiving summary
    path('<int:pk>/receiving-summary/', views.po_receiving_summary, name='po-receiving-summary'),
    
    # ============================================================================
    # Reporting & Analytics
    # ============================================================================
    # PO count by status
    path('by-status/', views.po_by_status, name='po-by-status'),
    
    # PO statistics by supplier
    path('by-supplier/', views.po_by_supplier, name='po-by-supplier'),
    
    # POs created from PRs
    path('from-pr/', views.po_from_pr, name='po-from-pr'),
    
    # ============================================================================
    # Attachments
    # ============================================================================
    # List attachments or upload new attachment for a PO
    path('<int:po_id>/attachments/', views.po_attachment_list, name='po-attachment-list'),
    
    # Retrieve or delete a specific attachment
    path('attachments/<int:attachment_id>/', views.po_attachment_detail, name='po-attachment-detail'),
]
