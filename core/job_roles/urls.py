"""
URL Configuration for Job Roles and Permissions app.
Handles role-based access control and permission management functionality.
"""
from django.urls import path
from . import views

app_name = 'job_roles'

urlpatterns = [
    # JobRole endpoints
    path('job-roles/', views.job_role_list, name='job-role-list'),
    path('job-roles/with-pages/', views.job_role_create_with_pages, name='job-role-create-with-pages'),
    path('job-roles/<int:pk>/', views.job_role_detail, name='job-role-detail'),
    path('job-roles/<int:pk>/assign-page/', views.job_role_assign_page, name='job-role-assign-page'),
    path('job-roles/<int:pk>/assign-user/', views.job_role_assign_user, name='job-role-assign-user'),
    path('job-roles/<int:pk>/remove-page/', views.job_role_remove_page, name='job-role-remove-page'),
    
    # Page endpoints
    path('pages/', views.page_list, name='page-list'),
    path('pages/<int:pk>/', views.page_detail, name='page-detail'),
    path('pages/<int:pk>/assign-action/', views.page_assign_action, name='page-assign-action'),
    path('pages/<int:pk>/remove-action/', views.page_remove_action, name='page-remove-action'),
    
    # Action endpoints
    path('actions/', views.action_list, name='action-list'),
    path('actions/<int:pk>/', views.action_detail, name='action-detail'),
    
    # PageAction endpoints
    path('page-actions/', views.page_action_list, name='page-action-list'),
    path('page-actions/<int:pk>/', views.page_action_detail, name='page-action-detail'),
    
    # User-specific permissions
    path('users/<int:pk>/actions/', views.user_actions, name='user-actions'),
    
    # UserActionDenial endpoints
    path('user-action-denials/', views.user_action_denial_list, name='user-action-denial-list'),
    path('user-action-denials/<int:pk>/', views.user_action_denial_detail, name='user-action-denial-detail'),
]
