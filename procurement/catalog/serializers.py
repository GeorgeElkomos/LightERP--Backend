"""
Serializers for Catalog models.
Handles serialization/deserialization of UnitOfMeasure and catalogItem models for API endpoints.
"""
from rest_framework import serializers
from .models import UnitOfMeasure, catalogItem


# ============================================================================
# Unit of Measure Serializers
# ============================================================================

class UnitOfMeasureSerializer(serializers.ModelSerializer):
    """
    Full serializer for UnitOfMeasure model.
    Used for create, update, and detail views.
    """
    class Meta:
        model = UnitOfMeasure
        fields = [
            'id',
            'code',
            'name',
            'description',
            'uom_type',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        """Ensure UoM code is uppercase"""
        return value.upper()
    
    def validate(self, data):
        """Cross-field validation"""
        # Ensure code is unique (case-insensitive)
        code = data.get('code', '').upper()
        instance = self.instance
        
        if code:
            existing = UnitOfMeasure.objects.filter(code=code)
            if instance:
                existing = existing.exclude(pk=instance.pk)
            if existing.exists():
                raise serializers.ValidationError({
                    'code': 'A Unit of Measure with this code already exists.'
                })
        
        return data


class UnitOfMeasureListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing Units of Measure.
    """
    class Meta:
        model = UnitOfMeasure
        fields = [
            'id',
            'code',
            'name',
            'uom_type',
            'is_active',
        ]


# ============================================================================
# Catalog Item Serializers
# ============================================================================

class CatalogItemSerializer(serializers.ModelSerializer):
    """
    Full serializer for catalogItem model.
    Used for create, update, and detail views.
    """
    short_description = serializers.SerializerMethodField()
    
    class Meta:
        model = catalogItem
        fields = [
            'id',
            'code',
            'name',
            'description',
            'short_description',
        ]
        read_only_fields = ['id', 'short_description']
    
    def get_short_description(self, obj):
        """Get shortened description"""
        return obj.get_short_description()
    
    def validate_code(self, value):
        """Ensure code is uppercase"""
        return value.upper()
    
    def validate(self, data):
        """Cross-field validation"""
        # Ensure code is unique (case-insensitive)
        code = data.get('code', '').upper()
        instance = self.instance
        
        if code:
            existing = catalogItem.objects.filter(code=code)
            if instance:
                existing = existing.exclude(pk=instance.pk)
            if existing.exists():
                raise serializers.ValidationError({
                    'code': 'A catalog item with this code already exists.'
                })
        
        return data


class CatalogItemListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing catalog items.
    """
    class Meta:
        model = catalogItem
        fields = [
            'id',
            'code',
            'name',
        ]


class CatalogItemSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for catalog item search results.
    """
    short_description = serializers.SerializerMethodField()
    
    class Meta:
        model = catalogItem
        fields = [
            'id',
            'code',
            'name',
            'short_description',
        ]
    
    def get_short_description(self, obj):
        """Get shortened description"""
        return obj.get_short_description(max_length=50)
