from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from datetime import date

from HR.work_structures.services.job_service import JobService
from HR.work_structures.serializers.job_serializers import (
    JobReadSerializer,
    JobCreateSerializer,
    JobUpdateSerializer
)
from HR.work_structures.models import Job
from core.job_roles.decorators import require_page_action
from django.utils.dateparse import parse_date
from erp_project.pagination import auto_paginate


@api_view(['GET', 'POST'])
@require_page_action('hr_job')
@auto_paginate
def job_list(request):
    """
    List all jobs or create a new job.
    
    GET /work_structures/jobs/
    - Filters: business_group (ID or code), category (ID), family (ID)
    - Search: ?search=query (searches code, job_title__name)
    - Date Filter: ?as_of_date=YYYY-MM-DD or 'ALL' (defaults to 'ALL')

    POST /work_structures/jobs/
    - Create new job using DTO pattern
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

        bg_filter = request.query_params.get('business_group')
        filters = {
            'job_category_id': request.query_params.get('category'),
            'job_family_id': request.query_params.get('family'),
            'search': request.query_params.get('search'),
            'as_of_date': as_of_date
        }
        
        # Determine business_group_id
        if bg_filter:
            filters['business_group_id'] = bg_filter
        
        jobs = JobService.list_jobs(filters)
            
        serializer = JobReadSerializer(jobs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = JobCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    job = JobService.create(request.user, dto)
                read_serializer = JobReadSerializer(job)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_job')
def job_detail(request, pk):
    """
    Retrieve, update or deactivate a job.
    """
    job = get_object_or_404(Job.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = JobReadSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['job_id'] = job.id
            
        serializer = JobUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_job = JobService.update(request.user, dto)
                read_serializer = JobReadSerializer(updated_job)
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
                JobService.deactivate(request.user, job.id, effective_end_date)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_job', action_name='view')
def job_versions(request, pk):
    """
    Get all versions of a job by ID (retrieves all versions sharing the same code).
    """
    try:
        versions = JobService.get_job_versions(pk)
    except ValidationError as e:
        return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = JobReadSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
