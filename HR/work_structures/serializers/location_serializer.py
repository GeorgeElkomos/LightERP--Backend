"""
Serializers for Location model
"""
from rest_framework import serializers
import datetime
from HR.work_structures.models import Location
from HR.work_structures.dtos import LocationCreateDTO, LocationUpdateDTO


class FlexibleDateField(serializers.DateField):
    """DateField that handles datetime objects by converting them to date"""
    def to_representation(self, value):
        if isinstance(value, datetime.datetime):
            value = value.date()
        return super().to_representation(value)


class LocationReadSerializer(serializers.ModelSerializer):
    """Read serializer for Location model"""
    business_group_name = serializers.SerializerMethodField()
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    city_code = serializers.CharField(source='city.code', read_only=True)
    effective_from = FlexibleDateField()

    class Meta:
        model = Location
        fields = [
            'id', 'business_group_name',
            'location_name', 'description',
            'country', 'country_name', 'country_code',
            'city', 'city_name', 'city_code',
            'zone', 'street', 'building', 'floor', 'office', 'po_box',
            'effective_from',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'business_group_name',
            'country_name', 'country_code', 'city_name', 'city_code',
            'status', 'created_at', 'updated_at'
        ]

    def get_business_group_name(self, obj):
        return obj.business_group.organization_name if obj.business_group else None


class LocationCreateSerializer(serializers.Serializer):
    """Write serializer for creating a location"""
    business_group_id = serializers.IntegerField(required=False, allow_null=True)
    location_name = serializers.CharField(max_length=128)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_id = serializers.IntegerField()
    city_id = serializers.IntegerField()
    zone = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    street = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    building = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    floor = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    office = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    po_box = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    effective_from = serializers.DateField()

    def validate_location_name(self, value):
        if Location.objects.filter(location_name=value).exists():
            raise serializers.ValidationError("Location with this name already exists")
        return value

    def to_dto(self) -> LocationCreateDTO:
        return LocationCreateDTO(**self.validated_data)


class LocationUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a location"""
    location_id = serializers.IntegerField()  # Primary Key
    location_name = serializers.CharField(max_length=128, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_id = serializers.IntegerField(required=False)
    city_id = serializers.IntegerField(required=False)
    business_group_id = serializers.IntegerField(required=False, allow_null=True)
    zone = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    street = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    building = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    floor = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    office = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    po_box = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)

    def to_dto(self) -> LocationUpdateDTO:
        return LocationUpdateDTO(**self.validated_data)
