"""
URL Configuration for Accounts app.
Handles user account management functionality (not authentication).
Authentication endpoints are in auth_urls.py
"""
from django.urls import path
from .views import (
    UserProfileView,
)

app_name = 'accounts'

urlpatterns = [
    # User profile management
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    # Future account management endpoints:
    # path('users/', UserListView.as_view(), name='user_list'),
    # path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    # path('users/<int:pk>/update/', UserUpdateView.as_view(), name='user_update'),
]
