"""
General Ledger - URL Configuration
Handles GL-specific API endpoints for segments, segment types, journal entries, and general ledger.
"""
from django.urls import path
from .views import segments_views, journal_views, general_ledger_views

app_name = 'GL'

urlpatterns = [
    # ========================================================================
    # Segment Type Endpoints
    # ========================================================================
    
    # List all segment types or create new
    path('segment-types/', segments_views.segment_type_list, name='segment_type_list'),
    
    # Segment type detail operations
    path('segment-types/<int:pk>/', segments_views.segment_type_detail, name='segment_type_detail'),
    
    # Segment type custom methods
    path('segment-types/<int:pk>/is-used-in-transactions/', 
         segments_views.segment_type_is_used_in_transactions, 
         name='segment_type_is_used_in_transactions'),
    
    path('segment-types/<int:pk>/can-delete/', 
         segments_views.segment_type_can_delete, 
         name='segment_type_can_delete'),
    
    path('segment-types/<int:pk>/toggle-active/', 
         segments_views.segment_type_toggle_active, 
         name='segment_type_toggle_active'),
    
    path('segment-types/<int:pk>/values/', 
         segments_views.segment_type_values, 
         name='segment_type_values'),
    
    # ========================================================================
    # Segment Endpoints
    # ========================================================================
    
    # List all segments or create new
    path('segments/', segments_views.segment_list, name='segment_list'),
    
    # Segment detail operations
    path('segments/<int:pk>/', segments_views.segment_detail, name='segment_detail'),
    
    path('segments/<int:pk>/children/', 
         segments_views.segment_children, 
         name='segment_children'),
    
    path('segments/<int:pk>/is-used-in-transactions/', 
         segments_views.segment_is_used_in_transactions, 
         name='segment_is_used_in_transactions'),
    
    path('segments/<int:pk>/can-delete/', 
         segments_views.segment_can_delete, 
         name='segment_can_delete'),
    
    path('segments/<int:pk>/toggle-active/', 
         segments_views.segment_toggle_active, 
         name='segment_toggle_active'),
    
    # ========================================================================
    # Journal Entry Endpoints
    # ========================================================================
    
    # List all journal entries
    path('journal-entries/', journal_views.journal_entry_list, name='journal_entry_list'),
    
    # Create or update journal entry (POST for create, PUT for update)
    path('journal-entries/save/', journal_views.journal_entry_create_update, name='journal_entry_save'),
    
    # Get journal entry details
    path('journal-entries/<int:pk>/', journal_views.journal_entry_detail, name='journal_entry_detail'),
    
    # Delete journal entry
    path('journal-entries/<int:pk>/delete/', journal_views.journal_entry_delete, name='journal_entry_delete'),
    
    # Post journal entry to General Ledger
    path('journal-entries/<int:pk>/post/', journal_views.journal_entry_post, name='journal_entry_post'),
    
    # ========================================================================
    # General Ledger Endpoints
    # ========================================================================
    
    # List all general ledger entries
    path('general-ledger/', general_ledger_views.general_ledger_list, name='general_ledger_list'),
    
    # Get general ledger entry details
    path('general-ledger/<int:pk>/', general_ledger_views.general_ledger_detail, name='general_ledger_detail'),
]

