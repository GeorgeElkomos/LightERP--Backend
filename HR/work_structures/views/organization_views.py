from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from datetime import date

from HR.work_structures.services.organization_service import OrganizationService
from HR.work_structures.serializers.organization_serializers import (
    OrganizationReadSerializer,
    OrganizationCreateSerializer,
    OrganizationUpdateSerializer
)
from HR.work_structures.models import Organization
from core.job_roles.decorators import require_page_action


from django.utils.dateparse import parse_date
from erp_project.pagination import auto_paginate


@api_view(['GET', 'POST'])
@require_page_action('hr_organization')
@auto_paginate
def organization_list(request):
    """
    List all organizations or create a new organization.
    
    GET /work_structures/organizations/
    - Filters: business_group (ID), location (ID), is_business_group (boolean)
    - Search: ?search=query (searches organization_name, organization_type__name)
    - Date Filter: ?as_of_date=YYYY-MM-DD or 'ALL' (defaults to 'ALL')

    POST /work_structures/organizations/
    - Create new organization using DTO pattern
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

        filters = {
            'business_group': request.query_params.get('business_group'),
            'is_business_group': request.query_params.get('is_business_group'),
            'location_id': request.query_params.get('location'),
            'search': request.query_params.get('search'),
            'as_of_date': as_of_date
        }
        
        organizations = OrganizationService.list_organizations(filters)
            
        serializer = OrganizationReadSerializer(organizations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = OrganizationCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    organization = OrganizationService.create(request.user, dto)
                read_serializer = OrganizationReadSerializer(organization)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_organization')
def organization_detail(request, pk):
    """
    Retrieve, update or deactivate an organization.
    
    GET /work_structures/organizations/<pk>/
    PUT/PATCH /work_structures/organizations/<pk>/
    DELETE /work_structures/organizations/<pk>/
    """
    organization = get_object_or_404(Organization.objects.all(), pk=pk)
    
    if request.method == 'GET':
        serializer = OrganizationReadSerializer(organization)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    elif request.method in ['PUT', 'PATCH']:
        data = request.data.copy()
        data['organization_id'] = organization.id
            
        serializer = OrganizationUpdateSerializer(data=data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    updated_org = OrganizationService.update(request.user, dto)
                read_serializer = OrganizationReadSerializer(updated_org)
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
                OrganizationService.deactivate(request.user, organization.id, effective_end_date)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({'error': 'Invalid date format for effective_end_date'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_page_action('hr_organization', action_name='view')
def organization_hierarchy(request, pk):
    """
    Get organization hierarchy starting from a business group.
    
    GET /work_structures/organizations/<pk>/hierarchy/
    """
    try:
        hierarchy = OrganizationService.get_organization_hierarchy(pk)
        return Response(hierarchy, status=status.HTTP_200_OK)
    except ValidationError as e:
        error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
        return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
