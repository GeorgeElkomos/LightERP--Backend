from django.db import transaction
from django.core.exceptions import ValidationError
from HR.person.models import PersonType
from HR.person.dtos import PersonTypeCreateDTO

class PersonTypeService:
    """Service for PersonType business logic"""
    
    @staticmethod
    def list_person_types(filters=None):
        """
        List person types with filtering.
        
        Args:
            filters (dict, optional): Filters for the query
                - base_type: Filter by base type (EMP, APL, CWK, CON)
                - is_active: Filter by active status (bool)
        
        Returns:
            QuerySet: Filtered PersonType queryset
        """
        queryset = PersonType.objects.all()
        
        if filters:
            if filters.get('base_type'):
                queryset = queryset.filter(base_type=filters['base_type'])
                
            # Handle is_active filter if explicitly provided
            # Note: If not provided, we return all (both active and inactive)
            # This matches the pattern of "view all records" default
            if filters.get('is_active') is not None:
                queryset = queryset.filter(is_active=filters['is_active'])
                
        return queryset.order_by('base_type', 'name')

    @staticmethod
    @transaction.atomic
    def create_person_type(user, dto: PersonTypeCreateDTO) -> PersonType:
        """
        Create a new person type.
        
        Args:
            user: The user performing the action (for audit)
            dto: PersonTypeCreateDTO with data
            
        Returns:
            PersonType: Created instance
        """
        # Validate base_type
        valid_base_types = [c[0] for c in PersonType.BASE_TYPE_CHOICES]
        if dto.base_type not in valid_base_types:
            raise ValidationError({'base_type': f"Invalid base_type. Must be one of: {', '.join(valid_base_types)}"})
            
        # Validate code uniqueness
        if PersonType.objects.filter(code=dto.code).exists():
             raise ValidationError({'code': f"Person type with code '{dto.code}' already exists."})

        person_type = PersonType(
            code=dto.code,
            name=dto.name,
            base_type=dto.base_type,
            description=dto.description or '',
            is_active=dto.is_active,
            created_by=user,
            updated_by=user
        )
        person_type.full_clean()
        person_type.save()
        
        return person_type
