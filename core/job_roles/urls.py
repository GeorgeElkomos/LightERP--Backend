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
    path('job-roles/<int:pk>/', views.job_role_detail, name='job-role-detail'),
    path('job-roles/<int:pk>/assign-page/', views.job_role_assign_page, name='job-role-assign-page'),
    path('job-roles/<int:pk>/remove-page/', views.job_role_remove_page, name='job-role-remove-page'),
    path('job-roles/with-pages/', views.job_role_create_with_pages, name='job-role-create-with-pages'),

    # Page endpoints
    path('pages/', views.page_list, name='page-list'),
    path('pages/<int:pk>/', views.page_detail, name='page-detail'),
    # ============================================================================
    # UserJobRole endpoints (Multiple Roles per User)
    # ============================================================================
    path('user-job-roles/', views.user_job_role_list, name='user-job-role-list'),
    path('user-job-roles/<int:pk>/', views.user_job_role_detail, name='user-job-role-detail'),

    # ============================================================================
    # UserPermissionOverride endpoints (Grants AND Denials)
    # ============================================================================
    path('user-permission-overrides/', views.user_permission_override_list, name='user-permission-override-list'),
    path('user-permission-overrides/<int:pk>/', views.user_permission_override_detail, name='user-permission-override-detail'),

    # ============================================================================
    # User-specific endpoints
    # ============================================================================
    # Get all roles for a user
    path('users/<int:pk>/roles/', views.user_roles, name='user-roles'),

    # Assign/remove roles for a user
    path('users/<int:pk>/assign-roles/', views.user_assign_roles, name='user-assign-roles'),
    path('users/<int:pk>/remove-roles/', views.user_remove_roles, name='user-remove-roles'),

    # Get complete permission summary for a user
    path('users/<int:pk>/permissions/', views.user_permissions, name='user-permissions'),
]
