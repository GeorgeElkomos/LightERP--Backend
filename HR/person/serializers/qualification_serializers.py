"""
Serializers for Qualification model
"""
from rest_framework import serializers
from HR.person.models import Qualification, Person, Competency
from HR.person.serializers.competency_serializers import CompetencySerializer
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from HR.person.dtos import QualificationCreateDTO, QualificationUpdateDTO
from datetime import date


class QualificationSerializer(serializers.ModelSerializer):
    """Read serializer for Qualification model"""
    person = serializers.IntegerField(source='person.id', read_only=True)
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    qualification_type = serializers.IntegerField(source='qualification_type.id', read_only=True)
    qualification_type_name = serializers.CharField(source='qualification_type.name', read_only=True)
    qualification_title = serializers.IntegerField(source='qualification_title.id', read_only=True)
    qualification_title_name = serializers.CharField(source='qualification_title.name', read_only=True)
    qualification_status = serializers.IntegerField(source='qualification_status.id', read_only=True)
    qualification_status_name = serializers.CharField(source='qualification_status.name', read_only=True)
    awarding_entity = serializers.IntegerField(source='awarding_entity.id', read_only=True)
    awarding_entity_name = serializers.CharField(source='awarding_entity.name', read_only=True)
    tuition_method = serializers.IntegerField(source='tuition_method.id', read_only=True, allow_null=True)
    tuition_method_name = serializers.CharField(source='tuition_method.name', read_only=True, allow_null=True)
    tuition_fees_currency = serializers.IntegerField(source='tuition_fees_currency.id', read_only=True, allow_null=True)
    tuition_fees_currency_name = serializers.CharField(source='tuition_fees_currency.name', read_only=True, allow_null=True)
    competency_achieved = CompetencySerializer(many=True, read_only=True)

    class Meta:
        model = Qualification
        fields = [
            'id', 'person', 'person_name',
            'qualification_type', 'qualification_type_name',
            'qualification_title', 'qualification_title_name', 'title_if_others',
            'qualification_status', 'qualification_status_name',
            'grade', 'awarding_entity', 'awarding_entity_name',
            'awarded_date', 'projected_completion_date', 'completed_percentage',
            'study_start_date', 'study_end_date',
            'competency_achieved',
            'tuition_method', 'tuition_method_name',
            'tuition_fees', 'tuition_fees_currency', 'tuition_fees_currency_name',
            'remarks', 'effective_start_date', 'effective_end_date',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'person_name', 'qualification_type_name',
            'qualification_title_name', 'qualification_status_name',
            'awarding_entity_name', 'tuition_method_name',
            'tuition_fees_currency_name', 'created_at', 'updated_at'
        ]


