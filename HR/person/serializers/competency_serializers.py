"""
Serializers for Competency and CompetencyProficiency models
"""
from datetime import date
from rest_framework import serializers
from HR.person.models import Competency, CompetencyProficiency, Person
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from HR.person.dtos import (
    CompetencyCreateDTO,
    CompetencyUpdateDTO,
    CompetencyProficiencyCreateDTO,
    CompetencyProficiencyUpdateDTO
)


class CompetencySerializer(serializers.ModelSerializer):
    """Read serializer for Competency model"""
    competency_category_id = serializers.IntegerField(source='category.id', read_only=True)
    competency_category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Competency
        fields = [
            'id', 'code', 'name', 'description', 
            'competency_category_id', 'competency_category_name',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'competency_category_id', 'competency_category_name', 'created_at', 'updated_at']


class CompetencyCreateSerializer(serializers.Serializer):
    """Write serializer for creating a competency"""
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=255)
    competency_category_id = serializers.IntegerField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_competency_category_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.COMPETENCY_CATEGORY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active competency category")
        return value

    def to_dto(self) -> CompetencyCreateDTO:
        return CompetencyCreateDTO(**self.validated_data)


class CompetencyUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a competency"""
    code = serializers.CharField(max_length=50)  # Used for identifying record to update if needed, but mainly for DTO
    name = serializers.CharField(max_length=255, required=False)
    competency_category_id = serializers.IntegerField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_competency_category_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.COMPETENCY_CATEGORY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active competency category")
        return value

    def to_dto(self) -> CompetencyUpdateDTO:
        return CompetencyUpdateDTO(**self.validated_data)


class CompetencyProficiencySerializer(serializers.ModelSerializer):
    """Read serializer for CompetencyProficiency model"""
    person = serializers.IntegerField(source='person.id', read_only=True)
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    competency = serializers.IntegerField(source='competency.id', read_only=True)
    competency_name = serializers.CharField(source='competency.name', read_only=True)
    competency_code = serializers.CharField(source='competency.code', read_only=True)
    competency_category_id = serializers.IntegerField(source='competency.category.id', read_only=True)
    competency_category_name = serializers.CharField(source='competency.category.name', read_only=True)
    proficiency_level = serializers.IntegerField(source='proficiency_level.id', read_only=True)
    proficiency_level_name = serializers.CharField(source='proficiency_level.name', read_only=True)
    proficiency_source = serializers.IntegerField(source='proficiency_source.id', read_only=True)
    proficiency_source_name = serializers.CharField(source='proficiency_source.name', read_only=True)

    class Meta:
        model = CompetencyProficiency
        fields = [
            'id', 'person', 'person_name',
            'competency', 'competency_name', 'competency_code',
            'competency_category_id', 'competency_category_name',
            'proficiency_level', 'proficiency_level_name',
            'effective_start_date', 'effective_end_date',
            'proficiency_source', 'proficiency_source_name',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'person_name', 'competency', 'competency_name', 'competency_code',
            'competency_category_id', 'competency_category_name',
            'proficiency_level', 'proficiency_level_name', 
            'proficiency_source', 'proficiency_source_name',
            'created_at', 'updated_at', 'status'
        ]


class CompetencyProficiencyCreateSerializer(serializers.Serializer):
    """Write serializer for creating a competency proficiency"""
    person_id = serializers.IntegerField()
    competency_id = serializers.IntegerField()
    proficiency_level_id = serializers.IntegerField()
    proficiency_source_id = serializers.IntegerField()
    effective_start_date = serializers.DateField()
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_person_id(self, value):
        try:
            Person.objects.get(pk=value)
        except Person.DoesNotExist:
            raise serializers.ValidationError("Person not found")
        return value

    def validate_competency_id(self, value):
        try:
            Competency.objects.active().get(pk=value)
        except Competency.DoesNotExist:
            raise serializers.ValidationError("Competency not found or inactive")
        return value

    def validate_proficiency_level_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.PROFICIENCY_LEVEL, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active proficiency level")
        return value

    def validate_proficiency_source_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.PROFICIENCY_SOURCE, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active proficiency source")
        return value

    def validate(self, attrs):
        effective_start_date = attrs.get('effective_start_date')
        effective_end_date = attrs.get('effective_end_date')
        
        if effective_start_date and effective_start_date > date.today():
            raise serializers.ValidationError({"effective_start_date": "Start date cannot be in the future"})
            
        if effective_end_date and effective_start_date and effective_end_date < effective_start_date:
            raise serializers.ValidationError({"effective_end_date": "End date must be on or after start date"})
            
        return attrs

    def to_dto(self) -> CompetencyProficiencyCreateDTO:
        return CompetencyProficiencyCreateDTO(**self.validated_data)


class CompetencyProficiencyUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a competency proficiency"""
    proficiency_id = serializers.IntegerField()
    proficiency_level_id = serializers.IntegerField(required=False, allow_null=True)
    proficiency_source_id = serializers.IntegerField(required=False, allow_null=True)
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_proficiency_id(self, value):
        try:
            CompetencyProficiency.objects.active_on(date.today()).get(pk=value)
        except CompetencyProficiency.DoesNotExist:
            raise serializers.ValidationError("Competency proficiency record not found or inactive")
        return value

    def validate_proficiency_level_id(self, value):
        if value is None: 
            return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.PROFICIENCY_LEVEL, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active proficiency level")
        return value

    def validate_proficiency_source_id(self, value):
        if value is None:
            return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.PROFICIENCY_SOURCE, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active proficiency source")
        return value

    def to_dto(self) -> CompetencyProficiencyUpdateDTO:
        return CompetencyProficiencyUpdateDTO(**self.validated_data)
