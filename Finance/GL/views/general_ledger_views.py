"""
General Ledger API Views
Handles list and detail operations for general ledger entries.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from erp_project.pagination import auto_paginate

from Finance.GL.models import GeneralLedger, JournalEntry


@api_view(['GET'])
@auto_paginate
def general_ledger_list(request):
    """
    List all general ledger entries with optional filtering.
    
    GET /general-ledger/
    
    Query Parameters:
    Basic Filters:
    - currency_id: Filter by currency
    - date_from: Filter entries from this date (YYYY-MM-DD) - filters by submitted_date
    - date_to: Filter entries to this date (YYYY-MM-DD) - filters by submitted_date
    - created_date_from: Filter by journal entry creation date from (YYYY-MM-DD)
    - created_date_to: Filter by journal entry creation date to (YYYY-MM-DD)
    
    Segment Filters (3 modes):
    
    Mode 1: Single Segment Filter
    - segment_type_id: ID of segment type
    - segment_code: Code of segment value
    Example: ?segment_type_id=1&segment_code=100
    (Finds GL entries using Entity "100")
    
    Mode 2: Multiple Segments Filter (AND logic)
    - segments: JSON array of segment filters (ALL must match)
    Example: ?segments=[{"segment_type_id":1,"segment_code":"100"},{"segment_type_id":2,"segment_code":"5000"}]
    (Finds GL entries using Entity "100" AND Account "5000")
    
    Mode 3: Any Segments Filter (OR logic)
    - segments_any: JSON array of segment filters (ANY can match)
    Example: ?segments_any=[{"segment_type_id":1,"segment_code":"100"},{"segment_type_id":1,"segment_code":"200"}]
    (Finds GL entries using Entity "100" OR Entity "200")
    
    Returns:
        200: List of general ledger entries
        400: Invalid filter parameters
    """
    try:
        import json
        
        queryset = GeneralLedger.objects.select_related('JournalEntry', 'JournalEntry__currency').all()
        
        # ====================================================================
        # Segment Filtering
        # ====================================================================
        
        # Mode 1: Single segment filter
        if 'segment_type_id' in request.query_params and 'segment_code' in request.query_params:
            try:
                segment_type_id = int(request.query_params['segment_type_id'])
                segment_code = request.query_params['segment_code']
                
                queryset = GeneralLedger.filter_by_segment(segment_type_id, segment_code)
            except ValueError:
                return Response(
                    {'error': 'segment_type_id must be a valid integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Mode 2: Multiple segments filter (AND logic)
        elif 'segments' in request.query_params:
            try:
                segments_param = request.query_params['segments']
                segments_list = json.loads(segments_param)
                
                # Validate format
                if not isinstance(segments_list, list):
                    return Response(
                        {'error': 'segments must be a JSON array'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Convert to tuple format for filter_by_segments
                segment_tuples = []
                for seg in segments_list:
                    if 'segment_type_id' not in seg or 'segment_code' not in seg:
                        return Response(
                            {'error': 'Each segment must have segment_type_id and segment_code'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    segment_tuples.append((int(seg['segment_type_id']), seg['segment_code']))
                
                queryset = GeneralLedger.filter_by_segments(segment_tuples)
                
            except json.JSONDecodeError:
                return Response(
                    {'error': 'segments must be valid JSON'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except (ValueError, KeyError) as e:
                return Response(
                    {'error': f'Invalid segments format: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Mode 3: Any segments filter (OR logic)
        elif 'segments_any' in request.query_params:
            try:
                segments_param = request.query_params['segments_any']
                segments_list = json.loads(segments_param)
                
                # Validate format
                if not isinstance(segments_list, list):
                    return Response(
                        {'error': 'segments_any must be a JSON array'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Convert to tuple format for filter_by_any_segment
                segment_tuples = []
                for seg in segments_list:
                    if 'segment_type_id' not in seg or 'segment_code' not in seg:
                        return Response(
                            {'error': 'Each segment must have segment_type_id and segment_code'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    segment_tuples.append((int(seg['segment_type_id']), seg['segment_code']))
                
                queryset = GeneralLedger.filter_by_any_segment(segment_tuples)
                
            except json.JSONDecodeError:
                return Response(
                    {'error': 'segments_any must be valid JSON'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except (ValueError, KeyError) as e:
                return Response(
                    {'error': f'Invalid segments_any format: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # ====================================================================
        # Basic Filters
        # ====================================================================
        
        if 'currency_id' in request.query_params:
            queryset = queryset.filter(JournalEntry__currency_id=request.query_params['currency_id'])
        
        # Filter by posted date (submitted_date)
        if 'date_from' in request.query_params:
            queryset = queryset.filter(submitted_date__gte=request.query_params['date_from'])
        
        if 'date_to' in request.query_params:
            queryset = queryset.filter(submitted_date__lte=request.query_params['date_to'])
        
        # Filter by journal entry creation date
        if 'created_date_from' in request.query_params:
            queryset = queryset.filter(JournalEntry__date__gte=request.query_params['created_date_from'])
        
        if 'created_date_to' in request.query_params:
            queryset = queryset.filter(JournalEntry__date__lte=request.query_params['created_date_to'])
        
        # ====================================================================
        # Order and Return Results
        # ====================================================================
        
        # Order by posted date descending
        queryset = queryset.order_by('-submitted_date', '-id')
        
        entries = [
            {
                'id': gl.id,
                'journal_entry_id': gl.JournalEntry.id,
                'created_date': gl.JournalEntry.date,
                'currency_code': gl.JournalEntry.currency.code,
                'memo': gl.JournalEntry.memo,
                'posted': gl.JournalEntry.posted,
                'posted_date': gl.submitted_date,
                'is_balanced': gl.JournalEntry.is_balanced(),
                'total_debit': str(gl.JournalEntry.get_total_debit()),
                'total_credit': str(gl.JournalEntry.get_total_credit()),
                'line_count': gl.JournalEntry.lines.count()
            }
            for gl in queryset
        ]
        
        return Response({
            'count': len(entries),
            'results': entries
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def general_ledger_detail(request, pk):
    """
    Get detailed information about a general ledger entry.
    
    GET /general-ledger/{id}/
    
    Returns:
        200: General ledger entry with all details including journal entry and lines
        404: Entry not found
    """
    gl = get_object_or_404(
        GeneralLedger.objects.select_related('JournalEntry', 'JournalEntry__currency'),
        pk=pk
    )
    
    try:
        
        entry = gl.JournalEntry
        
        response_data = {
            # General Ledger Information
            'general_ledger': {
                'id': gl.id,
                'submitted_date': gl.submitted_date,
                'posted_date': gl.submitted_date,  # Alias for clarity
            },
            
            # Journal Entry Information
            'journal_entry': {
                'id': entry.id,
                'date': entry.date,
                'created_date': entry.date,  # Alias for clarity
                'currency_id': entry.currency.id,
                'currency_code': entry.currency.code,
                'currency_name': entry.currency.name,
                'memo': entry.memo,
                'posted': entry.posted,
                'is_balanced': entry.is_balanced(),
                'total_debit': str(entry.get_total_debit()),
                'total_credit': str(entry.get_total_credit()),
                'balance_difference': str(entry.get_balance_difference()),
            },
            
            # Journal Lines
            'lines': [
                {
                    'id': line.id,
                    'amount': str(line.amount),
                    'type': line.type,
                    'segment_combination_id': line.segment_combination.id,
                    'segments': line.segment_combination.get_combination_display(),
                    'segment_details': [
                        {
                            'segment_type_id': detail.segment_type.id,
                            'segment_type_name': detail.segment_type.segment_name,
                            'segment_code': detail.segment.code,
                            'segment_alias': detail.segment.alias
                        }
                        for detail in line.segment_combination.details.all()
                    ]
                }
                for line in entry.lines.all()
            ]
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
