"""
API Views for Position and Grade models.
Provides REST API endpoints for managing positions and grades with date tracking.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from HR.work_structures.models import Position, BusinessGroup
from HR.work_structures.services.position_service import PositionService
from HR.work_structures.serializers import (
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
        - department: Filter by department code or name
        - grade: Filter by grade code or name
        - location: Filter by location code or name
        - code: Filter by position code
        - name: Filter by position name
        - search: Search across code and name
    
    POST /hr/positions/
    - Create a new position
    - Request body: PositionCreateSerializer fields
    """
    if request.method == 'GET':
        positions = Position.objects.scoped(request.user).active()
        positions = positions.select_related('department', 'location', 'grade', 'reports_to')
        
        # Apply filters
        # Note: Status is computed from dates, so filtering handled by .active() above
        # If user wants all records (active + inactive), they should use include_inactive param
        status_param = request.query_params.get('status')
        if status_param and status_param.lower() == 'inactive':
            # Get all records, then filter out active ones (return inactive only)
            from django.utils import timezone
            today = timezone.now().date()
            positions = Position.objects.scoped(request.user).exclude(
                Q(effective_start_date__lte=today) &
                (Q(effective_end_date__gt=today) | Q(effective_end_date__isnull=True))
            )
        
        # Filter by department (name or code)
        department_filter = request.query_params.get('department')
        if department_filter:
            positions = positions.filter(
                Q(department__name__icontains=department_filter) |
                Q(department__code__icontains=department_filter)
            )
        
        # Filter by grade (name or code)
        grade_filter = request.query_params.get('grade')
        if grade_filter:
            positions = positions.filter(
                Q(grade__name__icontains=grade_filter) |
                Q(grade__code__icontains=grade_filter)
            )
        
        # Filter by location (name or code)
        location_filter = request.query_params.get('location')
        if location_filter:
            positions = positions.filter(
                Q(location__name__icontains=location_filter) |
                Q(location__code__icontains=location_filter)
            )
            
        # Apply standard code/name/search filters
        positions = positions.filter_by_search_params(request.query_params)
        
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
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to create position: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        print(f"DEBUG POSITION ERRORS: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_position')
def position_detail(request, pk):
    """
    Retrieve, update, or delete a specific position.
    
    GET /hr/positions/{id}/
    - Returns detailed information about a position
    
    PUT/PATCH /hr/positions/{id}/
    - Update a position (creates new version with date tracking)
    - Request body: PositionUpdateSerializer fields
    
    DELETE /hr/positions/{id}/
    - Deactivate a position (end-dates it and sets status to inactive)
    - Optional body: {"effective_end_date": "YYYY-MM-DD"} (defaults to today)
    """
    try:
        position = Position.objects.scoped(request.user).select_related(
            'department', 'location', 'grade', 'reports_to'
        ).get(pk=pk)
    except Position.DoesNotExist:
        # Check if position exists at all
        if Position.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this position. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Position not found.'},
            status=status.HTTP_404_NOT_FOUND
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
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to update position: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            effective_end_date = request.data.get('effective_end_date') if request.data else None
            if effective_end_date:
                from django.utils.dateparse import parse_date
                effective_end_date = parse_date(effective_end_date)
            
            deactivated_position = PositionService.deactivate_position(request.user, pk, effective_end_date)
            return Response(
                {
                    'message': 'Position deactivated successfully',
                    'position': PositionSerializer(deactivated_position).data
                },
                status=status.HTTP_200_OK
            )
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@require_page_action('hr_position', 'view')
def position_history(request, pk):
    """
    Get all historical versions of a position.
    
    GET /hr/positions/{id}/history/
    - Returns all versions of a position (date tracked)
    """
    try:
        position = Position.objects.scoped(request.user).get(pk=pk)
    except Position.DoesNotExist:
        # Check if position exists at all
        if Position.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this position. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Position not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all versions with the same code within the same scope (business_group)
    versions = Position.objects.filter(
        code=position.code,
        **position.get_version_scope_filters()
    ).order_by('-effective_start_date')
    
    serializer = PositionSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@require_page_action('hr_position', 'view')
def position_hierarchy(request):
    """
    Get position reporting hierarchy for a business group.
    
    GET /hr/positions/hierarchy/?bg={id_or_code}
    - Returns nested position reporting structure
    - Required query param: bg (business group ID or code)
    """
    bg_param = request.query_params.get('bg')
    
    if not bg_param:
        return Response(
            {'error': 'bg parameter (ID or code) required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Try numeric ID first
        if bg_param.isdigit():
            bg = BusinessGroup.objects.get(id=int(bg_param))
        else:
            # Try code (case insensitive)
            bg = BusinessGroup.objects.active().filter(code__iexact=bg_param).first()
            if not bg:
                raise BusinessGroup.DoesNotExist
        
        hierarchy = PositionService.get_position_hierarchy(request.user, bg.id)
        return Response(hierarchy, status=status.HTTP_200_OK)
    except BusinessGroup.DoesNotExist:
        return Response(
            {'error': f"Business Group '{bg_param}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except PermissionDenied as e:
        return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f"Failed to retrieve position hierarchy: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@require_page_action('hr_position', 'view')
def position_direct_reports(request, pk):
    """
    Get all positions that directly report to this position.
    
    GET /hr/positions/{id}/direct-reports/
    - Returns list of positions that have this position as reports_to
    - Only returns active positions by default
    """
    try:
        position = Position.objects.scoped(request.user).get(pk=pk)
    except Position.DoesNotExist:
        # Check if position exists at all
        if Position.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this position. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Position not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all positions that report to this one
    direct_reports = Position.objects.filter(
        reports_to=position
    ).select_related('department', 'location', 'grade').order_by('name')
    
    serializer = PositionSerializer(direct_reports, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
