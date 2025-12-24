"""
URL Configuration for Catalog API endpoints.
"""
from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    # Unit of Measure endpoints
    path('uom/', views.uom_list, name='uom-list'),
    path('uom/<int:pk>/', views.uom_detail, name='uom-detail'),
    
    # Catalog Item endpoints
    path('items/', views.catalog_item_list, name='catalog-item-list'),
    path('items/<int:pk>/', views.catalog_item_detail, name='catalog-item-detail'),
    path('items/by-code/<str:code>/', views.catalog_item_by_code, name='catalog-item-by-code'),
    path('items/search/', views.catalog_item_search, name='catalog-item-search'),
]
