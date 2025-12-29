import re
from rest_framework import serializers
from HR.work_structures.models import Enterprise, BusinessGroup, Location
from HR.work_structures.models.base import StatusChoices

from HR.work_structures.dtos import (
    EnterpriseCreateDTO, EnterpriseUpdateDTO,
    BusinessGroupCreateDTO, BusinessGroupUpdateDTO
)

class EnterpriseSerializer(serializers.ModelSerializer):
    """
    Serializer for Enterprise model (list/retrieve/update).
    Code is auto-generated from name if not provided.
    Code cannot be changed after creation.
    """
    code = serializers.CharField(required=False, allow_blank=True, default='', read_only=True)
    
    class Meta:
        model = Enterprise
        fields = [
            'id',
            'code',
            'name',
            'status',
            'effective_start_date',
            'effective_end_date'
        ]
        read_only_fields = ['id', 'code', 'status']


class EnterpriseCreateSerializer(serializers.Serializer):
    """
    Serializer for creating Enterprise.
    Code is optional - auto-generated from name if not provided.
    """
    code = serializers.CharField(required=False, allow_blank=True, default='')
    name = serializers.CharField(max_length=128)
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value
    
    def to_dto(self):
        return EnterpriseCreateDTO(
            code=self.validated_data.get('code', ''),
            name=self.validated_data['name'],
            effective_start_date=self.validated_data.get('effective_start_date'),
            effective_end_date=self.validated_data.get('effective_end_date')
        )


class EnterpriseUpdateSerializer(serializers.Serializer):
    """Serializer for updating Enterprise (creating new version)"""
    name = serializers.CharField(max_length=128, required=False)
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self, code):
        provided_fields = set()
        for field in ['name', 'effective_start_date', 'effective_end_date']:
            if field in self.validated_data:
                provided_fields.add(field)
        
        dto = EnterpriseUpdateDTO(
            code=code,
            name=self.validated_data.get('name'),
            effective_start_date=self.validated_data.get('effective_start_date'),
            effective_end_date=self.validated_data.get('effective_end_date')
        )
        dto._provided_fields = provided_fields
        return dto


class BusinessGroupSerializer(serializers.ModelSerializer):
    """
    Serializer for BusinessGroup model (list/retrieve/update).
    Code is auto-generated from name if not provided (scoped to enterprise).
    Enterprise cannot be changed after creation.
    """
    enterprise = serializers.IntegerField(source='enterprise.id', read_only=True)
    enterprise_name = serializers.CharField(source='enterprise.name', read_only=True)
    enterprise_code = serializers.CharField(source='enterprise.code', read_only=True)
    
    class Meta:
        model = BusinessGroup
        fields = [
            'id',
            'enterprise',
            'enterprise_name',
            'enterprise_code',
            'code',
            'name',
            'status',
            'effective_start_date',
            'effective_end_date'
        ]
        read_only_fields = ['id', 'enterprise', 'enterprise_name', 'enterprise_code', 'code', 'status']



class BusinessGroupCreateSerializer(serializers.Serializer):
    """
    Serializer for creating BusinessGroup.
    Code is optional - auto-generated from name if not provided.
    Enterprise is required and cannot be changed later.
    
    Supports flexible lookups for FK fields:
    - enterprise (ID) or enterprise_code (string)
    """
    code = serializers.CharField(required=False, allow_blank=True, default='')
    name = serializers.CharField(max_length=128)
    
    # Enterprise - ID or code lookup
    enterprise = serializers.IntegerField(required=False, allow_null=True)
    enterprise_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value
    
    def validate(self, data):
        """Convert enterprise_code to enterprise_id and validate"""        
        # Enterprise: code → ID
        enterprise_code = data.pop('enterprise_code', None)
        if enterprise_code and not data.get('enterprise'):
            try:
                ent = Enterprise.objects.filter(code=enterprise_code).first()
                if not ent:
                    raise Enterprise.DoesNotExist
                data['enterprise'] = ent.id
            except Enterprise.DoesNotExist:
                raise serializers.ValidationError({
                    'enterprise_code': f"No enterprise found with code '{enterprise_code}'"
                })
        
        if not data.get('enterprise'):
            raise serializers.ValidationError({'enterprise': 'Either enterprise or enterprise_code is required.'})
        
        return data
    
    def to_dto(self):
        return BusinessGroupCreateDTO(
            enterprise_id=self.validated_data['enterprise'],
            code=self.validated_data.get('code', ''),
            name=self.validated_data['name'],
            effective_start_date=self.validated_data.get('effective_start_date'),
            effective_end_date=self.validated_data.get('effective_end_date')
        )


class BusinessGroupUpdateSerializer(serializers.Serializer):
    """Serializer for updating BusinessGroup (creating new version)"""
    name = serializers.CharField(max_length=128, required=False)
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self, code):
        provided_fields = set()
        for field in ['name', 'effective_start_date', 'effective_end_date']:
            if field in self.validated_data:
                provided_fields.add(field)
        
        dto = BusinessGroupUpdateDTO(
            code=code,
            name=self.validated_data.get('name'),
            effective_start_date=self.validated_data.get('effective_start_date'),
            effective_end_date=self.validated_data.get('effective_end_date')
        )
        dto._provided_fields = provided_fields
        return dto
    


