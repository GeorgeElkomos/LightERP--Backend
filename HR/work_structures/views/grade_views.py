from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from datetime import date

from HR.work_structures.services.grade_service import GradeService
from HR.work_structures.serializers.grade_serializers import (
    GradeReadSerializer,
    GradeCreateSerializer,
    GradeUpdateSerializer,
    GradeRateTypeReadSerializer,
    GradeRateReadSerializer,
    GradeRateCreateSerializer,
    GradeRateUpdateSerializer,
    GradeRateTypeCreateSerializer,
    GradeRateTypeUpdateSerializer
)
from HR.work_structures.models import Grade, GradeRate, GradeRateType
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate


@api_view(['GET', 'POST'])
@require_page_action('hr_grade')
@auto_paginate
def grade_list(request):
    """
    List all grades or create a new grade.
    
    GET /work-structures/grades/
    - Filters: business_group (business group ID or code)
    - Search: ?search=query (searches grade_name__name)

    POST /work-structures/grades/
    - Create new grade using DTO pattern
    """
    if request.method == 'GET':
        filters = {
            'business_group': request.query_params.get('business_group'),
            'search': request.query_params.get('search'),
            'status': request.query_params.get('status', 'ALL') # Default to 'ALL'
        }
        
        grades = GradeService.list_grades(filters)
            
        serializer = GradeReadSerializer(grades, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = GradeCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    grade = GradeService.create(request.user, dto)
                read_serializer = GradeReadSerializer(grade)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_grade')
def grade_detail(request, pk):
    """
    Retrieve, update or deactivate a grade.
    """
    grade = get_object_or_404(Grade.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = GradeReadSerializer(grade)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        # Add grade_id to data for serializer
        data['grade_id'] = grade.id
            
        serializer = GradeUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_grade = GradeService.update(request.user, dto)
                read_serializer = GradeReadSerializer(updated_grade)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                GradeService.deactivate(request.user, grade.id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@require_page_action('hr_grade', action_name='view')
@auto_paginate
def grade_rate_type_list(request):
    """
    List all grade rate types or create a new one.
    """
    if request.method == 'GET':
        rate_types = GradeService.list_grade_rate_types()
        serializer = GradeRateTypeReadSerializer(rate_types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = GradeRateTypeCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    rate_type = GradeService.create_grade_rate_type(request.user, dto)
                read_serializer = GradeRateTypeReadSerializer(rate_type)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_grade')
def grade_rate_type_detail(request, pk):
    """
    Retrieve, update or delete a grade rate type.
    """
    rate_type = get_object_or_404(GradeRateType.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = GradeRateTypeReadSerializer(rate_type)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['rate_type_id'] = rate_type.id
        
        serializer = GradeRateTypeUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_rate_type = GradeService.update_grade_rate_type(request.user, dto)
                read_serializer = GradeRateTypeReadSerializer(updated_rate_type)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                GradeService.delete_grade_rate_type(request.user, rate_type.id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@require_page_action('hr_grade')
@auto_paginate
def grade_rate_list(request):
    """
    List all rates or create a new rate.
    
    GET /work-structures/grade-rates/
    - Filters: grade (ID), rate_type (ID)
    """
    if request.method == 'GET':
        as_of_date_param = request.query_params.get('as_of_date')
        if as_of_date_param:
            if as_of_date_param == 'ALL':
                as_of_date = 'ALL'
            else:
                as_of_date = parse_date(as_of_date_param)
                print(as_of_date)
        else:
            as_of_date = 'ALL'
        filters = {
            'grade_id': request.query_params.get('grade'),
            'rate_type_id': request.query_params.get('rate_type'),
            'as_of_date': as_of_date
        }
        
        rates = GradeService.list_grade_rates(filters)
            
        serializer = GradeRateReadSerializer(rates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = GradeRateCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    rate = GradeService.create_grade_rate(request.user, dto)
                read_serializer = GradeRateReadSerializer(rate)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_grade')
def grade_rate_detail(request, pk):
    """
    Retrieve, update or delete a grade rate.
    """
    rate = get_object_or_404(GradeRate.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = GradeRateReadSerializer(rate)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['grade_id'] = rate.grade_id
        data['rate_type_id'] = rate.rate_type_id
        
        serializer = GradeRateUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_rate = GradeService.update_grade_rate(request.user, dto)
                read_serializer = GradeRateReadSerializer(updated_rate)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                GradeService.delete_grade_rate(request.user, rate.id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
