"""
API Views for Business Partner models.
Provides REST API endpoints for Customer and Supplier with comprehensive CRUD operations.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q

from erp_project.pagination import auto_paginate

from .models import Customer, Supplier
from .serializers import (
    CustomerSerializer,
    CustomerListSerializer,
    SupplierSerializer,
    SupplierListSerializer,
)


# ============================================================================
# Customer API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def customer_list(request):
    """
    List all customers or create a new customer.
    
    GET /customers/
    - Returns list of all customers
    - Query params:
        - is_active: Filter by active status (true/false)
        - country: Filter by country ID
        - country_code: Filter by country code
        - name: Filter by name (case-insensitive contains)
        - email: Filter by email (case-insensitive contains)
        - phone: Filter by phone (contains)
        - search: Search across name, email, phone (case-insensitive)
    
    POST /customers/
    - Create a new customer
    - Request body: CustomerSerializer fields
    """
    if request.method == 'GET':
        customers = Customer.objects.select_related(
            'business_partner',
            'business_partner__country'
        ).all()
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            customers = customers.filter(business_partner__is_active=is_active_bool)
        
        country_id = request.query_params.get('country')
        if country_id:
            customers = customers.filter(business_partner__country_id=country_id)
        
        country_code = request.query_params.get('country_code')
        if country_code:
            customers = customers.filter(business_partner__country__code__iexact=country_code)
        
        name = request.query_params.get('name')
        if name:
            customers = customers.filter(business_partner__name__icontains=name)
        
        email = request.query_params.get('email')
        if email:
            customers = customers.filter(business_partner__email__icontains=email)
        
        phone = request.query_params.get('phone')
        if phone:
            customers = customers.filter(business_partner__phone__icontains=phone)
        
        # General search across multiple fields
        search = request.query_params.get('search')
        if search:
            customers = customers.filter(
                Q(business_partner__name__icontains=search) |
                Q(business_partner__email__icontains=search) |
                Q(business_partner__phone__icontains=search) |
                Q(business_partner__address__icontains=search) |
                Q(address_in_details__icontains=search)
            )
        
        serializer = CustomerListSerializer(customers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = CustomerSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to create customer: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def customer_detail(request, pk):
    """
    Retrieve, update, or delete a specific customer.
    
    GET /customers/{id}/
    - Returns detailed information about a customer
    
    PUT/PATCH /customers/{id}/
    - Update a customer
    - Request body: CustomerSerializer fields
    
    DELETE /customers/{id}/
    - Delete a customer (also deletes associated BusinessPartner if not used elsewhere)
    """
    customer = get_object_or_404(
        Customer.objects.select_related('business_partner', 'business_partner__country'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = CustomerSerializer(customer)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = CustomerSerializer(customer, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to update customer: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            customer_name = customer.name
            customer.delete()
            return Response(
                {'message': f'Customer "{customer_name}" deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"Cannot delete customer: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def customer_toggle_active(request, pk):
    """
    Toggle the active status of a customer.
    
    POST /customers/{id}/toggle-active/
    
    Returns:
        {
            "id": 1,
            "name": "Acme Corp",
            "is_active": true/false
        }
    """
    customer = get_object_or_404(Customer, pk=pk)
    customer.is_active = not customer.is_active
    customer.save()
    
    return Response({
        'id': customer.id,
        'name': customer.name,
        'is_active': customer.is_active
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@auto_paginate
def customer_active_list(request):
    """
    Get all active customers.
    
    GET /customers/active/
    
    Returns list of all active customers with the same filters as customer_list.
    """
    customers = Customer.objects.select_related(
        'business_partner',
        'business_partner__country'
    ).filter(business_partner__is_active=True)
    
    # Apply additional filters
    country_id = request.query_params.get('country')
    if country_id:
        customers = customers.filter(business_partner__country_id=country_id)
    
    country_code = request.query_params.get('country_code')
    if country_code:
        customers = customers.filter(business_partner__country__code__iexact=country_code)
    
    name = request.query_params.get('name')
    if name:
        customers = customers.filter(business_partner__name__icontains=name)
    
    search = request.query_params.get('search')
    if search:
        customers = customers.filter(
            Q(business_partner__name__icontains=search) |
            Q(business_partner__email__icontains=search) |
            Q(business_partner__phone__icontains=search)
        )
    
    serializer = CustomerListSerializer(customers, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# Supplier API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def supplier_list(request):
    """
    List all suppliers or create a new supplier.
    
    GET /suppliers/
    - Returns list of all suppliers
    - Query params:
        - is_active: Filter by active status (true/false)
        - country: Filter by country ID
        - country_code: Filter by country code
        - name: Filter by name (case-insensitive contains)
        - email: Filter by email (case-insensitive contains)
        - phone: Filter by phone (contains)
        - vat_number: Filter by VAT number (contains)
        - tax_id: Filter by tax ID (contains)
        - search: Search across name, email, phone, vat_number (case-insensitive)
    
    POST /suppliers/
    - Create a new supplier
    - Request body: SupplierSerializer fields
    """
    if request.method == 'GET':
        suppliers = Supplier.objects.select_related(
            'business_partner',
            'business_partner__country'
        ).all()
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            suppliers = suppliers.filter(business_partner__is_active=is_active_bool)
        
        country_id = request.query_params.get('country')
        if country_id:
            suppliers = suppliers.filter(business_partner__country_id=country_id)
        
        country_code = request.query_params.get('country_code')
        if country_code:
            suppliers = suppliers.filter(business_partner__country__code__iexact=country_code)
        
        name = request.query_params.get('name')
        if name:
            suppliers = suppliers.filter(business_partner__name__icontains=name)
        
        email = request.query_params.get('email')
        if email:
            suppliers = suppliers.filter(business_partner__email__icontains=email)
        
        phone = request.query_params.get('phone')
        if phone:
            suppliers = suppliers.filter(business_partner__phone__icontains=phone)
        
        vat_number = request.query_params.get('vat_number')
        if vat_number:
            suppliers = suppliers.filter(vat_number__icontains=vat_number)
        
        tax_id = request.query_params.get('tax_id')
        if tax_id:
            suppliers = suppliers.filter(tax_id__icontains=tax_id)
        
        # General search across multiple fields
        search = request.query_params.get('search')
        if search:
            suppliers = suppliers.filter(
                Q(business_partner__name__icontains=search) |
                Q(business_partner__email__icontains=search) |
                Q(business_partner__phone__icontains=search) |
                Q(business_partner__address__icontains=search) |
                Q(vat_number__icontains=search) |
                Q(tax_id__icontains=search) |
                Q(website__icontains=search)
            )
        
        serializer = SupplierListSerializer(suppliers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = SupplierSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to create supplier: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def supplier_detail(request, pk):
    """
    Retrieve, update, or delete a specific supplier.
    
    GET /suppliers/{id}/
    - Returns detailed information about a supplier
    
    PUT/PATCH /suppliers/{id}/
    - Update a supplier
    - Request body: SupplierSerializer fields
    
    DELETE /suppliers/{id}/
    - Delete a supplier (also deletes associated BusinessPartner if not used elsewhere)
    """
    supplier = get_object_or_404(
        Supplier.objects.select_related('business_partner', 'business_partner__country'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = SupplierSerializer(supplier)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = SupplierSerializer(supplier, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to update supplier: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            supplier_name = supplier.name
            supplier.delete()
            return Response(
                {'message': f'Supplier "{supplier_name}" deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"Cannot delete supplier: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def supplier_toggle_active(request, pk):
    """
    Toggle the active status of a supplier.
    
    POST /suppliers/{id}/toggle-active/
    
    Returns:
        {
            "id": 1,
            "name": "Tech Supplies Inc",
            "is_active": true/false
        }
    """
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.is_active = not supplier.is_active
    supplier.save()
    
    return Response({
        'id': supplier.id,
        'name': supplier.name,
        'is_active': supplier.is_active
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@auto_paginate
def supplier_active_list(request):
    """
    Get all active suppliers.
    
    GET /suppliers/active/
    
    Returns list of all active suppliers with the same filters as supplier_list.
    """
    suppliers = Supplier.objects.select_related(
        'business_partner',
        'business_partner__country'
    ).filter(business_partner__is_active=True)
    
    # Apply additional filters
    country_id = request.query_params.get('country')
    if country_id:
        suppliers = suppliers.filter(business_partner__country_id=country_id)
    
    country_code = request.query_params.get('country_code')
    if country_code:
        suppliers = suppliers.filter(business_partner__country__code__iexact=country_code)
    
    name = request.query_params.get('name')
    if name:
        suppliers = suppliers.filter(business_partner__name__icontains=name)
    
    vat_number = request.query_params.get('vat_number')
    if vat_number:
        suppliers = suppliers.filter(vat_number__icontains=vat_number)
    
    search = request.query_params.get('search')
    if search:
        suppliers = suppliers.filter(
            Q(business_partner__name__icontains=search) |
            Q(business_partner__email__icontains=search) |
            Q(business_partner__phone__icontains=search) |
            Q(vat_number__icontains=search)
        )
    
    serializer = SupplierListSerializer(suppliers, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
