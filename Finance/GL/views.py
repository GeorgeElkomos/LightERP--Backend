"""
API Views for General Ledger models.
Provides REST API endpoints for segment types and segments.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from .models import XX_SegmentType, XX_Segment
from .serializers import (
    SegmentTypeSerializer,
    SegmentTypeListSerializer,
    SegmentSerializer,
    SegmentListSerializer,
    UsageDetailsSerializer,
    SegmentChildrenSerializer,
    FullPathSerializer,
)


# ============================================================================
# XX_SegmentType API Views
# ============================================================================

@api_view(['GET', 'POST'])
def segment_type_list(request):
    """
    List all segment types or create a new segment type.
    
    GET /segment-types/
    - Returns list of all segment types
    - Query params:
        - is_active: Filter by active status (true/false)
        - has_hierarchy: Filter by hierarchy support (true/false)
    
    POST /ent-types/
    - Create a new segment type
    - Request body: SegmentTypeSerializer fields
    """
    if request.method == 'GET':
        segment_types = XX_SegmentType.objects.all()
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            segment_types = segment_types.filter(is_active=is_active_bool)
        
        has_hierarchy = request.query_params.get('has_hierarchy')
        if has_hierarchy is not None:
            has_hierarchy_bool = has_hierarchy.lower() == 'true'
            segment_types = segment_types.filter(has_hierarchy=has_hierarchy_bool)
        
        serializer = SegmentTypeListSerializer(segment_types, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = SegmentTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def segment_type_detail(request, pk):
    """
    Retrieve, update, or delete a specific segment type.
    
    GET /segment-types/{id}/
    - Returns detailed information about a segment type
    
    PUT/PATCH /segment-types/{id}/
    - Update a segment type
    - Request body: SegmentTypeSerializer fields
    
    DELETE /segment-types/{id}/
    - Delete a segment type (if not used in transactions)
    """
    segment_type = get_object_or_404(XX_SegmentType, pk=pk)
    
    if request.method == 'GET':
        serializer = SegmentTypeSerializer(segment_type)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = SegmentTypeSerializer(segment_type, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            segment_type.delete()
            return Response(
                {'message': f'Segment type "{segment_type.segment_name}" deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
def segment_type_is_used_in_transactions(request, pk):
    """
    Check if a segment type is used in any transactions.
    
    GET /segment-types/{id}/is-used-in-transactions/
    
    Returns:
        {
            "is_used": true/false,
            "usage_details": ["detail 1", "detail 2", ...]
        }
    """
    segment_type = get_object_or_404(XX_SegmentType, pk=pk)
    is_used, usage_details = segment_type.is_used_in_transactions()
    
    serializer = UsageDetailsSerializer({
        'is_used': is_used,
        'usage_details': usage_details
    })
    return Response(serializer.data)


@api_view(['GET'])
def segment_type_can_delete(request, pk):
    """
    Check if a segment type can be safely deleted.
    
    GET /segment-types/{id}/can-delete/
    
    Returns:
        {
            "can_delete": true/false,
            "reason": "explanation if cannot delete"
        }
    """
    segment_type = get_object_or_404(XX_SegmentType, pk=pk)
    can_delete = segment_type.can_delete
    
    reason = None
    if not can_delete:
        is_used, usage_details = segment_type.is_used_in_transactions()
        if is_used:
            reason = "Segment type is used in transactions: " + "; ".join(usage_details)
        elif segment_type.values.exists():
            reason = f"Segment type has {segment_type.values.count()} segment value(s)"
    
    return Response({
        'can_delete': can_delete,
        'reason': reason
    })


@api_view(['POST'])
def segment_type_toggle_active(request, pk):
    """
    Toggle the active status of a segment type.
    
    POST /segment-types/{id}/toggle-active/
    
    Returns:
        {
            "id": 1,
            "segment_name": "Entity",
            "is_active": true/false
        }
    """
    segment_type = get_object_or_404(XX_SegmentType, pk=pk)
    segment_type.is_active = not segment_type.is_active
    segment_type.save()
    
    return Response({
        'id': segment_type.id,
        'segment_name': segment_type.segment_name,
        'is_active': segment_type.is_active
    })


@api_view(['GET'])
def segment_type_values(request, pk):
    """
    Get all segment values for a specific segment type.
    
    GET /segment-types/{id}/values/
    
    Query params:
        - is_active: Filter by active status (true/false)
        - node_type: Filter by node type (parent/sub_parent/child)
    """
    segment_type = get_object_or_404(XX_SegmentType, pk=pk)
    segments = segment_type.values.all()
    
    # Apply filters
    is_active = request.query_params.get('is_active')
    if is_active is not None:
        is_active_bool = is_active.lower() == 'true'
        segments = segments.filter(is_active=is_active_bool)
    
    node_type = request.query_params.get('node_type')
    if node_type:
        segments = segments.filter(node_type=node_type)
    
    serializer = SegmentListSerializer(segments, many=True)
    return Response(serializer.data)


# ============================================================================
# XX_Segment API Views
# ============================================================================

@api_view(['GET', 'POST'])
def segment_list(request):
    """
    List all segments or create a new segment.
    
    GET /segments/
    - Returns list of all segments
    - Query params:
        - segment_type: Filter by segment type ID
        - is_active: Filter by active status (true/false)
        - node_type: Filter by node type (parent/sub_parent/child)
        - parent_code: Filter by parent code
    
    POST /segments/
    - Create a new segment
    - Request body: SegmentSerializer fields
    """
    if request.method == 'GET':
        segments = XX_Segment.objects.select_related('segment_type').all()
        
        # Apply filters
        segment_type_id = request.query_params.get('segment_type')
        if segment_type_id:
            segments = segments.filter(segment_type_id=segment_type_id)
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            segments = segments.filter(is_active=is_active_bool)
        
        node_type = request.query_params.get('node_type')
        if node_type:
            segments = segments.filter(node_type=node_type)
        
        parent_code = request.query_params.get('parent_code')
        if parent_code:
            segments = segments.filter(parent_code=parent_code)
        
        serializer = SegmentListSerializer(segments, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = SegmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def segment_detail(request, pk):
    """
    Retrieve, update, or delete a specific segment.
    
    GET /segments/{id}/
    - Returns detailed information about a segment
    
    PUT/PATCH /segments/{id}/
    - Update a segment
    - Request body: SegmentSerializer fields
    
    DELETE /segments/{id}/
    - Delete a segment (if not used in transactions and has no children)
    """
    segment = get_object_or_404(XX_Segment.objects.select_related('segment_type'), pk=pk)
    
    if request.method == 'GET':
        serializer = SegmentSerializer(segment)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = SegmentSerializer(segment, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            segment.delete()
            return Response(
                {'message': f'Segment "{segment.code} - {segment.alias}" deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
def segment_parent(request, pk):
    """
    Get the parent segment of a specific segment.
    
    GET /segments/{id}/parent/
    
    Returns:
        - Parent segment details if exists
        - null if no parent
    """
    segment = get_object_or_404(XX_Segment, pk=pk)
    parent = segment.parent
    
    if parent:
        serializer = SegmentSerializer(parent)
        return Response(serializer.data)
    else:
        return Response(None)


@api_view(['GET'])
def segment_full_path(request, pk):
    """
    Get the full hierarchical path of a segment.
    
    GET /segments/{id}/full-path/
    
    Returns:
        {
            "full_path": "Parent > Child > GrandChild",
            "path_segments": ["Parent", "Child", "GrandChild"]
        }
    """
    segment = get_object_or_404(XX_Segment, pk=pk)
    full_path = segment.full_path
    path_segments = full_path.split(" > ")
    
    serializer = FullPathSerializer({
        'full_path': full_path,
        'path_segments': path_segments
    })
    return Response(serializer.data)


@api_view(['GET'])
def segment_children(request, pk):
    """
    Get all descendant segments (children, grandchildren, etc.) of a segment.
    
    GET /segments/{id}/children/
    
    Query params:
        - include_details: If true, return full segment objects; if false, return only codes
    
    Returns:
        {
            "children_codes": ["code1", "code2", ...],
            "children_count": 5
        }
        
        OR (if include_details=true):
        
        {
            "children": [{segment1}, {segment2}, ...],
            "children_count": 5
        }
    """
    segment = get_object_or_404(XX_Segment, pk=pk)
    children_codes = segment.get_all_children()
    
    include_details = request.query_params.get('include_details', 'false').lower() == 'true'
    
    if include_details:
        # Get full segment objects
        children_segments = XX_Segment.objects.filter(
            segment_type=segment.segment_type,
            code__in=children_codes
        )
        serializer = SegmentListSerializer(children_segments, many=True)
        return Response({
            'children': serializer.data,
            'children_count': len(children_codes)
        })
    else:
        # Return only codes
        serializer = SegmentChildrenSerializer({
            'children_codes': children_codes,
            'children_count': len(children_codes)
        })
        return Response(serializer.data)


@api_view(['GET'])
def segment_is_used_in_transactions(request, pk):
    """
    Check if a segment is used in any transactions.
    
    GET /segments/{id}/is-used-in-transactions/
    
    Returns:
        {
            "is_used": true/false,
            "usage_details": ["detail 1", "detail 2", ...]
        }
    """
    segment = get_object_or_404(XX_Segment, pk=pk)
    is_used, usage_details = segment.is_used_in_transactions()
    
    serializer = UsageDetailsSerializer({
        'is_used': is_used,
        'usage_details': usage_details
    })
    return Response(serializer.data)


@api_view(['GET'])
def segment_can_delete(request, pk):
    """
    Check if a segment can be safely deleted.
    
    GET /segments/{id}/can-delete/
    
    Returns:
        {
            "can_delete": true/false,
            "reason": "explanation if cannot delete"
        }
    """
    segment = get_object_or_404(XX_Segment, pk=pk)
    can_delete = segment.can_delete
    
    reason = None
    if not can_delete:
        is_used, usage_details = segment.is_used_in_transactions()
        if is_used:
            reason = "Segment is used in transactions: " + "; ".join(usage_details)
        else:
            children_count = XX_Segment.objects.filter(
                segment_type=segment.segment_type,
                parent_code=segment.code
            ).count()
            if children_count > 0:
                reason = f"Segment has {children_count} child segment(s)"
    
    return Response({
        'can_delete': can_delete,
        'reason': reason
    })


@api_view(['POST'])
def segment_toggle_active(request, pk):
    """
    Toggle the active status of a segment.
    
    POST /segments/{id}/toggle-active/
    
    Returns:
        {
            "id": 1,
            "code": "100",
            "alias": "Main Entity",
            "is_active": true/false
        }
    """
    segment = get_object_or_404(XX_Segment, pk=pk)
    segment.is_active = not segment.is_active
    segment.save()
    
    return Response({
        'id': segment.id,
        'code': segment.code,
        'alias': segment.alias,
        'is_active': segment.is_active
    })
