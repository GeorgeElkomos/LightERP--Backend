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
from django.db.models import Q, Sum, F
from decimal import Decimal

from erp_project.pagination import auto_paginate

from Finance.payments.models import Payment, PaymentAllocation, InvoicePaymentPlan, PaymentPlanInstallment
from Finance.Invoice.models import Invoice
from Finance.BusinessPartner.models import BusinessPartner
from Finance.payments.serializers import (
    PaymentListSerializer, PaymentDetailSerializer,
    PaymentCreateSerializer, PaymentUpdateSerializer,
    AllocationCreateSerializer, AllocationUpdateSerializer,
    PaymentAllocationDetailSerializer,
    PaymentPlanListSerializer, PaymentPlanDetailSerializer,
    PaymentPlanCreateSerializer, PaymentPlanUpdateSerializer,
    InstallmentListSerializer, InstallmentDetailSerializer,
    InstallmentCreateSerializer, InstallmentUpdateSerializer,
    ProcessPaymentSerializer, SuggestPaymentPlanSerializer,
    PaymentPlanSummarySerializer, OverdueInstallmentSerializer
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


# ============================================================================
# Payment Plan API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def invoice_payment_plans_list(request, invoice_pk):
    """
    List or create payment plans for a specific invoice.
    
    GET /invoices/{invoice_id}/payment-plans/
    - Returns list of payment plans for this invoice
    
    POST /invoices/{invoice_id}/payment-plans/
    - Create a new payment plan for this invoice
    - Request body: PaymentPlanCreateSerializer fields
    """
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    
    if request.method == 'GET':
        plans = invoice.payment_plans.all().select_related(
            'invoice', 'invoice__business_partner', 'invoice__currency'
        )
        serializer = PaymentPlanListSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # Pass invoice_id in context for serializer validation/creation
        context = {'invoice_id': invoice.id}
        serializer = PaymentPlanCreateSerializer(data=request.data, context=context)
        
        if serializer.is_valid():
            try:
                payment_plan = serializer.save()
                response_serializer = PaymentPlanDetailSerializer(payment_plan)
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
def payment_plan_detail(request, pk):
    """
    Retrieve, update, or delete a payment plan.
    
    GET /payment-plans/{id}/
    - Returns detailed payment plan with installments
    
    PUT/PATCH /payment-plans/{id}/
    - Update payment plan (description, status - limited)
    
    DELETE /payment-plans/{id}/
    - Delete payment plan (only if no payments made)
    """
    payment_plan = get_object_or_404(InvoicePaymentPlan, pk=pk)
    
    if request.method == 'GET':
        serializer = PaymentPlanDetailSerializer(payment_plan)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = PaymentPlanUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                if 'description' in serializer.validated_data:
                    payment_plan.description = serializer.validated_data['description']
                
                if 'status' in serializer.validated_data:
                    payment_plan.status = serializer.validated_data['status']
                
                payment_plan.save()
                
                response_serializer = PaymentPlanDetailSerializer(payment_plan)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Check if any installments have payments
        if payment_plan.get_total_paid() > 0:
            return Response(
                {'error': 'Cannot delete payment plan that has payments. Cancel it instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Payment Plan Operations Views
# ============================================================================

@api_view(['POST'])
def payment_plan_process_payment(request, pk):
    """
    Apply a payment to the payment plan installments.
    
    POST /payment-plans/{id}/process-payment/
    - Request body: {payment_amount: decimal}
    - Applies payment using waterfall method (oldest unpaid first)
    """
    payment_plan = get_object_or_404(InvoicePaymentPlan, pk=pk)
    
    serializer = ProcessPaymentSerializer(data=request.data)
    if serializer.is_valid():
        try:
            payment_amount = serializer.validated_data['payment_amount']
            result = payment_plan.process_payment(payment_amount)
            return Response(result, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def payment_plan_update_status(request, pk):
    """
    Force update of payment plan status based on installment states.
    
    POST /payment-plans/{id}/update-status/
    """
    payment_plan = get_object_or_404(InvoicePaymentPlan, pk=pk)
    
    try:
        payment_plan.update_status()
        
        # Also update all installment statuses
        for installment in payment_plan.installments.all():
            installment.update_status()
            
        return Response({
            'message': 'Status updated successfully',
            'status': payment_plan.status
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def payment_plan_cancel(request, pk):
    """
    Cancel a payment plan.
    
    POST /payment-plans/{id}/cancel/
    """
    payment_plan = get_object_or_404(InvoicePaymentPlan, pk=pk)
    
    try:
        payment_plan.status = 'cancelled'
        payment_plan.save(update_fields=['status', 'updated_at'])
        
        return Response({
            'message': 'Payment plan cancelled successfully',
            'status': payment_plan.status
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def payment_plan_summary(request, pk):
    """
    Get summary for a payment plan.
    
    GET /payment-plans/{id}/summary/
    """
    payment_plan = get_object_or_404(InvoicePaymentPlan, pk=pk)
    
    # Get next due installment manually for serializer
    from django.db.models import F
    next_installment = payment_plan.installments.filter(
        paid_amount__lt=F('amount')
    ).order_by('due_date').first()
    
    next_due_data = None
    if next_installment:
        next_due_data = {
            'installment_number': next_installment.installment_number,
            'due_date': next_installment.due_date,
            'amount': next_installment.amount,
            'paid_amount': next_installment.paid_amount,
            'remaining_balance': next_installment.get_remaining_balance()
        }
    
    serializer = PaymentPlanSummarySerializer({
        'payment_plan_id': payment_plan.id,
        'invoice_id': payment_plan.invoice.id,
        'total_amount': payment_plan.total_amount,
        'total_paid': payment_plan.get_total_paid(),
        'remaining_balance': payment_plan.get_remaining_balance(),
        'is_fully_paid': payment_plan.is_fully_paid(),
        'has_overdue_installments': payment_plan.has_overdue_installments(),
        'overdue_count': payment_plan.get_overdue_installments().count(),
        'next_due_installment': next_due_data
    })
    
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def payment_plan_overdue_installments(request, pk):
    """
    List all overdue installments for a payment plan.
    
    GET /payment-plans/{id}/overdue-installments/
    """
    payment_plan = get_object_or_404(InvoicePaymentPlan, pk=pk)
    
    overdue_installments = payment_plan.get_overdue_installments()
    serializer = OverdueInstallmentSerializer(overdue_installments, many=True)
    
    return Response({
        'overdue_installments': serializer.data,
        'count': overdue_installments.count()
    }, status=status.HTTP_200_OK)


# ============================================================================
# Installment API Views
# ============================================================================

@api_view(['GET', 'POST'])
def payment_plan_installments_list(request, payment_plan_pk):
    """
    List or create installments for a payment plan.
    
    GET /payment-plans/{payment_plan_id}/installments/
    - List all installments
    - Query params: status (paid/pending/overdue/partial)
    
    POST /payment-plans/{payment_plan_id}/installments/
    - Add new installment manually
    """
    payment_plan = get_object_or_404(InvoicePaymentPlan, pk=payment_plan_pk)
    
    if request.method == 'GET':
        installments = payment_plan.installments.all()
        
        # Filtering
        status_param = request.query_params.get('status')
        if status_param:
            installments = installments.filter(status=status_param)
            
        overdue = request.query_params.get('overdue')
        if overdue == 'true':
            # Use model method logic for filtering overdue
            from django.utils import timezone
            today = timezone.now().date()
            installments = installments.filter(
                due_date__lt=today,
                paid_amount__lt=F('amount')
            )
            
        serializer = InstallmentListSerializer(installments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = InstallmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Check for duplicate installment number
                if PaymentPlanInstallment.objects.filter(
                    payment_plan=payment_plan,
                    installment_number=serializer.validated_data['installment_number']
                ).exists():
                    return Response(
                        {'error': f"Installment number {serializer.validated_data['installment_number']} already exists"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                installment = PaymentPlanInstallment.objects.create(
                    payment_plan=payment_plan,
                    installment_number=serializer.validated_data['installment_number'],
                    due_date=serializer.validated_data['due_date'],
                    amount=serializer.validated_data['amount'],
                    description=serializer.validated_data.get('description', ''),
                    status='pending',
                    paid_amount=Decimal('0.00')
                )
                
                response_serializer = InstallmentDetailSerializer(installment)
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def installment_detail(request, pk):
    """
    Retrieve, update, or delete an installment.
    
    GET /installments/{id}/
    - Returns detailed installment info
    
    PUT/PATCH /installments/{id}/
    - Update installment (due_date, amount, description)
    - Cannot modify if already paid
    
    DELETE /installments/{id}/
    - Delete installment (only if not paid)
    """
    installment = get_object_or_404(PaymentPlanInstallment, pk=pk)
    
    if request.method == 'GET':
        serializer = InstallmentDetailSerializer(installment)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = InstallmentUpdateSerializer(installment, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                serializer.save()
                response_serializer = InstallmentDetailSerializer(installment)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        if installment.paid_amount > 0:
            return Response(
                {'error': 'Cannot delete installment that has payments'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        installment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def installment_update_status(request, pk):
    """
    Force update of installment status.
    
    POST /installments/{id}/update-status/
    """
    installment = get_object_or_404(PaymentPlanInstallment, pk=pk)
    
    try:
        installment.update_status()
        return Response({
            'message': 'Status updated successfully',
            'status': installment.status
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# Payment Plan Utility Views
# ============================================================================

@api_view(['POST'])
def invoice_suggest_payment_plan(request, invoice_pk):
    """
    Generate a suggested payment plan (preview only).
    
    POST /invoices/{invoice_id}/suggest-payment-plan/
    - Request body: {start_date, num_installments, frequency}
    - Returns suggested schedule
    """
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    
    serializer = SuggestPaymentPlanSerializer(data=request.data)
    if serializer.is_valid():
        try:
            suggestions = InvoicePaymentPlan.suggest_schedule(
                invoice_total=invoice.total,
                start_date=serializer.validated_data['start_date'],
                num_installments=serializer.validated_data['num_installments'],
                frequency=serializer.validated_data['frequency']
            )
            
            return Response({
                'invoice_id': invoice.id,
                'invoice_total': str(invoice.total),
                'suggested_installments': suggestions
            }, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@auto_paginate
def payment_plans_overdue_list(request):
    """
    List all payment plans with overdue installments.
    
    GET /payment-plans/overdue/
    - Query params: business_partner_id
    """
    # Find plans that match overdue criteria
    # This complex query mimics has_overdue_installments() logic but in ORM
    from django.utils import timezone
    today = timezone.now().date()
    
    plans = InvoicePaymentPlan.objects.filter(
        installments__due_date__lt=today,
        installments__paid_amount__lt=F('installments__amount')
    ).distinct().select_related(
        'invoice', 'invoice__business_partner'
    )
    
    business_partner_id = request.query_params.get('business_partner_id')
    if business_partner_id:
        plans = plans.filter(invoice__business_partner_id=business_partner_id)
    
    serializer = PaymentPlanListSerializer(plans, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@auto_paginate
def installments_due_soon(request):
    """
    List installments due within a specified timeframe.
    
    GET /installments/due-soon/
    - Query params: days_ahead (default 7), business_partner_id
    """
    from django.utils import timezone
    from datetime import timedelta
    
    days_ahead = int(request.query_params.get('days_ahead', 7))
    today = timezone.now().date()
    future_date = today + timedelta(days=days_ahead)
    
    # Get unpaid installments due between today and future_date
    installments = PaymentPlanInstallment.objects.filter(
        due_date__gte=today,
        due_date__lte=future_date,
        paid_amount__lt=F('amount')
    ).select_related(
        'payment_plan', 
        'payment_plan__invoice', 
        'payment_plan__invoice__business_partner'
    ).order_by('due_date')
    
    business_partner_id = request.query_params.get('business_partner_id')
    if business_partner_id:
        installments = installments.filter(
            payment_plan__invoice__business_partner_id=business_partner_id
        )
    
    serializer = InstallmentListSerializer(installments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@auto_paginate
def business_partner_payment_plans(request, bp_pk):
    """
    Get all payment plans for a business partner.
    
    GET /business-partners/{bp_id}/payment-plans/
    """
    bp = get_object_or_404(BusinessPartner, pk=bp_pk)
    
    plans = InvoicePaymentPlan.objects.filter(
        invoice__business_partner=bp
    ).select_related(
        'invoice', 'invoice__currency'
    ).order_by('-created_at')
    
    serializer = PaymentPlanListSerializer(plans, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
