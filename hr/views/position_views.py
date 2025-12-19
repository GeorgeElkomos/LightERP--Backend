"""
API Views for Position and Grade models.
Provides REST API endpoints for managing positions and grades with date tracking.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from hr.models import Position
from hr.services.position_service import PositionService
from hr.serializers import (
    PositionSerializer,
    PositionCreateSerializer,
    PositionUpdateSerializer
)


@api_view(['GET', 'POST'])
@require_page_action('hr_position')
@auto_paginate
def position_list(request):
    """
    List all active positions or create a new position.
    
    GET /hr/positions/
    - Returns list of currently active positions (scoped by user's business groups)
    - Query params:
        - status: Filter by status (active/inactive)
        - department: Filter by department ID
        - grade: Filter by grade ID
        - location: Filter by location ID
        - search: Search across code and name
    
    POST /hr/positions/
    - Create a new position
    - Request body: PositionCreateSerializer fields
    """
    if request.method == 'GET':
        positions = Position.objects.scoped(request.user).currently_active()
        positions = positions.select_related('department', 'location', 'grade', 'reports_to')
        
        # Apply filters
        status_param = request.query_params.get('status')
        if status_param:
            positions = positions.filter(status=status_param)
        
        department_id = request.query_params.get('department')
        if department_id:
            positions = positions.filter(department_id=department_id)
        
        grade_id = request.query_params.get('grade')
        if grade_id:
            positions = positions.filter(grade_id=grade_id)
        
        location_id = request.query_params.get('location')
        if location_id:
            positions = positions.filter(location_id=location_id)
        
        search = request.query_params.get('search')
        if search:
            positions = positions.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
        serializer = PositionSerializer(positions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = PositionCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            dto = serializer.to_dto()
            try:
                position = PositionService.create_position(request.user, dto)
                return Response(
                    PositionSerializer(position).data,
                    status=status.HTTP_201_CREATED
                )
            except (ValidationError, PermissionDenied) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to create position: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH'])
@require_page_action('hr_position')
def position_detail(request, pk):
    """
    Retrieve or update a specific position.
    
    GET /hr/positions/{id}/
    - Returns detailed information about a position
    
    PUT/PATCH /hr/positions/{id}/
    - Update a position (creates new version with date tracking)
    - Request body: PositionUpdateSerializer fields
    """
    position = get_object_or_404(
        Position.objects.scoped(request.user).select_related(
            'department', 'location', 'grade', 'reports_to'
        ),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = PositionSerializer(position)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = PositionUpdateSerializer(data=request.data)
        if serializer.is_valid():
            dto = serializer.to_dto(code=position.code)
            try:
                updated_position = PositionService.update_position(request.user, dto)
                return Response(
                    PositionSerializer(updated_position).data,
                    status=status.HTTP_200_OK
                )
            except (ValidationError, PermissionDenied) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to update position: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_position', 'view')
def position_history(request, pk):
    """
    Get all historical versions of a position.
    
    GET /hr/positions/{id}/history/
    - Returns all versions of a position (date tracked)
    """
    position = get_object_or_404(Position, pk=pk)
    
    # Get all versions with the same code
    versions = Position.objects.filter(
        code=position.code
    ).order_by('-effective_start_date')
    
    serializer = PositionSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@require_page_action('hr_position', 'view')
def position_hierarchy(request):
    """
    Get position reporting hierarchy for a business group.
    
    GET /hr/positions/hierarchy/?bg={id}
    - Returns nested position reporting structure
    - Required query param: bg (business group ID)
    """
    bg_id = request.query_params.get('bg')
    
    if not bg_id:
        return Response(
            {'error': 'bg parameter required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        hierarchy = PositionService.get_position_hierarchy(request.user, int(bg_id))
        return Response(hierarchy, status=status.HTTP_200_OK)
    except (ValidationError, PermissionDenied) as e:
        return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response(
            {'error': f"Failed to retrieve position hierarchy: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )
