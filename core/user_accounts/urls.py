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
    # Future account management endpoints:
    # path('users/', user_list, name='user_list'),
    # path('users/<int:pk>/', user_detail, name='user_detail'),
]
