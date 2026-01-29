from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from datetime import date

from HR.person.services.contract_service import ContractService
from HR.person.serializers.contract_serializers import (
    ContractSerializer,
    ContractCreateSerializer,
    ContractUpdateSerializer
)
from HR.person.models import Contract
from core.job_roles.decorators import require_page_action
from erp_project.pagination import auto_paginate

@api_view(['GET', 'POST'])
@require_page_action('hr_contract')
@auto_paginate
def contract_list(request):
    """
    List all contracts or create a new one.
    
    GET /person/contracts/
    - Filters: person (ID), status (code), active_only (bool)
    
    POST /person/contracts/
    - Create new contract
    """
    if request.method == 'GET':
        person_id = request.query_params.get('person_id')
        status_code = request.query_params.get('status_code')
        as_of_date = request.query_params.get('as_of_date')
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        
        try:
            if as_of_date:
                if as_of_date == 'ALL':
                    contracts = Contract.objects.all()
                else:
                    contracts = Contract.objects.active_on(as_of_date)
            elif active_only:
                contracts = Contract.objects.active_on(date.today())
            else:
                contracts = Contract.objects.all()

            contracts = contracts.select_related(
                'person', 'contract_status', 'contract_end_reason'
            ).order_by('person__last_name', '-effective_start_date')
            
            if person_id:
                contracts = contracts.filter(person_id=person_id)
                
            if status_code:
                contracts = contracts.filter(contract_status__code=status_code)
                
            serializer = ContractSerializer(contracts, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'POST':
        serializer = ContractCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    contract = ContractService.create(request.user, dto)
                read_serializer = ContractSerializer(contract)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_contract')
def contract_detail(request, pk):
    """
    Retrieve, update or deactivate a contract.
    """
    # Allow viewing inactive/past versions too
    contract = get_object_or_404(Contract.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = ContractSerializer(contract)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        # To update, we usually need the contract reference from the existing object
        # The serializer validates inputs, but service typically works on reference for versioning
        data = request.data.copy()
        data['contract_reference'] = contract.contract_reference 
        
        # If effective_start_date not provided, default to today for new version or let service handle correction
        # The serializer requires it.
        if 'effective_start_date' not in data:
            data['effective_start_date'] = str(date.today())

        serializer = ContractUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_contract = ContractService.update(request.user, dto)
                read_serializer = ContractSerializer(updated_contract)
                return Response(read_serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        try:
            with transaction.atomic():
                ContractService.deactivate(request.user, contract.contract_reference)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
