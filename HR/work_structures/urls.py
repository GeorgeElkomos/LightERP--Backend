"""
URL configuration for HR Work Structures module.
"""
from django.urls import path
from HR.work_structures import views

app_name = 'work_structures'

urlpatterns = [
    # Location endpoints
    path('locations/', views.location_list, name='location_list'),
    path('locations/<int:pk>/', views.location_detail, name='location_detail'),

    # Organization endpoints
    path('organizations/', views.organization_list, name='organization_list'),
    path('organizations/<int:pk>/', views.organization_detail, name='organization_detail'),
    path('organizations/<int:pk>/hierarchy/', views.organization_hierarchy, name='organization_hierarchy'),

    # Grade endpoints
    path('grades/', views.grade_list, name='grade_list'),
    path('grades/<int:pk>/', views.grade_detail, name='grade_detail'),
    path('grade-rate-types/', views.grade_rate_type_list, name='grade_rate_type_list'),
    path('grade-rate-types/<int:pk>/', views.grade_rate_type_detail, name='grade_rate_type_detail'),
    path('grade-rates/', views.grade_rate_list, name='grade_rate_list'),
    path('grade-rates/<int:pk>/', views.grade_rate_detail, name='grade_rate_detail'),

    # Job endpoints
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
    path('jobs/<int:pk>/versions/', views.job_versions, name='job_versions'),

    # Position endpoints
    path('positions/', views.position_list, name='position_list'),
    path('positions/<int:pk>/', views.position_detail, name='position_detail'),
    path('positions/<int:pk>/versions/', views.position_versions, name='position_versions'),
]
