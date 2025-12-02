"""
General Ledger - URL Configuration
Handles GL-specific API endpoints for segments and segment types.
"""
from django.urls import path
from . import views

app_name = 'gl'

urlpatterns = [
    # ========================================================================
    # Segment Type Endpoints
    # ========================================================================
    
    # List all segment types or create new
    path('segment-types/', views.segment_type_list, name='segment_type_list'),
    
    # Segment type detail operations
    path('segment-types/<int:pk>/', views.segment_type_detail, name='segment_type_detail'),
    
    # Segment type custom methods
    path('segment-types/<int:pk>/is-used-in-transactions/', 
         views.segment_type_is_used_in_transactions, 
         name='segment_type_is_used_in_transactions'),
    
    path('segment-types/<int:pk>/can-delete/', 
         views.segment_type_can_delete, 
         name='segment_type_can_delete'),
    
    path('segment-types/<int:pk>/toggle-active/', 
         views.segment_type_toggle_active, 
         name='segment_type_toggle_active'),
    
    path('segment-types/<int:pk>/values/', 
         views.segment_type_values, 
         name='segment_type_values'),
    
    # ========================================================================
    # Segment Endpoints
    # ========================================================================
    
    # List all segments or create new
    path('segments/', views.segment_list, name='segment_list'),
    
    # Segment detail operations
    path('segments/<int:pk>/', views.segment_detail, name='segment_detail'),
    
#     # Segment custom methods
#     path('segments/<int:pk>/parent/', 
#          views.segment_parent, 
#          name='segment_parent'),
    
#     path('segments/<int:pk>/full-path/', 
#          views.segment_full_path, 
#          name='segment_full_path'),
    
    path('segments/<int:pk>/children/', 
         views.segment_children, 
         name='segment_children'),
    
    path('segments/<int:pk>/is-used-in-transactions/', 
         views.segment_is_used_in_transactions, 
         name='segment_is_used_in_transactions'),
    
    path('segments/<int:pk>/can-delete/', 
         views.segment_can_delete, 
         name='segment_can_delete'),
    
    path('segments/<int:pk>/toggle-active/', 
         views.segment_toggle_active, 
         name='segment_toggle_active'),
]

