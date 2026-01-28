"""
HR App - Main URL Configuration
This file routes URLs to the appropriate sub-apps within the HR module.
"""
from django.urls import path, include

app_name = 'hr'

urlpatterns = [
    # Work Structures URLs
    path('work_structures/', include('HR.work_structures.urls')),
    # Person Domain URLs
    path('person/', include('HR.person.urls')),
]
