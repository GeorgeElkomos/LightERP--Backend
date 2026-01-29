from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from HR.person.services.qualification_service import QualificationService
from HR.person.serializers.qualification_serializers import (
    QualificationSerializer,
    QualificationCreateSerializer,
    QualificationUpdateSerializer
)
from HR.person.models import Qualification, Person
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate

@api_view(['GET', 'POST'])
@require_page_action('hr_qualification')
@auto_paginate
def qualification_list(request):
    """
    List all qualifications or create a new one.
    
    GET /person/qualifications/
    - Filters: person (ID), type (code), status (code)
    
    POST /person/qualifications/
    - Create new qualification
    """
    if request.method == 'GET':
        person_id = request.query_params.get('person_id')
        type_code = request.query_params.get('type_code')
        status_code = request.query_params.get('status_code')
        
        qualifications = Qualification.objects.active().select_related(
            'person', 'qualification_type', 'qualification_title', 
            'qualification_status', 'awarding_entity', 
            'tuition_method', 'tuition_fees_currency'
        ).prefetch_related('competency_achieved').order_by('person__last_name', '-effective_start_date')
        
        if person_id:
            qualifications = qualifications.filter(person_id=person_id)
            
        if type_code:
            qualifications = qualifications.filter(qualification_type__code=type_code)
            
        if status_code:
            qualifications = qualifications.filter(qualification_status__code=status_code)
            
        serializer = QualificationSerializer(qualifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = QualificationCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    qualification = QualificationService.create(request.user, dto)
                read_serializer = QualificationSerializer(qualification)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_qualification')
def qualification_detail(request, pk):
    """
    Retrieve, update or deactivate a qualification.
    """
    qualification = get_object_or_404(Qualification.objects.active(), pk=pk)
    
    if request.method == 'GET':
        serializer = QualificationSerializer(qualification)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['qualification_id'] = pk
        
        serializer = QualificationUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_qual = QualificationService.update(request.user, dto)
                read_serializer = QualificationSerializer(updated_qual)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                QualificationService.deactivate(request.user, pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
