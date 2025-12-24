"""
Purchase Order Views - API Endpoints for PO Operations

These views follow the PR/Invoice pattern - thin wrappers that handle:
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
from django.db.models import Q
from django.core.exceptions import ValidationError

from erp_project.response_formatter import success_response, error_response
from erp_project.pagination import auto_paginate
from core.approval.managers import ApprovalManager

from procurement.po.models import POHeader, POLineItem
from procurement.po.serializers import (
    POHeaderCreateSerializer,
    POHeaderListSerializer,
    POHeaderDetailSerializer,
    POSubmitSerializer,
    POConfirmSerializer,
    POCancelSerializer,
    POReceiveSerializer
)


# ============================================================================
# PO HEADER VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def po_list(request):
    """
    GET: List all POs with optional filtering
    POST: Create a new PO (manual or from PR)
    
    Query Parameters for GET:
    - status: Filter by status (DRAFT, SUBMITTED, APPROVED, etc.)
    - po_type: Filter by type (Catalog, Non-Catalog, Service)
    - supplier_id: Filter by supplier ID
    - date_from: Filter by PO date (>=)
    - date_to: Filter by PO date (<=)
    - search: Search in PO number, description, supplier name
    """
    if request.method == 'GET':
        # Get queryset
        queryset = POHeader.objects.all().select_related(
            'supplier_name', 'currency', 'created_by'
        ).order_by('-po_date', '-created_at')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        po_type_filter = request.query_params.get('po_type')
        if po_type_filter:
            queryset = queryset.filter(po_type=po_type_filter)
        
        supplier_filter = request.query_params.get('supplier_id')
        if supplier_filter:
            queryset = queryset.filter(supplier_name_id=supplier_filter)
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(po_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(po_date__lte=date_to)
        
        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(po_number__icontains=search) |
                Q(description__icontains=search) |
                Q(supplier_name__name__icontains=search)
            )
        
        # Serialize
        serializer = POHeaderListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = POHeaderCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                po_header = serializer.save()
                response_serializer = POHeaderDetailSerializer(po_header)
                return success_response(
                    data=response_serializer.data,
                    message="PO created successfully",
                    status_code=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return error_response(
                    data={'detail': str(e)},
                    message="Failed to create PO",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return error_response(
                    data={'detail': str(e)},
                    message="Failed to create PO",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return error_response(
            data=serializer.errors,
            message="Invalid data provided",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def po_detail(request, pk):
    """
    GET: Retrieve a specific PO by ID
    DELETE: Delete a PO (only if in DRAFT status)
    """
    po_header = get_object_or_404(
        POHeader.objects.select_related('supplier_name', 'currency', 'created_by')
        .prefetch_related('line_items__unit_of_measure', 'source_pr_headers'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = POHeaderDetailSerializer(po_header)
        return success_response(
            data=serializer.data,
            message="PO retrieved successfully"
        )
    
    elif request.method == 'DELETE':
        if po_header.status != 'DRAFT':
            return error_response(
                data={'detail': 'Only draft POs can be deleted'},
                message="Cannot delete non-draft PO",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        po_header.delete()
        return success_response(
            data={},
            message="PO deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )


# ============================================================================
# PO WORKFLOW ACTIONS
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def po_submit_for_approval(request, pk):
    """
    POST: Submit a PO for approval
    """
    po_header = get_object_or_404(POHeader, pk=pk)
    
    try:
        po_header.submit_for_approval(submitted_by=request.user)
        return success_response(
            data={'status': po_header.status},
            message="PO submitted for approval successfully"
        )
    except ValidationError as e:
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
def po_approval_action(request, pk):
    """
    POST: Approve or reject a PO
    Expected data: {'action': 'approve'/'reject', 'comment': 'optional comment'}
    """
    po_header = get_object_or_404(POHeader, pk=pk)
    action = request.data.get('action')
    comment = request.data.get('comment', '')
    
    if action not in ['approve', 'reject']:
        return error_response(
            data={'detail': 'Invalid action. Must be "approve" or "reject"'},
            message="Invalid action",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Use centralized approval manager
        ApprovalManager.process_action(po_header, request.user, action, comment)
        
        # Refresh from DB
        po_header.refresh_from_db()
        
        message = f"PO {action}d successfully"
        return success_response(
            data={'status': po_header.status},
            message=message
        )
    except ValidationError as e:
        return error_response(
            data={'detail': str(e)},
            message=f"Failed to {action} PO",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return error_response(
            data={'detail': str(e)},
            message=f"Failed to {action} PO",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def po_pending_approvals(request):
    """
    GET: List POs pending approval for the current user
    """
    # Get pending POs for current user
    pending_pos = ApprovalManager.get_pending_approvals(request.user, POHeader)
    
    # Serialize
    serializer = POHeaderListSerializer(pending_pos, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def po_confirm(request, pk):
    """
    POST: Confirm PO (send to vendor)
    """
    po_header = get_object_or_404(POHeader, pk=pk)
    
    serializer = POConfirmSerializer(data=request.data)
    if serializer.is_valid():
        try:
            po_header.confirm_po(confirmed_by=request.user)
            return success_response(
                data={'status': po_header.status},
                message="PO confirmed successfully"
            )
        except ValidationError as e:
            return error_response(
                data={'detail': str(e)},
                message="Failed to confirm PO",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return error_response(
                data={'detail': str(e)},
                message="Failed to confirm PO",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return error_response(
        data=serializer.errors,
        message="Invalid data provided",
        status_code=status.HTTP_400_BAD_REQUEST
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def po_cancel(request, pk):
    """
    POST: Cancel a PO
    Expected data: {'reason': 'cancellation reason'}
    """
    po_header = get_object_or_404(POHeader, pk=pk)
    
    serializer = POCancelSerializer(data=request.data)
    if serializer.is_valid():
        try:
            po_header.cancel_po(
                reason=serializer.validated_data['reason'],
                cancelled_by=request.user
            )
            return success_response(
                data={'status': po_header.status},
                message="PO cancelled successfully"
            )
        except ValidationError as e:
            return error_response(
                data={'detail': str(e)},
                message="Failed to cancel PO",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return error_response(
                data={'detail': str(e)},
                message="Failed to cancel PO",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return error_response(
        data=serializer.errors,
        message="Invalid data provided",
        status_code=status.HTTP_400_BAD_REQUEST
    )


# ============================================================================
# RECEIVING VIEWS
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def po_record_receipt(request, pk):
    """
    POST: Record goods receipt for a PO line item
    Expected data: {'line_item_id': 123, 'quantity_received': '10.000'}
    """
    po_header = get_object_or_404(POHeader, pk=pk)
    
    # Check PO is in confirmed state
    if po_header.status not in ['CONFIRMED', 'PARTIALLY_RECEIVED']:
        return error_response(
            data={'detail': 'PO must be confirmed before receiving goods'},
            message="Invalid PO status",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = POReceiveSerializer(data=request.data, context={'po_id': pk})
    if serializer.is_valid():
        try:
            line_item = serializer.validated_data['_line_item']
            quantity = serializer.validated_data['quantity_received']
            
            line_item.record_receipt(quantity, received_by=request.user)
            
            # Refresh PO to update status
            po_header.refresh_from_db()
            
            return success_response(
                data={
                    'line_item_id': line_item.id,
                    'quantity_received': float(line_item.quantity_received),
                    'remaining_quantity': float(line_item.get_remaining_quantity()),
                    'po_status': po_header.status
                },
                message="Receipt recorded successfully"
            )
        except ValidationError as e:
            return error_response(
                data={'detail': str(e)},
                message="Failed to record receipt",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return error_response(
                data={'detail': str(e)},
                message="Failed to record receipt",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return error_response(
        data=serializer.errors,
        message="Invalid data provided",
        status_code=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def po_receiving_summary(request, pk):
    """
    GET: Get receiving summary for a PO
    """
    po_header = get_object_or_404(POHeader, pk=pk)
    
    if po_header.status in ['DRAFT', 'SUBMITTED', 'APPROVED']:
        return success_response(
            data={'message': 'PO not yet confirmed for receiving'},
            message="No receiving data available"
        )
    
    summary = po_header.get_receiving_summary()
    
    return success_response(
        data=summary,
        message="Receiving summary retrieved successfully"
    )


# ============================================================================
# REPORTING & ANALYTICS VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def po_by_status(request):
    """
    GET: Get PO count grouped by status
    """
    from django.db.models import Count
    
    status_counts = POHeader.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    return success_response(
        data=list(status_counts),
        message="PO status summary retrieved successfully"
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def po_by_supplier(request):
    """
    GET: Get PO statistics grouped by supplier
    
    Query Parameters:
    - date_from: Filter by PO date (>=)
    - date_to: Filter by PO date (<=)
    """
    from django.db.models import Count, Sum
    
    queryset = POHeader.objects.all()
    
    # Apply date filters
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        queryset = queryset.filter(po_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(po_date__lte=date_to)
    
    supplier_stats = queryset.values(
        'supplier_name__id',
        'supplier_name__name'
    ).annotate(
        po_count=Count('id'),
        total_amount=Sum('total_amount')
    ).order_by('-total_amount')
    
    return success_response(
        data=list(supplier_stats),
        message="Supplier statistics retrieved successfully"
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def po_from_pr(request):
    """
    GET: List POs created from PRs
    
    Query Parameters:
    - pr_number: Filter by source PR number
    """
    queryset = POHeader.objects.filter(
        source_pr_headers__isnull=False
    ).distinct().select_related(
        'supplier_name', 'currency'
    ).prefetch_related('source_pr_headers').order_by('-po_date')
    
    # Filter by PR number if provided
    pr_number = request.query_params.get('pr_number')
    if pr_number:
        queryset = queryset.filter(source_pr_headers__pr_number__icontains=pr_number)
    
    serializer = POHeaderListSerializer(queryset, many=True)
    return Response(serializer.data)
