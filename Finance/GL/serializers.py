"""
Serializers for General Ledger models.
Handles serialization/deserialization of GL models for API endpoints.
"""
from rest_framework import serializers
from .models import XX_SegmentType, XX_Segment


class SegmentTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for XX_SegmentType model.
    Includes all fields and computed properties.
    """
    can_delete = serializers.ReadOnlyField()
    
    class Meta:
        model = XX_SegmentType
        fields = [
            'id',
            'segment_name',
            'is_required',
            'has_hierarchy',
            'length',
            'display_order',
            'description',
            'is_active',
            'created_at',
            'updated_at',
            'can_delete',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'can_delete']


class SegmentTypeListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing segment types.
    """
    values_count = serializers.SerializerMethodField()
    
    class Meta:
        model = XX_SegmentType
        fields = [
            'id',
            'segment_name',
            'is_required',
            'has_hierarchy',
            'display_order',
            'description',
            'is_active',
            'values_count',
        ]
    
    def get_values_count(self, obj):
        """Get count of segment values for this type"""
        return obj.values.count()


class SegmentSerializer(serializers.ModelSerializer):
    """
    Serializer for XX_Segment model.
    Includes nested segment type information and computed properties.
    """
    segment_type_name = serializers.CharField(source='segment_type.segment_name', read_only=True)
    name = serializers.ReadOnlyField()
    parent_segment = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField()
    can_delete = serializers.ReadOnlyField()
    
    class Meta:
        model = XX_Segment
        fields = [
            'id',
            'segment_type',
            'segment_type_name',
            'code',
            'parent_code',
            'alias',
            'node_type',
            'is_active',
            'created_at',
            'updated_at',
            'name',
            'parent_segment',
            'full_path',
            'can_delete',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'name', 'parent_segment', 'full_path', 'can_delete']
    
    def get_parent_segment(self, obj):
        """Get parent segment information if exists"""
        parent = obj.parent
        if parent:
            return {
                'id': parent.id,
                'code': parent.code,
                'alias': parent.alias,
            }
        return None


class SegmentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing segments.
    """
    segment_type_name = serializers.CharField(source='segment_type.segment_name', read_only=True)
    
    class Meta:
        model = XX_Segment
        fields = [
            'id',
            'segment_type',
            'segment_type_name',
            'code',
            'alias',
            'node_type',
            'is_active',
        ]


class UsageDetailsSerializer(serializers.Serializer):
    """
    Serializer for usage details response.
    """
    is_used = serializers.BooleanField()
    usage_details = serializers.ListField(child=serializers.CharField())


class SegmentChildrenSerializer(serializers.Serializer):
    """
    Serializer for segment children response.
    """
    children_codes = serializers.ListField(child=serializers.CharField())
    children_count = serializers.IntegerField()


class FullPathSerializer(serializers.Serializer):
    """
    Serializer for full path response.
    """
    full_path = serializers.CharField()
    path_segments = serializers.ListField(child=serializers.CharField())
