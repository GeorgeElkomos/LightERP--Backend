"""
Goods Receipt Views - API Endpoints for Receiving Operations

These views follow the PO/PR/Invoice pattern - thin wrappers that handle:
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
from django.db.models import Q, Sum, Count
from django.core.exceptions import ValidationError

from erp_project.response_formatter import success_response, error_response
from erp_project.pagination import auto_paginate

from procurement.receiving.models import GoodsReceipt, GoodsReceiptLine
from procurement.po.models import POHeader
from procurement.receiving.serializers import (
    GoodsReceiptCreateSerializer,
    GoodsReceiptListSerializer,
    GoodsReceiptDetailSerializer
)


# ============================================================================
# GOODS RECEIPT VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def grn_list(request):
    """
    GET: List all GRNs with optional filtering
    POST: Create a new GRN (manual lines or from PO lines)
    
    Query Parameters for GET:
    - po_id: Filter by PO ID
    - supplier_id: Filter by supplier ID
    - grn_type: Filter by type (Catalog, Non-Catalog, Service)
    - date_from: Filter by receipt date (>=)
    - date_to: Filter by receipt date (<=)
    - search: Search in GRN number, notes, supplier name
    """
    if request.method == 'GET':
        # Get queryset
        queryset = GoodsReceipt.objects.all().select_related(
            'po_header', 'supplier', 'received_by', 'created_by'
        ).order_by('-receipt_date', '-created_at')
        
        # Apply filters
        po_filter = request.query_params.get('po_id')
        if po_filter:
            queryset = queryset.filter(po_header_id=po_filter)
        
        supplier_filter = request.query_params.get('supplier_id')
        if supplier_filter:
            queryset = queryset.filter(supplier_id=supplier_filter)
        
        grn_type_filter = request.query_params.get('grn_type')
        if grn_type_filter:
            queryset = queryset.filter(grn_type=grn_type_filter)
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(receipt_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(receipt_date__lte=date_to)
        
        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(grn_number__icontains=search) |
                Q(notes__icontains=search) |
                Q(supplier__business_partner__name__icontains=search) |
                Q(po_header__po_number__icontains=search)
            )
        
        # Serialize
        serializer = GoodsReceiptListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = GoodsReceiptCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                grn = serializer.save()
                response_serializer = GoodsReceiptDetailSerializer(grn)
                return success_response(
                    data=response_serializer.data,
                    message="GRN created successfully",
                    status_code=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return error_response(
                    data={'detail': str(e)},
                    message="Failed to create GRN",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return error_response(
                    data={'detail': str(e)},
                    message="Failed to create GRN",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return error_response(
            data=serializer.errors,
            message="Invalid data provided",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def grn_detail(request, pk):
    """
    GET: Retrieve a specific GRN by ID
    DELETE: Delete a GRN
    """
    grn = get_object_or_404(
        GoodsReceipt.objects.select_related(
            'po_header', 'supplier', 'received_by', 'created_by'
        ).prefetch_related('lines__unit_of_measure', 'lines__po_line_item'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = GoodsReceiptDetailSerializer(grn)
        return success_response(
            data=serializer.data,
            message="GRN retrieved successfully"
        )
    
    elif request.method == 'DELETE':
        # Store PO lines to reverse quantities
        po_lines_to_update = []
        for line in grn.lines.filter(po_line_item__isnull=False):
            po_lines_to_update.append({
                'po_line': line.po_line_item,
                'quantity': line.quantity_received
            })
        
        # Delete GRN
        grn.delete()
        
        # Reverse received quantities on PO lines
        for item in po_lines_to_update:
            po_line = item['po_line']
            po_line.quantity_received -= item['quantity']
            po_line.save()
        
        return success_response(
            data={},
            message="GRN deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )


# ============================================================================
# GRN SUMMARY & REPORTING
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def grn_summary(request, pk):
    """
    GET: Get detailed summary for a specific GRN
    """
    grn = get_object_or_404(GoodsReceipt, pk=pk)
    
    summary = grn.get_receipt_summary()
    po_completion = grn.get_po_completion_status()
    
    return success_response(
        data={
            'grn_number': grn.grn_number,
            'receipt_date': grn.receipt_date,
            'summary': summary,
            'po_completion': po_completion
        },
        message="GRN summary retrieved successfully"
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def po_receiving_status(request, po_id):
    """
    GET: Get receiving status for a specific PO
    """
    po = get_object_or_404(POHeader, pk=po_id)
    
    # Get all GRNs for this PO
    grns = GoodsReceipt.objects.filter(po_header=po).order_by('-receipt_date')
    
    # Calculate totals
    total_received = grns.aggregate(total=Sum('total_amount'))['total'] or 0
    grn_count = grns.count()
    
    # Get line-level status
    lines_status = []
    for po_line in po.line_items.all():
        remaining = po_line.get_remaining_quantity()
        percentage = po_line.get_receiving_percentage()
        
        lines_status.append({
            'line_number': po_line.line_number,
            'item_name': po_line.item_name,
            'quantity_ordered': str(po_line.quantity),
            'quantity_received': str(po_line.quantity_received),
            'quantity_remaining': str(remaining),
            'receipt_percentage': percentage,
            'is_fully_received': po_line.is_fully_received()
        })
    
    # Serialize GRNs
    grn_serializer = GoodsReceiptListSerializer(grns, many=True)
    
    return success_response(
        data={
            'po_number': po.po_number,
            'po_total': str(po.total_amount),
            'total_received': str(total_received),
            'grn_count': grn_count,
            'grns': grn_serializer.data,
            'lines_status': lines_status
        },
        message="PO receiving status retrieved successfully"
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def grn_by_supplier(request):
    """
    GET: Get GRN statistics grouped by supplier
    """
    stats = GoodsReceipt.objects.values(
        'supplier__id', 'supplier__business_partner__name'
    ).annotate(
        grn_count=Count('id'),
        total_amount=Sum('total_amount')
    ).order_by('-total_amount')
    
    return Response(list(stats))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def grn_by_type(request):
    """
    GET: Get GRN statistics grouped by type
    """
    stats = GoodsReceipt.objects.values('grn_type').annotate(
        grn_count=Count('id'),
        total_amount=Sum('total_amount')
    ).order_by('-total_amount')
    
    return Response(list(stats))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def grn_recent(request):
    """
    GET: Get recent GRNs (last 30 days by default)
    Query Parameters:
    - days: Number of days to look back (default: 30)
    """
    from datetime import timedelta
    from django.utils import timezone
    
    days = int(request.query_params.get('days', 30))
    date_from = timezone.now().date() - timedelta(days=days)
    
    grns = GoodsReceipt.objects.filter(
        receipt_date__gte=date_from
    ).select_related(
        'po_header', 'supplier', 'received_by'
    ).order_by('-receipt_date')
    
    serializer = GoodsReceiptListSerializer(grns, many=True)
    return Response(serializer.data)
