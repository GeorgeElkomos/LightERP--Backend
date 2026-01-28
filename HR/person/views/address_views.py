from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from HR.person.services.address_service import AddressService
from HR.person.serializers.address_serializers import (
    AddressSerializer,
    AddressCreateSerializer,
    AddressUpdateSerializer
)
from HR.person.models import Address
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate

@api_view(['GET', 'POST'])
@require_page_action('hr_person')
@auto_paginate
def address_list(request):
    """
    List all addresses or create a new one.
    
    GET /person/addresses/?person=<id>
    POST /person/addresses/
    """
    if request.method == 'GET':
        person_id = request.query_params.get('person_id')
        
        addresses = Address.objects.active().select_related(
            'person', 'address_type', 'country', 'city'
        )
        
        if person_id:
            addresses = addresses.filter(person_id=person_id)
            
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = AddressCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    address = AddressService.create(request.user, dto)
                read_serializer = AddressSerializer(address)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_person')
def address_detail(request, pk):
    """
    Retrieve, update or deactivate an address.
    """
    address = get_object_or_404(Address.objects.active(), pk=pk)
    
    if request.method == 'GET':
        serializer = AddressSerializer(address)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['address_id'] = pk  # Ensure ID is passed to DTO
        
        serializer = AddressUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_address = AddressService.update(request.user, dto)
                read_serializer = AddressSerializer(updated_address)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                AddressService.deactivate(request.user, pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_person', action_name='view')
def primary_address(request, person_id):
    """
    Get the primary address for a specific person.
    """
    address = AddressService.get_primary_address(person_id)
    if not address:
        return Response({'detail': 'No primary address found for this person'}, status=status.HTTP_404_NOT_FOUND)
        
    serializer = AddressSerializer(address)
    return Response(serializer.data, status=status.HTTP_200_OK)
