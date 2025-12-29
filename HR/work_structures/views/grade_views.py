"""
API Views for Grade and GradeRate models.
Provides REST API endpoints for managing grades and grade rate levels with date tracking.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from HR.work_structures.models import Grade, GradeRate, GradeRateType
from HR.work_structures.services.grade_service import GradeService
from HR.work_structures.serializers import (
    GradeSerializer,
    GradeCreateSerializer,
    GradeUpdateSerializer,
    GradeRateSerializer,
    GradeRateCreateSerializer
)


@api_view(['GET', 'POST'])
@require_page_action('hr_grade')
@auto_paginate
def grade_list(request):
    """
    List all active grades or create a new grade.
    
    GET /hr/grades/
    - Returns list of currently active grades (scoped by user's business groups)
    - Query params:
        - business_group: Filter by business group code or name
        - code: Filter by grade code
        - name: Filter by grade name
        - search: Search across code and name
    
    POST /hr/grades/
    - Create a new grade
    - Request body: GradeCreateSerializer fields
    """
    if request.method == 'GET':
        grades = Grade.objects.scoped(request.user).active()
        grades = grades.select_related('business_group').prefetch_related('rate_levels')
        
        # Apply filters
        business_group_filter = request.query_params.get('business_group')
        if business_group_filter:
            grades = grades.filter(
                Q(business_group__name__icontains=business_group_filter) |
                Q(business_group__code__icontains=business_group_filter)
            )
        
        # Apply standard code/name/search filters
        grades = grades.filter_by_search_params(request.query_params)
        
        serializer = GradeSerializer(grades, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = GradeCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            dto = serializer.to_dto()
            try:
                grade = GradeService.create_grade(request.user, dto)
                return Response(
                    GradeSerializer(grade).data,
                    status=status.HTTP_201_CREATED
                )
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to create grade: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_grade')
def grade_detail(request, pk):
    """
    Retrieve or update a specific grade.
    
    GET /hr/grades/{id}/
    - Returns detailed information about a grade including rates
    
    PUT/PATCH /hr/grades/{id}/
    - Update a grade
    - Request body: GradeSerializer fields (excluding rates)
    """
    try:
        grade = Grade.objects.scoped(request.user).select_related('business_group').prefetch_related('rate_levels').get(pk=pk)
    except Grade.DoesNotExist:
        # Check if grade exists at all
        if Grade.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this grade. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Grade not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = GradeSerializer(grade)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = GradeUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto(code=grade.code)
                updated_grade = GradeService.update_grade(request.user, dto)
                return Response(GradeSerializer(updated_grade).data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to update grade: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        try:
            incoming_end = request.data.get('effective_end_date') if hasattr(request, 'data') else None
            from django.utils.dateparse import parse_date
            end_date = parse_date(incoming_end) if isinstance(incoming_end, str) else incoming_end
            deactivated = GradeService.deactivate_grade(request.user, grade.id, end_date)
            return Response(GradeSerializer(deactivated).data, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_grade', 'view')
def grade_history(request, pk):
    """
    Get all historical versions of a grade.
    
    GET /hr/grades/{id}/history/
    - Returns all versions of a grade (date tracked)
    """
    try:
        grade = Grade.objects.scoped(request.user).get(pk=pk)
    except Grade.DoesNotExist:
        # Check if grade exists at all
        if Grade.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this grade. It may belong to a different business group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Grade not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all versions with the same code within the same scope (business_group)
    versions = Grade.objects.filter(
        code=grade.code,
        **grade.get_version_scope_filters()
    ).order_by('-effective_start_date')
    
    serializer = GradeSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# Grade Rate API Views
# ============================================================================

@api_view(['GET', 'POST'])
@require_page_action('hr_grade')
def grade_rate_list(request, grade_pk):
    """
    List all rates for a grade or create a new rate.
    
    GET /hr/grades/{grade_id}/rates/
    - Returns list of all rates for the specific grade
    
    POST /hr/grades/{grade_id}/rates/
    - Create a new grade rate
    - Request body: GradeRateCreateSerializer fields (grade_id will be set from URL)
    """
    # Verify grade exists and user has access
    grade = get_object_or_404(
        Grade.objects.scoped(request.user),
        pk=grade_pk
    )
    
    if request.method == 'GET':
        rates = GradeRate.objects.filter(grade=grade).order_by('-effective_start_date')
        serializer = GradeRateSerializer(rates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # Inject grade (ID) from URL into the incoming payload so validation succeeds
        incoming = request.data.copy()
        incoming['grade'] = grade_pk
        serializer = GradeRateCreateSerializer(data=incoming)
        
        if serializer.is_valid():
            dto = serializer.to_dto()
            try:
                rate = GradeService.create_grade_rate(request.user, dto)
                return Response(
                    GradeRateSerializer(rate).data,
                    status=status.HTTP_201_CREATED
                )
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to create grade rate: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_grade')
def grade_rate_detail(request, grade_pk, rate_pk):
    """
    Retrieve, update, or delete a specific grade rate.
    
    GET /hr/grades/{grade_id}/rates/{rate_id}/
    - Returns detailed information about a grade rate
    
    PUT/PATCH /hr/grades/{grade_id}/rates/{rate_id}/
    - Update a grade rate
    - Request body: GradeRateSerializer fields
    
    DELETE /hr/grades/{grade_id}/rates/{rate_id}/
    - Delete a grade rate
    """
    # Verify grade exists and user has access
    grade = get_object_or_404(
        Grade.objects.scoped(request.user),
        pk=grade_pk
    )
    
    rate = get_object_or_404(GradeRate, pk=rate_pk, grade=grade)
    
    if request.method == 'GET':
        serializer = GradeRateSerializer(rate)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        # Use service to create new version (preserves history)
        try:
            updated_rate = GradeService.update_grade_rate(
                request.user,
                rate_pk,
                request.data
            )
            return Response(
                GradeRateSerializer(updated_rate).data,
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
        except Exception as e:
            return Response(
                {'error': f"Failed to update grade rate: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    elif request.method == 'DELETE':
        try:
            rate.delete()
            return Response(
                {'message': 'Grade rate deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f"Failed to delete grade rate: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@require_page_action('hr_grade', 'view')
def grade_rate_history(request, grade_pk, rate_type):
    """
    Get version history for a specific rate type.
    
    GET /hr/grades/{grade_id}/rates/history/{rate_type}/
    - Returns all versions (past and current) of a specific rate type
    - Ordered by effective_start_date (newest first)
    
    Example: /hr/grades/1/rates/history/Base/
    Returns all historical versions of the "Base" rate for grade 1
    """
    # Verify grade exists and user has access
    grade = get_object_or_404(
        Grade.objects.scoped(request.user),
        pk=grade_pk
    )
    
    # Resolve rate type by code (from URL) and fetch versions
    try:
        rate_type_obj = GradeRateType.objects.get(code=rate_type)
    except GradeRateType.DoesNotExist:
        return Response(
            {'error': f"Rate type with code '{rate_type}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    rate_versions = GradeRate.objects.filter(
        grade=grade,
        rate_type=rate_type_obj
    ).order_by('-effective_start_date')
    
    serializer = GradeRateSerializer(rate_versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
