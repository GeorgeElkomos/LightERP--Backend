from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from datetime import date

from HR.work_structures.services.position_service import PositionService
from HR.work_structures.serializers.position_serializers import (
    PositionReadSerializer,
    PositionCreateSerializer,
    PositionUpdateSerializer
)
from HR.work_structures.models import Position
from core.job_roles.decorators import require_page_action
from django.utils.dateparse import parse_date
from erp_project.pagination import auto_paginate


@api_view(['GET', 'POST'])
@require_page_action('hr_position')
@auto_paginate
def position_list(request):
    """
    List all positions or create a new position.
    
    GET /work_structures/positions/
    - Filters: organization (ID), job (ID), location (ID)
    - Search: ?search=query (searches code, position_title__name)
    - Date Filter: ?as_of_date=YYYY-MM-DD or 'ALL' (defaults to today)

    POST /work_structures/positions/
    - Create new position using DTO pattern
    """
    if request.method == 'GET':
        as_of_date_param = request.query_params.get('as_of_date')
        if as_of_date_param:
            if as_of_date_param == 'ALL':
                as_of_date = 'ALL'
            else:
                as_of_date = parse_date(as_of_date_param)
        else:
            as_of_date = 'ALL'

        filters = {
            'organization_id': request.query_params.get('organization'),
            'job_id': request.query_params.get('job'),
            'location_id': request.query_params.get('location'),
            'search': request.query_params.get('search'),
            'as_of_date': as_of_date
        }
        
        # Use service to get base queryset, then apply status filtering in view
        positions = PositionService.list_positions(filters)
            
        serializer = PositionReadSerializer(positions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = PositionCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    position = PositionService.create(request.user, dto)
                read_serializer = PositionReadSerializer(position)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_position')
def position_detail(request, pk):
    """
    Retrieve, update or deactivate a position.
    """
    # For detail view, we want to retrieve the specific version regardless of effective date
    position = get_object_or_404(Position.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = PositionReadSerializer(position)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        # Add position_id to data for serializer
        data['position_id'] = position.id
            
        serializer = PositionUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_position = PositionService.update(request.user, dto)
                read_serializer = PositionReadSerializer(updated_position)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            effective_end_date = request.data.get('effective_end_date')
            if effective_end_date:
                effective_end_date = date.fromisoformat(effective_end_date)
                
            with transaction.atomic():
                PositionService.deactivate(request.user, position.id, effective_end_date)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_position', action_name='view')
def position_versions(request, pk):
    """
    Get all versions of a position by ID (retrieves all versions sharing the same code).
    """
    try:
        versions = PositionService.get_position_versions(pk)
    except ValidationError as e:
        return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)

    serializer = PositionReadSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
