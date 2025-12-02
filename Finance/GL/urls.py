"""
General Ledger - URL Configuration
Handles GL-specific views and endpoints
"""
from django.urls import path
from . import views

app_name = 'gl'

urlpatterns = [
    # Example: Chart of Accounts, Journal Entries
    # path('accounts/', views.chart_of_accounts, name='chart_of_accounts'),
    # path('journal/', views.journal_entries, name='journal_entries'),
]
