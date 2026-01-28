from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from HR.work_structures.services.location_service import LocationService
from HR.work_structures.serializers.location_serializer import (
    LocationReadSerializer,
    LocationCreateSerializer,
    LocationUpdateSerializer
)
from HR.work_structures.models import Location
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate

@api_view(['GET', 'POST'])
@require_page_action('hr_location')
@auto_paginate
def location_list(request):
    """
    List all locations or create a new location.
    
    GET /work-structures/locations/
    - Filters: business_group (ID), country (ID), city (ID)
    - Search: ?search=query (searches name, description)

    POST /work-structures/locations/
    - Create new location using DTO pattern
    """
    if request.method == 'GET':
        # Prepare filters from request params
        filters = {
            'business_group': request.query_params.get('business_group'),
            'country_id': request.query_params.get('country'),
            'city_id': request.query_params.get('city'),
            'search': request.query_params.get('search'),
            'status': request.query_params.get('status', 'ALL') # Default to 'ALL'
        }
        
        # Get data via service
        locations = LocationService.list_locations(filters)
            
        serializer = LocationReadSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = LocationCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    location = LocationService.create(request.user, dto)
                read_serializer = LocationReadSerializer(location)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                # Return raw error detail to match tests expectation
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_location')
def location_detail(request, pk):
    """
    Retrieve, update or deactivate a location.
    
    GET /work-structures/locations/<pk>/
    PUT/PATCH /work-structures/locations/<pk>/
    DELETE /work-structures/locations/<pk>/
    """
    location = get_object_or_404(Location, pk=pk)
    
    if request.method == 'GET':
        serializer = LocationReadSerializer(location)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['location_id'] = location.id
            
        serializer = LocationUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_location = LocationService.update(request.user, dto)
                read_serializer = LocationReadSerializer(updated_location)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                LocationService.deactivate(request.user, location.id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
