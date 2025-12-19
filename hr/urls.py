"""
URL configuration for HR module.
Routes all HR-related API endpoints.
"""
from django.urls import path
from hr import views

urlpatterns = [
    # Enterprise endpoints
    path('enterprises/', views.enterprise_list, name='hr-enterprise-list'),
    path('enterprises/<int:pk>/', views.enterprise_detail, name='hr-enterprise-detail'),
    
    # Business Group endpoints
    path('business-groups/', views.business_group_list, name='hr-business-group-list'),
    path('business-groups/<int:pk>/', views.business_group_detail, name='hr-business-group-detail'),
    
    # Location endpoints
    path('locations/', views.location_list, name='hr-location-list'),
    path('locations/<int:pk>/', views.location_detail, name='hr-location-detail'),
    
    # Department endpoints
    path('departments/', views.department_list, name='hr-department-list'),
    path('departments/<int:pk>/', views.department_detail, name='hr-department-detail'),
    path('departments/<int:pk>/history/', views.department_history, name='hr-department-history'),
    path('departments/tree/', views.department_tree, name='hr-department-tree'),
    
    # Position endpoints
    path('positions/', views.position_list, name='hr-position-list'),
    path('positions/<int:pk>/', views.position_detail, name='hr-position-detail'),
    path('positions/<int:pk>/history/', views.position_history, name='hr-position-history'),
    path('positions/hierarchy/', views.position_hierarchy, name='hr-position-hierarchy'),
    
    # Grade endpoints
    path('grades/', views.grade_list, name='hr-grade-list'),
    path('grades/<int:pk>/', views.grade_detail, name='hr-grade-detail'),
    path('grades/<int:pk>/history/', views.grade_history, name='hr-grade-history'),
    
    # Grade Rate endpoints
    path('grades/<int:grade_pk>/rates/', views.grade_rate_list, name='hr-grade-rate-list'),
    path('grades/<int:grade_pk>/rates/<int:rate_pk>/', views.grade_rate_detail, name='hr-grade-rate-detail'),
]
