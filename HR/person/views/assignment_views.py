from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from datetime import date

from HR.person.services.assignment_service import AssignmentService
from HR.person.serializers.assignment_serializers import (
    AssignmentSerializer,
    AssignmentCreateSerializer,
    AssignmentUpdateSerializer
)
from HR.person.models import Assignment
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate

@api_view(['GET', 'POST'])
@require_page_action('hr_assignment')
@auto_paginate
def assignment_list(request):
    """
    List all assignments or create a new one.
    
    GET /person/assignments/
    - Filters: person (ID), department (ID), job (ID), primary_only (bool), active_only (bool)
    """
    if request.method == 'GET':
        person_id = request.query_params.get('person_id')
        organization_id = request.query_params.get('organization_id')
        job_id = request.query_params.get('job_id')
        as_of_date = request.query_params.get('as_of_date')
        primary_only = request.query_params.get('primary_only', 'false').lower() == 'true'
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        
        try:
            if as_of_date:
                if as_of_date == 'ALL':
                    assignments = Assignment.objects.all()
                else:
                    assignments = Assignment.objects.active_on(as_of_date)
            elif active_only:
                 assignments = Assignment.objects.active_on(date.today())
            else:
                 assignments = Assignment.objects.all()

            assignments = assignments.select_related(
                'person', 'business_group', 'department', 'job', 'position', 'grade',
                'payroll', 'salary_basis', 'assignment_action_reason', 'assignment_status'
            ).order_by('person__last_name', '-effective_start_date')
            
            if person_id:
                assignments = assignments.filter(person_id=person_id)
                
            if organization_id:
                assignments = assignments.filter(department_id=organization_id)
            
            if job_id:
               assignments = assignments.filter(job_id=job_id)

            if primary_only:
                assignments = assignments.filter(primary_assignment=True)
                
            serializer = AssignmentSerializer(assignments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'POST':
        serializer = AssignmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    assignment = AssignmentService.create(request.user, dto)
                read_serializer = AssignmentSerializer(assignment)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_assignment')
def assignment_detail(request, pk):
    """
    Retrieve, update or deactivate an assignment.
    """
    assignment = get_object_or_404(Assignment.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = AssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['assignment_no'] = assignment.assignment_no
        
        if 'effective_start_date' not in data:
            data['effective_start_date'] = str(date.today())

        serializer = AssignmentUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_assignment = AssignmentService.update(request.user, dto)
                read_serializer = AssignmentSerializer(updated_assignment)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                AssignmentService.deactivate(request.user, assignment.assignment_no)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_assignment')
def primary_assignment(request, person_id):
    """
    Get the current primary assignment for a person.
    """
    assignment = AssignmentService.get_primary_assignment(person_id)
    if assignment:
        serializer = AssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response({"detail": "No primary assignment found"}, status=status.HTTP_404_NOT_FOUND)
