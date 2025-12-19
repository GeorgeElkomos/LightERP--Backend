"""
API Views for Enterprise and Business Group models.
Provides REST API endpoints for managing organizational structure.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from hr.models import Enterprise, BusinessGroup
from hr.serializers import (
    EnterpriseSerializer,
    BusinessGroupSerializer,
    LocationSerializer
    )


# ============================================================================
# Enterprise API Views
# ============================================================================

@api_view(['GET', 'POST'])
@require_page_action('hr_enterprise')
@auto_paginate
def enterprise_list(request):
    """
    List all enterprises or create a new enterprise.
    
    GET /hr/enterprises/
    - Returns list of all enterprises
    - Query params:
        - status: Filter by status (active/inactive)
        - code: Filter by code (exact match)
        - name: Filter by name (case-insensitive contains)
        - search: Search across code and name
    
    POST /hr/enterprises/
    - Create a new enterprise
    - Request body: EnterpriseSerializer fields
    """
    if request.method == 'GET':
        enterprises = Enterprise.objects.all()
        
        # Apply filters
        status_param = request.query_params.get('status')
        if status_param:
            enterprises = enterprises.filter(status=status_param)
        
        code = request.query_params.get('code')
        if code:
            enterprises = enterprises.filter(code__iexact=code)
        
        name = request.query_params.get('name')
        if name:
            enterprises = enterprises.filter(name__icontains=name)
        
        search = request.query_params.get('search')
        if search:
            enterprises = enterprises.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
        serializer = EnterpriseSerializer(enterprises, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = EnterpriseSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to create enterprise: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_enterprise')
def enterprise_detail(request, pk):
    """
    Retrieve, update, or delete a specific enterprise.
    
    GET /hr/enterprises/{id}/
    - Returns detailed information about an enterprise
    
    PUT/PATCH /hr/enterprises/{id}/
    - Update an enterprise
    - Request body: EnterpriseSerializer fields
    
    DELETE /hr/enterprises/{id}/
    - Delete an enterprise (deactivate)
    """
    enterprise = get_object_or_404(Enterprise, pk=pk)
    
    if request.method == 'GET':
        serializer = EnterpriseSerializer(enterprise)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = EnterpriseSerializer(enterprise, data=request.data, partial=partial)
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
                    {'error': f"Failed to update enterprise: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            enterprise.deactivate()
            return Response(
                {'message': 'Enterprise deactivated successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f"Failed to deactivate enterprise: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================================================
# Business Group API Views
# ============================================================================

@api_view(['GET', 'POST'])
@require_page_action('hr_business_group')
@auto_paginate
def business_group_list(request):
    """
    List all business groups or create a new business group.
    
    GET /hr/business-groups/
    - Returns list of all business groups
    - Query params:
        - status: Filter by status (active/inactive)
        - enterprise: Filter by enterprise ID
        - code: Filter by code (exact match)
        - name: Filter by name (case-insensitive contains)
        - search: Search across code and name
    
    POST /hr/business-groups/
    - Create a new business group
    - Request body: BusinessGroupSerializer fields
    """
    
    if request.method == 'GET':
        business_groups = BusinessGroup.objects.select_related('enterprise')
        
        # Apply filters
        status_param = request.query_params.get('status')
        if status_param:
            business_groups = business_groups.filter(status=status_param)
        
        enterprise_id = request.query_params.get('enterprise')
        if enterprise_id:
            business_groups = business_groups.filter(enterprise_id=enterprise_id)
        
        code = request.query_params.get('code')
        if code:
            business_groups = business_groups.filter(code__iexact=code)
        
        name = request.query_params.get('name')
        if name:
            business_groups = business_groups.filter(name__icontains=name)
        
        search = request.query_params.get('search')
        if search:
            business_groups = business_groups.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search) |
                Q(enterprise__name__icontains=search)
            )
        
        serializer = BusinessGroupSerializer(business_groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = BusinessGroupSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to create business group: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_business_group')
def business_group_detail(request, pk):
    """
    Retrieve, update, or delete a specific business group.
    
    GET /hr/business-groups/{id}/
    - Returns detailed information about a business group
    
    PUT/PATCH /hr/business-groups/{id}/
    - Update a business group
    - Request body: BusinessGroupSerializer fields
    
    DELETE /hr/business-groups/{id}/
    - Delete a business group (deactivate)
    """
    business_group = get_object_or_404(
        BusinessGroup.objects.select_related('enterprise'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = BusinessGroupSerializer(business_group)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = BusinessGroupSerializer(business_group, data=request.data, partial=partial)
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
                    {'error': f"Failed to update business group: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            business_group.status = 'inactive'
            business_group.save()
            return Response(
                {'message': 'Business group deactivated successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f"Failed to deactivate business group: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================================================
# Location API Views
# ============================================================================

@api_view(['GET', 'POST'])
@require_page_action('hr_location')
@auto_paginate
def location_list(request):
    """
    List all locations or create a new location.
    
    GET /hr/locations/
    - Returns list of all locations (scoped by user's business groups)
    - Query params:
        - status: Filter by status (active/inactive)
        - business_group: Filter by business group ID
        - country: Filter by country
        - city: Filter by city
        - search: Search across code, name, city
    
    POST /hr/locations/
    - Create a new location
    - Request body: LocationSerializer fields
    """
    if request.method == 'GET':
        from hr.models import Location
        
        locations = Location.objects.scoped(request.user).select_related(
            'enterprise',
            'business_group'
        )
        
        # Apply filters
        status_param = request.query_params.get('status')
        if status_param:
            locations = locations.filter(status=status_param)
        
        business_group_id = request.query_params.get('business_group')
        if business_group_id:
            locations = locations.filter(business_group_id=business_group_id)
        
        country = request.query_params.get('country')
        if country:
            locations = locations.filter(country__icontains=country)
        
        city = request.query_params.get('city')
        if city:
            locations = locations.filter(city__icontains=city)
        
        search = request.query_params.get('search')
        if search:
            locations = locations.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search) |
                Q(city__icontains=search)
            )
        
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = LocationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': f"Failed to create location: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_location')
def location_detail(request, pk):
    """
    Retrieve, update, or delete a specific location.
    """
    from hr.models import Location
    from hr.serializers import LocationSerializer
    
    location = get_object_or_404(
        Location.objects.select_related('enterprise', 'business_group'),
        pk=pk
    )
    
    if request.method == 'GET':
        serializer = LocationSerializer(location)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = LocationSerializer(location, data=request.data, partial=partial)
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
                    {'error': f"Failed to update location: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            location.status = 'inactive'
            location.save()
            return Response(
                {'message': 'Location deactivated successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f"Failed to deactivate location: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
