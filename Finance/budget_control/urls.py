"""
URL Configuration for Budget Control API endpoints.
"""
from django.urls import path
from . import views

app_name = 'budget_control'

urlpatterns = [
    # ========================================================================
    # BUDGET HEADER ENDPOINTS
    # ========================================================================
    
    # List and Create
    path('budget-headers/', 
         views.budget_header_list, 
         name='budget-header-list'),
    
    # Active budgets only
    path('budget-headers/active/', 
         views.budget_header_active_list, 
         name='budget-header-active-list'),
    
    # Detail, Update, Delete
    path('budget-headers/<int:pk>/', 
         views.budget_header_detail, 
         name='budget-header-detail'),
    
    # Budget lifecycle operations
    path('budget-headers/<int:pk>/activate/', 
         views.budget_header_activate, 
         name='budget-header-activate'),
    
    path('budget-headers/<int:pk>/close/', 
         views.budget_header_close, 
         name='budget-header-close'),
    
    path('budget-headers/<int:pk>/deactivate/', 
         views.budget_header_deactivate, 
         name='budget-header-deactivate'),
    
    # Budget summary and reporting
    path('budget-headers/<int:pk>/summary/', 
         views.budget_summary, 
         name='budget-summary'),
    
    # ========================================================================
    # BUDGET CHECKING ENDPOINT
    # ========================================================================
    
    # Check budget availability
    path('budget-check/', 
         views.budget_check, 
         name='budget-check'),
    
    # ========================================================================
    # BUDGET SEGMENT VALUE ENDPOINTS (Nested under budget)
    # ========================================================================
    
    # List and Create segment values for a budget
    path('budget-headers/<int:budget_id>/segments/', 
         views.budget_segment_value_list, 
         name='budget-segment-value-list'),
    
    # Detail, Update, Delete segment value
    path('budget-headers/<int:budget_id>/segments/<int:segment_id>/', 
         views.budget_segment_value_detail, 
         name='budget-segment-value-detail'),
    
    # ========================================================================
    # BUDGET AMOUNT ENDPOINTS (Nested under budget)
    # ========================================================================
    
    # List and Create budget amounts for a budget
    path('budget-headers/<int:budget_id>/amounts/', 
         views.budget_amount_list, 
         name='budget-amount-list'),
    
    # Detail, Update, Delete budget amount
    path('budget-headers/<int:budget_id>/amounts/<int:amount_id>/', 
         views.budget_amount_detail, 
         name='budget-amount-detail'),
    
    # Adjust budget amount (for ACTIVE budgets)
    path('budget-headers/<int:budget_id>/amounts/<int:amount_id>/adjust/', 
         views.budget_amount_adjust, 
         name='budget-amount-adjust'),
    
    # ========================================================================
    # REPORTING ENDPOINTS
    # ========================================================================
    
    # Budget violations report
    path('budget-violations/', 
         views.budget_violations_report, 
         name='budget-violations-report'),
    
    # ========================================================================
    # EXCEL IMPORT/EXPORT ENDPOINTS
    # ========================================================================
    
    # Export budget to Excel
    path('budget-headers/<int:pk>/export/', 
         views.budget_export_excel, 
         name='budget-export'),
    
    # Import budget from Excel
    path('budget-headers/<int:pk>/import/', 
         views.budget_import_excel, 
         name='budget-import'),
    
    # Download Excel template
    path('budget-headers/<int:pk>/template/', 
         views.budget_template_excel, 
         name='budget-template'),
]
