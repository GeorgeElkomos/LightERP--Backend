"""
Budget Control API Views
Provides REST API endpoints for Budget Management with comprehensive CRUD operations.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, F
from django.db import transaction
from decimal import Decimal
from datetime import date

from erp_project.pagination import auto_paginate
from erp_project.response_formatter import success_response, error_response

from .models import BudgetHeader, BudgetSegmentValue, BudgetAmount
from .serializers import (
    BudgetHeaderListSerializer,
    BudgetHeaderDetailSerializer,
    BudgetHeaderCreateSerializer,
    BudgetHeaderUpdateSerializer,
    BudgetSegmentValueListSerializer,
    BudgetSegmentValueCreateSerializer,
    BudgetAmountListSerializer,
    BudgetAmountCreateSerializer,
    BudgetActivateSerializer,
    BudgetCheckSerializer,
    BudgetCheckResponseSerializer,
    BudgetAmountImportSerializer,
)
from Finance.GL.models import XX_Segment


# ============================================================================
# BUDGET HEADER API VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def budget_header_list(request):
    """
    List all budget headers or create a new budget header.
    
    GET /budget-headers/
    - Returns list of all budget headers with summary data
    - Query params:
        - status: Filter by status (DRAFT/ACTIVE/CLOSED)
        - is_active: Filter by active flag (true/false)
        - budget_code: Filter by code (contains)
        - budget_name: Filter by name (contains)
        - start_date: Filter by start date (gte)
        - end_date: Filter by end date (lte)
        - currency: Filter by currency ID
        - search: Search across code and name
    
    POST /budget-headers/
    - Create a new budget header with nested segment values and amounts
    - Request body: BudgetHeaderCreateSerializer fields
    """
    if request.method == 'GET':
        budgets = BudgetHeader.objects.select_related('currency').all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            budgets = budgets.filter(status=status_filter.upper())
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            budgets = budgets.filter(is_active=is_active_bool)
        
        budget_code = request.query_params.get('budget_code')
        if budget_code:
            budgets = budgets.filter(budget_code__icontains=budget_code)
        
        budget_name = request.query_params.get('budget_name')
        if budget_name:
            budgets = budgets.filter(budget_name__icontains=budget_name)
        
        start_date = request.query_params.get('start_date')
        if start_date:
            budgets = budgets.filter(start_date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            budgets = budgets.filter(end_date__lte=end_date)
        
        currency_id = request.query_params.get('currency')
        if currency_id:
            budgets = budgets.filter(currency_id=currency_id)
        
        # General search
        search = request.query_params.get('search')
        if search:
            budgets = budgets.filter(
                Q(budget_code__icontains=search) |
                Q(budget_name__icontains=search) |
                Q(description__icontains=search)
            )
        
        serializer = BudgetHeaderListSerializer(budgets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = BudgetHeaderCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                budget = serializer.save()
                response_serializer = BudgetHeaderDetailSerializer(budget)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def budget_header_active_list(request):
    """
    List all active budget headers.
    
    GET /budget-headers/active/
    - Returns only budgets with status=ACTIVE and is_active=True
    - Same query params as budget_header_list
    """
    budgets = BudgetHeader.objects.filter(
        status='ACTIVE',
        is_active=True
    ).select_related('currency')
    
    # Apply same filters as budget_header_list
    budget_code = request.query_params.get('budget_code')
    if budget_code:
        budgets = budgets.filter(budget_code__icontains=budget_code)
    
    search = request.query_params.get('search')
    if search:
        budgets = budgets.filter(
            Q(budget_code__icontains=search) |
            Q(budget_name__icontains=search)
        )
    
    serializer = BudgetHeaderListSerializer(budgets, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def budget_header_detail(request, pk):
    """
    Retrieve, update, or delete a budget header.
    
    GET /budget-headers/{id}/
    - Returns detailed budget header with nested segments and amounts
    
    PUT/PATCH /budget-headers/{id}/
    - Update budget header fields (not segments/amounts)
    - Only DRAFT budgets can be fully updated
    
    DELETE /budget-headers/{id}/
    - Delete budget header (only if DRAFT and no transactions)
    """
    budget = get_object_or_404(BudgetHeader, pk=pk)
    
    if request.method == 'GET':
        serializer = BudgetHeaderDetailSerializer(budget)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        # Check if budget can be updated
        if budget.status not in ['DRAFT', 'ACTIVE']:
            return Response(
                {'error': f'Cannot update budget with status {budget.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        partial = request.method == 'PATCH'
        serializer = BudgetHeaderUpdateSerializer(
            budget,
            data=request.data,
            partial=partial
        )
        
        if serializer.is_valid():
            try:
                serializer.save()
                response_serializer = BudgetHeaderDetailSerializer(budget)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Check if budget can be deleted
        can_delete, error = budget.can_delete()
        if not can_delete:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        budget.delete()
        return Response(
            {'message': f'Budget {budget.budget_code} deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def budget_header_activate(request, pk):
    """
    Activate a budget header.
    
    POST /budget-headers/{id}/activate/
    - Changes status from DRAFT to ACTIVE
    - Validates all requirements are met
    - Request body: { "activated_by": "username" }
    """
    budget = get_object_or_404(BudgetHeader, pk=pk)
    
    serializer = BudgetActivateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    activated_by = serializer.validated_data.get('activated_by', 'system')
    
    try:
        budget.activate(activated_by)
        response_serializer = BudgetHeaderDetailSerializer(budget)
        return Response(
            {
                'message': f'Budget {budget.budget_code} activated successfully',
                'budget': response_serializer.data
            },
            status=status.HTTP_200_OK
        )
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def budget_header_close(request, pk):
    """
    Close a budget header.
    
    POST /budget-headers/{id}/close/
    - Changes status from ACTIVE to CLOSED
    - Request body: { "closed_by": "username" } (optional)
    """
    budget = get_object_or_404(BudgetHeader, pk=pk)
    
    closed_by = request.data.get('closed_by', 'system')
    
    try:
        budget.close(closed_by)
        response_serializer = BudgetHeaderDetailSerializer(budget)
        return Response(
            {
                'message': f'Budget {budget.budget_code} closed successfully',
                'budget': response_serializer.data
            },
            status=status.HTTP_200_OK
        )
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def budget_header_deactivate(request, pk):
    """
    Deactivate a budget header.
    
    POST /budget-headers/{id}/deactivate/
    - Sets is_active to False without changing status
    """
    budget = get_object_or_404(BudgetHeader, pk=pk)
    
    try:
        budget.deactivate()
        response_serializer = BudgetHeaderDetailSerializer(budget)
        return Response(
            {
                'message': f'Budget {budget.budget_code} deactivated successfully',
                'budget': response_serializer.data
            },
            status=status.HTTP_200_OK
        )
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def budget_check(request):
    """
    Check budget availability for a transaction.
    
    POST /budget-check/
    - Validates budget availability before PR/PO/Invoice approval
    - Request body:
        {
            "segment_ids": [101, 202, 303],
            "transaction_amount": "5000.00",
            "transaction_date": "2026-01-22"
        }
    - Response:
        {
            "allowed": true/false,
            "control_level": "ADVISORY",
            "message": "...",
            "violations": [...]
        }
    """
    serializer = BudgetCheckSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    segment_ids = serializer.validated_data['segment_ids']
    transaction_amount = serializer.validated_data['transaction_amount']
    transaction_date = serializer.validated_data.get('transaction_date', date.today())
    
    # Get segment objects
    segments = XX_Segment.objects.filter(id__in=segment_ids)
    if segments.count() != len(segment_ids):
        return Response(
            {'error': 'One or more segment IDs not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Find active budget that covers this date
    active_budgets = BudgetHeader.objects.filter(
        status='ACTIVE',
        is_active=True,
        start_date__lte=transaction_date,
        end_date__gte=transaction_date
    )
    
    if not active_budgets.exists():
        return Response(
            {
                'allowed': True,
                'control_level': 'NONE',
                'message': 'No active budget found for this date - transaction allowed',
                'violations': []
            },
            status=status.HTTP_200_OK
        )
    
    # Check against each active budget (usually just one)
    results = []
    for budget in active_budgets:
        result = budget.check_budget_for_segments(
            list(segments),
            transaction_amount,
            transaction_date
        )
        results.append(result)
    
    # Return the strictest result
    strictest_result = max(results, key=lambda r: {
        'ABSOLUTE': 4, 'ADVISORY': 3, 'TRACK_ONLY': 2, 'NONE': 1
    }.get(r['control_level'], 0))
    
    response_serializer = BudgetCheckResponseSerializer(data=strictest_result)
    if response_serializer.is_valid():
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    return Response(strictest_result, status=status.HTTP_200_OK)


# ============================================================================
# BUDGET SEGMENT VALUE API VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def budget_segment_value_list(request, budget_id):
    """
    List all segment values for a budget or add a new one.
    
    GET /budget-headers/{budget_id}/segments/
    - Returns all segment values for this budget
    - Query params:
        - is_active: Filter by active status
        - control_level: Filter by control level
    
    POST /budget-headers/{budget_id}/segments/
    - Add a new segment value to the budget
    - Request body: { "segment_value_id": 101, "control_level": "ADVISORY" }
    """
    budget = get_object_or_404(BudgetHeader, pk=budget_id)
    
    if request.method == 'GET':
        segments = budget.budget_segment_values.select_related(
            'segment_value',
            'segment_value__segment_type'
        ).all()
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            segments = segments.filter(is_active=is_active_bool)
        
        control_level = request.query_params.get('control_level')
        if control_level:
            segments = segments.filter(control_level=control_level.upper())
        
        serializer = BudgetSegmentValueListSerializer(segments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        if budget.status not in ['DRAFT']:
            return Response(
                {'error': 'Can only add segments to DRAFT budgets'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = BudgetSegmentValueCreateSerializer(data=request.data)
        if serializer.is_valid():
            segment_value_id = serializer.validated_data['segment_value_id']
            
            # Check if segment already exists in this budget
            if budget.budget_segment_values.filter(segment_value_id=segment_value_id).exists():
                return Response(
                    {'error': 'Segment value already exists in this budget'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                segment = BudgetSegmentValue.objects.create(
                    budget_header=budget,
                    segment_value_id=segment_value_id,
                    control_level=serializer.validated_data.get('control_level'),
                    notes=serializer.validated_data.get('notes', '')
                )
                response_serializer = BudgetSegmentValueListSerializer(segment)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def budget_segment_value_detail(request, budget_id, segment_id):
    """
    Retrieve, update, or delete a budget segment value.
    
    GET /budget-headers/{budget_id}/segments/{segment_id}/
    PUT/PATCH /budget-headers/{budget_id}/segments/{segment_id}/
    DELETE /budget-headers/{budget_id}/segments/{segment_id}/
    """
    budget = get_object_or_404(BudgetHeader, pk=budget_id)
    segment = get_object_or_404(
        BudgetSegmentValue,
        pk=segment_id,
        budget_header=budget
    )
    
    if request.method == 'GET':
        serializer = BudgetSegmentValueListSerializer(segment)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        if budget.status not in ['DRAFT', 'ACTIVE']:
            return Response(
                {'error': 'Cannot update segments in CLOSED budget'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Only allow updating control_level and notes
        allowed_fields = ['control_level', 'notes', 'is_active']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        for field, value in update_data.items():
            setattr(segment, field, value)
        
        try:
            segment.save()
            response_serializer = BudgetSegmentValueListSerializer(segment)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    elif request.method == 'DELETE':
        if budget.status != 'DRAFT':
            return Response(
                {'error': 'Can only delete segments from DRAFT budgets'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if segment has budget amounts
        if hasattr(segment, 'budget_amount'):
            return Response(
                {'error': 'Cannot delete segment with budget amount. Delete amount first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        segment.delete()
        return Response(
            {'message': 'Segment value deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


# ============================================================================
# BUDGET AMOUNT API VIEWS
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@auto_paginate
def budget_amount_list(request, budget_id):
    """
    List all budget amounts for a budget or create a new one.
    
    GET /budget-headers/{budget_id}/amounts/
    - Returns all budget amounts with consumption details
    - Query params:
        - segment_value_id: Filter by specific segment value
        - low_availability: Show only amounts with < 20% available
    
    POST /budget-headers/{budget_id}/amounts/
    - Create a new budget amount
    - Request body: {
        "budget_segment_value": segment_value_id,
        "original_budget": "100000.00",
        "notes": "..."
      }
    """
    budget = get_object_or_404(BudgetHeader, pk=budget_id)
    
    if request.method == 'GET':
        amounts = BudgetAmount.objects.filter(
            budget_header=budget
        ).select_related(
            'budget_segment_value',
            'budget_segment_value__segment_value',
            'budget_segment_value__segment_value__segment_type'
        )
        
        segment_value_id = request.query_params.get('segment_value_id')
        if segment_value_id:
            amounts = amounts.filter(budget_segment_value__segment_value_id=segment_value_id)
        
        # Filter by low availability (< 20%)
        low_availability = request.query_params.get('low_availability')
        if low_availability and low_availability.lower() == 'true':
            amounts = [amt for amt in amounts if amt.get_utilization_percentage() > 80]
        
        serializer = BudgetAmountListSerializer(amounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        if budget.status not in ['DRAFT']:
            return Response(
                {'error': 'Can only add amounts to DRAFT budgets'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Ensure budget_segment_value belongs to this budget
        segment_value_id = request.data.get('budget_segment_value')
        if not BudgetSegmentValue.objects.filter(
            id=segment_value_id,
            budget_header=budget
        ).exists():
            return Response(
                {'error': 'Segment value does not belong to this budget'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add budget_header to data
        data = request.data.copy()
        data['budget_header'] = budget.id
        
        serializer = BudgetAmountCreateSerializer(data=data)
        if serializer.is_valid():
            try:
                amount = BudgetAmount.objects.create(
                    budget_header=budget,
                    budget_segment_value_id=serializer.validated_data['budget_segment_value'],
                    original_budget=serializer.validated_data['original_budget'],
                    notes=serializer.validated_data.get('notes', '')
                )
                response_serializer = BudgetAmountListSerializer(amount)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def budget_amount_detail(request, budget_id, amount_id):
    """
    Retrieve, update, or delete a budget amount.
    
    GET /budget-headers/{budget_id}/amounts/{amount_id}/
    PUT/PATCH /budget-headers/{budget_id}/amounts/{amount_id}/
    DELETE /budget-headers/{budget_id}/amounts/{amount_id}/
    """
    budget = get_object_or_404(BudgetHeader, pk=budget_id)
    amount = get_object_or_404(
        BudgetAmount,
        pk=amount_id,
        budget_header=budget
    )
    
    if request.method == 'GET':
        serializer = BudgetAmountListSerializer(amount)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        # Only allow updating original_budget for DRAFT budgets
        # For ACTIVE budgets, use adjustment endpoint instead
        if budget.status == 'DRAFT':
            allowed_fields = ['original_budget', 'notes']
        else:
            allowed_fields = ['notes']
        
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        for field, value in update_data.items():
            setattr(amount, field, value)
        
        try:
            amount.save()
            response_serializer = BudgetAmountListSerializer(amount)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    elif request.method == 'DELETE':
        if budget.status != 'DRAFT':
            return Response(
                {'error': 'Can only delete amounts from DRAFT budgets'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if any consumption exists
        if (amount.committed_amount > 0 or 
            amount.encumbered_amount > 0 or 
            amount.actual_amount > 0):
            return Response(
                {'error': 'Cannot delete budget amount with consumption. Reset consumption first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount.delete()
        return Response(
            {'message': 'Budget amount deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def budget_amount_adjust(request, budget_id, amount_id):
    """
    Adjust budget amount (increase or decrease).
    
    POST /budget-headers/{budget_id}/amounts/{amount_id}/adjust/
    - Add or subtract from adjustment_amount
    - Request body:
        {
            "adjustment_amount": "5000.00",  // Can be negative
            "reason": "Budget reallocation from other department"
        }
    """
    budget = get_object_or_404(BudgetHeader, pk=budget_id)
    amount = get_object_or_404(
        BudgetAmount,
        pk=amount_id,
        budget_header=budget
    )
    
    if budget.status != 'ACTIVE':
        return Response(
            {'error': 'Can only adjust ACTIVE budgets'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    adjustment_amount = request.data.get('adjustment_amount')
    reason = request.data.get('reason', '')
    
    if adjustment_amount is None:
        return Response(
            {'error': 'adjustment_amount is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        adjustment_amount = Decimal(str(adjustment_amount))
        new_total = amount.adjust_budget(adjustment_amount, reason)
        
        response_serializer = BudgetAmountListSerializer(amount)
        return Response(
            {
                'message': f'Budget adjusted by {adjustment_amount}',
                'new_total_budget': str(new_total),
                'budget_amount': response_serializer.data
            },
            status=status.HTTP_200_OK
        )
    except (ValueError, ValidationError) as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================================================
# REPORTING AND ANALYTICS VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_summary(request, pk):
    """
    Get comprehensive budget summary with totals and utilization.
    
    GET /budget-headers/{id}/summary/
    - Returns aggregated data:
        - Total original budget
        - Total adjustments
        - Total budget (original + adjustments)
        - Total committed
        - Total encumbered
        - Total actual
        - Total available
        - Overall utilization percentage
        - Breakdown by segment type
    """
    budget = get_object_or_404(BudgetHeader, pk=pk)
    
    amounts = budget.budget_amounts.select_related(
        'budget_segment_value__segment_value__segment_type'
    )
    
    # Calculate totals
    totals = amounts.aggregate(
        total_original=Sum('original_budget'),
        total_adjustments=Sum('adjustment_amount'),
        total_committed=Sum('committed_amount'),
        total_encumbered=Sum('encumbered_amount'),
        total_actual=Sum('actual_amount')
    )
    
    total_original = totals['total_original'] or Decimal('0')
    total_adjustments = totals['total_adjustments'] or Decimal('0')
    total_budget = total_original + total_adjustments
    total_committed = totals['total_committed'] or Decimal('0')
    total_encumbered = totals['total_encumbered'] or Decimal('0')
    total_actual = totals['total_actual'] or Decimal('0')
    total_consumed = total_committed + total_encumbered + total_actual
    total_available = total_budget - total_consumed
    
    utilization = Decimal('0')
    if total_budget > 0:
        utilization = (total_consumed / total_budget * 100).quantize(Decimal('0.01'))
    
    # Breakdown by segment type
    segment_breakdown = {}
    for amount in amounts:
        segment_type = amount.budget_segment_value.segment_value.segment_type.segment_name
        if segment_type not in segment_breakdown:
            segment_breakdown[segment_type] = {
                'total_budget': Decimal('0'),
                'committed': Decimal('0'),
                'encumbered': Decimal('0'),
                'actual': Decimal('0'),
                'available': Decimal('0'),
                'count': 0
            }
        
        breakdown = segment_breakdown[segment_type]
        breakdown['total_budget'] += amount.get_total_budget()
        breakdown['committed'] += amount.committed_amount
        breakdown['encumbered'] += amount.encumbered_amount
        breakdown['actual'] += amount.actual_amount
        breakdown['available'] += amount.get_available()
        breakdown['count'] += 1
    
    # Convert to list and add utilization
    segment_list = []
    for seg_type, data in segment_breakdown.items():
        util = Decimal('0')
        if data['total_budget'] > 0:
            consumed = data['committed'] + data['encumbered'] + data['actual']
            util = (consumed / data['total_budget'] * 100).quantize(Decimal('0.01'))
        
        segment_list.append({
            'segment_type': seg_type,
            'total_budget': str(data['total_budget']),
            'committed': str(data['committed']),
            'encumbered': str(data['encumbered']),
            'actual': str(data['actual']),
            'available': str(data['available']),
            'utilization_percentage': str(util),
            'count': data['count']
        })
    
    return Response({
        'budget_code': budget.budget_code,
        'budget_name': budget.budget_name,
        'status': budget.status,
        'period': f"{budget.start_date} to {budget.end_date}",
        'currency': budget.currency.code,
        'totals': {
            'original_budget': str(total_original),
            'adjustments': str(total_adjustments),
            'total_budget': str(total_budget),
            'committed': str(total_committed),
            'encumbered': str(total_encumbered),
            'actual': str(total_actual),
            'total_consumed': str(total_consumed),
            'available': str(total_available),
            'utilization_percentage': str(utilization)
        },
        'segment_breakdown': segment_list
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@auto_paginate
def budget_violations_report(request):
    """
    Get report of all budget violations (amounts with low availability).
    
    GET /budget-violations/
    - Returns budget amounts that are over 80% utilized
    - Query params:
        - threshold: Utilization threshold percentage (default: 80)
        - status: Filter by budget status
        - control_level: Filter by control level
    """
    threshold = int(request.query_params.get('threshold', 80))
    
    amounts = BudgetAmount.objects.filter(
        budget_header__status='ACTIVE',
        budget_header__is_active=True
    ).select_related(
        'budget_header',
        'budget_segment_value__segment_value__segment_type'
    )
    
    status_filter = request.query_params.get('status')
    if status_filter:
        amounts = amounts.filter(budget_header__status=status_filter.upper())
    
    # Filter by utilization (need to do in Python since it's calculated)
    violations = []
    for amount in amounts:
        utilization = amount.get_utilization_percentage()
        if utilization >= threshold:
            violations.append({
                'budget_code': amount.budget_header.budget_code,
                'budget_name': amount.budget_header.budget_name,
                'segment_value': str(amount.budget_segment_value.segment_value),
                'segment_type': amount.budget_segment_value.segment_value.segment_type.segment_name,
                'control_level': amount.get_effective_control_level(),
                'total_budget': str(amount.get_total_budget()),
                'committed': str(amount.committed_amount),
                'encumbered': str(amount.encumbered_amount),
                'actual': str(amount.actual_amount),
                'available': str(amount.get_available()),
                'utilization_percentage': str(utilization)
            })
    
    return Response(violations, status=status.HTTP_200_OK)


# Excel Import/Export Views
from .excel_utils import export_budget_to_excel, create_budget_template, import_budget_from_excel


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_export_excel(request, pk):
    """
    Export budget to Excel file.
    """
    try:
        budget = BudgetHeader.objects.select_related('currency').get(id=pk)
        return export_budget_to_excel(budget)
    except BudgetHeader.DoesNotExist:
        return Response(
            {'error': 'Budget not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def budget_import_excel(request, pk):
    """
    Import budget amounts from Excel file.
    """
    try:
        budget = BudgetHeader.objects.get(id=pk)
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        excel_file = request.FILES['file']
        
        # Validate file extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            return Response(
                {'error': 'Invalid file format. Please upload an Excel file (.xlsx or .xls)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = import_budget_from_excel(budget, excel_file)
        
        # Check if there was a validation error (e.g., budget not DRAFT)
        if 'error' in results:
            return Response(
                {'error': results['error']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if any rows were processed successfully
        if results['total_rows'] == 0:
            return Response(
                {'error': 'No data rows found in Excel file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if there are any errors - return 400 if so
        if results['error_count'] > 0:
            return Response({
                'error': 'Import completed with errors',
                'total_rows': results['total_rows'],
                'success_count': results['success_count'],
                'imported_count': results.get('imported_count', 0),
                'error_count': results['error_count'],
                'errors': results['errors'],
                'total_budget': results.get('total_budget', '0')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'status': 'success',
            'message': 'Import completed',
            'total_rows': results['total_rows'],
            'success_count': results['success_count'],
            'imported_count': results.get('imported_count', 0),
            'error_count': results['error_count'],
            'errors': results['errors'],
            'total_budget': results.get('total_budget', '0')
        }, status=status.HTTP_200_OK)
        
    except BudgetHeader.DoesNotExist:
        return Response(
            {'error': 'Budget not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_template_excel(request, pk):
    """
    Generate Excel template for budget import.
    """
    try:
        budget = BudgetHeader.objects.get(id=pk)
        return create_budget_template(budget)
    except BudgetHeader.DoesNotExist:
        return Response(
            {'error': 'Budget not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Error generating template: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
