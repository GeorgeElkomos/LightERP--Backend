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
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q, F
from django.db import models

from erp_project.response_formatter import success_response, error_response
from erp_project.pagination import auto_paginate
from core.approval.managers import ApprovalManager

from procurement.PR.models import Catalog_PR, NonCatalog_PR, Service_PR, PR, PRItem, PRAttachment
from procurement.PR.serializers import (
    CatalogPRCreateSerializer, CatalogPRListSerializer, CatalogPRDetailSerializer,
    NonCatalogPRCreateSerializer, NonCatalogPRListSerializer, NonCatalogPRDetailSerializer,
    ServicePRCreateSerializer, ServicePRListSerializer, ServicePRDetailSerializer,
    PRItemSerializer,
    PRAttachmentSerializer,
    PRAttachmentListSerializer
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
        return Response(serializer.data)
    
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
    from django.core.exceptions import ValidationError
    catalog_pr = get_object_or_404(Catalog_PR, pr_id=pk)
    
    try:
        workflow = catalog_pr.submit_for_approval()
        return success_response(
            data={'workflow_id': workflow.id, 'status': catalog_pr.pr.status},
            message="Catalog PR submitted for approval successfully"
        )
    except (ValidationError, ValueError) as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to submit for approval",
            status_code=status.HTTP_400_BAD_REQUEST
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
        # Use process_action on the catalog PR instance (child model)
        ApprovalManager.process_action(catalog_pr, request.user, action, comment)
        
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
    return Response(serializer.data)


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
        return Response(serializer.data)
    
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
    from django.core.exceptions import ValidationError
    noncatalog_pr = get_object_or_404(NonCatalog_PR, pr_id=pk)
    
    try:
        workflow = noncatalog_pr.submit_for_approval()
        return success_response(
            data={'workflow_id': workflow.id, 'status': noncatalog_pr.pr.status},
            message="Non-Catalog PR submitted for approval successfully"
        )
    except (ValidationError, ValueError) as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to submit for approval",
            status_code=status.HTTP_400_BAD_REQUEST
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
        # Use process_action on the non-catalog PR instance (child model)
        ApprovalManager.process_action(noncatalog_pr, request.user, action, comment)
        
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
    return Response(serializer.data)


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
        return Response(serializer.data)
    
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
    from django.core.exceptions import ValidationError
    service_pr = get_object_or_404(Service_PR, pr_id=pk)
    
    try:
        workflow = service_pr.submit_for_approval()
        return success_response(
            data={'workflow_id': workflow.id, 'status': service_pr.pr.status},
            message="Service PR submitted for approval successfully"
        )
    except (ValidationError, ValueError) as e:
        return error_response(
            data={'detail': str(e)},
            message="Failed to submit for approval",
            status_code=status.HTTP_400_BAD_REQUEST
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
        # Use process_action on the service PR instance (child model)
        ApprovalManager.process_action(service_pr, request.user, action, comment)
        
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
    return Response(serializer.data)


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


# ============================================================================
# PR-TO-PO CONVERSION VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def approved_prs_for_conversion(request):
    """
    GET: Get all approved PRs available for PO conversion, filtered by type
    Query params:
        - pr_type: 'Catalog', 'Non-Catalog', or 'Service' (required)
        - has_unconverted_items: true/false (optional, default: true)
    
    Returns PRs with their available items for PO creation
    """
    pr_type = request.query_params.get('pr_type')
    
    # Validate pr_type
    if pr_type not in ['Catalog', 'Non-Catalog', 'Service']:
        return error_response(
            data={'detail': 'Invalid pr_type. Must be "Catalog", "Non-Catalog", or "Service"'},
            message="Invalid PR type",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Get approved PRs of specified type
    queryset = PR.objects.filter(
        status='APPROVED',
        type_of_pr=pr_type
    )
    
    # Optional: Filter only PRs with unconverted items
    has_unconverted = request.query_params.get('has_unconverted_items', 'true').lower() == 'true'
    if has_unconverted:
        queryset = queryset.filter(
            items__converted_to_po=False
        ).distinct()
    
    queryset = queryset.order_by('-approved_at')
    
    # Build response with PR details and item counts
    response_data = []
    for pr in queryset:
        unconverted_items = pr.items.filter(converted_to_po=False).count()
        partially_converted = pr.items.filter(
            converted_to_po=False,
            quantity_converted__gt=0
        ).count()
        
        response_data.append({
            'pr_id': pr.id,
            'pr_number': pr.pr_number,
            'pr_type': pr.type_of_pr,
            'date': pr.date,
            'required_date': pr.required_date,
            'requester_name': pr.requester_name,
            'requester_department': pr.requester_department,
            'total': float(pr.total),
            'approved_at': pr.approved_at,
            'total_items': pr.items.count(),
            'unconverted_items': unconverted_items,
            'partially_converted_items': partially_converted
        })
    
    return response_data


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pr_available_items(request, pk):
    """
    GET: Get available items from a specific PR for PO conversion
    Only returns items that:
    - Belong to an approved PR
    - Have remaining quantity to convert (not fully converted)
    
    Response includes remaining quantities for each item
    """
    pr = get_object_or_404(PR, id=pk)
    
    # Validate PR is approved
    if pr.status != 'APPROVED':
        return error_response(
            data={'detail': 'Only approved PRs can be converted to PO'},
            message="PR not approved",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Get items with remaining quantity
    available_items = pr.items.filter(
        Q(converted_to_po=False) | 
        Q(quantity_converted__lt=models.F('quantity'))
    ).select_related('catalog_item', 'unit_of_measure')
    
    serializer = PRItemSerializer(available_items, many=True)
    
    return success_response(
        data={
            'pr_id': pr.id,
            'pr_number': pr.pr_number,
            'pr_type': pr.type_of_pr,
            'items': serializer.data
        },
        message="Available items retrieved successfully"
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pr_items_by_type(request):
    """
    GET: Get all available PR items filtered by type for PO creation
    Query params:
        - pr_type: 'Catalog', 'Non-Catalog', or 'Service' (required)
        - pr_ids: Comma-separated list of PR IDs (optional)
    
    Returns all available items from approved PRs matching the type
    """
    pr_type = request.query_params.get('pr_type')
    
    # Validate pr_type
    if pr_type not in ['Catalog', 'Non-Catalog', 'Service']:
        return error_response(
            data={'detail': 'Invalid pr_type. Must be "Catalog", "Non-Catalog", or "Service"'},
            message="Invalid PR type",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Base query: approved PRs of specified type
    queryset = PRItem.objects.filter(
        pr__status='APPROVED',
        pr__type_of_pr=pr_type
    ).filter(
        # Items with remaining quantity
        Q(converted_to_po=False) | 
        Q(quantity_converted__lt=models.F('quantity'))
    ).select_related('pr', 'catalog_item', 'unit_of_measure')
    
    # Optional: filter by specific PR IDs
    pr_ids = request.query_params.get('pr_ids')
    if pr_ids:
        try:
            pr_id_list = [int(id.strip()) for id in pr_ids.split(',')]
            queryset = queryset.filter(pr_id__in=pr_id_list)
        except ValueError:
            return error_response(
                data={'detail': 'Invalid pr_ids format. Must be comma-separated integers'},
                message="Invalid format",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    serializer = PRItemSerializer(queryset, many=True)
    
    return success_response(
        data={
            'pr_type': pr_type,
            'total_items': queryset.count(),
            'items': serializer.data
        },
        message=f"Available {pr_type} items retrieved successfully"
    )


# ============================================================================
# PR ATTACHMENT VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def pr_attachment_list(request, pr_id):
    """
    GET: List all attachments for a PR
    POST: Upload a new attachment to a PR
    
    POST Request Body:
    {
        "file_name": "quote.pdf",
        "file_type": "application/pdf",
        "file_data_base64": "base64_encoded_file_data...",
        "description": "Vendor quote"
    }
    """
    # Verify PR exists
    pr = get_object_or_404(PR, id=pr_id)
    
    if request.method == 'GET':
        # List attachments (without file data for efficiency)
        attachments = pr.attachments.all()
        serializer = PRAttachmentListSerializer(attachments, many=True)
        return success_response(
            data=serializer.data,
            message=f"Retrieved {len(attachments)} attachment(s)"
        )
    
    elif request.method == 'POST':
        # Upload new attachment
        serializer = PRAttachmentSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save(pr=pr)
            return success_response(
                data=serializer.data,
                message="Attachment uploaded successfully",
                status_code=status.HTTP_201_CREATED
            )
        
        return error_response(
            message="Failed to upload attachment",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def pr_attachment_detail(request, attachment_id):
    """
    GET: Download/retrieve a specific attachment
    DELETE: Delete an attachment
    """
    attachment = get_object_or_404(PRAttachment, attachment_id=attachment_id)
    
    if request.method == 'GET':
        # Return attachment with file data encoded as base64
        import base64
        file_data_base64 = base64.b64encode(attachment.file_data).decode('utf-8')
        
        data = {
            'attachment_id': attachment.attachment_id,
            'file_name': attachment.file_name,
            'file_type': attachment.file_type,
            'file_size': attachment.file_size,
            'file_size_display': attachment.get_file_size_display(),
            'upload_date': attachment.upload_date,
            'uploaded_by': attachment.uploaded_by,
            'description': attachment.description,
            'file_data_base64': file_data_base64
        }
        
        return success_response(
            data=data,
            message="Attachment retrieved successfully"
        )
    
    elif request.method == 'DELETE':
        # Delete attachment
        pr_number = attachment.pr.pr_number
        file_name = attachment.file_name
        attachment.delete()
        
        return success_response(
            message=f"Attachment '{file_name}' deleted from PR {pr_number}"
        )

