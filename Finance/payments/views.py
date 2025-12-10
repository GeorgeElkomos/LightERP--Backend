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

from erp_project.pagination import auto_paginate

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
@auto_paginate
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
    - Create a new payment with optional allocations and GL entry
    - Request body: PaymentCreateSerializer fields
    """
    if request.method == 'GET':
        payments = Payment.objects.select_related(
            'business_partner',
            'currency',
            'gl_entry'
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
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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
@auto_paginate
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
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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
@auto_paginate
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
@auto_paginate
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
    }, status=status.HTTP_200_OK)


# ============================================================================
# Payment Approval Workflow Views
# ============================================================================

@api_view(['POST'])
def payment_post_to_gl(request, pk):
    """
    Post the journal entry to GL (mark as posted).
    
    POST /payments/{id}/post-to-gl/
    
    Once posted, the journal entry becomes immutable.
    """
    payment = get_object_or_404(Payment, pk=pk)
    
    if not payment.gl_entry:
        return Response(
            {'error': 'No journal entry associated with this payment'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if payment.gl_entry.posted:
        return Response(
            {'message': 'Journal entry is already posted'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if payment.approval_status != 'APPROVED':
        return Response(
            {'error': 'Payment must be approved before posting to GL'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        payment.post_to_gl()
        
        return Response({
            'message': 'Journal entry posted successfully',
            'journal_entry_id': payment.gl_entry.id,
            'payment_id': payment.id
        }, status=status.HTTP_200_OK)
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def payment_submit_for_approval(request, pk):
    """
    Submit a payment for approval workflow.
    
    POST /payments/{id}/submit-for-approval/
    
    Starts the approval workflow for the payment.
    """
    payment = get_object_or_404(Payment, pk=pk)
    
    try:
        workflow_instance = payment.submit_for_approval()
        
        return Response({
            'message': 'Payment submitted for approval',
            'payment_id': payment.id,
            'workflow_id': workflow_instance.id,
            'status': workflow_instance.status,
            'approval_status': payment.approval_status
        }, status=status.HTTP_200_OK)
    except (ValueError, ValidationError) as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@auto_paginate
def payment_pending_approvals(request):
    """
    List payments pending approval for the current user.
    
    GET /payments/pending-approvals/
    
    Returns only payments where the current user has an active approval assignment.
    """
    from django.contrib.auth import get_user_model
    from core.approval.managers import ApprovalManager
    from core.approval.models import ApprovalAssignment
    from django.contrib.contenttypes.models import ContentType
    
    # Get user from request (use first user if not authenticated for testing)
    User = get_user_model()
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        user = User.objects.first()
    
    if not user:
        return Response(
            {'error': 'No authenticated user'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Use ApprovalManager to get all pending workflows for this user
    pending_workflows = ApprovalManager.get_user_pending_approvals(user)
    
    # Filter to only Payment content type
    payment_content_type = ContentType.objects.get_for_model(Payment)
    payment_workflows = pending_workflows.filter(content_type=payment_content_type)
    
    payment_ids = [wf.object_id for wf in payment_workflows]
    payments = Payment.objects.filter(
        id__in=payment_ids
    ).select_related(
        'business_partner',
        'currency'
    )
    
    # Build response with approval info
    result = []
    for payment in payments:
        workflow = ApprovalManager.get_workflow_instance(payment)
        if workflow:
            active_stage = workflow.stage_instances.filter(status='active').first()
            assignment = None
            
            if active_stage:
                assignment = active_stage.assignments.filter(
                    user=user,
                    status=ApprovalAssignment.STATUS_PENDING
                ).first()
            
            result.append({
                'payment_id': payment.id,
                'business_partner_name': payment.business_partner.name,
                'date': payment.date,
                'amount': str(payment.get_total_allocated()),
                'currency': payment.currency.code,
                'approval_status': payment.approval_status,
                'workflow_id': workflow.id,
                'current_stage': active_stage.stage_template.name if active_stage else None,
                'can_approve': assignment is not None,
                'can_reject': active_stage.stage_template.allow_reject if active_stage else False,
                'can_delegate': active_stage.stage_template.allow_delegate if active_stage else False,
            })
    
    return Response(result)


@api_view(['POST'])
def payment_approval_action(request, pk):
    """
    Perform an approval action on a payment.
    
    POST /payments/{id}/approval-action/
    
    Request body:
        {
            "action": "approve" | "reject" | "delegate" | "comment",
            "comment": "Optional comment",
            "target_user_id": 123  // Required for delegation
        }
    """
    from django.contrib.auth import get_user_model
    from core.approval.managers import ApprovalManager
    
    payment = get_object_or_404(Payment, pk=pk)
    
    # Get user from request
    User = get_user_model()
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        user = User.objects.first()
    
    if not user:
        return Response(
            {'error': 'No authenticated user'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    action = request.data.get('action', 'approve').lower()  # Default to 'approve'
    comment = request.data.get('comment', '')
    target_user_id = request.data.get('target_user_id')
    
    # Map status values to workflow actions
    action_mapping = {
        'approved': 'approve',
        'rejected': 'reject',
        'approve': 'approve',
        'reject': 'reject',
        'delegate': 'delegate',
        'comment': 'comment'
    }
    
    action = action_mapping.get(action)
    if not action:
        return Response(
            {'error': 'Invalid action. Must be approve, reject, delegate, or comment'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get target user for delegation
    target_user = None
    if action == 'delegate':
        if not target_user_id:
            return Response(
                {'error': 'target_user_id required for delegation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            target_user = User.objects.get(pk=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': f'User with id {target_user_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    try:
        # Check if payment is already approved or rejected
        if payment.approval_status == 'APPROVED' and action == 'approve':
            return Response(
                {'error': 'Payment is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif payment.approval_status == 'REJECTED' and action == 'reject':
            return Response(
                {'error': 'Payment is already rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        workflow_instance = ApprovalManager.process_action(
            payment,
            user=user,
            action=action,
            comment=comment,
            target_user=target_user
        )
        
        payment.refresh_from_db()
        
        return Response({
            'message': f'Action {action} completed successfully',
            'payment_id': payment.id,
            'workflow_id': workflow_instance.id,
            'workflow_status': workflow_instance.status,
            'approval_status': payment.approval_status
        })
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
