"""
Finance Period URL Configuration

Provides endpoints for:
1. Standard CRUD operations for periods
2. Generate period preview (without saving)
3. Bulk save generated periods
4. Child period endpoints (AR, AP, GL)
"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import PeriodViewSet, AR_PeriodViewSet, AP_PeriodViewSet, GL_PeriodViewSet

# Create router and register viewsets
router = SimpleRouter()
router.register(r'periods', PeriodViewSet, basename='period')
router.register(r'ar-periods', AR_PeriodViewSet, basename='ar-period')
router.register(r'ap-periods', AP_PeriodViewSet, basename='ap-period')
router.register(r'gl-periods', GL_PeriodViewSet, basename='gl-period')

urlpatterns = [
    # Router URLs include:
    # 
    # Period endpoints:
    # GET    /periods/                  -> List all periods
    # POST   /periods/                  -> Create single period manually
    # GET    /periods/{id}/             -> Retrieve period detail
    # PUT    /periods/{id}/             -> Update period
    # PATCH  /periods/{id}/             -> Partial update period
    # DELETE /periods/{id}/             -> Delete period
    # GET    /periods/current/          -> Get current period
    # POST   /periods/generate-preview/ -> Generate period preview (not saved)
    # POST   /periods/bulk-save/        -> Bulk save periods
    #
    # AR Period endpoints:
    # GET    /ar-periods/               -> List all AR periods
    # GET    /ar-periods/{id}/          -> Retrieve AR period detail
    # PATCH  /ar-periods/{id}/update_state/ -> Update AR period state
    #
    # AP Period endpoints:
    # GET    /ap-periods/               -> List all AP periods
    # GET    /ap-periods/{id}/          -> Retrieve AP period detail
    # PATCH  /ap-periods/{id}/update_state/ -> Update AP period state
    #
    # GL Period endpoints:
    # GET    /gl-periods/               -> List all GL periods
    # GET    /gl-periods/{id}/          -> Retrieve GL period detail
    # PATCH  /gl-periods/{id}/update_state/ -> Update GL period state
    path('', include(router.urls)),
]

