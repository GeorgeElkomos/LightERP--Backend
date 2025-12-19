"""
API Views for Grade and GradeRate models.
Provides REST API endpoints for managing grades and grade rates with date tracking.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from hr.models import Grade, GradeRate
from hr.services.grade_service import GradeService
from hr.serializers import (
    GradeSerializer,
    GradeCreateSerializer,
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
        - business_group: Filter by business group ID
        - code: Filter by code (exact match)
        - search: Search across code and name
    
    POST /hr/grades/
    - Create a new grade
    - Request body: GradeCreateSerializer fields
    """
    if request.method == 'GET':
        grades = Grade.objects.scoped(request.user).currently_active()
        grades = grades.select_related('business_group').prefetch_related('rates')
        
        # Apply filters
        business_group_id = request.query_params.get('business_group')
        if business_group_id:
            grades = grades.filter(business_group_id=business_group_id)
        
        code = request.query_params.get('code')
        if code:
            grades = grades.filter(code__iexact=code)
        
        search = request.query_params.get('search')
        if search:
            grades = grades.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
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
            except (ValidationError, PermissionDenied) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to create grade: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH'])
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
    grade = get_object_or_404(
        Grade.objects.scoped(request.user).select_related('business_group').prefetch_related('rates'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = GradeSerializer(grade)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = GradeSerializer(grade, data=request.data, partial=partial)
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
                    {'error': f"Failed to update grade: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_grade', 'view')
def grade_history(request, pk):
    """
    Get all historical versions of a grade.
    
    GET /hr/grades/{id}/history/
    - Returns all versions of a grade (date tracked)
    """
    grade = get_object_or_404(Grade, pk=pk)
    
    # Get all versions with the same code
    versions = Grade.objects.filter(
        code=grade.code
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
        # Inject grade_id from URL into the incoming payload so validation succeeds
        incoming = dict(request.data)
        incoming['grade_id'] = grade_pk
        serializer = GradeRateCreateSerializer(data=incoming)
        
        if serializer.is_valid():
            dto = serializer.to_dto()
        try:
            rate = GradeService.create_grade_rate(request.user, dto)
            return Response(
                GradeRateSerializer(rate).data,
                status=status.HTTP_201_CREATED
            )
        except (ValidationError, PermissionDenied) as e:
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
        partial = request.method == 'PATCH'
        serializer = GradeRateSerializer(rate, data=request.data, partial=partial)
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
                    {'error': f"Failed to update grade rate: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
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
