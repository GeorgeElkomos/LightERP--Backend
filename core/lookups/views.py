from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import LookupType, LookupValue
from .services import LookupService
from .serializers import LookupTypeSerializer, LookupValueSerializer

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def lookup_type_list(request):
    """
    List all lookup types or create a new one.
    """
    if request.method == 'GET':
        types = LookupService.get_lookup_types()
        serializer = LookupTypeSerializer(types, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = LookupTypeSerializer(data=request.data)
        if serializer.is_valid():
            lookup_type = LookupService.create_lookup_type(serializer.validated_data)
            return Response(LookupTypeSerializer(lookup_type).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def lookup_type_detail(request, pk):
    """
    Retrieve, update or delete a lookup type.
    """
    if request.method == 'GET':
        lookup_type = get_object_or_404(LookupType, pk=pk)
        serializer = LookupTypeSerializer(lookup_type)
        return Response(serializer.data)

    elif request.method == 'PUT':
        lookup_type = get_object_or_404(LookupType, pk=pk)
        serializer = LookupTypeSerializer(lookup_type, data=request.data)
        if serializer.is_valid():
            updated_type = LookupService.update_lookup_type(pk, serializer.validated_data)
            return Response(LookupTypeSerializer(updated_type).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        get_object_or_404(LookupType, pk=pk)
        LookupService.delete_lookup_type(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def lookup_value_list(request):
    """
    List lookup values with optional filtering or create a new one.
    Query Params:
    - lookup_type: Filter by lookup type ID or Code
    - parent_name: Filter by parent value ID
    - search: Search by name or code
    """
    if request.method == 'GET':
        filters = {
            'lookup_type': request.query_params.get('lookup_type'),
            'parent_name': request.query_params.get('parent_name'),
            'search': request.query_params.get('search')
        }
        values = LookupService.get_lookup_values(filters)
        serializer = LookupValueSerializer(values, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = LookupValueSerializer(data=request.data)
        if serializer.is_valid():
            lookup_value = LookupService.create_lookup_value(serializer.validated_data)
            return Response(LookupValueSerializer(lookup_value).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def lookup_value_detail(request, pk):
    """
    Retrieve, update or delete a lookup value.
    """
    if request.method == 'GET':
        lookup_value = get_object_or_404(LookupValue, pk=pk)
        serializer = LookupValueSerializer(lookup_value)
        return Response(serializer.data)

    elif request.method == 'PUT':
        lookup_value = get_object_or_404(LookupValue, pk=pk)
        serializer = LookupValueSerializer(lookup_value, data=request.data)
        if serializer.is_valid():
            updated_value = LookupService.update_lookup_value(pk, serializer.validated_data)
            return Response(LookupValueSerializer(updated_value).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        get_object_or_404(LookupValue, pk=pk)
        LookupService.delete_lookup_value(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
