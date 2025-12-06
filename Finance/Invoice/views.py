"""
Invoice Views - API Endpoints

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

from Finance.Invoice.models import AP_Invoice, AR_Invoice, one_use_supplier
from Finance.Invoice.serializers import (
    APInvoiceCreateSerializer, APInvoiceListSerializer, APInvoiceDetailSerializer,
    ARInvoiceCreateSerializer, ARInvoiceListSerializer,
    OneTimeSupplierCreateSerializer, OneTimeSupplierListSerializer, OneTimeSupplierDetailSerializer
)


# ============================================================================
# AP Invoice API Views
# ============================================================================

@api_view(['GET', 'POST'])
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
        return Response(serializer.data)
    
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
        return Response(serializer.data)
    
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
def ap_invoice_approve(request, pk):
    """
    Approve or reject an AP invoice.
    
    POST /invoices/ap/{id}/approve/
    
    Request body:
        {
            "action": "APPROVED" or "REJECTED"
        }
    
    Changes status from DRAFT -> APPROVED/REJECTED.
    """
    ap_invoice = get_object_or_404(AP_Invoice, pk=pk)
    
    action = request.data.get('action', 'APPROVED').upper()
    
    if action not in ['APPROVED', 'REJECTED']:
        return Response(
            {'error': 'Invalid action. Must be APPROVED or REJECTED'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if ap_invoice.approval_status == action:
        return Response(
            {'message': f'Invoice is already {action.lower()}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    ap_invoice.approval_status = action
    ap_invoice.save()
    
    serializer = APInvoiceDetailSerializer(ap_invoice)
    return Response(serializer.data)


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
    
    journal_entry.post()
    
    return Response({
        'message': 'Journal entry posted successfully',
        'journal_entry_id': journal_entry.id,
        'invoice_id': ap_invoice.invoice_id
    })


# ============================================================================
# AR Invoice API Views
# ============================================================================

@api_view(['GET', 'POST'])
def ar_invoice_list(request):
    """
    List all AR invoices or create a new AR invoice.
    
    GET /invoices/ar/
    - Returns list of all AR invoices
    - Query params:
        - customer_id: Filter by customer
        - currency_id: Filter by currency
        - country_id: Filter by country
        - approval_status: Filter by status (DRAFT/APPROVED/REJECTED)
        - date_from: Filter by date range start
        - date_to: Filter by date range end
    
    POST /invoices/ar/
    - Create a new AR invoice with items and GL distribution
    - Request body: ARInvoiceCreateSerializer fields
    """
    if request.method == 'GET':
        invoices = AR_Invoice.objects.select_related(
            'invoice',
            'invoice__currency',
            'invoice__country',
            'customer',
            'customer__business_partner'
        ).all()
        
        # Apply filters
        customer_id = request.query_params.get('customer_id')
        if customer_id:
            invoices = invoices.filter(customer_id=customer_id)
        
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
        
        serializer = ARInvoiceListSerializer(invoices, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = ARInvoiceCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                ar_invoice = serializer.save()
                response_serializer = ARInvoiceListSerializer(ar_invoice)
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
def ar_invoice_detail(request, pk):
    """
    Retrieve, update, or delete a specific AR invoice.
    
    GET /invoices/ar/{id}/
    - Returns detailed information about an AR invoice
    
    PUT/PATCH /invoices/ar/{id}/
    - Update an AR invoice (future implementation)
    
    DELETE /invoices/ar/{id}/
    - Delete an AR invoice (if not posted to GL)
    """
    ar_invoice = get_object_or_404(
        AR_Invoice.objects.select_related(
            'invoice',
            'invoice__currency',
            'invoice__country',
            'customer',
            'customer__business_partner'
        ),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = ARInvoiceListSerializer(ar_invoice)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        return Response(
            {'error': 'Update functionality not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    elif request.method == 'DELETE':
        journal_entry = ar_invoice.gl_distributions
        if journal_entry and journal_entry.posted:
            return Response(
                {'error': 'Cannot delete invoice with posted journal entry'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            invoice_id = ar_invoice.invoice_id
            ar_invoice.delete()
            return Response(
                {'message': f'AR Invoice {invoice_id} deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': f'Cannot delete invoice: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def ar_invoice_approve(request, pk):
    """
    Approve or reject an AR invoice.
    
    POST /invoices/ar/{id}/approve/
    
    Request body:
        {
            "action": "APPROVED" or "REJECTED"
        }
    
    Changes status from DRAFT -> APPROVED/REJECTED.
    """
    ar_invoice = get_object_or_404(AR_Invoice, pk=pk)
    
    action = request.data.get('action', 'APPROVED').upper()
    
    if action not in ['APPROVED', 'REJECTED']:
        return Response(
            {'error': 'Invalid action. Must be APPROVED or REJECTED'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if ar_invoice.approval_status == action:
        return Response(
            {'message': f'Invoice is already {action.lower()}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    ar_invoice.approval_status = action
    ar_invoice.save()
    
    serializer = ARInvoiceListSerializer(ar_invoice)
    return Response(serializer.data)


@api_view(['POST'])
def ar_invoice_post_to_gl(request, pk):
    """
    Post the journal entry to GL (mark as posted).
    
    POST /invoices/ar/{id}/post-to-gl/
    
    Once posted, the journal entry becomes immutable.
    """
    ar_invoice = get_object_or_404(AR_Invoice, pk=pk)
    journal_entry = ar_invoice.gl_distributions
    
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
    
    if ar_invoice.approval_status != 'APPROVED':
        return Response(
            {'error': 'Invoice must be approved before posting to GL'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    journal_entry.post()
    
    return Response({
        'message': 'Journal entry posted successfully',
        'journal_entry_id': journal_entry.id,
        'invoice_id': ar_invoice.invoice_id
    })


# ============================================================================
# One-Time Supplier Invoice API Views
# ============================================================================

@api_view(['GET', 'POST'])
def one_time_supplier_invoice_list(request):
    """
    List all one-time supplier invoices or create a new one.
    
    GET /invoices/one-time-supplier/
    - Returns list of all one-time supplier invoices
    - Query params:
        - supplier_name: Filter by supplier name (contains)
        - currency_id: Filter by currency
        - country_id: Filter by country
        - approval_status: Filter by status (DRAFT/APPROVED/REJECTED)
        - date_from: Filter by date range start
        - date_to: Filter by date range end
    
    POST /invoices/one-time-supplier/
    - Create a new one-time supplier invoice
    - Request body: OneTimeSupplierCreateSerializer fields
    """
    if request.method == 'GET':
        invoices = one_use_supplier.objects.select_related(
            'invoice',
            'invoice__currency',
            'invoice__country'
        ).all()
        
        # Apply filters
        supplier_name = request.query_params.get('supplier_name')
        if supplier_name:
            invoices = invoices.filter(supplier_name__icontains=supplier_name)
        
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
        
        serializer = OneTimeSupplierListSerializer(invoices, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = OneTimeSupplierCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                one_time_invoice = serializer.save()
                return Response(
                    {
                        'id': one_time_invoice.invoice_id,
                        'supplier_name': one_time_invoice.supplier_name,
                        'total': str(one_time_invoice.total),
                        'message': 'One-time supplier invoice created successfully'
                    },
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
def one_time_supplier_invoice_detail(request, pk):
    """
    Retrieve, update, or delete a specific one-time supplier invoice.
    
    GET /invoices/one-time-supplier/{id}/
    - Returns detailed information about a one-time supplier invoice
    
    PUT/PATCH /invoices/one-time-supplier/{id}/
    - Update a one-time supplier invoice (future implementation)
    
    DELETE /invoices/one-time-supplier/{id}/
    - Delete a one-time supplier invoice (if not posted to GL)
    """
    invoice = get_object_or_404(
        one_use_supplier.objects.select_related(
            'invoice',
            'invoice__currency',
            'invoice__country'
        ),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = OneTimeSupplierDetailSerializer(invoice)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        return Response(
            {'error': 'Update functionality not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    elif request.method == 'DELETE':
        journal_entry = invoice.gl_distributions
        if journal_entry and journal_entry.posted:
            return Response(
                {'error': 'Cannot delete invoice with posted journal entry'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            invoice_id = invoice.invoice_id
            invoice.delete()
            return Response(
                {'message': f'One-time supplier invoice {invoice_id} deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': f'Cannot delete invoice: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def one_time_supplier_invoice_approve(request, pk):
    """
    Approve or reject a one-time supplier invoice.
    
    POST /invoices/one-time-supplier/{id}/approve/
    
    Request body:
        {
            "action": "APPROVED" or "REJECTED"
        }
    
    Changes status from DRAFT -> APPROVED/REJECTED.
    """
    invoice = get_object_or_404(one_use_supplier, pk=pk)
    
    action = request.data.get('action', 'APPROVED').upper()
    
    if action not in ['APPROVED', 'REJECTED']:
        return Response(
            {'error': 'Invalid action. Must be APPROVED or REJECTED'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if invoice.approval_status == action:
        return Response(
            {'message': f'Invoice is already {action.lower()}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    invoice.approval_status = action
    invoice.save()
    
    return Response({
        'id': invoice.invoice_id,
        'supplier_name': invoice.supplier_name,
        'approval_status': invoice.approval_status,
        'message': f'Invoice {action.lower()} successfully'
    })


@api_view(['POST'])
def one_time_supplier_invoice_post_to_gl(request, pk):
    """
    Post the journal entry to GL (mark as posted).
    
    POST /invoices/one-time-supplier/{id}/post-to-gl/
    
    Once posted, the journal entry becomes immutable.
    """
    invoice = get_object_or_404(one_use_supplier, pk=pk)
    journal_entry = invoice.gl_distributions
    
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
    
    if invoice.approval_status != 'APPROVED':
        return Response(
            {'error': 'Invoice must be approved before posting to GL'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    journal_entry.post()
    
    return Response({
        'message': 'Journal entry posted successfully',
        'journal_entry_id': journal_entry.id,
        'invoice_id': invoice.invoice_id
    })
