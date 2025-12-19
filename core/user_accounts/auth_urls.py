"""
URL Configuration for Authentication endpoints.
Handles user registration, login, logout, password changes, and token management.
Account management endpoints are in urls.py
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'auth'

urlpatterns = [
    # Registration and Login
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    
    # Password management
    path('change-password/', views.change_password, name='change_password'),
    
    # Token management
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
