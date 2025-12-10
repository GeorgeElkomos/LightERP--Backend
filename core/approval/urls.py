"""
URL Configuration for Approval app.
Handles approval workflows and approval management functionality.
"""
from django.urls import path
from . import views

app_name = 'approval'

urlpatterns = [
    # Add your approval-related URL patterns here
    # Example:
    # path('', views.approval_list, name='approval-list'),
    # path('<int:pk>/', views.approval_detail, name='approval-detail'),
    # path('<int:pk>/approve/', views.approve, name='approve'),
    # path('<int:pk>/reject/', views.reject, name='reject'),
]
