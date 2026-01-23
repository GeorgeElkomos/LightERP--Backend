"""
Budget Control Serializers - API Serialization for Budget Management

Provides serializers for:
- BudgetHeader: Main budget with nested segment values and amounts
- BudgetSegmentValue: Individual segment with control level override
- BudgetAmount: Budget allocation with consumption tracking
- Budget checking and reporting
"""

from rest_framework import serializers
from decimal import Decimal
from datetime import date

from Finance.budget_control.models import (
    BudgetHeader,
    BudgetSegmentValue,
    BudgetAmount
)
from Finance.GL.models import XX_Segment, XX_SegmentType
from Finance.core.models import Currency


# ============================================================================
# BUDGET AMOUNT SERIALIZERS
# ============================================================================

class BudgetAmountListSerializer(serializers.ModelSerializer):
    """
    List/Read serializer for BudgetAmount - includes segment details and calculations.
    """
    segment_value_code = serializers.CharField(source='budget_segment_value.segment_value.code', read_only=True)
    segment_value_name = serializers.CharField(source='budget_segment_value.segment_value.name', read_only=True)
    segment_type_name = serializers.CharField(source='budget_segment_value.segment_value.segment_type.segment_name', read_only=True)
    control_level = serializers.CharField(source='budget_segment_value.control_level', read_only=True)
    effective_control_level = serializers.SerializerMethodField()
    
    # Calculated fields
    total_budget = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    consumed_total = serializers.SerializerMethodField()
    utilization_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = BudgetAmount
        fields = [
            'id',
            'budget_segment_value',
            'segment_value_code',
            'segment_value_name',
            'segment_type_name',
            'control_level',
            'effective_control_level',
            'original_budget',
            'adjustment_amount',
            'total_budget',
            'committed_amount',
            'encumbered_amount',
            'actual_amount',
            'available',
            'consumed_total',
            'utilization_percentage',
            'notes',
            'last_committed_date',
            'last_encumbered_date',
            'last_actual_date',
            'last_adjustment_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'committed_amount',
            'encumbered_amount',
            'actual_amount',
            'last_committed_date',
            'last_encumbered_date',
            'last_actual_date',
            'last_adjustment_date',
            'created_at',
            'updated_at',
        ]
    
    def get_effective_control_level(self, obj):
        return obj.get_effective_control_level()
    
    def get_total_budget(self, obj):
        return obj.get_total_budget()
    
    def get_available(self, obj):
        return str(obj.get_available())
    
    def get_consumed_total(self, obj):
        return str(obj.get_consumed_total())
    
    def get_utilization_percentage(self, obj):
        return str(obj.get_utilization_percentage())


