"""
URL Configuration for Core module.
This module handles core functionality including accounts and approval workflows.
"""
from django.urls import path, include

app_name = 'core'

urlpatterns = [
    # User accounts sub-app URLs
    path('user_accounts/', include('core.user_accounts.urls')),
    
    # Approval sub-app URLs
    path('approval/', include('core.approval.urls')),
    
    # Job roles and permissions sub-app URLs
    path('job_roles/', include('core.job_roles.urls')),
]
