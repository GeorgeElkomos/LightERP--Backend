"""
Finance Period URL Configuration

Provides endpoints for:
1. Standard CRUD operations for periods
2. Generate period preview (without saving)
3. Bulk save generated periods
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PeriodViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'periods', PeriodViewSet, basename='period')

urlpatterns = [
    # Router URLs include:
    # GET    /periods/                  -> List all periods
    # POST   /periods/                  -> Create single period manually
    # GET    /periods/{id}/             -> Retrieve period detail
    # PUT    /periods/{id}/             -> Update period
    # PATCH  /periods/{id}/             -> Partial update period
    # DELETE /periods/{id}/             -> Delete period
    # GET    /periods/current/          -> Get current period
    # POST   /periods/generate-preview/ -> Generate period preview (not saved)
    # POST   /periods/bulk-save/        -> Bulk save periods
    path('', include(router.urls)),
]
