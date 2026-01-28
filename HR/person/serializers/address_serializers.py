"""
Serializers for Address model
"""
from rest_framework import serializers
from HR.person.models import Address, Person
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from HR.person.dtos import AddressCreateDTO, AddressUpdateDTO
class AddressSerializer(serializers.ModelSerializer):
    """Read serializer for Address model"""
    person = serializers.IntegerField(source='person.id', read_only=True)
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    address_type = serializers.IntegerField(source='address_type.id', read_only=True)
    address_type_name = serializers.CharField(source='address_type.name', read_only=True)
    country = serializers.IntegerField(source='country.id', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    city = serializers.IntegerField(source='city.id', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    class Meta:
        model = Address
        fields = [
            'id', 'person', 'person_name', 'address_type', 'address_type_name',
            'country', 'country_name', 'city', 'city_name',
            'street', 'address_line_1', 'address_line_2', 'address_line_3',
            'building_number', 'apartment_number', 'is_primary',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'person_id', 'person_name', 'address_type_id', 'address_type_name', 'country_id', 'country_name', 
                            'city_id', 'city_name', 'created_at', 'updated_at']
class AddressCreateSerializer(serializers.Serializer):
    """Write serializer for creating an address"""
    person_id = serializers.IntegerField()
    address_type_id = serializers.IntegerField()
    country_id = serializers.IntegerField()
    city_id = serializers.IntegerField()
    street = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address_line_1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line_3 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    building_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    apartment_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(default=False)
    def validate_person_id(self, value):
        try:
            Person.objects.get(pk=value)
        except Person.DoesNotExist:
            raise serializers.ValidationError("Person not found")
        return value
    def validate_address_type_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.ADDRESS_TYPE, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid address type")
        return value
    def validate_country_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.COUNTRY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid country")
        return value
    def validate_city_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CITY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid city")
        return value
    def validate(self, attrs):
        city_id = attrs.get('city_id')
        country_id = attrs.get('country_id')
        if city_id and country_id:
            city = LookupValue.objects.get(pk=city_id)
            if city.parent_id != country_id:
                raise serializers.ValidationError({
                    'city_id': "Selected city does not belong to the selected country"
                })
        return attrs
    def to_dto(self):
        return AddressCreateDTO(**self.validated_data)
class AddressUpdateSerializer(serializers.Serializer):
    """Write serializer for updating an address"""
    address_id = serializers.IntegerField()
    address_type_id = serializers.IntegerField(required=False)
    country_id = serializers.IntegerField(required=False)
    city_id = serializers.IntegerField(required=False)
    street = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address_line_1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line_3 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    building_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    apartment_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(required=False)
    def validate_address_id(self, value):
        try:
            Address.objects.get(pk=value, status='active')
        except Address.DoesNotExist:
            raise serializers.ValidationError("Address not found or inactive")
        return value
    def validate(self, attrs):
        city_id = attrs.get('city_id')
        country_id = attrs.get('country_id')
        if city_id and country_id:
            city = LookupValue.objects.get(pk=city_id)
            if city.parent_id != country_id:
                raise serializers.ValidationError({
                    'city_id': "Selected city does not belong to the selected country"
                })
        return attrs
    def to_dto(self):
        return AddressUpdateDTO(**self.validated_data)
