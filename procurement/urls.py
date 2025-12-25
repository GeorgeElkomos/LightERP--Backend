from django.urls import path, include

urlpatterns = [
    path('pr/', include('procurement.PR.urls')),
    path('catalog/', include('procurement.catalog.urls')),
    path('po/', include('procurement.po.urls')),
    path('receiving/', include('procurement.receiving.urls')),
]
