"""
Purchase Requisition Views - API Endpoints for PR Operations

These views follow the Invoice pattern - thin wrappers that handle:
1. HTTP request/response
2. Authentication/Authorization
3. Pagination
4. Format conversion

Business logic is in the models and serializers.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q

from erp_project.response_formatter import success_response, error_response
from erp_project.pagination import auto_paginate
from core.approval.managers import ApprovalManager

from procurement.PR.models import Catalog_PR, NonCatalog_PR, Service_PR, PR
from procurement.PR.serializers import (
    CatalogPRCreateSerializer, CatalogPRListSerializer, CatalogPRDetailSerializer,
    NonCatalogPRCreateSerializer, NonCatalogPRListSerializer, NonCatalogPRDetailSerializer,
    ServicePRCreateSerializer, ServicePRListSerializer, ServicePRDetailSerializer
)


# ============================================================================
# CATALOG PR VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def catalog_pr_list(request):
    """
    GET: List all Catalog PRs with optional filtering
    POST: Create a new Catalog PR
    """
    if request.method == 'GET':
        # Get queryset
        queryset = Catalog_PR.objects.all().order_by('-pr__created_at')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(pr__status=status_filter)
        
        priority_filter = request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(pr__priority=priority_filter)
        
        department_filter = request.query_params.get('requester_department')
        if department_filter:
            queryset = queryset.filter(pr__requester_department=department_filter)
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(pr__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(pr__date__lte=date_to)
        
        # Serialize
        serializer = CatalogPRListSerializer(queryset, many=True)
        return serializer.data
    
    elif request.method == 'POST':
        serializer = CatalogPRCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                catalog_pr = serializer.save()
                response_serializer = CatalogPRDetailSerializer(catalog_pr)
                return success_response(
                    data=response_serializer.data,
                    message="Catalog PR created successfully",
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return error_response(
                    data={'detail': str(e)},
                    message="Failed to create Catalog PR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return error_response(
            data=serializer.errors,
            message="Invalid data provided",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def catalog_pr_detail(request, pk):
    """
    GET: Retrieve a specific Catalog PR by ID
    DELETE: Delete a Catalog PR (only if in DRAFT status)
    """
    catalog_pr = get_object_or_404(Catalog_PR, pr_id=pk)
    
    if request.method == 'GET':
        serializer = CatalogPRDetailSerializer(catalog_pr)
        return success_response(
            data=serializer.data,
            message="Catalog PR retrieved successfully"
        )
    
    elif request.method == 'DELETE':
        if catalog_pr.pr.status != 'DRAFT':
            return error_response(
                data={'detail': 'Only draft PRs can be deleted'},
                message="Cannot delete non-draft PR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        catalog_pr.delete()
        return success_response(
            data={},
            message="Catalog PR deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def catalog_pr_submit_for_approval(request, pk):
    """
    POST: Submit a Catalog PR for approval
    """
    catalog_pr = get_object_or_404(Catalog_PR, pr_id=pk)
    
    try:
        workflow = catalog_pr.submit_for_approval()
        return success_response(
            data={'workflow_id': workflow.id, 'status': catalog_pr.pr.status},
            message="Catalog PR submitted for approval successfully"
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to submit for approval",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def catalog_pr_approval_action(request, pk):
    """
    POST: Approve or reject a Catalog PR
    Expected data: {'action': 'approve'/'reject', 'comment': 'optional comment'}
    """
    catalog_pr = get_object_or_404(Catalog_PR, pr_id=pk)
    action = request.data.get('action')
    comment = request.data.get('comment', '')
    
    if action not in ['approve', 'reject']:
        return error_response(
            data={'detail': 'Invalid action. Must be "approve" or "reject"'},
            message="Invalid action",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Use process_action on the PR instance
        ApprovalManager.process_action(catalog_pr.pr, request.user, action, comment)
        
        # Refresh from DB
        catalog_pr.refresh_from_db()
        
        message = f"Catalog PR {action}d successfully"
        return success_response(
            data={'status': catalog_pr.pr.status},
            message=message
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message=f"Failed to {action} PR",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def catalog_pr_pending_approvals(request):
    """
    GET: Get list of Catalog PRs pending approval for the current user
    """
    # Get PRs where user has pending approval tasks
    pending_prs = Catalog_PR.objects.filter(
        pr__status='PENDING_APPROVAL'
    ).order_by('-pr__submitted_for_approval_at')
    
    serializer = CatalogPRListSerializer(pending_prs, many=True)
    return serializer.data


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def catalog_pr_cancel(request, pk):
    """
    POST: Cancel a Catalog PR
    Expected data: {'reason': 'cancellation reason'}
    """
    catalog_pr = get_object_or_404(Catalog_PR, pr_id=pk)
    reason = request.data.get('reason', '')
    
    if not reason:
        return error_response(
            data={'detail': 'Cancellation reason is required'},
            message="Reason required",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        catalog_pr.cancel(reason)
        return success_response(
            data={'status': catalog_pr.pr.status},
            message="Catalog PR cancelled successfully"
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to cancel PR",
            status_code=status.HTTP_400_BAD_REQUEST
        )


# ============================================================================
# NON-CATALOG PR VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def noncatalog_pr_list(request):
    """
    GET: List all Non-Catalog PRs with optional filtering
    POST: Create a new Non-Catalog PR
    """
    if request.method == 'GET':
        # Get queryset
        queryset = NonCatalog_PR.objects.all().order_by('-pr__created_at')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(pr__status=status_filter)
        
        priority_filter = request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(pr__priority=priority_filter)
        
        department_filter = request.query_params.get('requester_department')
        if department_filter:
            queryset = queryset.filter(pr__requester_department=department_filter)
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(pr__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(pr__date__lte=date_to)
        
        # Serialize
        serializer = NonCatalogPRListSerializer(queryset, many=True)
        return serializer.data
    
    elif request.method == 'POST':
        serializer = NonCatalogPRCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                noncatalog_pr = serializer.save()
                response_serializer = NonCatalogPRDetailSerializer(noncatalog_pr)
                return success_response(
                    data=response_serializer.data,
                    message="Non-Catalog PR created successfully",
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return error_response(
                    data={'detail': str(e)},
                    message="Failed to create Non-Catalog PR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return error_response(
            data=serializer.errors,
            message="Invalid data provided",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def noncatalog_pr_detail(request, pk):
    """
    GET: Retrieve a specific Non-Catalog PR by ID
    DELETE: Delete a Non-Catalog PR (only if in DRAFT status)
    """
    noncatalog_pr = get_object_or_404(NonCatalog_PR, pr_id=pk)
    
    if request.method == 'GET':
        serializer = NonCatalogPRDetailSerializer(noncatalog_pr)
        return success_response(
            data=serializer.data,
            message="Non-Catalog PR retrieved successfully"
        )
    
    elif request.method == 'DELETE':
        if noncatalog_pr.pr.status != 'DRAFT':
            return error_response(
                data={'detail': 'Only draft PRs can be deleted'},
                message="Cannot delete non-draft PR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        noncatalog_pr.delete()
        return success_response(
            data={},
            message="Non-Catalog PR deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def noncatalog_pr_submit_for_approval(request, pk):
    """
    POST: Submit a Non-Catalog PR for approval
    """
    noncatalog_pr = get_object_or_404(NonCatalog_PR, pr_id=pk)
    
    try:
        workflow = noncatalog_pr.submit_for_approval()
        return success_response(
            data={'workflow_id': workflow.id, 'status': noncatalog_pr.pr.status},
            message="Non-Catalog PR submitted for approval successfully"
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to submit for approval",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def noncatalog_pr_approval_action(request, pk):
    """
    POST: Approve or reject a Non-Catalog PR
    Expected data: {'action': 'approve'/'reject', 'comment': 'optional comment'}
    """
    noncatalog_pr = get_object_or_404(NonCatalog_PR, pr_id=pk)
    action = request.data.get('action')
    comment = request.data.get('comment', '')
    
    if action not in ['approve', 'reject']:
        return error_response(
            data={'detail': 'Invalid action. Must be "approve" or "reject"'},
            message="Invalid action",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Use process_action on the PR instance
        ApprovalManager.process_action(noncatalog_pr.pr, request.user, action, comment)
        
        # Refresh from DB
        noncatalog_pr.refresh_from_db()
        
        message = f"Non-Catalog PR {action}d successfully"
        return success_response(
            data={'status': noncatalog_pr.pr.status},
            message=message
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message=f"Failed to {action} PR",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def noncatalog_pr_pending_approvals(request):
    """
    GET: Get list of Non-Catalog PRs pending approval for the current user
    """
    # Get PRs where user has pending approval tasks
    pending_prs = NonCatalog_PR.objects.filter(
        pr__status='PENDING_APPROVAL'
    ).order_by('-pr__submitted_for_approval_at')
    
    serializer = NonCatalogPRListSerializer(pending_prs, many=True)
    return serializer.data


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def noncatalog_pr_cancel(request, pk):
    """
    POST: Cancel a Non-Catalog PR
    Expected data: {'reason': 'cancellation reason'}
    """
    noncatalog_pr = get_object_or_404(NonCatalog_PR, pr_id=pk)
    reason = request.data.get('reason', '')
    
    if not reason:
        return error_response(
            data={'detail': 'Cancellation reason is required'},
            message="Reason required",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        noncatalog_pr.cancel(reason)
        return success_response(
            data={'status': noncatalog_pr.pr.status},
            message="Non-Catalog PR cancelled successfully"
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to cancel PR",
            status_code=status.HTTP_400_BAD_REQUEST
        )


# ============================================================================
# SERVICE PR VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def service_pr_list(request):
    """
    GET: List all Service PRs with optional filtering
    POST: Create a new Service PR
    """
    if request.method == 'GET':
        # Get queryset
        queryset = Service_PR.objects.all().order_by('-pr__created_at')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(pr__status=status_filter)
        
        priority_filter = request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(pr__priority=priority_filter)
        
        department_filter = request.query_params.get('requester_department')
        if department_filter:
            queryset = queryset.filter(pr__requester_department=department_filter)
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(pr__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(pr__date__lte=date_to)
        
        # Serialize
        serializer = ServicePRListSerializer(queryset, many=True)
        return serializer.data
    
    elif request.method == 'POST':
        serializer = ServicePRCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                service_pr = serializer.save()
                response_serializer = ServicePRDetailSerializer(service_pr)
                return success_response(
                    data=response_serializer.data,
                    message="Service PR created successfully",
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return error_response(
                    data={'detail': str(e)},
                    message="Failed to create Service PR",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return error_response(
            data=serializer.errors,
            message="Invalid data provided",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def service_pr_detail(request, pk):
    """
    GET: Retrieve a specific Service PR by ID
    DELETE: Delete a Service PR (only if in DRAFT status)
    """
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    
    if request.method == 'GET':
        serializer = ServicePRDetailSerializer(service_pr)
        return success_response(
            data=serializer.data,
            message="Service PR retrieved successfully"
        )
    
    elif request.method == 'DELETE':
        if service_pr.pr.status != 'DRAFT':
            return error_response(
                data={'detail': 'Only draft PRs can be deleted'},
                message="Cannot delete non-draft PR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        service_pr.delete()
        return success_response(
            data={},
            message="Service PR deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def service_pr_submit_for_approval(request, pk):
    """
    POST: Submit a Service PR for approval
    """
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    
    try:
        workflow = service_pr.submit_for_approval()
        return success_response(
            data={'workflow_id': workflow.id, 'status': service_pr.pr.status},
            message="Service PR submitted for approval successfully"
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to submit for approval",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def service_pr_approval_action(request, pk):
    """
    POST: Approve or reject a Service PR
    Expected data: {'action': 'approve'/'reject', 'comment': 'optional comment'}
    """
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    action = request.data.get('action')
    comment = request.data.get('comment', '')
    
    if action not in ['approve', 'reject']:
        return error_response(
            data={'detail': 'Invalid action. Must be "approve" or "reject"'},
            message="Invalid action",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Use process_action on the PR instance
        ApprovalManager.process_action(service_pr.pr, request.user, action, comment)
        
        # Refresh from DB
        service_pr.refresh_from_db()
        
        message = f"Service PR {action}d successfully"
        return success_response(
            data={'status': service_pr.pr.status},
            message=message
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message=f"Failed to {action} PR",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def service_pr_pending_approvals(request):
    """
    GET: Get list of Service PRs pending approval for the current user
    """
    # Get PRs where user has pending approval tasks
    pending_prs = Service_PR.objects.filter(
        pr__status='PENDING_APPROVAL'
    ).order_by('-pr__submitted_for_approval_at')
    
    serializer = ServicePRListSerializer(pending_prs, many=True)
    return serializer.data


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def service_pr_cancel(request, pk):
    """
    POST: Cancel a Service PR
    Expected data: {'reason': 'cancellation reason'}
    """
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    reason = request.data.get('reason', '')
    
    if not reason:
        return error_response(
            data={'detail': 'Cancellation reason is required'},
            message="Reason required",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        service_pr.cancel(reason)
        return success_response(
            data={'status': service_pr.pr.status},
            message="Service PR cancelled successfully"
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to cancel PR",
            status_code=status.HTTP_400_BAD_REQUEST
        )
