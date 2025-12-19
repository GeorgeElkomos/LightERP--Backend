import re
from rest_framework import serializers
from hr.models import Enterprise, BusinessGroup, Location


class EnterpriseSerializer(serializers.ModelSerializer):
    """
    Serializer for Enterprise model.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    """
    code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Enterprise
        fields = [
            'id',
            'code',
            'name',
            'status'
        ]
        read_only_fields = ['id']

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value


class BusinessGroupSerializer(serializers.ModelSerializer):
    """
    Serializer for BusinessGroup model.
    Code is auto-generated from name if not provided (scoped to enterprise).
    Access control for code editing is handled by role-based permissions.
    """
    enterprise_name = serializers.CharField(source='enterprise.name', read_only=True)
    enterprise_code = serializers.CharField(source='enterprise.code', read_only=True)
    code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = BusinessGroup
        fields = [
            'id',
            'enterprise',
            'enterprise_name',
            'enterprise_code',
            'code',
            'name',
            'status'
        ]
        read_only_fields = ['id', 'enterprise_name', 'enterprise_code']

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value


class LocationSerializer(serializers.ModelSerializer):
    """
    Serializer for Location model.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    """
    enterprise_name = serializers.CharField(source='enterprise.name', read_only=True, allow_null=True)
    business_group_name = serializers.CharField(source='business_group.name', read_only=True, allow_null=True)
    code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Location
        fields = [
            'id',
            'enterprise',
            'enterprise_name',
            'business_group',
            'business_group_name',
            'code',
            'name',
            'address_line1',
            'city',
            'country',
            'status'
        ]
        read_only_fields = ['id', 'enterprise_name', 'business_group_name']

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value