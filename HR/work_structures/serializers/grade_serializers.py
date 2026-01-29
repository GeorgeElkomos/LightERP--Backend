"""
Serializers for Grade and GradeRate models
"""
from rest_framework import serializers
import datetime
from HR.work_structures.models import Grade, GradeRate, GradeRateType, Organization
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from HR.work_structures.dtos import (
    GradeCreateDTO, GradeUpdateDTO,
    GradeRateCreateDTO, GradeRateUpdateDTO,
    GradeRateTypeCreateDTO, GradeRateTypeUpdateDTO
)


class FlexibleDateField(serializers.DateField):
    """DateField that handles datetime objects by converting them to date"""
    def to_representation(self, value):
        if isinstance(value, datetime.datetime):
            value = value.date()
        return super().to_representation(value)


class GradeReadSerializer(serializers.ModelSerializer):
    """Read serializer for Grade model"""
    business_group_id = serializers.IntegerField(source='organization.id', read_only=True)
    business_group_name = serializers.CharField(source='organization.organization_name', read_only=True)
    grade_name_id = serializers.IntegerField(source='grade_name.id', read_only=True)
    grade_name = serializers.CharField(source='grade_name.name', read_only=True)
    effective_from = FlexibleDateField()
    
    class Meta:
        model = Grade
        fields = [
            'id', 'business_group_id', 'business_group_name',
            'sequence', 'grade_name_id', 'grade_name', 'effective_from', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'business_group_id', 'business_group_name', 'grade_name_id', 'grade_name',
            'status', 'created_at', 'updated_at'
        ]


class GradeCreateSerializer(serializers.Serializer):
    """Write serializer for creating a grade"""
    business_group_id = serializers.IntegerField()
    grade_name_id = serializers.IntegerField()
    sequence = serializers.IntegerField()
    effective_from = serializers.DateField()

    def validate_sequence(self, value):
        if value <= 0:
            raise serializers.ValidationError("Sequence must be greater than 0")
        return value

    def to_dto(self) -> GradeCreateDTO:
        return GradeCreateDTO(**self.validated_data)


class GradeUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a grade"""
    grade_id = serializers.IntegerField()  # Primary Key
    grade_name_id = serializers.IntegerField(required=False)
    sequence = serializers.IntegerField(required=False)

    def validate_sequence(self, value):
        if value <= 0:
            raise serializers.ValidationError("Sequence must be greater than 0")
        return value

    def to_dto(self) -> GradeUpdateDTO:
        return GradeUpdateDTO(**self.validated_data)


class GradeRateTypeReadSerializer(serializers.ModelSerializer):
    """Read serializer for GradeRateType model"""
    class Meta:
        model = GradeRateType
        fields = ['id', 'code', 'description']


class GradeRateReadSerializer(serializers.ModelSerializer):
    """Read serializer for GradeRate model"""
    rate_type_code = serializers.CharField(source='rate_type.code', read_only=True)
    currency = serializers.CharField(source='currency.name', read_only=True)

    class Meta:
        model = GradeRate
        fields = [
            'id', 'grade', 'rate_type', 'rate_type_code',
            'min_amount', 'max_amount', 'fixed_amount', 'currency', 'currency_id',
            'effective_start_date', 'effective_end_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'rate_type_code',
            'created_at', 'updated_at'
        ]


class GradeRateCreateSerializer(serializers.Serializer):
    """Write serializer for creating a grade rate"""
    grade_id = serializers.IntegerField()
    rate_type_id = serializers.IntegerField()
    min_amount = serializers.FloatField(required=False, allow_null=True)
    max_amount = serializers.FloatField(required=False, allow_null=True)
    fixed_amount = serializers.FloatField(required=False, allow_null=True)
    currency_id = serializers.IntegerField(required=False, allow_null=True)
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_currency_id(self, value):
        if value is None:
            return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CURRENCY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active currency lookup ID")
        return value

    def to_dto(self) -> GradeRateCreateDTO:
        return GradeRateCreateDTO(**self.validated_data)


class GradeRateUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a grade rate"""
    grade_id = serializers.IntegerField()
    rate_type_id = serializers.IntegerField()
    min_amount = serializers.FloatField(required=False, allow_null=True)
    max_amount = serializers.FloatField(required=False, allow_null=True)
    fixed_amount = serializers.FloatField(required=False, allow_null=True)
    currency_id = serializers.IntegerField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)
    new_start_date = serializers.DateField(required=False, allow_null=True)

    def validate_currency_id(self, value):
        if value is None:
            return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CURRENCY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active currency lookup ID")
        return value

    def to_dto(self) -> GradeRateUpdateDTO:
        return GradeRateUpdateDTO(**self.validated_data)


class GradeRateTypeCreateSerializer(serializers.Serializer):
    """Write serializer for creating a grade rate type"""
    code = serializers.CharField(max_length=50)
    description = serializers.CharField(required=False, allow_blank=True)

    def to_dto(self) -> GradeRateTypeCreateDTO:
        return GradeRateTypeCreateDTO(**self.validated_data)


class GradeRateTypeUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a grade rate type"""
    rate_type_id = serializers.IntegerField()
    code = serializers.CharField(max_length=50, required=False)
    description = serializers.CharField(required=False, allow_blank=True)

    def to_dto(self) -> GradeRateTypeUpdateDTO:
        return GradeRateTypeUpdateDTO(**self.validated_data)
