"""
API Views for Catalog models.
Provides REST API endpoints for UnitOfMeasure and catalogItem.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError

from erp_project.pagination import auto_paginate
from erp_project.response_formatter import success_response, error_response

from .models import UnitOfMeasure, catalogItem
from .serializers import (
    UnitOfMeasureSerializer,
    UnitOfMeasureListSerializer,
    CatalogItemSerializer,
    CatalogItemListSerializer,
    CatalogItemSearchSerializer,
)


# ============================================================================
# Unit of Measure API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def uom_list(request):
    """
    List all Units of Measure or create a new one.
    
    GET /catalog/uom/
    - Returns list of all Units of Measure
    - Query params:
        - is_active: Filter by active status (true/false)
        - uom_type: Filter by UoM type (QUANTITY, WEIGHT, LENGTH, AREA, VOLUME)
        - search: Search by code or name
    
    POST /catalog/uom/
    - Create a new Unit of Measure
    - Request body: UnitOfMeasureSerializer fields
    """
    if request.method == 'GET':
        uoms = UnitOfMeasure.objects.all()
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            uoms = uoms.filter(is_active=is_active)
        
        uom_type = request.query_params.get('uom_type')
        if uom_type:
            uoms = uoms.filter(uom_type=uom_type.upper())
        
        search = request.query_params.get('search')
        if search:
            uoms = uoms.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
        serializer = UnitOfMeasureListSerializer(uoms, many=True)
        return success_response(
            data=serializer.data,
            message="Units of Measure retrieved successfully"
        )
    
    elif request.method == 'POST':
        serializer = UnitOfMeasureSerializer(data=request.data)
        if serializer.is_valid():
            try:
                uom = serializer.save()
                response_serializer = UnitOfMeasureSerializer(uom)
                return success_response(
                    data=response_serializer.data,
                    message="Unit of Measure created successfully",
                    status_code=status.HTTP_201_CREATED
                )
            except DjangoValidationError as e:
                return error_response(
                    message="Validation error",
                    errors=e.message_dict if hasattr(e, 'message_dict') else {'error': str(e)},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return error_response(
            message="Invalid data",
            data=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'PUT', 'DELETE'])
def uom_detail(request, pk):
    """
    Retrieve, update or delete a Unit of Measure.
    
    GET /catalog/uom/{id}/
    - Returns details of a specific Unit of Measure
    
    PUT /catalog/uom/{id}/
    - Update a Unit of Measure
    - Request body: UnitOfMeasureSerializer fields
    
    DELETE /catalog/uom/{id}/
    - Delete a Unit of Measure
    """
    uom = get_object_or_404(UnitOfMeasure, pk=pk)
    
    if request.method == 'GET':
        serializer = UnitOfMeasureSerializer(uom)
        return success_response(
            data=serializer.data,
            message="Unit of Measure retrieved successfully"
        )
    
    elif request.method == 'PUT':
        serializer = UnitOfMeasureSerializer(uom, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                updated_uom = serializer.save()
                response_serializer = UnitOfMeasureSerializer(updated_uom)
                return success_response(
                    data=response_serializer.data,
                    message="Unit of Measure updated successfully"
                )
            except DjangoValidationError as e:
                return error_response(
                    message="Validation error",
                    errors=e.message_dict if hasattr(e, 'message_dict') else {'error': str(e)},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return error_response(
            message="Invalid data",
            data=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    elif request.method == 'DELETE':
        uom.delete()
        return success_response(
            message="Unit of Measure deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )


# ============================================================================
# Catalog Item API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def catalog_item_list(request):
    """
    List all catalog items or create a new one.
    
    GET /catalog/items/
    - Returns list of all catalog items
    - Query params:
        - search: Search by name or code
        - name: Filter by name (case-insensitive partial match)
        - code: Filter by code (exact match)
    
    POST /catalog/items/
    - Create a new catalog item
    - Request body: CatalogItemSerializer fields
    """
    if request.method == 'GET':
        items = catalogItem.objects.all()
        
        # Apply filters
        search = request.query_params.get('search')
        if search:
            items = items.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        name = request.query_params.get('name')
        if name:
            items = items.filter(name__icontains=name)
        
        code = request.query_params.get('code')
        if code:
            items = items.filter(code__iexact=code)
        
        serializer = CatalogItemListSerializer(items, many=True)
        return success_response(
            data=serializer.data,
            message="Catalog items retrieved successfully"
        )
    
    elif request.method == 'POST':
        serializer = CatalogItemSerializer(data=request.data)
        if serializer.is_valid():
            try:
                item = serializer.save()
                response_serializer = CatalogItemSerializer(item)
                return success_response(
                    data=response_serializer.data,
                    message="Catalog item created successfully",
                    status_code=status.HTTP_201_CREATED
                )
            except DjangoValidationError as e:
                return error_response(
                    message="Validation error",
                    errors=e.message_dict if hasattr(e, 'message_dict') else {'error': str(e)},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return error_response(
            message="Invalid data",
            data=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'PUT', 'DELETE'])
def catalog_item_detail(request, pk):
    """
    Retrieve, update or delete a catalog item.
    
    GET /catalog/items/{id}/
    - Returns details of a specific catalog item
    
    PUT /catalog/items/{id}/
    - Update a catalog item
    - Request body: CatalogItemSerializer fields
    
    DELETE /catalog/items/{id}/
    - Delete a catalog item
    """
    item = get_object_or_404(catalogItem, pk=pk)
    
    if request.method == 'GET':
        serializer = CatalogItemSerializer(item)
        return success_response(
            data=serializer.data,
            message="Catalog item retrieved successfully"
        )
    
    elif request.method == 'PUT':
        serializer = CatalogItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                updated_item = serializer.save()
                response_serializer = CatalogItemSerializer(updated_item)
                return success_response(
                    data=response_serializer.data,
                    message="Catalog item updated successfully"
                )
            except DjangoValidationError as e:
                return error_response(
                    message="Validation error",
                    data=e.message_dict if hasattr(e, 'message_dict') else {'error': str(e)},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        return error_response(
            message="Invalid data",
            data=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    elif request.method == 'DELETE':
        item.delete()
        return success_response(
            message="Catalog item deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )


@api_view(['GET'])
def catalog_item_by_code(request, code):
    """
    Get a catalog item by its code.
    
    GET /catalog/items/by-code/{code}/
    - Returns catalog item with matching code (case-insensitive)
    """
    item = catalogItem.get_by_code(code)
    
    if item is None:
        return error_response(
            message=f"Catalog item with code '{code}' not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = CatalogItemSerializer(item)
    return success_response(
        data=serializer.data,
        message="Catalog item retrieved successfully"
    )


@api_view(['GET'])
def catalog_item_search(request):
    """
    Search catalog items by name.
    
    GET /catalog/items/search/
    - Query params:
        - q: Search term (required)
    - Returns items with names matching the search term (case-insensitive)
    """
    search_term = request.query_params.get('q')
    
    if not search_term:
        return error_response(
            message="Search term 'q' is required",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    items = catalogItem.search_by_name(search_term)
    serializer = CatalogItemSearchSerializer(items, many=True)
    
    return success_response(
        data=serializer.data,
        message=f"Found {items.count()} catalog items"
    )

