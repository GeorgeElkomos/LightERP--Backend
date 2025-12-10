"""
AP Invoice Views - API Endpoints

These views are THIN WRAPPERS around serializers (which call the service layer).
They handle:
1. HTTP request/response
2. Authentication/permissions
3. Routing
4. Error formatting

Business logic is in services.py, validation in serializers.py.
Views should be as simple as possible!
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from erp_project.pagination import auto_paginate

from Finance.Invoice.models import AP_Invoice
from Finance.Invoice.serializers import (
    APInvoiceCreateSerializer, 
    APInvoiceListSerializer, 
    APInvoiceDetailSerializer
)


@api_view(['GET', 'POST'])
@auto_paginate
def ap_invoice_list(request):
    """
    List all AP invoices or create a new AP invoice.
    
    GET /invoices/ap/
    - Returns list of all AP invoices
    - Query params:
        - supplier_id: Filter by supplier
        - currency_id: Filter by currency
        - country_id: Filter by country
        - approval_status: Filter by status (DRAFT/APPROVED/REJECTED)
        - date_from: Filter by date range start
        - date_to: Filter by date range end
    
    POST /invoices/ap/
    - Create a new AP invoice with items and GL distribution
    - Request body: APInvoiceCreateSerializer fields
    """
    if request.method == 'GET':
        invoices = AP_Invoice.objects.select_related(
            'invoice', 
            'invoice__currency',
            'invoice__country',
            'supplier',
            'supplier__business_partner'
        ).all()
        
        # Apply filters
        supplier_id = request.query_params.get('supplier_id')
        if supplier_id:
            invoices = invoices.filter(supplier_id=supplier_id)
        
        currency_id = request.query_params.get('currency_id')
        if currency_id:
            invoices = invoices.filter(invoice__currency_id=currency_id)
        
        country_id = request.query_params.get('country_id')
        if country_id:
            invoices = invoices.filter(invoice__country_id=country_id)
        
        approval_status = request.query_params.get('approval_status')
        if approval_status:
            invoices = invoices.filter(invoice__approval_status=approval_status.upper())
        
        date_from = request.query_params.get('date_from')
        if date_from:
            invoices = invoices.filter(invoice__date__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            invoices = invoices.filter(invoice__date__lte=date_to)
        
        serializer = APInvoiceListSerializer(invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = APInvoiceCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                ap_invoice = serializer.save()
                response_serializer = APInvoiceDetailSerializer(ap_invoice)
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED
                )
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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def ap_invoice_detail(request, pk):
    """
    Retrieve, update, or delete a specific AP invoice.
    
    GET /invoices/ap/{id}/
    - Returns detailed information about an AP invoice
    
    PUT/PATCH /invoices/ap/{id}/
    - Update an AP invoice (future implementation)
    
    DELETE /invoices/ap/{id}/
    - Delete an AP invoice (if not posted to GL)
    """
    ap_invoice = get_object_or_404(
        AP_Invoice.objects.select_related(
            'invoice', 
            'invoice__currency',
            'invoice__country',
            'supplier',
            'supplier__business_partner'
        ),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = APInvoiceDetailSerializer(ap_invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        return Response(
            {'error': 'Update functionality not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    elif request.method == 'DELETE':
        journal_entry = ap_invoice.gl_distributions
        if journal_entry and journal_entry.posted:
            return Response(
                {'error': 'Cannot delete invoice with posted journal entry'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            invoice_id = ap_invoice.invoice_id
            ap_invoice.delete()
            return Response(
                {'message': f'AP Invoice {invoice_id} deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': f'Cannot delete invoice: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def ap_invoice_post_to_gl(request, pk):
    """
    Post the journal entry to GL (mark as posted).
    
    POST /invoices/ap/{id}/post-to-gl/
    
    Once posted, the journal entry becomes immutable.
    """
    ap_invoice = get_object_or_404(AP_Invoice, pk=pk)
    journal_entry = ap_invoice.gl_distributions
    
    if not journal_entry:
        return Response(
            {'error': 'No journal entry associated with this invoice'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if journal_entry.posted:
        return Response(
            {'message': 'Journal entry is already posted'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if ap_invoice.approval_status != 'APPROVED':
        return Response(
            {'error': 'Invoice must be approved before posting to GL'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    ap_invoice.post_to_gl()
    
    return Response({
        'message': 'Journal entry posted successfully',
        'journal_entry_id': journal_entry.id,
        'invoice_id': ap_invoice.invoice_id
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def ap_invoice_submit_for_approval(request, pk):
    """
    Submit an AP invoice for approval workflow.
    
    POST /invoices/ap/{id}/submit-for-approval/
    
    Starts the approval workflow for the invoice.
    """
    ap_invoice = get_object_or_404(AP_Invoice, pk=pk)
    
    try:
        workflow_instance = ap_invoice.submit_for_approval()
        
        return Response({
            'message': 'Invoice submitted for approval',
            'invoice_id': ap_invoice.invoice_id,
            'workflow_id': workflow_instance.id,
            'status': workflow_instance.status,
            'approval_status': ap_invoice.approval_status
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
def ap_invoice_pending_approvals(request):
    """
    List AP invoices pending approval for the current user.
    
    GET /invoices/ap/pending-approvals/
    
    Returns only invoices where the current user has an active approval assignment.
    """
    from django.contrib.auth import get_user_model
    from core.approval.managers import ApprovalManager
    from core.approval.models import ApprovalAssignment
    from django.contrib.contenttypes.models import ContentType
    from Finance.Invoice.models import Invoice
    
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
    
    # Filter to only Invoice content type, then get AP invoices
    invoice_content_type = ContentType.objects.get_for_model(Invoice)
    invoice_workflows = pending_workflows.filter(content_type=invoice_content_type)
    
    invoice_ids = [wf.object_id for wf in invoice_workflows]
    ap_invoices = AP_Invoice.objects.filter(
        invoice_id__in=invoice_ids
    ).select_related(
        'invoice',
        'invoice__currency',
        'invoice__country',
        'supplier',
        'supplier__business_partner'
    )
    
    # Build response with approval info
    result = []
    for ap_invoice in ap_invoices:
        workflow = ApprovalManager.get_workflow_instance(ap_invoice.invoice)
        if workflow:
            active_stage = workflow.stage_instances.filter(status='active').first()
            assignment = None
            
            if active_stage:
                assignment = active_stage.assignments.filter(
                    user=user,
                    status=ApprovalAssignment.STATUS_PENDING
                ).first()
            
            result.append({
                'invoice_id': ap_invoice.invoice_id,
                'supplier_name': ap_invoice.supplier.name,
                'date': ap_invoice.date,
                'total': str(ap_invoice.total),
                'currency': ap_invoice.currency.code,
                'approval_status': ap_invoice.approval_status,
                'workflow_id': workflow.id,
                'current_stage': active_stage.stage_template.name if active_stage else None,
                'can_approve': assignment is not None,
                'can_reject': active_stage.stage_template.allow_reject if active_stage else False,
                'can_delegate': active_stage.stage_template.allow_delegate if active_stage else False,
            })
    
    return Response(result)


@api_view(['POST'])
def ap_invoice_approval_action(request, pk):
    """
    Perform an approval action on an AP invoice.
    
    POST /invoices/ap/{id}/approval-action/
    
    Request body:
        {
            "action": "approve" | "reject" | "delegate" | "comment",
            "comment": "Optional comment",
            "target_user_id": 123  // Required for delegation
        }
    """
    from django.contrib.auth import get_user_model
    from core.approval.managers import ApprovalManager
    
    ap_invoice = get_object_or_404(AP_Invoice, pk=pk)
    
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
        # Check if invoice is already approved or rejected
        if hasattr(ap_invoice, 'approval_status'):
            if ap_invoice.approval_status == 'APPROVED' and action == 'approve':
                return Response(
                    {'error': 'Invoice is already approved'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif ap_invoice.approval_status == 'REJECTED' and action == 'reject':
                return Response(
                    {'error': 'Invoice is already rejected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        workflow_instance = ApprovalManager.process_action(
            ap_invoice.invoice,
            user=user,
            action=action,
            comment=comment,
            target_user=target_user
        )
        
        ap_invoice.refresh_from_db()
        
        return Response({
            'message': f'Action {action} completed successfully',
            'invoice_id': ap_invoice.invoice_id,
            'workflow_id': workflow_instance.id,
            'workflow_status': workflow_instance.status,
            'approval_status': ap_invoice.approval_status
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
