from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from HR.person.services.contact_service import ContactService
from HR.person.serializers.contact_serializers import (
    ContactSerializer,
    ContactCreateSerializer,
    ContactUpdateSerializer
)
from HR.person.models import Contact
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate

@api_view(['GET', 'POST'])
@require_page_action('hr_person')
@auto_paginate
def contact_list(request):
    """
    List all contacts or create a new one.
    
    GET /person/contacts/
    - Filters: organization_name, contact_number, as_of_date
    
    POST /person/contacts/
    - Create new contact (and person)
    """
    if request.method == 'GET':
        as_of_date = request.query_params.get('as_of_date')
        
        # Base active contacts
        contacts = ContactService.get_active_contacts(as_of_date)
        
        # Filters
        person_id = request.query_params.get('person_id')
        if person_id:
            contacts = contacts.filter(person_id=person_id)

        organization_name = request.query_params.get('organization_name')
        if organization_name:
            contacts = contacts.filter(organization_name__icontains=organization_name)
            
        contact_number = request.query_params.get('contact_number')
        if contact_number:
            contacts = contacts.filter(contact_number__icontains=contact_number)
            
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = ContactCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                person_data, contact_data, start_date = serializer.to_data()
                with transaction.atomic():
                    contact = ContactService.create_contact(person_data, contact_data, start_date)
                read_serializer = ContactSerializer(contact)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_person')
def contact_detail(request, pk):
    """
    Retrieve, update or deactivate a contact.
    """
    contact = get_object_or_404(Contact, pk=pk)
    
    if request.method == 'GET':
        serializer = ContactSerializer(contact)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['contact_id'] = pk
        
        serializer = ContactUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_contact = ContactService.update(request.user, dto)
                read_serializer = ContactSerializer(updated_contact)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                ContactService.deactivate_contact(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@require_page_action('hr_person_employee')
def employee_emergency_contacts(request, employee_id):
    """
    Get emergency contacts for an employee.
    """
    contacts = ContactService.get_emergency_contacts_for_employee(employee_id)
    serializer = ContactSerializer(contacts, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
