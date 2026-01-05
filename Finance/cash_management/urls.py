"""
URL Configuration for Cash Management API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'cash_management'

# Create router and register viewsets
router = DefaultRouter()
router.register(r'banks', views.BankViewSet, basename='bank')
router.register(r'branches', views.BankBranchViewSet, basename='branch')
router.register(r'accounts', views.BankAccountViewSet, basename='account')

urlpatterns = [
    path('', include(router.urls)),
]
