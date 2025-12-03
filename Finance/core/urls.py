"""
URL Configuration for Finance Core API endpoints.
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Currency endpoints
    path('currencies/', views.currency_list, name='currency-list'),
    path('currencies/<int:pk>/', views.currency_detail, name='currency-detail'),
    path('currencies/<int:pk>/toggle-active/', views.currency_toggle_active, name='currency-toggle-active'),
    path('currencies/<int:pk>/convert-to-base/', views.currency_convert_to_base, name='currency-convert-to-base'),
    path('currencies/base/', views.currency_get_base, name='currency-get-base'),
    
    # Country endpoints
    path('countries/', views.country_list, name='country-list'),
    path('countries/<int:pk>/', views.country_detail, name='country-detail'),
    path('countries/<int:pk>/tax-rates/', views.country_tax_rates, name='country-tax-rates'),
    
    # TaxRate endpoints
    path('tax-rates/', views.tax_rate_list, name='tax-rate-list'),
    path('tax-rates/<int:pk>/', views.tax_rate_detail, name='tax-rate-detail'),
    path('tax-rates/<int:pk>/toggle-active/', views.tax_rate_toggle_active, name='tax-rate-toggle-active'),
]
