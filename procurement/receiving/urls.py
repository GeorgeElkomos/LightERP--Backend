"""
Goods Receipt URL Configuration

URL patterns for Receiving module API endpoints.
Uses function-based views matching the PO/PR/Invoice pattern.
"""

from django.urls import path
from procurement.receiving import views

app_name = 'receiving'

urlpatterns = [
    # ============================================================================
    # GRN CRUD Operations
    # ============================================================================
    # List all GRNs / Create new GRN
    path('', views.grn_list, name='grn-list'),
    
    # Get GRN detail / Delete GRN
    path('<int:pk>/', views.grn_detail, name='grn-detail'),
    
    # Get GRN summary (receipt summary + PO completion)
    path('<int:pk>/summary/', views.grn_summary, name='grn-summary'),
    
    # ============================================================================
    # PO Receiving Status
    # ============================================================================
    # Get receiving status for a specific PO
    path('po/<int:po_id>/status/', views.po_receiving_status, name='po-receiving-status'),
    
    # ============================================================================
    # Reporting & Analytics
    # ============================================================================
    # GRN statistics by supplier
    path('by-supplier/', views.grn_by_supplier, name='grn-by-supplier'),
    
    # GRN statistics by type
    path('by-type/', views.grn_by_type, name='grn-by-type'),
    
    # Recent GRNs (last N days)
    path('recent/', views.grn_recent, name='grn-recent'),
]
