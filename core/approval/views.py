"""
API Views for Approval Workflow models.
Provides REST API endpoints for workflow templates and stage templates.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from erp_project.pagination import auto_paginate

from .models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
)
from .serializers import (
    ApprovalWorkflowTemplateSerializer,
    ApprovalWorkflowTemplateListSerializer,
    ApprovalWorkflowTemplateCreateUpdateSerializer,
    ApprovalWorkflowStageTemplateSerializer,
    ApprovalWorkflowStageTemplateListSerializer,
    ContentTypeSerializer,
)


# ============================================================================
# ApprovalWorkflowTemplate API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def workflow_template_list(request):
    """
    List all workflow templates or create a new template.
    
    GET /workflow-templates/
    - Returns list of all workflow templates
    - Query params:
        - is_active: Filter by active status (true/false)
        - content_type: Filter by content type ID
        - code: Filter by template code (exact match)
    
    POST /workflow-templates/
    - Create a new workflow template
    - Request body: ApprovalWorkflowTemplateCreateUpdateSerializer fields
    - Can include nested stages array
    """
    if request.method == 'GET':
        templates = ApprovalWorkflowTemplate.objects.all()
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            templates = templates.filter(is_active=is_active_bool)
        
        content_type_id = request.query_params.get('content_type')
        if content_type_id:
            templates = templates.filter(content_type_id=content_type_id)
        
        code = request.query_params.get('code')
        if code:
            templates = templates.filter(code=code)
        
        serializer = ApprovalWorkflowTemplateListSerializer(templates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = ApprovalWorkflowTemplateCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                template = serializer.save()
                # Return full details
                result_serializer = ApprovalWorkflowTemplateSerializer(template)
                return Response(result_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def workflow_template_detail(request, pk):
    """
    Retrieve, update, or delete a specific workflow template.
    
    GET /workflow-templates/{id}/
    - Returns detailed information about a template including stages
    
    PUT/PATCH /workflow-templates/{id}/
    - Update a workflow template
    - Request body: ApprovalWorkflowTemplateCreateUpdateSerializer fields
    - Note: Stages should be updated via separate stage endpoints
    
    DELETE /workflow-templates/{id}/
    - Delete a workflow template (if no active instances)
    """
    template = get_object_or_404(ApprovalWorkflowTemplate, pk=pk)
    
    if request.method == 'GET':
        serializer = ApprovalWorkflowTemplateSerializer(template)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = ApprovalWorkflowTemplateCreateUpdateSerializer(
            template, 
            data=request.data, 
            partial=partial
        )
        if serializer.is_valid():
            try:
                template = serializer.save()
                result_serializer = ApprovalWorkflowTemplateSerializer(template)
                return Response(result_serializer.data)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            # Check if template has active instances
            active_instances = template.instances.filter(
                status__in=['pending', 'in_progress']
            ).count()
            
            if active_instances > 0:
                return Response(
                    {
                        'error': f'Cannot delete template with {active_instances} active workflow instance(s). '
                                'Please cancel or complete all workflows first.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            template_name = template.name
            template.delete()
            return Response(
                {'message': f'Workflow template "{template_name}" deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f'Error deleting template: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@auto_paginate
def workflow_template_stages(request, pk):
    """
    Get all stages for a specific workflow template.
    
    GET /workflow-templates/{id}/stages/
    - Returns list of all stages for the template, ordered by order_index
    """
    template = get_object_or_404(ApprovalWorkflowTemplate, pk=pk)
    stages = template.stages.all().order_by('order_index')
    serializer = ApprovalWorkflowStageTemplateSerializer(stages, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# ApprovalWorkflowStageTemplate API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def stage_template_list(request):
    """
    List all stage templates or create a new stage template.
    
    GET /stage-templates/
    - Returns list of all stage templates
    - Query params:
        - workflow_template: Filter by workflow template ID
        - decision_policy: Filter by decision policy (ALL, ANY, QUORUM)
        - allow_delegate: Filter by delegation allowance (true/false)
    
    POST /stage-templates/
    - Create a new stage template
    - Request body: ApprovalWorkflowStageTemplateSerializer fields
    """
    if request.method == 'GET':
        stages = ApprovalWorkflowStageTemplate.objects.all()
        
        # Apply filters
        workflow_template_id = request.query_params.get('workflow_template')
        if workflow_template_id:
            stages = stages.filter(workflow_template_id=workflow_template_id)
        
        decision_policy = request.query_params.get('decision_policy')
        if decision_policy:
            stages = stages.filter(decision_policy=decision_policy.upper())
        
        allow_delegate = request.query_params.get('allow_delegate')
        if allow_delegate is not None:
            allow_delegate_bool = allow_delegate.lower() == 'true'
            stages = stages.filter(allow_delegate=allow_delegate_bool)
        
        serializer = ApprovalWorkflowStageTemplateListSerializer(stages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = ApprovalWorkflowStageTemplateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Validate that workflow_template exists
                workflow_template_id = request.data.get('workflow_template')
                if not workflow_template_id:
                    return Response(
                        {'error': 'workflow_template is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check for duplicate order_index
                order_index = request.data.get('order_index')
                if ApprovalWorkflowStageTemplate.objects.filter(
                    workflow_template_id=workflow_template_id,
                    order_index=order_index
                ).exists():
                    return Response(
                        {
                            'error': f'Stage with order_index {order_index} already exists '
                                    'for this workflow template'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                stage = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def stage_template_detail(request, pk):
    """
    Retrieve, update, or delete a specific stage template.
    
    GET /stage-templates/{id}/
    - Returns detailed information about a stage template
    
    PUT/PATCH /stage-templates/{id}/
    - Update a stage template
    - Request body: ApprovalWorkflowStageTemplateSerializer fields
    
    DELETE /stage-templates/{id}/
    - Delete a stage template (if no active instances using it)
    """
    stage = get_object_or_404(ApprovalWorkflowStageTemplate, pk=pk)
    
    if request.method == 'GET':
        serializer = ApprovalWorkflowStageTemplateSerializer(stage)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = ApprovalWorkflowStageTemplateSerializer(
            stage, 
            data=request.data, 
            partial=partial
        )
        if serializer.is_valid():
            try:
                # If updating order_index, check for conflicts
                if 'order_index' in request.data:
                    new_order = request.data['order_index']
                    conflict = ApprovalWorkflowStageTemplate.objects.filter(
                        workflow_template=stage.workflow_template,
                        order_index=new_order
                    ).exclude(pk=stage.pk).exists()
                    
                    if conflict:
                        return Response(
                            {
                                'error': f'Stage with order_index {new_order} already exists '
                                        'for this workflow template'
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                stage = serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            # Check if stage template is used in active instances
            active_instances = stage.stage_instances.filter(
                status__in=['active', 'pending']
            ).count()
            
            if active_instances > 0:
                return Response(
                    {
                        'error': f'Cannot delete stage template with {active_instances} active '
                                'stage instance(s). Please complete or cancel related workflows first.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            stage_name = stage.name
            stage.delete()
            return Response(
                {'message': f'Stage template "{stage_name}" deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f'Error deleting stage: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================================================
# Utility Views
# ============================================================================

@api_view(['GET'])
@auto_paginate
def content_types_list(request):
    """
    List content types for models that support approval workflows.
    
    GET /content-types/
    - Returns content types for all models that use ApprovableMixin
    - Excludes test models from the approval app
    - Currently: Invoice and Payment models
    - Useful for dropdown in UI when creating workflow templates
    """
    from django.apps import apps
    from .mixins import ApprovableMixin
    
    # Find all models that inherit from ApprovableMixin
    approvable_models = []
    for model in apps.get_models():
        # Check if model uses ApprovableMixin (but is not abstract)
        # Exclude test models from the approval app itself
        if (issubclass(model, ApprovableMixin) and 
            not model._meta.abstract and
            model._meta.app_label != 'approval'):
            approvable_models.append(model)
    
    # Get content types for these models
    content_types = []
    for model in approvable_models:
        ct = ContentType.objects.get_for_model(model)
        content_types.append(ct)
    
    # Sort by app_label and model name
    content_types.sort(key=lambda ct: (ct.app_label, ct.model))
    
    serializer = ContentTypeSerializer(content_types, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

