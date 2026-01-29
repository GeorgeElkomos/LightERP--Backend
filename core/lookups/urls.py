from django.urls import path
from . import views

urlpatterns = [
    path('types/', views.lookup_type_list, name='lookup-type-list'),
    path('types/<int:pk>/', views.lookup_type_detail, name='lookup-type-detail'),
    path('values/', views.lookup_value_list, name='lookup-value-list'),
    path('values/<int:pk>/', views.lookup_value_detail, name='lookup-value-detail'),
]
