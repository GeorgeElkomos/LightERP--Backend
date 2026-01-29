"""
Serializers for Contract model
"""
from rest_framework import serializers
from HR.person.models import Contract, Person
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups
from HR.person.dtos import ContractCreateDTO, ContractUpdateDTO
from datetime import date
from decimal import Decimal


class ContractSerializer(serializers.ModelSerializer):
    """Read serializer for Contract model"""
    person = serializers.IntegerField(source='person.id', read_only=True)
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    contract_status = serializers.IntegerField(source='contract_status.id', read_only=True)
    contract_status_name = serializers.CharField(source='contract_status.name', read_only=True)
    contract_end_reason = serializers.IntegerField(source='contract_end_reason.id', read_only=True, allow_null=True)
    contract_end_reason_name = serializers.CharField(source='contract_end_reason.name', read_only=True, allow_null=True)

    class Meta:
        model = Contract
        fields = [
            'id', 'contract_reference', 
            'person', 'person_name',
            'contract_status', 'contract_status_name',
            'contract_end_reason', 'contract_end_reason_name',
            'description',
            'contract_duration', 'contract_period',
            'contract_start_date', 'contract_end_date',
            'contractual_job_position',
            'extension_duration', 'extension_period',
            'extension_start_date', 'extension_end_date',
            'basic_salary',
            'effective_start_date', 'effective_end_date',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 
            'person', 'person_name', 'contract_status', 'contract_status_name', 
            'contract_end_reason', 'contract_end_reason_name'
        ]


class ContractCreateSerializer(serializers.Serializer):
    """Write serializer for creating a contract"""
    contract_reference = serializers.CharField(max_length=100)
    person_id = serializers.IntegerField()
    contract_status_id = serializers.IntegerField()
    contract_end_reason_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    contract_duration = serializers.DecimalField(max_digits=10, decimal_places=2)
    contract_period = serializers.ChoiceField(choices=Contract.PERIOD_CHOICES)
    contract_start_date = serializers.DateField()
    contract_end_date = serializers.DateField()
    
    contractual_job_position = serializers.CharField()
    
    extension_duration = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    extension_period = serializers.ChoiceField(choices=Contract.PERIOD_CHOICES, required=False, allow_null=True)
    extension_start_date = serializers.DateField(required=False, allow_null=True)
    extension_end_date = serializers.DateField(required=False, allow_null=True)
    
    basic_salary = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    effective_start_date = serializers.DateField()  # REQUIRED
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_person_id(self, value):
        try:
            Person.objects.get(pk=value)
        except Person.DoesNotExist:
            raise serializers.ValidationError("Person not found")
        return value

    def validate_contract_status_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CONTRACT_STATUS, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active contract status")
        return value

    def validate_contract_end_reason_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CONTRACT_END_REASON, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active contract end reason")
        return value

    def validate(self, attrs):
        start_date = attrs.get('contract_start_date')
        end_date = attrs.get('contract_end_date')
        
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"contract_end_date": "Contract end date must be after or equal to start date"})

        # Extension validation
        ext_start = attrs.get('extension_start_date')
        ext_end = attrs.get('extension_end_date')
        
        if ext_start and ext_end and ext_end < ext_start:
             raise serializers.ValidationError({"extension_end_date": "Extension end date must be after or equal to start date"})
             
        if end_date and ext_start and ext_start < end_date:
             raise serializers.ValidationError({"extension_start_date": "Extension start date must be after or equal to contract end date"})

        # Check reference uniqueness for effective start date
        ref = attrs.get('contract_reference')
        eff_start = attrs.get('effective_start_date') or date.today()
        
        if Contract.objects.filter(contract_reference=ref, effective_start_date=eff_start).exists():
             raise serializers.ValidationError({"contract_reference": "A contract with this reference and effective start date already exists"})

        return attrs

    def to_dto(self) -> ContractCreateDTO:
        data = self.validated_data.copy()
        # Default effective_start_date handled in service if None, but DTO expects date
        if not data.get('effective_start_date'):
            data['effective_start_date'] = date.today()
            
        return ContractCreateDTO(**data)


class ContractUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a contract"""
    contract_reference = serializers.CharField(max_length=100)
    effective_start_date = serializers.DateField() # Required to identify version or create new one
    
    contract_status_id = serializers.IntegerField(required=False, allow_null=True)
    contract_end_reason_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    contract_duration = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    contract_period = serializers.ChoiceField(choices=Contract.PERIOD_CHOICES, required=False, allow_null=True)
    contract_start_date = serializers.DateField(required=False, allow_null=True)
    contract_end_date = serializers.DateField(required=False, allow_null=True)
    
    contractual_job_position = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    extension_duration = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    extension_period = serializers.ChoiceField(choices=Contract.PERIOD_CHOICES, required=False, allow_null=True)
    extension_start_date = serializers.DateField(required=False, allow_null=True)
    extension_end_date = serializers.DateField(required=False, allow_null=True)
    
    basic_salary = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_contract_status_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CONTRACT_STATUS, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active contract status")
        return value

    def validate_contract_end_reason_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.CONTRACT_END_REASON, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active contract end reason")
        return value

    def to_dto(self) -> ContractUpdateDTO:
        return ContractUpdateDTO(**self.validated_data)
