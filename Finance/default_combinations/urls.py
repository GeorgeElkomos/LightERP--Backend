"""
Default Combinations URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DefaultCombinationsViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(
    r'default-combinations',
    DefaultCombinationsViewSet,
    basename='default-combinations'
)

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]

# Available endpoints:
# GET    /default-combinations/                          - List all defaults
# POST   /default-combinations/                          - Create/update default
# GET    /default-combinations/{id}/                     - Retrieve specific default
# PUT    /default-combinations/{id}/                     - Update default
# PATCH  /default-combinations/{id}/                     - Partial update
# DELETE /default-combinations/{id}/                     - Delete default
# GET    /default-combinations/by-transaction-type/{type}/ - Get by transaction type
# GET    /default-combinations/ap-invoice-default/       - Get AP invoice default
# GET    /default-combinations/ar-invoice-default/       - Get AR invoice default
# POST   /default-combinations/{id}/validate/            - Validate combination
# POST   /default-combinations/check-all-validity/       - Check all defaults
# POST   /default-combinations/{id}/activate/            - Activate default
# POST   /default-combinations/{id}/deactivate/          - Deactivate default
# GET    /default-combinations/transaction-types/        - List transaction types
# GET    /default-combinations/gl-segments/?transaction_type={type} - Get GL segment details
# GET    /default-combinations/ap-invoice-segments/      - Get AP invoice GL segments
# GET    /default-combinations/ar-invoice-segments/      - Get AR invoice GL segments
