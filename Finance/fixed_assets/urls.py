from django.urls import path
from . import views

app_name = 'fixed_assets'

urlpatterns = [
    # Asset Category URLs
    # path('categories/', views.category_list, name='category_list'),
    
    # Asset Location URLs
    # path('locations/', views.location_list, name='location_list'),
    
    # Fixed Asset URLs
    # path('', views.asset_list, name='asset_list'),
    # path('create/', views.asset_create, name='asset_create'),
    # path('<int:pk>/', views.asset_detail, name='asset_detail'),
    # path('<int:pk>/activate/', views.asset_activate, name='asset_activate'),
    # path('<int:pk>/dispose/', views.asset_dispose, name='asset_dispose'),
    
    # Depreciation URLs
    # path('depreciation/run/', views.run_depreciation, name='run_depreciation'),
    # path('depreciation/history/', views.depreciation_history, name='depreciation_history'),
]
