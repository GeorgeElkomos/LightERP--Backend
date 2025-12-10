"""
URL Configuration for Authentication endpoints.
Handles user registration, login, logout, password changes, and token management.
Account management endpoints are in urls.py
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    ChangePasswordView,
    LogoutView
)

app_name = 'auth'

urlpatterns = [
    # Registration and Login
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Password management
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Token management
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