class QualificationCreateSerializer(serializers.Serializer):
    """Write serializer for creating a qualification"""
    person_id = serializers.IntegerField()
    qualification_type_id = serializers.IntegerField()
    qualification_title_id = serializers.IntegerField()
    qualification_status_id = serializers.IntegerField()
    awarding_entity_id = serializers.IntegerField()
    
    title_if_others = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    grade = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    awarded_date = serializers.DateField(required=False, allow_null=True)
    projected_completion_date = serializers.DateField(required=False, allow_null=True)
    completed_percentage = serializers.IntegerField(required=False, allow_null=True)
    
    study_start_date = serializers.DateField(required=False, allow_null=True)
    study_end_date = serializers.DateField(required=False, allow_null=True)
    
    competency_achieved_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_null=True)
    
    tuition_method_id = serializers.IntegerField(required=False, allow_null=True)
    tuition_fees = serializers.FloatField(required=False, allow_null=True)
    tuition_fees_currency_id = serializers.IntegerField(required=False, allow_null=True)
    
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    effective_start_date = serializers.DateField(required=False, allow_null=True)

    def validate_person_id(self, value):
        try:
            Person.objects.get(pk=value)
        except Person.DoesNotExist:
            raise serializers.ValidationError("Person not found")
        return value

    def validate_qualification_type_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.QUALIFICATION_TYPE, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active qualification type")
        return value

    def validate_qualification_title_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.QUALIFICATION_TITLE, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active qualification title")
        return value

    def validate_qualification_status_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.QUALIFICATION_STATUS, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active qualification status")
        return value

    def validate_awarding_entity_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.AWARDING_ENTITY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active awarding entity")
        return value

    def validate_tuition_method_id(self, value):
        if value is None:
            return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.TUITION_METHOD, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active tuition method")
        return value

    def validate_tuition_fees_currency_id(self, value):
        if value is None:
            return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CURRENCY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active currency")
        return value

    def validate(self, attrs):
        # Date validations
        study_start = attrs.get('study_start_date')
        study_end = attrs.get('study_end_date')
        
        if study_start and study_end and study_end < study_start:
            raise serializers.ValidationError({"study_end_date": "Study end date cannot be before start date"})

        # Percentage validation
        percentage = attrs.get('completed_percentage')
        if percentage is not None and (percentage < 0 or percentage > 100):
            raise serializers.ValidationError({"completed_percentage": "Percentage must be between 0 and 100"})

        # Fees validation
        fees = attrs.get('tuition_fees')
        currency = attrs.get('tuition_fees_currency_id')
        
        if fees is not None and fees < 0:
             raise serializers.ValidationError({"tuition_fees": "Tuition fees cannot be negative"})
        
        if fees is not None and not currency:
            raise serializers.ValidationError({"tuition_fees_currency_id": "Currency is required when fees are specified"})

        return attrs

    def to_dto(self) -> QualificationCreateDTO:
        return QualificationCreateDTO(**self.validated_data)


class QualificationUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a qualification"""
    qualification_id = serializers.IntegerField()
    qualification_type_id = serializers.IntegerField(required=False, allow_null=True)
    qualification_title_id = serializers.IntegerField(required=False, allow_null=True)
    qualification_status_id = serializers.IntegerField(required=False, allow_null=True)
    awarding_entity_id = serializers.IntegerField(required=False, allow_null=True)
    
    title_if_others = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    grade = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    awarded_date = serializers.DateField(required=False, allow_null=True)
    projected_completion_date = serializers.DateField(required=False, allow_null=True)
    completed_percentage = serializers.IntegerField(required=False, allow_null=True)
    
    study_start_date = serializers.DateField(required=False, allow_null=True)
    study_end_date = serializers.DateField(required=False, allow_null=True)
    
    competency_achieved_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_null=True)
    
    tuition_method_id = serializers.IntegerField(required=False, allow_null=True)
    tuition_fees = serializers.FloatField(required=False, allow_null=True)
    tuition_fees_currency_id = serializers.IntegerField(required=False, allow_null=True)
    
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_qualification_id(self, value):
        try:
            Qualification.objects.active().get(pk=value)
        except Qualification.DoesNotExist:
            raise serializers.ValidationError("Qualification not found or inactive")
        return value

    def validate_qualification_type_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.QUALIFICATION_TYPE, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active qualification type")
        return value

    def validate_qualification_title_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.QUALIFICATION_TITLE, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active qualification title")
        return value

    def validate_qualification_status_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.QUALIFICATION_STATUS, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active qualification status")
        return value

    def validate_awarding_entity_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.AWARDING_ENTITY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active awarding entity")
        return value

    def validate_tuition_method_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.TUITION_METHOD, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active tuition method")
        return value

    def validate_tuition_fees_currency_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CURRENCY, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active currency")
        return value
        
    def validate(self, attrs):
        # Percentage validation
        percentage = attrs.get('completed_percentage')
        if percentage is not None and (percentage < 0 or percentage > 100):
            raise serializers.ValidationError({"completed_percentage": "Percentage must be between 0 and 100"})

        # Fees validation
        fees = attrs.get('tuition_fees')
        if fees is not None and fees < 0:
             raise serializers.ValidationError({"tuition_fees": "Tuition fees cannot be negative"})
             
        return attrs

    def to_dto(self) -> QualificationUpdateDTO:
        return QualificationUpdateDTO(**self.validated_data)
