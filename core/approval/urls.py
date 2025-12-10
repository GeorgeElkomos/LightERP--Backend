"""
URL Configuration for Approval app.
Handles approval workflows and approval management functionality.
"""
from django.urls import path
from . import views

app_name = 'approval'

urlpatterns = [
    # Workflow Template endpoints
    path('workflow-templates/', views.workflow_template_list, name='workflow-template-list'),
    path('workflow-templates/<int:pk>/', views.workflow_template_detail, name='workflow-template-detail'),
    path('workflow-templates/<int:pk>/stages/', views.workflow_template_stages, name='workflow-template-stages'),
    
    # Stage Template endpoints
    path('stage-templates/', views.stage_template_list, name='stage-template-list'),
    path('stage-templates/<int:pk>/', views.stage_template_detail, name='stage-template-detail'),
    
    # Utility endpoints
    path('content-types/', views.content_types_list, name='content-types-list'),
]

