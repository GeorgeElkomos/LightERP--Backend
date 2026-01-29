"""
Serializers for Organization model
"""
from rest_framework import serializers
from HR.work_structures.models import Organization, Location
from core.lookups.models import LookupValue
from HR.work_structures.dtos import OrganizationCreateDTO, OrganizationUpdateDTO


class OrganizationReadSerializer(serializers.ModelSerializer):
    """Read serializer for Organization model"""
    organization_type = serializers.CharField(source='organization_type.name', read_only=True)
    organization_name = serializers.CharField(read_only=True)
    business_group = serializers.CharField(source='business_group.organization_name', read_only=True)
    business_group_id = serializers.IntegerField(source='business_group.id', read_only=True, allow_null=True)
    location_name = serializers.CharField(source='location.location_name', read_only=True)
    is_business_group = serializers.BooleanField(read_only=True)
    hierarchy_level = serializers.IntegerField(read_only=True)
    working_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'organization_name', 'organization_type',
            'business_group', 'business_group_id',
            'location', 'location_name',
            'work_start_time', 'work_end_time', 'working_hours',
            'is_business_group', 'hierarchy_level',
            'effective_start_date', 'effective_end_date', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'organization_type', 'business_group', 'business_group_id',
            'location_name', 'is_business_group',
            'hierarchy_level', 'working_hours', 'status',
            'created_at', 'updated_at'
        ]



class OrganizationCreateSerializer(serializers.Serializer):
    """Write serializer for creating an organization"""
    organization_name = serializers.CharField(max_length=50)
    organization_type_id = serializers.IntegerField()
    location_id = serializers.IntegerField(required=False, allow_null=True)
    business_group_id = serializers.IntegerField(required=False, allow_null=True)
    work_start_time = serializers.TimeField(required=False)
    work_end_time = serializers.TimeField(required=False)
    effective_start_date = serializers.DateField()  # REQUIRED
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_organization_name(self, value):
        from datetime import date
        if Organization.objects.active_on(date.today()).filter(organization_name=value).exists():
            raise serializers.ValidationError("Active organization with this name already exists")
        return value

    def to_dto(self) -> OrganizationCreateDTO:
        # Filter out fields not in DTO if needed, but here we can just pass validated_data
        data = self.validated_data.copy()
        return OrganizationCreateDTO(**data)


class OrganizationUpdateSerializer(serializers.Serializer):
    """Write serializer for updating an organization"""
    organization_id = serializers.IntegerField()  # Primary Key
    organization_type_id = serializers.IntegerField(required=False)
    location_id = serializers.IntegerField(required=False, allow_null=True)
    work_start_time = serializers.TimeField(required=False)
    work_end_time = serializers.TimeField(required=False)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self) -> OrganizationUpdateDTO:
        data = self.validated_data.copy()
        return OrganizationUpdateDTO(**data)
