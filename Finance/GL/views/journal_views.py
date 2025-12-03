"""
Journal Entry API Views
Handles create, update, and delete operations for journal entries with their lines.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from decimal import Decimal

from Finance.GL.models import (
    JournalEntry,
    JournalLine,
    XX_Segment_combination,
    Currency,
)


@api_view(['POST', 'PUT'])
def journal_entry_create_update(request):
    """
    Create or update a journal entry with its lines.
    
    POST /journal-entries/ - Create new entry (no id in body)
    PUT /journal-entries/ - Update existing entry (id required in body)
    
    Request Body:
    {
        "id": 123,  // Optional for create, required for update
        "date": "2025-12-03",
        "currency_id": 1,
        "memo": "Payment for services",
        "lines": [
            {
                "id": 456,  // Optional - if present, update; if absent, create
                "amount": "1500.00",
                "type": "DEBIT",
                "segments": [
                    {"segment_type_id": 1, "segment_code": "100"},
                    {"segment_type_id": 2, "segment_code": "5000"},
                    {"segment_type_id": 3, "segment_code": "PROJ1"}
                ]
            },
            {
                "amount": "1500.00",
                "type": "CREDIT",
                "segments": [
                    {"segment_type_id": 1, "segment_code": "100"},
                    {"segment_type_id": 2, "segment_code": "6000"}
                ]
            }
        ]
    }
    
    Returns:
        201/200: Created/Updated journal entry with all details
        400: Validation errors
        404: Entry not found (for update)
    """
    try:
        entry_id = request.data.get('id')
        is_update = entry_id is not None
        
        # Validate required fields
        if not request.data.get('date'):
            return Response(
                {'error': 'date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.data.get('currency_id'):
            return Response(
                {'error': 'currency_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.data.get('lines'):
            return Response(
                {'error': 'lines array is required and cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get currency
        try:
            currency = Currency.objects.get(id=request.data['currency_id'])
        except Currency.DoesNotExist:
            return Response(
                {'error': f"Currency with id {request.data['currency_id']} does not exist"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use atomic transaction to ensure data consistency
        with transaction.atomic():
            if is_update:
                # UPDATE MODE
                entry = get_object_or_404(JournalEntry, pk=entry_id)
                
                # Check if posted
                if entry.posted:
                    return Response(
                        {'error': f'Cannot update Journal Entry #{entry_id} because it is already posted'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Update entry fields
                entry.date = request.data['date']
                entry.currency = currency
                entry.memo = request.data.get('memo', '')
                entry.save()
                
                # Handle lines update
                existing_line_ids = set(entry.lines.values_list('id', flat=True))
                provided_line_ids = set()
                
                for line_data in request.data['lines']:
                    line_id = line_data.get('id')
                    
                    if line_id:
                        # Update existing line
                        provided_line_ids.add(line_id)
                        
                        try:
                            line = JournalLine.objects.get(id=line_id, entry=entry)
                            
                            # Get or create segment combination
                            segment_list = [
                                (seg['segment_type_id'], seg['segment_code'])
                                for seg in line_data['segments']
                            ]
                            combo_id = XX_Segment_combination.get_combination_id(segment_list)
                            
                            # Update line
                            line.amount = Decimal(str(line_data['amount']))
                            line.type = line_data['type']
                            line.segment_combination_id = combo_id
                            line.save()
                            
                        except JournalLine.DoesNotExist:
                            return Response(
                                {'error': f"Journal Line #{line_id} does not belong to this entry"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        # Create new line
                        segment_list = [
                            (seg['segment_type_id'], seg['segment_code'])
                            for seg in line_data['segments']
                        ]
                        combo_id = XX_Segment_combination.get_combination_id(segment_list)
                        
                        JournalLine.objects.create(
                            entry=entry,
                            amount=Decimal(str(line_data['amount'])),
                            type=line_data['type'],
                            segment_combination_id=combo_id
                        )
                
                # Delete lines that were not provided
                lines_to_delete = existing_line_ids - provided_line_ids
                if lines_to_delete:
                    JournalLine.objects.filter(id__in=lines_to_delete).delete()
                
                response_status = status.HTTP_200_OK
                message = f"Journal Entry #{entry.id} updated successfully"
                
            else:
                # CREATE MODE
                entry = JournalEntry.objects.create(
                    date=request.data['date'],
                    currency=currency,
                    memo=request.data.get('memo', '')
                )
                
                # Create lines
                for line_data in request.data['lines']:
                    # Get or create segment combination
                    segment_list = [
                        (seg['segment_type_id'], seg['segment_code'])
                        for seg in line_data['segments']
                    ]
                    combo_id = XX_Segment_combination.get_combination_id(segment_list)
                    
                    JournalLine.objects.create(
                        entry=entry,
                        amount=Decimal(str(line_data['amount'])),
                        type=line_data['type'],
                        segment_combination_id=combo_id
                    )
                
                response_status = status.HTTP_201_CREATED
                message = f"Journal Entry #{entry.id} created successfully"
            
            # Refresh entry to get all related data
            entry.refresh_from_db()
            
            # Build response
            response_data = {
                'message': message,
                'journal_entry': {
                    'id': entry.id,
                    'date': entry.date,
                    'currency_id': entry.currency.id,
                    'currency_code': entry.currency.code,
                    'memo': entry.memo,
                    'posted': entry.posted,
                    'is_balanced': entry.is_balanced(),
                    'total_debit': str(entry.get_total_debit()),
                    'total_credit': str(entry.get_total_credit()),
                    'balance_difference': str(entry.get_balance_difference()),
                    'lines': [
                        {
                            'id': line.id,
                            'amount': str(line.amount),
                            'type': line.type,
                            'segment_combination_id': line.segment_combination.id,
                            'segments': line.segment_combination.get_combination_display()
                        }
                        for line in entry.lines.all()
                    ]
                }
            }
            
            return Response(response_data, status=response_status)
    
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


@api_view(['DELETE'])
def journal_entry_delete(request, pk):
    """
    Delete a journal entry and all its lines.
    
    DELETE /journal-entries/{id}/
    
    Validates:
    - Entry exists
    - Entry is not posted to General Ledger
    
    Returns:
        204: Successfully deleted
        400: Cannot delete (posted)
        404: Entry not found
    """
    entry = get_object_or_404(JournalEntry, pk=pk)
    
    try:
        # Check if posted
        if entry.posted:
            return Response(
                {
                    'error': f'Cannot delete Journal Entry #{pk} because it is posted to the General Ledger',
                    'detail': 'Posted entries cannot be deleted for accounting integrity. Consider creating a reversing entry instead.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete entry (lines will be cascade deleted)
        entry_id = entry.id
        entry.delete()
        
        return Response(
            {'message': f'Journal Entry #{entry_id} and all its lines deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
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


@api_view(['GET'])
def journal_entry_detail(request, pk):
    """
    Get detailed information about a journal entry.
    
    GET /journal-entries/{id}/
    
    Returns:
        200: Journal entry with all details
        404: Entry not found
    """
    entry = get_object_or_404(JournalEntry, pk=pk)
    
    try:
        
        response_data = {
            'id': entry.id,
            'date': entry.date,
            'currency_id': entry.currency.id,
            'currency_code': entry.currency.code,
            'currency_name': entry.currency.name,
            'memo': entry.memo,
            'posted': entry.posted,
            'is_balanced': entry.is_balanced(),
            'total_debit': str(entry.get_total_debit()),
            'total_credit': str(entry.get_total_credit()),
            'balance_difference': str(entry.get_balance_difference()),
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


@api_view(['GET'])
def journal_entry_list(request):
    """
    List all journal entries with optional filtering.
    
    GET /journal-entries/
    
    Query Parameters:
    Basic Filters:
    - posted: Filter by posted status (true/false)
    - currency_id: Filter by currency
    - date_from: Filter entries from this date (YYYY-MM-DD)
    - date_to: Filter entries to this date (YYYY-MM-DD)
    
    Segment Filters (3 modes):
    
    Mode 1: Single Segment Filter
    - segment_type_id: ID of segment type
    - segment_code: Code of segment value
    Example: ?segment_type_id=1&segment_code=100
    (Finds entries using Entity "100")
    
    Mode 2: Multiple Segments Filter (AND logic)
    - segments: JSON array of segment filters (ALL must match)
    Example: ?segments=[{"segment_type_id":1,"segment_code":"100"},{"segment_type_id":2,"segment_code":"5000"}]
    (Finds entries using Entity "100" AND Account "5000")
    
    Mode 3: Any Segments Filter (OR logic)
    - segments_any: JSON array of segment filters (ANY can match)
    Example: ?segments_any=[{"segment_type_id":1,"segment_code":"100"},{"segment_type_id":1,"segment_code":"200"}]
    (Finds entries using Entity "100" OR Entity "200")
    
    Returns:
        200: List of journal entries
        400: Invalid filter parameters
    """
    try:
        import json
        
        queryset = JournalEntry.objects.all()
        
        # ====================================================================
        # Segment Filtering
        # ====================================================================
        
        # Mode 1: Single segment filter
        if 'segment_type_id' in request.query_params and 'segment_code' in request.query_params:
            try:
                segment_type_id = int(request.query_params['segment_type_id'])
                segment_code = request.query_params['segment_code']
                
                queryset = JournalEntry.filter_by_segment(segment_type_id, segment_code)
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
                
                queryset = JournalEntry.filter_by_segments(segment_tuples)
                
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
                
                queryset = JournalEntry.filter_by_any_segment(segment_tuples)
                
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
        
        if 'posted' in request.query_params:
            posted = request.query_params['posted'].lower() == 'true'
            queryset = queryset.filter(posted=posted)
        
        if 'currency_id' in request.query_params:
            queryset = queryset.filter(currency_id=request.query_params['currency_id'])
        
        if 'date_from' in request.query_params:
            queryset = queryset.filter(date__gte=request.query_params['date_from'])
        
        if 'date_to' in request.query_params:
            queryset = queryset.filter(date__lte=request.query_params['date_to'])
        
        # ====================================================================
        # Order and Return Results
        # ====================================================================
        
        # Order by date descending
        queryset = queryset.order_by('-date', '-id')
        
        entries = [
            {
                'id': entry.id,
                'date': entry.date,
                'currency_code': entry.currency.code,
                'memo': entry.memo,
                'posted': entry.posted,
                'is_balanced': entry.is_balanced(),
                'total_debit': str(entry.get_total_debit()),
                'total_credit': str(entry.get_total_credit()),
                'line_count': entry.lines.count()
            }
            for entry in queryset
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


@api_view(['POST'])
def journal_entry_post(request, pk):
    """
    Post a journal entry to the General Ledger.
    
    POST /journal-entries/{id}/post/
    
    Validates:
    - Entry exists
    - Entry is not already posted
    - Entry is balanced
    
    Returns:
        200: Successfully posted
        400: Validation errors
        404: Entry not found
    """
    entry = get_object_or_404(JournalEntry, pk=pk)
    
    try:
        # Post the entry (this will validate and create GL entry)
        gl_entry = entry.post()
        
        return Response({
            'message': f'Journal Entry #{entry.id} posted successfully',
            'journal_entry_id': entry.id,
            'general_ledger_id': gl_entry.id,
            'submitted_date': gl_entry.submitted_date
        }, status=status.HTTP_200_OK)
    
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
