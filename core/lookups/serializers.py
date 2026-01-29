from rest_framework import serializers
from .models import LookupType, LookupValue

class LookupTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupType
        fields = ['id', 'name', 'description']

class LookupValueSerializer(serializers.ModelSerializer):
    parent_name = serializers.SerializerMethodField()
    lookup_type_name = serializers.CharField(source='lookup_type.name', read_only=True)

    class Meta:
        model = LookupValue
        fields = ['id', 'lookup_type', 'lookup_type_name', 'name', 'description', 'sequence', 'is_active', 'parent', 'parent_name']

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent else None
