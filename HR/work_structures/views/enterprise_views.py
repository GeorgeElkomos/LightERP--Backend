"""
API Views for Enterprise and Business Group models.
Provides REST API endpoints for managing organizational structure.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db.models import Q

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action

from HR.work_structures.models import Enterprise, BusinessGroup, Location
from HR.work_structures.services.structure_service import StructureService
from HR.work_structures.security import validate_location_scope
from HR.work_structures.serializers import (
    EnterpriseSerializer,
    EnterpriseCreateSerializer,
    EnterpriseUpdateSerializer,
    BusinessGroupSerializer,
    BusinessGroupCreateSerializer,
    BusinessGroupUpdateSerializer,
    LocationSerializer,
    LocationCreateSerializer
    )


from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status as http_status  # Avoid name collision
from django.core.exceptions import ValidationError, PermissionDenied

from erp_project.pagination import auto_paginate
from core.job_roles.decorators import require_page_action


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
    - Returns list of currently active enterprises
    - Query params:
        - status: Filter by status (active/inactive)
        - code: Filter by code (exact match)
        - name: Filter by name (exact match)
        - search: Search across code and name
        - include_inactive: Include inactive versions (default: false)
    
    POST /hr/enterprises/
    - Create a new enterprise
    - Request body: EnterpriseCreateSerializer fields
    """
    if request.method == 'GET':
        # Base queryset with scope filtering
        enterprises = Enterprise.objects.scoped(request.user)
        
        # Default: only currently active versions
        include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
        if not include_inactive:
            enterprises = enterprises.active()
        
        # Filter by status (computed property, so we handle it via date filtering)
        status_filter = request.query_params.get('status')
        if status_filter and status_filter.lower() == 'active':
            # Explicitly filter to active records
            enterprises = enterprises.active()
        elif status_filter and status_filter.lower() == 'inactive':
            # Filter to inactive records (future start or past end)
            from django.utils import timezone
            today = timezone.now().date()
            enterprises = enterprises.exclude(
                Q(effective_start_date__lte=today) &
                (Q(effective_end_date__gte=today) | Q(effective_end_date__isnull=True))
            )
        
        # Apply standard code/name/search filters
        enterprises = enterprises.filter_by_search_params(request.query_params)
        
        serializer = EnterpriseSerializer(enterprises, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = EnterpriseCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            dto = serializer.to_dto()
            
            try:
                enterprise = StructureService.create_enterprise(request.user, dto)
                return Response(
                    EnterpriseSerializer(enterprise).data,
                    status=status.HTTP_201_CREATED
                )
            except PermissionDenied as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_403_FORBIDDEN
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@require_page_action('hr_enterprise')
def enterprise_detail(request, pk):
    """
    Retrieve, update, or delete a specific enterprise.
    Enforces data scope - returns 403 if enterprise exists but user lacks access.
    
    GET /hr/enterprises/{id}/
    - Returns detailed information about an enterprise
    
    PUT/PATCH /hr/enterprises/{id}/
    - Update an enterprise
    - Request body: EnterpriseSerializer fields
    
    DELETE /hr/enterprises/{id}/
    - Delete an enterprise (deactivate)
    """
    # Scope-aware retrieval with proper 403 vs 404 handling
    try:
        enterprise = Enterprise.objects.scoped(request.user).get(pk=pk)
    except Enterprise.DoesNotExist:
        # Check if exists outside user's scope
        if Enterprise.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this enterprise'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Enterprise not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = EnterpriseSerializer(enterprise)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = EnterpriseUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto(code=enterprise.code)
                updated_enterprise = StructureService.update_enterprise(request.user, dto)
                return Response(EnterpriseSerializer(updated_enterprise).data, status=status.HTTP_200_OK)
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
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
            effective_end_date = request.data.get('effective_end_date') if request.data else None
            StructureService.deactivate_enterprise(request.user, pk, effective_end_date)
            return Response({'message': 'Enterprise deactivated successfully'}, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f"Failed to deactivate enterprise: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@require_page_action('hr_enterprise', 'view')
def enterprise_history(request, pk):
    """Get historical versions of an enterprise.
    GET /hr/enterprises/{id}/history/"""
    try:
        enterprise = Enterprise.objects.scoped(request.user).get(pk=pk)
    except Enterprise.DoesNotExist:
        return Response({'error': 'Enterprise not found'}, status=status.HTTP_404_NOT_FOUND)
    
    versions = Enterprise.objects.filter(code=enterprise.code).order_by('-effective_start_date')
    serializer = EnterpriseSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


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
    - Returns list of all currently active business groups
    - Query params:
        - status: Filter by status (active/inactive)
        - code: Filter by code (exact match)
        - name: Filter by name (exact match)
        - enterprise: Filter by enterprise name or code
        - search: Search across business group code and name
        - include_inactive: Include inactive versions (default: false)
    
    POST /hr/business-groups/
    - Create a new business group
    - Request body: BusinessGroupCreateSerializer fields
    """
    
    if request.method == 'GET':
        # Base queryset with scope filtering
        business_groups = BusinessGroup.objects.scoped(request.user).select_related('enterprise')
        
        # Default: only currently active versions
        include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
        if not include_inactive:
            business_groups = business_groups.active()
        
        # Filter by enterprise (name or code)
        enterprise_filter = request.query_params.get('enterprise')
        if enterprise_filter:
            business_groups = business_groups.filter(
                Q(enterprise__name__icontains=enterprise_filter) |
                Q(enterprise__code__icontains=enterprise_filter)
            )
        
        # Filter by status (computed property, so we handle it via date filtering)
        status_filter = request.query_params.get('status')
        if status_filter and status_filter.lower() == 'active':
            # Explicitly filter to active records
            business_groups = business_groups.active()
        elif status_filter and status_filter.lower() == 'inactive':
            # Filter to inactive records (future start or past end)
            from django.utils import timezone
            today = timezone.now().date()
            business_groups = business_groups.exclude(
                Q(effective_start_date__lte=today) &
                (Q(effective_end_date__gte=today) | Q(effective_end_date__isnull=True))
            )
        
        # Apply standard code/name/search filters
        business_groups = business_groups.filter_by_search_params(request.query_params)
        
        # Serialize and return
        serializer = BusinessGroupSerializer(business_groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = BusinessGroupCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            dto = serializer.to_dto()
            
            try:
                bg = StructureService.create_business_group(request.user, dto)
                return Response(
                    BusinessGroupSerializer(bg).data,
                    status=http_status.HTTP_201_CREATED
                )
            except PermissionDenied as e:
                return Response(
                    {'error': str(e)},
                    status=http_status.HTTP_403_FORBIDDEN
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=http_status.HTTP_400_BAD_REQUEST
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
    # Scope-aware retrieval with proper 403 vs 404 handling
    try:
        business_group = BusinessGroup.objects.scoped(request.user).select_related('enterprise').get(pk=pk)
    except BusinessGroup.DoesNotExist:
        # Check if exists outside user's scope
        if BusinessGroup.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this business group'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Business group not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = BusinessGroupSerializer(business_group)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = BusinessGroupUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto(code=business_group.code)
                updated_bg = StructureService.update_business_group(request.user, dto)
                return Response(BusinessGroupSerializer(updated_bg).data, status=status.HTTP_200_OK)
            except PermissionDenied as e:
                return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to update business group: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            effective_end_date = request.data.get('effective_end_date') if request.data else None
            StructureService.deactivate_business_group(request.user, pk, effective_end_date)
            return Response({'message': 'Business group deactivated successfully'}, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f"Failed to deactivate business group: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

@api_view(['GET'])
@require_page_action('hr_business_group', 'view')
def business_group_history(request, pk):
    """Get historical versions of a business group.
    GET /hr/business-groups/{id}/history/"""
    try:
        business_group = BusinessGroup.objects.scoped(request.user).get(pk=pk)
    except BusinessGroup.DoesNotExist:
        return Response({'error': 'Business group not found'}, status=status.HTTP_404_NOT_FOUND)
    
    versions = BusinessGroup.objects.filter(code=business_group.code).order_by('-effective_start_date')
    serializer = BusinessGroupSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

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
        - business_group: Filter by business group code or name
        - enterprise: Filter by enterprise code or name
        - code: Filter by location code
        - name: Filter by location name
        - country: Filter by country
        - search: Search across code, name, country
    
    POST /hr/locations/
    - Create a new location
    - Request body: LocationSerializer fields
    """
    if request.method == 'GET':        
        locations = Location.objects.scoped(request.user).select_related(
            'enterprise',
            'business_group'
        )
        
        # Apply filters
        status_param = request.query_params.get('status')
        if status_param:
            locations = locations.filter(status=status_param)
        
        # Filter by enterprise (name or code)
        enterprise_filter = request.query_params.get('enterprise')
        if enterprise_filter:
            locations = locations.filter(
                Q(enterprise__name__icontains=enterprise_filter) |
                Q(enterprise__code__icontains=enterprise_filter)
            )
            
        # Filter by business group (name or code)
        business_group_filter = request.query_params.get('business_group')
        if business_group_filter:
            locations = locations.filter(
                Q(business_group__name__icontains=business_group_filter) |
                Q(business_group__code__icontains=business_group_filter)
            )
        code_filter = request.query_params.get('code')
        if code_filter:
            locations = locations.filter(code__icontains=code_filter)
        
        name_filter = request.query_params.get('name')
        if name_filter:
            locations = locations.filter(name__icontains=name_filter)
        
        country = request.query_params.get('country')
        if country:
            locations = locations.filter(country__icontains=country)
        
        search = request.query_params.get('search')
        if search:
            locations = locations.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search) |
                Q(country__icontains=search)
            )
        
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = LocationCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Validate data scope
                validate_location_scope(
                    request.user,
                    enterprise_id=serializer.validated_data.get('enterprise'),
                    business_group_id=serializer.validated_data.get('business_group')
                )
                
                location = serializer.save()
                # Return response using the read serializer for consistency
                response_serializer = LocationSerializer(location)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except PermissionDenied as e:
                return Response(
                    {'error': 'Permission denied', 'detail': str(e)},
                    status=status.HTTP_403_FORBIDDEN
                )
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
    Enforces data scope - returns 403 if location exists but user lacks access.
    """    
    # Scope-aware retrieval with proper 403 vs 404 handling
    try:
        location = Location.objects.scoped(request.user).select_related(
            'enterprise', 'business_group'
        ).get(pk=pk)
    except Location.DoesNotExist:
        # Check if exists outside user's scope
        if Location.objects.filter(pk=pk).exists():
            return Response(
                {'error': 'You do not have access to this location'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Location not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = LocationSerializer(location)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = LocationSerializer(location, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                # Validate new data scope if enterprise or business group is changing
                if 'enterprise' in serializer.validated_data or 'business_group' in serializer.validated_data:
                    new_ent = serializer.validated_data.get('enterprise', location.enterprise)
                    new_bg = serializer.validated_data.get('business_group', location.business_group)
                    
                    # For ModelSerializer, validated_data for FKs contains the instance
                    ent_id = new_ent.id if new_ent else None
                    bg_id = new_bg.id if new_bg else None
                    
                    validate_location_scope(request.user, enterprise_id=ent_id, business_group_id=bg_id)
                
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except PermissionDenied as e:
                return Response(
                    {'error': 'Permission denied', 'detail': str(e)},
                    status=status.HTTP_403_FORBIDDEN
                )
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
            # Validate location is not linked to active enterprise or business group
            if location.enterprise and location.enterprise.is_active:
                return Response(
                    {
                        'error': 'Cannot deactivate location linked to active enterprise',
                        'detail': 'Please deactivate or unlink the enterprise first',
                        'enterprise': {
                            'id': location.enterprise.id,
                            'code': location.enterprise.code,
                            'name': location.enterprise.name
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if location.business_group:
                # Check if business group is active
                active_bg = BusinessGroup.objects.filter(id=location.business_group.id).active()
                if active_bg.exists():
                    bg = location.business_group
                    return Response(
                        {
                            'error': 'Cannot deactivate location linked to active business group',
                            'detail': 'Please deactivate or unlink the business group first',
                            'business_group': {
                                'id': bg.id,
                                'code': bg.code,
                                'name': bg.name
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            location.status = 'inactive'
            location.save(update_fields=['status'])
            return Response(
                {'message': 'Location deactivated successfully'},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"Failed to deactivate location: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
