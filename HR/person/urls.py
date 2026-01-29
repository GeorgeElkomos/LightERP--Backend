"""
URL configuration for HR Person module.
"""
from django.urls import path

from . import views

app_name = 'person'

urlpatterns = [
    # Person Type endpoints
    path('types/', views.person_type_list, name='person_type_list'),

    # Employee endpoints
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),

    # Address endpoints
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/<int:pk>/', views.address_detail, name='address_detail'),
    path('persons/<int:person_id>/primary-address/', views.primary_address, name='primary_address'),

    # Competency endpoints
    path('competencies/', views.competency_list, name='competency_list'),
    path('competencies/<int:pk>/', views.competency_detail, name='competency_detail'),

    # Competency Proficiency endpoints
    path('competency-proficiencies/', views.proficiency_list, name='proficiency_list'),
    path('competency-proficiencies/<int:pk>/', views.proficiency_detail, name='proficiency_detail'),

    # Qualification endpoints
    path('qualifications/', views.qualification_list, name='qualification_list'),
    path('qualifications/<int:pk>/', views.qualification_detail, name='qualification_detail'),

    # Contract endpoints
    path('contracts/', views.contract_list, name='contract_list'),
    path('contracts/<int:pk>/', views.contract_detail, name='contract_detail'),

    # Assignment endpoints
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/primary/<int:person_id>/', views.primary_assignment, name='primary_assignment'),

    # Contact endpoints
    path('contacts/', views.contact_list, name='contact_list'),
    path('contacts/<int:pk>/', views.contact_detail, name='contact_detail'),
    path('employees/<int:employee_id>/emergency-contacts/', views.employee_emergency_contacts, name='employee_emergency_contacts'),
]
