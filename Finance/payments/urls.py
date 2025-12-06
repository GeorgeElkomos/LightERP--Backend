from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment Method URLs
    # path('methods/', views.payment_method_list, name='payment_method_list'),
    
    # Bank Account URLs
    # path('banks/', views.bank_account_list, name='bank_account_list'),
    
    # Payment URLs
    # path('', views.payment_list, name='payment_list'),
    # path('create/', views.payment_create, name='payment_create'),
    # path('<int:pk>/', views.payment_detail, name='payment_detail'),
    
    # Supplier Payment URLs
    # path('supplier/', views.supplier_payment_list, name='supplier_payment_list'),
    
    # Customer Payment URLs
    # path('customer/', views.customer_payment_list, name='customer_payment_list'),
]
