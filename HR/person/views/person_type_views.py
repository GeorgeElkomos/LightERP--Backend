from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from core.job_roles.decorators import require_page_action
from HR.person.services.person_type_service import PersonTypeService
from HR.person.serializers.person_type_serializers import PersonTypeSerializer, PersonTypeCreateSerializer

@api_view(['GET', 'POST'])
@require_page_action('hr_person')
def person_type_list(request):
    """
    List person types or create a new one.
    
    GET /person/types/
    - Filters: base_type, is_active
    
    POST /person/types/
    - Create new person type
    """
    if request.method == 'GET':
        filters = {
            'base_type': request.query_params.get('base_type'),
            'is_active': request.query_params.get('is_active')
        }
        
        # Handle boolean conversion for is_active
        if filters['is_active'] is not None:
            filters['is_active'] = filters['is_active'].lower() == 'true'

        types = PersonTypeService.list_person_types(filters)
        serializer = PersonTypeSerializer(types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        serializer = PersonTypeCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                dto = serializer.to_dto()
                with transaction.atomic():
                    person_type = PersonTypeService.create_person_type(request.user, dto)
                return Response(PersonTypeSerializer(person_type).data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                error_detail = e.message_dict if hasattr(e, 'message_dict') else str(e)
                return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
