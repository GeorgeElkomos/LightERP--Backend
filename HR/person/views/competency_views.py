from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Q
from datetime import date

from HR.person.services.competency_service import CompetencyService
from HR.person.services.competency_proficiency_service import CompetencyProficiencyService
from HR.person.serializers.competency_serializers import (
    CompetencySerializer,
    CompetencyCreateSerializer,
    CompetencyUpdateSerializer,
    CompetencyProficiencySerializer,
    CompetencyProficiencyCreateSerializer,
    CompetencyProficiencyUpdateSerializer
)
from HR.person.models import Competency, CompetencyProficiency
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate

# =================================================================================================
# COMPETENCY VIEWS
# =================================================================================================

@api_view(['GET', 'POST'])
@require_page_action('hr_competency')
@auto_paginate
def competency_list(request):
    """
    List all competencies or create a new one.
    
    GET /person/competencies/
    - Filters: category (code), search (code, name, description)
    - Pagination: Standard DRF pagination
    
    POST /person/competencies/
    - Create new competency using DTO pattern
    """
    if request.method == 'GET':
        category_code = request.query_params.get('category_code')
        search_query = request.query_params.get('search')
        
        competencies = Competency.objects.active().select_related('category').order_by('category__name', 'name')
        
        if category_code:
            competencies = competencies.filter(category__code=category_code)
            
        if search_query:
            competencies = competencies.filter(
                Q(code__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
            
        serializer = CompetencySerializer(competencies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = CompetencyCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    competency = CompetencyService.create(request.user, dto)
                read_serializer = CompetencySerializer(competency)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_competency')
def competency_detail(request, pk):
    """
    Retrieve, update or deactivate a competency.
    
    DELETE /person/competencies/<pk>/ - Soft delete
    """
    competency = get_object_or_404(Competency.objects.active(), pk=pk)
    
    if request.method == 'GET':
        serializer = CompetencySerializer(competency)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['code'] = competency.code  # Ensure code is passed to DTO for lookup
        
        serializer = CompetencyUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_competency = CompetencyService.update(request.user, dto)
                read_serializer = CompetencySerializer(updated_competency)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                CompetencyService.deactivate(request.user, competency.code)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)


# =================================================================================================
# COMPETENCY PROFICIENCY VIEWS
# =================================================================================================

@api_view(['GET', 'POST'])
@require_page_action('hr_competency')
def proficiency_list(request):
    """
    List all competency proficiencies or create a new one.
    
    GET /person/competency-proficiencies/
    - Filters: person (ID), competency (ID), current_only (bool)
    - Default: Returns all history unless current_only=true
    
    POST /person/competency-proficiencies/
    - Create new proficiency record
    """
    if request.method == 'GET':
        person_id = request.query_params.get('person_id')
        competency_id = request.query_params.get('competency_id')
        current_only = request.query_params.get('current_only', 'false').lower() == 'true'
        
        proficiencies = CompetencyProficiency.objects.all().select_related(
            'person', 'competency', 'proficiency_level', 'proficiency_source'
        ).order_by('person__last_name', 'competency__name', '-effective_start_date')
        
        if person_id:
            proficiencies = proficiencies.filter(person_id=person_id)
            
        if competency_id:
            proficiencies = proficiencies.filter(competency_id=competency_id)
            
        if current_only:
            proficiencies = proficiencies.active_on(date.today())
            
        serializer = CompetencyProficiencySerializer(proficiencies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = CompetencyProficiencyCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    proficiency = CompetencyProficiencyService.create(request.user, dto)
                read_serializer = CompetencyProficiencySerializer(proficiency)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_competency')
def proficiency_detail(request, pk):
    """
    Retrieve, update or deactivate a competency proficiency.
    """
    proficiency = get_object_or_404(CompetencyProficiency.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = CompetencyProficiencySerializer(proficiency)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['proficiency_id'] = pk
        
        serializer = CompetencyProficiencyUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_proficiency = CompetencyProficiencyService.update(request.user, dto)
                read_serializer = CompetencyProficiencySerializer(updated_proficiency)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                CompetencyProficiencyService.deactivate(request.user, pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
