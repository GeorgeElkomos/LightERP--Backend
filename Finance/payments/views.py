"""
Payment Views - API Endpoints

These views are THIN WRAPPERS that handle:
1. HTTP request/response
2. Authentication/permissions  
3. Routing
4. Error formatting

Business logic is in models.py (helper methods).
Views should be as simple as possible!
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from decimal import Decimal

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import Invoice
from Finance.BusinessPartner.models import BusinessPartner
from Finance.payments.serializers import (
    PaymentListSerializer, PaymentDetailSerializer,
    PaymentCreateSerializer, PaymentUpdateSerializer,
    AllocationCreateSerializer, AllocationUpdateSerializer,
    PaymentAllocationDetailSerializer
)


# ============================================================================
# Payment API Views
# ============================================================================

@api_view(['GET', 'POST'])
def payment_list(request):
    """
    List all payments or create a new payment.
    
    GET /payments/
    - Returns list of all payments
    - Query params:
        - business_partner_id: Filter by business partner
        - currency_id: Filter by currency
        - approval_status: Filter by status (DRAFT/APPROVED/REJECTED)
        - date_from: Filter by date range start
        - date_to: Filter by date range end
        - has_allocations: Filter by allocation status (true/false)
    
    POST /payments/
    - Create a new payment with optional allocations
    - Request body: PaymentCreateSerializer fields
    """
    if request.method == 'GET':
        payments = Payment.objects.select_related(
            'business_partner',
            'currency'
        ).prefetch_related('allocations').all()
        
        # Apply filters
        business_partner_id = request.query_params.get('business_partner_id')
        if business_partner_id:
            payments = payments.filter(business_partner_id=business_partner_id)
        
        currency_id = request.query_params.get('currency_id')
        if currency_id:
            payments = payments.filter(currency_id=currency_id)
        
        approval_status = request.query_params.get('approval_status')
        if approval_status:
            payments = payments.filter(approval_status=approval_status.upper())
        
        date_from = request.query_params.get('date_from')
        if date_from:
            payments = payments.filter(date__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            payments = payments.filter(date__lte=date_to)
        
        has_allocations = request.query_params.get('has_allocations')
        if has_allocations is not None:
            if has_allocations.lower() == 'true':
                payments = payments.filter(allocations__isnull=False).distinct()
            elif has_allocations.lower() == 'false':
                payments = payments.filter(allocations__isnull=True)
        
        serializer = PaymentListSerializer(payments, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = PaymentCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                payment = serializer.save()
                response_serializer = PaymentDetailSerializer(payment)
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e.message_dict) if hasattr(e, 'message_dict') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def payment_detail(request, pk):
    """
    Retrieve, update, or delete a payment.
    
    GET /payments/{id}/
    - Returns detailed payment information with allocations
    
    PUT/PATCH /payments/{id}/
    - Update payment fields (date, exchange_rate, approval_status, rejection_reason)
    - Cannot modify business_partner or currency after creation
    
    DELETE /payments/{id}/
    - Delete payment and all its allocations
    - This will decrease paid_amount on all allocated invoices
    """
    payment = get_object_or_404(Payment, pk=pk)
    
    if request.method == 'GET':
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = PaymentUpdateSerializer(payment, data=request.data, partial=(request.method == 'PATCH'))
        if serializer.is_valid():
            try:
                serializer.save()
                response_serializer = PaymentDetailSerializer(payment)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message_dict) if hasattr(e, 'message_dict') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Clear all allocations first (will update invoice paid_amounts)
        payment.clear_all_allocations()
        # Then delete the payment
        payment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Payment Allocation Management Views
# ============================================================================

@api_view(['GET', 'POST'])
def payment_allocations(request, payment_pk):
    """
    List or create allocations for a specific payment.
    
    GET /payments/{payment_id}/allocations/
    - Returns all allocations for this payment
    
    POST /payments/{payment_id}/allocations/
    - Add new allocation to this payment
    - Request body: {invoice_id: int, amount_allocated: decimal}
    """
    payment = get_object_or_404(Payment, pk=payment_pk)
    
    if request.method == 'GET':
        allocations = payment.allocations.select_related('invoice').all()
        serializer = PaymentAllocationDetailSerializer(allocations, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = AllocationCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                invoice = Invoice.objects.get(id=serializer.validated_data['invoice_id'])
                amount = serializer.validated_data['amount_allocated']
                
                # Use payment helper method to create allocation
                allocation = payment.allocate_to_invoice(invoice, amount)
                
                response_serializer = PaymentAllocationDetailSerializer(allocation)
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e.message_dict) if hasattr(e, 'message_dict') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def payment_allocation_detail(request, payment_pk, allocation_pk):
    """
    Retrieve, update, or delete a specific allocation.
    
    GET /payments/{payment_id}/allocations/{allocation_id}/
    - Returns allocation details
    
    PUT/PATCH /payments/{payment_id}/allocations/{allocation_id}/
    - Update allocation amount
    - Request body: {amount_allocated: decimal}
    
    DELETE /payments/{payment_id}/allocations/{allocation_id}/
    - Remove allocation (decreases invoice paid_amount)
    """
    payment = get_object_or_404(Payment, pk=payment_pk)
    allocation = get_object_or_404(PaymentAllocation, pk=allocation_pk, payment=payment)
    
    if request.method == 'GET':
        serializer = PaymentAllocationDetailSerializer(allocation)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = AllocationUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                allocation.amount_allocated = serializer.validated_data['amount_allocated']
                allocation.save()
                
                response_serializer = PaymentAllocationDetailSerializer(allocation)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message_dict) if hasattr(e, 'message_dict') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        allocation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Invoice Payment Information Views
# ============================================================================

@api_view(['GET'])
def invoice_payment_info(request, invoice_pk):
    """
    Get payment information for a specific invoice.
    
    GET /invoices/{invoice_id}/payments/
    - Returns all payment allocations for this invoice
    - Includes payment status, total paid, remaining amount
    """
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    
    summary = invoice.get_payment_allocations_summary()
    
    data = {
        'invoice_id': invoice.id,
        'total': str(invoice.total),
        'paid_amount': str(invoice.paid_amount),
        'remaining_amount': str(invoice.remaining_amount()),
        'payment_status': invoice.payment_status,
        'is_paid': invoice.is_paid(),
        'is_partially_paid': invoice.is_partially_paid(),
        'allocations': PaymentAllocationDetailSerializer(
            invoice.payment_allocations.select_related('payment').all(),
            many=True
        ).data,
        'summary': {
            'total_allocated': str(summary['total_allocated']),
            'allocation_count': summary['allocation_count']
        }
    }
    
    return Response(data)


# ============================================================================
# Business Partner Payment Summary Views
# ============================================================================

@api_view(['GET'])
def business_partner_payment_summary(request, bp_pk):
    """
    Get payment summary for a business partner.
    
    GET /business-partners/{bp_id}/payment-summary/
    - Returns summary of all payments and invoices for this business partner
    - Includes totals, paid amounts, unpaid amounts
    """
    bp = get_object_or_404(BusinessPartner, pk=bp_pk)
    
    # Get all payments
    payments = Payment.objects.filter(business_partner=bp)
    total_payments = payments.count()
    
    # Get all invoices
    invoices = Invoice.objects.filter(business_partner=bp)
    total_invoices = invoices.count()
    
    # Calculate totals
    invoice_totals = invoices.aggregate(
        total_amount=Sum('total'),
        total_paid=Sum('paid_amount')
    )
    
    total_invoice_amount = invoice_totals['total_amount'] or Decimal('0')
    total_paid_amount = invoice_totals['total_paid'] or Decimal('0')
    total_unpaid_amount = total_invoice_amount - total_paid_amount
    
    # Count by status
    paid_count = invoices.filter(payment_status='PAID').count()
    partial_count = invoices.filter(payment_status='PARTIALLY_PAID').count()
    unpaid_count = invoices.filter(payment_status='UNPAID').count()
    
    data = {
        'business_partner_id': bp.id,
        'business_partner_name': bp.name,
        'total_payments': total_payments,
        'total_invoices': total_invoices,
        'total_invoice_amount': str(total_invoice_amount),
        'total_paid_amount': str(total_paid_amount),
        'total_unpaid_amount': str(total_unpaid_amount),
        'paid_invoices_count': paid_count,
        'partially_paid_invoices_count': partial_count,
        'unpaid_invoices_count': unpaid_count
    }
    
    return Response(data)


# ============================================================================
# Utility Views
# ============================================================================

@api_view(['GET'])
def available_invoices_for_payment(request, payment_pk):
    """
    Get list of invoices that can be allocated to this payment.
    
    GET /payments/{payment_id}/available-invoices/
    - Returns invoices from the same business partner
    - Same currency
    - Not fully paid
    - Not already allocated to this payment
    """
    payment = get_object_or_404(Payment, pk=payment_pk)
    
    # Get invoices that match the payment's business partner and currency
    available_invoices = Invoice.objects.filter(
        business_partner=payment.business_partner,
        currency=payment.currency
    ).exclude(
        payment_status='PAID'  # Exclude fully paid invoices
    ).exclude(
        payment_allocations__payment=payment  # Exclude already allocated
    ).select_related('currency')
    
    # Format response
    data = [
        {
            'id': invoice.id,
            'date': invoice.date,
            'total': str(invoice.total),
            'paid_amount': str(invoice.paid_amount),
            'remaining_amount': str(invoice.remaining_amount()),
            'payment_status': invoice.payment_status,
            'currency_code': invoice.currency.code
        }
        for invoice in available_invoices
    ]
    
    return Response(data)


@api_view(['POST'])
def recalculate_invoice_payments(request, invoice_pk):
    """
    Recalculate paid_amount for an invoice from its allocations.
    
    POST /invoices/{invoice_id}/recalculate-payments/
    - Fixes any inconsistencies between paid_amount and allocations
    - Returns before and after amounts
    """
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    
    old_amount, new_amount, was_changed = invoice.recalculate_paid_amount()
    
    return Response({
        'invoice_id': invoice.id,
        'old_paid_amount': str(old_amount),
        'new_paid_amount': str(new_amount),
        'was_changed': was_changed,
        'message': 'Paid amount recalculated successfully' if was_changed else 'Paid amount was already correct'
    })
