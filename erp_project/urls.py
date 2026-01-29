"""
URL configuration for erp_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('finance/', include('Finance.urls')),
    path('core/', include('core.urls')),
    path('procurement/catalog/', include('procurement.catalog.urls')),
    path('procurement/pr/', include('procurement.PR.urls')),
    path('procurement/po/', include('procurement.po.urls')),
    path('procurement/receiving/', include('procurement.receiving.urls')),
    path('hr/', include('HR.urls')),
    
    # Budget Control (direct access for API)
    path('api/', include('Finance.budget_control.urls')),
    
    # Authentication endpoints (register, login, logout, password, tokens)
    path('auth/', include('core.user_accounts.auth_urls')),
    
    # Account management endpoints (profile, users, etc.)
    path('accounts/', include('core.user_accounts.urls')),
]
