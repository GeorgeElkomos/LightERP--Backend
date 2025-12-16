"""
URL Configuration for Accounts app.
Handles user account management functionality (not authentication).
Authentication endpoints are in auth_urls.py
"""
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # User profile management
    path('profile/', views.user_profile, name='user_profile'),
    # Password reset flow
    path('password-reset-request/', views.password_reset_request, name='password_reset_request'),
    path('superadmin/password-reset/', views.superadmin_password_reset, name='superadmin_password_reset'),
    # Admin User Management Endpoints (Admin/Super Admin Only)
    path('admin/users/', views.admin_user_list, name='admin_user_list'),
    path('admin/users/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
]