class LocationSerializer(serializers.ModelSerializer):
    """
    Serializer for Location model (list/retrieve/update).
    Code is auto-generated from name if not provided.
    Code cannot be changed after creation.
    """
    enterprise_name = serializers.CharField(source='enterprise.name', read_only=True, allow_null=True)
    business_group_name = serializers.CharField(source='business_group.name', read_only=True, allow_null=True)
    
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
            'address_details',
            'country',
            'status'
        ]
        read_only_fields = ['id', 'enterprise_name', 'business_group_name', 'code', 'status']
    
    def validate(self, data):
        """Validate that either enterprise or business_group is provided"""
        # Get from data or from instance if updating
        enterprise = data.get('enterprise', getattr(self.instance, 'enterprise', None) if self.instance else None)
        business_group = data.get('business_group', getattr(self.instance, 'business_group', None) if self.instance else None)
        
        if not enterprise and not business_group:
            raise serializers.ValidationError(
                "Must specify either 'enterprise' or 'business_group'."
            )
        
        if enterprise and business_group:
            # Validate that business_group belongs to the enterprise
            if business_group.enterprise != enterprise:
                raise serializers.ValidationError(
                    "Business Group must belong to the specified Enterprise."
                )
        
        return data


class LocationCreateSerializer(serializers.Serializer):
    """
    Serializer for creating Location.
    Code is optional - auto-generated from name if not provided.
    
    Supports flexible lookups for FK fields:
    - enterprise (ID) or enterprise_code (string)
    - business_group (ID) or business_group_code (string)
    """
    code = serializers.CharField(required=False, allow_blank=True, default='')
    name = serializers.CharField(max_length=128)
    address_details = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Enterprise - ID or code lookup (optional)
    enterprise = serializers.IntegerField(required=False, allow_null=True)
    enterprise_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Business Group - ID or code lookup (optional)
    business_group = serializers.IntegerField(required=False, allow_null=True)
    business_group_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value
    
    def validate(self, data):
        """Convert code lookups to IDs and validate hierarchy"""        
        # Enterprise: code → ID
        enterprise_code = data.pop('enterprise_code', None)
        if enterprise_code and not data.get('enterprise'):
            try:
                ent = Enterprise.objects.get(code=enterprise_code)
                data['enterprise'] = ent.id
            except Enterprise.DoesNotExist:
                raise serializers.ValidationError({
                    'enterprise_code': f"No enterprise found with code '{enterprise_code}'"
                })
        
        # Business Group: code → ID
        business_group_code = data.pop('business_group_code', None)
        if business_group_code and not data.get('business_group'):
            try:
                bg = BusinessGroup.objects.filter(code=business_group_code).active().first()
                if not bg:
                    raise BusinessGroup.DoesNotExist
                data['business_group'] = bg.id
            except BusinessGroup.DoesNotExist:
                raise serializers.ValidationError({
                    'business_group_code': f"No active business group found with code '{business_group_code}'"
                })
        
        enterprise = data.get('enterprise')
        business_group = data.get('business_group')
        
        if not enterprise and not business_group:
            raise serializers.ValidationError(
                "Must specify either 'enterprise'/'enterprise_code' or 'business_group'/'business_group_code'."
            )
        
        # If both provided, validate that business_group belongs to the enterprise
        if enterprise and business_group:
            try:
                bg = BusinessGroup.objects.get(id=business_group)
                if bg.enterprise_id != enterprise:
                    raise serializers.ValidationError(
                        "Business Group must belong to the specified Enterprise."
                    )
            except BusinessGroup.DoesNotExist:
                raise serializers.ValidationError({'business_group': 'Business Group not found.'})
        
        # Validate active status
        if business_group:
            try:
                bg = BusinessGroup.objects.get(id=business_group)
                if bg.status != StatusChoices.ACTIVE:
                    raise serializers.ValidationError(
                        f"Cannot create Location under inactive Business Group '{bg.name}'."
                    )
            except BusinessGroup.DoesNotExist:
                pass  # Already handled above
        
        if enterprise:
            try:
                ent = Enterprise.objects.get(id=enterprise)
                if ent.status != StatusChoices.ACTIVE:
                    raise serializers.ValidationError(
                        f"Cannot create Location under inactive Enterprise '{ent.name}'."
                    )
            except Enterprise.DoesNotExist:
                raise serializers.ValidationError({'enterprise': 'Enterprise not found.'})
        
        return data
    
    def create(self, validated_data):
        # Convert enterprise and business_group (IDs) to _id suffix for model creation
        if 'enterprise' in validated_data:
            validated_data['enterprise_id'] = validated_data.pop('enterprise')
        if 'business_group' in validated_data:
            validated_data['business_group_id'] = validated_data.pop('business_group')
        return Location.objects.create(**validated_data)
