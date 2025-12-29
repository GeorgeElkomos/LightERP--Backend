"""
URL configuration for HR Work Structures module.
Routes all HR Work Structures-related API endpoints.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Enterprise endpoints
    path('enterprises/', views.enterprise_list, name='hr-enterprise-list'),
    path('enterprises/<int:pk>/', views.enterprise_detail, name='hr-enterprise-detail'),
    path('enterprises/<int:pk>/history/', views.enterprise_history, name='hr-enterprise-history'),
    
    # Business Group endpoints
    path('business-groups/', views.business_group_list, name='hr-business-group-list'),
    path('business-groups/<int:pk>/', views.business_group_detail, name='hr-business-group-detail'),
    path('business-groups/<int:pk>/history/', views.business_group_history, name='hr-business-group-history'),
    
    # Location endpoints
    path('locations/', views.location_list, name='hr-location-list'),
    path('locations/<int:pk>/', views.location_detail, name='hr-location-detail'),
    
    # Department endpoints
    path('departments/', views.department_list, name='hr-department-list'),
    path('departments/<int:pk>/', views.department_detail, name='hr-department-detail'),
    path('departments/<int:pk>/history/', views.department_history, name='hr-department-history'),
    path('departments/<int:pk>/children/', views.department_children, name='hr-department-children'),
    path('departments/<int:pk>/parent/', views.department_parent, name='hr-department-parent'),
    path('departments/tree/', views.department_tree, name='hr-department-tree'),
    
    # Department Manager endpoints
    path('departments/<int:department_pk>/managers/', views.department_manager_list, name='hr-department-manager-list'),
    path('departments/<int:department_pk>/managers/<int:manager_pk>/', views.department_manager_detail, name='hr-department-manager-detail'),
    
    # Position endpoints
    path('positions/', views.position_list, name='hr-position-list'),
    path('positions/<int:pk>/', views.position_detail, name='hr-position-detail'),
    path('positions/<int:pk>/history/', views.position_history, name='hr-position-history'),
    path('positions/<int:pk>/direct-reports/', views.position_direct_reports, name='hr-position-direct-reports'),
    path('positions/hierarchy/', views.position_hierarchy, name='hr-position-hierarchy'),
    
    # Grade endpoints
    path('grades/', views.grade_list, name='hr-grade-list'),
    path('grades/<int:pk>/', views.grade_detail, name='hr-grade-detail'),
    path('grades/<int:pk>/history/', views.grade_history, name='hr-grade-history'),
    
    # Grade Rate endpoints
    path('grades/<int:grade_pk>/rates/', views.grade_rate_list, name='hr-grade-rate-list'),
    path('grades/<int:grade_pk>/rates/<int:rate_pk>/', views.grade_rate_detail, name='hr-grade-rate-detail'),
    path('grades/<int:grade_pk>/rates/history/<str:rate_type>/', views.grade_rate_history, name='hr-grade-rate-history'),
    
    # User Data Scope endpoints
    path('user-scopes/', views.user_scope_list, name='hr-user-scope-list'),
    path('user-scopes/<int:pk>/', views.user_scope_detail, name='hr-user-scope-detail'),
    
    # ============================================================================
    # Hard Delete Endpoints (Super Admin Only)
    # ============================================================================
    # WARNING: These endpoints permanently delete records from the database
    # Requires super admin privileges
    path('enterprises/<int:pk>/hard-delete/', views.enterprise_hard_delete, name='hr-enterprise-hard-delete'),
    path('business-groups/<int:pk>/hard-delete/', views.business_group_hard_delete, name='hr-business-group-hard-delete'),
    path('departments/<int:pk>/hard-delete/', views.department_hard_delete, name='hr-department-hard-delete'),
    path('department-managers/<int:pk>/hard-delete/', views.department_manager_hard_delete, name='hr-department-manager-hard-delete'),
    path('positions/<int:pk>/hard-delete/', views.position_hard_delete, name='hr-position-hard-delete'),
    path('grades/<int:pk>/hard-delete/', views.grade_hard_delete, name='hr-grade-hard-delete'),
    path('locations/<int:pk>/hard-delete/', views.location_hard_delete, name='hr-location-hard-delete'),
]