class BudgetAmountCreateSerializer(serializers.Serializer):
    """
    Create serializer for BudgetAmount - used within BudgetHeader creation.
    Accepts segment_value_id and original_budget.
    """
    segment_value_id = serializers.IntegerField()
    original_budget = serializers.DecimalField(max_digits=15, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_segment_value_id(self, value):
        """Validate that segment exists"""
        if not XX_Segment.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Segment with ID {value} does not exist")
        return value
    
    def validate_original_budget(self, value):
        """Validate budget amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Budget amount must be greater than zero")
        return value


# ============================================================================
# BUDGET SEGMENT VALUE SERIALIZERS
# ============================================================================

class BudgetSegmentValueListSerializer(serializers.ModelSerializer):
    """
    List/Read serializer for BudgetSegmentValue - includes segment details and budget amount.
    """
    segment_value_code = serializers.CharField(source='segment_value.code', read_only=True)
    segment_value_name = serializers.CharField(source='segment_value.name', read_only=True)
    segment_type_id = serializers.IntegerField(source='segment_value.segment_type.id', read_only=True)
    segment_type_name = serializers.CharField(source='segment_value.segment_type.segment_name', read_only=True)
    effective_control_level = serializers.SerializerMethodField()
    has_budget_amount = serializers.SerializerMethodField()
    budget_amount_details = BudgetAmountListSerializer(source='budget_amount', read_only=True)
    
    class Meta:
        model = BudgetSegmentValue
        fields = [
            'id',
            'budget_header',
            'segment_value',
            'segment_value_code',
            'segment_value_name',
            'segment_type_id',
            'segment_type_name',
            'control_level',
            'effective_control_level',
            'is_active',
            'notes',
            'has_budget_amount',
            'budget_amount_details',
            'created_at',
            'updated_at',
        ]
    
    def get_effective_control_level(self, obj):
        return obj.get_effective_control_level()
    
    def get_has_budget_amount(self, obj):
        return obj.has_budget()


class BudgetSegmentValueCreateSerializer(serializers.Serializer):
    """
    Create serializer for BudgetSegmentValue - used within BudgetHeader creation.
    Accepts segment_value_id and optional control_level override.
    """
    segment_value_id = serializers.IntegerField()
    control_level = serializers.ChoiceField(
        choices=BudgetSegmentValue.CONTROL_LEVEL_CHOICES,
        required=False,
        allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_segment_value_id(self, value):
        """Validate that segment exists"""
        if not XX_Segment.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Segment with ID {value} does not exist")
        return value


# ============================================================================
# BUDGET HEADER SERIALIZERS
# ============================================================================

class BudgetHeaderListSerializer(serializers.ModelSerializer):
    """
    List serializer for BudgetHeader - summary view with totals.
    """
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    total_budget = serializers.SerializerMethodField()
    total_encumbered = serializers.SerializerMethodField()
    total_actual = serializers.SerializerMethodField()
    total_available = serializers.SerializerMethodField()
    utilization_percentage = serializers.SerializerMethodField()
    segment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BudgetHeader
        fields = [
            'id',
            'budget_code',
            'budget_name',
            'description',
            'start_date',
            'end_date',
            'currency',
            'currency_code',
            'default_control_level',
            'status',
            'is_active',
            'total_budget',
            'total_encumbered',
            'total_actual',
            'total_available',
            'utilization_percentage',
            'segment_count',
            'created_by',
            'created_at',
            'activated_by',
            'activated_at',
        ]
    
    def get_total_budget(self, obj):
        return str(obj.get_total_budget())
    
    def get_total_encumbered(self, obj):
        return str(obj.get_total_encumbered())
    
    def get_total_actual(self, obj):
        return str(obj.get_total_actual())
    
    def get_total_available(self, obj):
        return str(obj.get_total_available())
    
    def get_utilization_percentage(self, obj):
        return str(obj.get_utilization_percentage())
    
    def get_segment_count(self, obj):
        return obj.budget_segment_values.count()


class BudgetHeaderDetailSerializer(serializers.ModelSerializer):
    """
    Detail serializer for BudgetHeader - includes nested segment values and amounts.
    """
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    segment_values = BudgetSegmentValueListSerializer(source='budget_segment_values', many=True, read_only=True)
    budget_amounts = BudgetAmountListSerializer(many=True, read_only=True)
    
    # Summary fields
    total_budget = serializers.SerializerMethodField()
    total_encumbered = serializers.SerializerMethodField()
    total_actual = serializers.SerializerMethodField()
    total_available = serializers.SerializerMethodField()
    utilization_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = BudgetHeader
        fields = [
            'id',
            'budget_code',
            'budget_name',
            'description',
            'start_date',
            'end_date',
            'currency',
            'currency_code',
            'default_control_level',
            'status',
            'is_active',
            'notes',
            'segment_values',
            'budget_amounts',
            'total_budget',
            'total_encumbered',
            'total_actual',
            'total_available',
            'utilization_percentage',
            'created_by',
            'created_at',
            'updated_at',
            'activated_by',
            'activated_at',
        ]
    
    def get_total_budget(self, obj):
        return str(obj.get_total_budget())
    
    def get_total_encumbered(self, obj):
        return str(obj.get_total_encumbered())
    
    def get_total_actual(self, obj):
        return str(obj.get_total_actual())
    
    def get_total_available(self, obj):
        return str(obj.get_total_available())
    
    def get_utilization_percentage(self, obj):
        return str(obj.get_utilization_percentage())


class BudgetHeaderCreateSerializer(serializers.Serializer):
    """
    Create serializer for BudgetHeader with nested segment values and amounts.
    This handles the complete budget creation workflow.
    """
    budget_code = serializers.CharField(max_length=50)
    budget_name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    currency_id = serializers.IntegerField()
    default_control_level = serializers.ChoiceField(
        choices=BudgetHeader.CONTROL_LEVEL_CHOICES,
        default='ABSOLUTE'
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Nested data
    segment_values = BudgetSegmentValueCreateSerializer(many=True)
    budget_amounts = BudgetAmountCreateSerializer(many=True)
    
    def validate_budget_code(self, value):
        """Validate that budget code is unique"""
        if BudgetHeader.objects.filter(budget_code=value).exists():
            raise serializers.ValidationError(f"Budget with code '{value}' already exists")
        return value
    
    def validate_currency_id(self, value):
        """Validate that currency exists"""
        if not Currency.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Currency with ID {value} does not exist")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Validate date range
        if data['end_date'] <= data['start_date']:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })
        
        # Validate that all budget amounts have corresponding segment values
        segment_value_ids = {sv['segment_value_id'] for sv in data['segment_values']}
        budget_amount_segment_ids = {ba['segment_value_id'] for ba in data['budget_amounts']}
        
        missing_segments = budget_amount_segment_ids - segment_value_ids
        if missing_segments:
            raise serializers.ValidationError({
                'budget_amounts': f'Budget amounts reference segments not in segment_values: {missing_segments}'
            })
        
        return data
    
    def create(self, validated_data):
        """Create budget header with nested segment values and amounts"""
        from django.db import transaction
        
        segment_values_data = validated_data.pop('segment_values')
        budget_amounts_data = validated_data.pop('budget_amounts')
        currency_id = validated_data.pop('currency_id')
        
        with transaction.atomic():
            # Create budget header
            budget_header = BudgetHeader.objects.create(
                currency_id=currency_id,
                status='DRAFT',
                is_active=False,
                **validated_data
            )
            
            # Create segment values
            segment_value_map = {}
            for sv_data in segment_values_data:
                segment_value_id = sv_data.pop('segment_value_id')
                budget_segment = BudgetSegmentValue.objects.create(
                    budget_header=budget_header,
                    segment_value_id=segment_value_id,
                    **sv_data
                )
                segment_value_map[segment_value_id] = budget_segment
            
            # Create budget amounts
            for ba_data in budget_amounts_data:
                segment_value_id = ba_data.pop('segment_value_id')
                budget_segment = segment_value_map[segment_value_id]
                
                BudgetAmount.objects.create(
                    budget_segment_value=budget_segment,
                    budget_header=budget_header,
                    **ba_data
                )
        
        return budget_header


class BudgetHeaderUpdateSerializer(serializers.ModelSerializer):
    """
    Update serializer for BudgetHeader - only allows updating header fields.
    Segment values and amounts must be updated separately.
    """
    class Meta:
        model = BudgetHeader
        fields = [
            'budget_name',
            'description',
            'start_date',
            'end_date',
            'default_control_level',
            'notes',
        ]
    
    def validate(self, data):
        """Prevent updates to active or closed budgets"""
        if self.instance.status == 'CLOSED':
            raise serializers.ValidationError("Cannot update a closed budget")
        
        if self.instance.status == 'ACTIVE':
            raise serializers.ValidationError("Cannot update an active budget. Deactivate it first.")
        
        # Validate date range if being updated
        if 'start_date' in data or 'end_date' in data:
            start_date = data.get('start_date', self.instance.start_date)
            end_date = data.get('end_date', self.instance.end_date)
            
            if end_date <= start_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })
        
        return data


# ============================================================================
# ACTION SERIALIZERS
# ============================================================================

class BudgetActivateSerializer(serializers.Serializer):
    """Serializer for activating a budget"""
    activated_by = serializers.CharField(max_length=100)


class BudgetCheckSerializer(serializers.Serializer):
    """
    Serializer for checking budget availability.
    Used by PO/Invoice approval process.
    """
    segment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of segment value IDs from the transaction"
    )
    transaction_amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Transaction amount to check"
    )
    transaction_date = serializers.DateField(
        required=False,
        help_text="Transaction date (defaults to today)"
    )
    
    def validate_segment_ids(self, value):
        """Validate that all segments exist"""
        if not value:
            raise serializers.ValidationError("Must provide at least one segment ID")
        
        existing_ids = set(XX_Segment.objects.filter(id__in=value).values_list('id', flat=True))
        missing_ids = set(value) - existing_ids
        
        if missing_ids:
            raise serializers.ValidationError(f"Segment IDs do not exist: {missing_ids}")
        
        return value
    
    def validate_transaction_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Transaction amount must be greater than zero")
        return value


class BudgetCheckResponseSerializer(serializers.Serializer):
    """
    Response serializer for budget check results.
    """
    allowed = serializers.BooleanField()
    control_level = serializers.CharField()
    message = serializers.CharField()
    violations = serializers.ListField(required=False)
    budget_code = serializers.CharField()
    budget_name = serializers.CharField()


# ============================================================================
# EXCEL IMPORT/EXPORT SERIALIZERS
# ============================================================================

class BudgetAmountImportSerializer(serializers.Serializer):
    """
    Serializer for bulk importing budget amounts from Excel.
    Expected format: segment_type_name, segment_code, original_budget, notes
    """
    segment_type_name = serializers.CharField()
    segment_code = serializers.CharField(max_length=50)
    original_budget = serializers.DecimalField(max_digits=15, decimal_places=2)
    control_level = serializers.ChoiceField(
        choices=BudgetSegmentValue.CONTROL_LEVEL_CHOICES,
        required=False,
        allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate that segment exists"""
        try:
            segment_type = XX_SegmentType.objects.get(segment_name=data['segment_type_name'])
            segment = XX_Segment.objects.get(
                segment_type=segment_type,
                code=data['segment_code']
            )
            data['segment_value'] = segment
            data['segment_type'] = segment_type
        except XX_SegmentType.DoesNotExist:
            raise serializers.ValidationError({
                'segment_type_name': f"Segment type '{data['segment_type_name']}' does not exist"
            })
        except XX_Segment.DoesNotExist:
            raise serializers.ValidationError({
                'segment_code': f"Segment '{data['segment_code']}' does not exist for type '{data['segment_type_name']}'"
            })
        
        return data
