from django.db.models import Q
from .models import LookupType, LookupValue

class LookupService:
    @staticmethod
    def get_lookup_types():
        """
        Get all lookup types.
        """
        return LookupType.objects.all().order_by('name')

    @staticmethod
    def get_lookup_values(filters=None):
        """
        Get active lookup values based on filters.
        """
        queryset = LookupValue.objects.filter(is_active=True)
        
        if filters:
            if filters.get('lookup_type'):
                 # Support filtering by ID or Name
                 lookup_type = filters['lookup_type']
                 if str(lookup_type).isdigit():
                     queryset = queryset.filter(lookup_type__id=lookup_type)
                 else:
                     queryset = queryset.filter(lookup_type__name=lookup_type)
            
            if filters.get('parent_name'):
                queryset = queryset.filter(parent__name=filters['parent_name'])
                
            if filters.get('search'):
                search_term = filters['search']
                queryset = queryset.filter(
                    Q(name__icontains=search_term)
                )
        
        return queryset.order_by('sequence', 'name')

    @staticmethod
    def create_lookup_type(data):
        """Create a new lookup type"""
        return LookupType.objects.create(**data)

    @staticmethod
    def update_lookup_type(pk, data):
        """Update a lookup type"""
        lookup_type = LookupType.objects.get(pk=pk)
        for key, value in data.items():
            setattr(lookup_type, key, value)
        lookup_type.save()
        return lookup_type

    @staticmethod
    def delete_lookup_type(pk):
        """Delete a lookup type"""
        lookup_type = LookupType.objects.get(pk=pk)
        lookup_type.delete()

    @staticmethod
    def create_lookup_value(data):
        """Create a new lookup value"""
        return LookupValue.objects.create(**data)

    @staticmethod
    def update_lookup_value(pk, data):
        """Update a lookup value"""
        lookup_value = LookupValue.objects.get(pk=pk)
        for key, value in data.items():
            setattr(lookup_value, key, value)
        lookup_value.save()
        return lookup_value

    @staticmethod
    def delete_lookup_value(pk):
        """Delete a lookup value"""
        lookup_value = LookupValue.objects.get(pk=pk)
        lookup_value.delete()
