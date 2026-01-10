"""
URL Configuration for Cash Management API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'cash_management'

# Create router and register viewsets
router = DefaultRouter()
router.register(r'payment-types', views.PaymentTypeViewSet, basename='paymenttype')
router.register(r'banks', views.BankViewSet, basename='bank')
router.register(r'branches', views.BankBranchViewSet, basename='branch')
router.register(r'accounts', views.BankAccountViewSet, basename='account')
router.register(r'statements', views.BankStatementViewSet, basename='bankstatement')
router.register(r'statement-lines', views.BankStatementLineViewSet, basename='bankstatementline')
router.register(r'matches', views.BankStatementLineMatchViewSet, basename='bankstatementlinematch')

urlpatterns = [
    path('', include(router.urls)),
]
