"""
Finance Period Serializers

Handles serialization for period management including:
1. Single period creation
2. Bulk period generation (preview)
3. Bulk period save
"""
from rest_framework import serializers
from datetime import date
from .models import Period, ar_period, ap_period, gl_period


class PeriodSerializer(serializers.ModelSerializer):
    """
    Standard serializer for Period model.
    Used for single period creation and display.
    """
    duration_days = serializers.SerializerMethodField()
    
    class Meta:
        model = Period
        fields = [
            'id',
            'name',
            'start_date',
            'end_date',
            'fiscal_year',
            'period_number',
            'is_adjustment_period',
            'description',
            'duration_days',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_duration_days(self, obj):
        """Calculate duration in days"""
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days + 1
        return 0
    
    def validate(self, data):
        """Validate period data"""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date.'
                })
        
        if data.get('period_number'):
            if data['period_number'] < 1 or data['period_number'] > 13:
                raise serializers.ValidationError({
                    'period_number': 'Period number must be between 1 and 13.'
                })
        
        return data


class PeriodGenerationInputSerializer(serializers.Serializer):
    """
    Input serializer for generating a list of periods (preview).
    Does not save to database - only generates preview data.
    """
    start_date = serializers.DateField(
        required=True,
        help_text="Starting date for the first period (e.g., 2026-01-01)"
    )
    fiscal_year = serializers.IntegerField(
        required=True,
        help_text="Fiscal year (e.g., 2026)",
        min_value=2000,
        max_value=2100
    )
    num_periods = serializers.IntegerField(
        required=True,
        help_text="Number of regular periods (typically 12)",
        min_value=1,
        max_value=12
    )
    num_adjustment_periods = serializers.IntegerField(
        required=False,
        default=0,
        help_text="Number of adjustment periods (0-2)",
        min_value=0,
        max_value=12
    )
    adjustment_period_days = serializers.IntegerField(
        required=False,
        default=1,
        help_text="Duration in days for each adjustment period",
        min_value=1,
        max_value=31
    )
    
    def validate(self, data):
        """Additional validation"""
        # Ensure fiscal year matches start date year (or is close)
        start_year = data['start_date'].year
        fiscal_year = data['fiscal_year']
        
        if abs(start_year - fiscal_year) > 1:
            raise serializers.ValidationError(
                "Fiscal year should match or be close to the start date year."
            )
        
        return data


class PeriodGenerationOutputSerializer(serializers.Serializer):
    """
    Output serializer for generated periods preview.
    Returns the generated period data without saving.
    """
    name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    fiscal_year = serializers.IntegerField()
    period_number = serializers.IntegerField()
    is_adjustment_period = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True, allow_null=True)
    duration_days = serializers.SerializerMethodField()
    
    def get_duration_days(self, obj):
        """Calculate duration in days"""
        if hasattr(obj, 'start_date') and hasattr(obj, 'end_date'):
            return (obj.end_date - obj.start_date).days + 1
        return 0


class PeriodBulkSaveSerializer(serializers.Serializer):
    """
    Serializer for bulk saving periods.
    Accepts a list of period data and saves them to the database.
    """
    periods = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        help_text="List of period objects to save"
    )
    
    def validate_periods(self, value):
        """Validate each period in the list"""
        if not value:
            raise serializers.ValidationError("At least one period is required.")
        
        if len(value) > 15:
            raise serializers.ValidationError("Cannot save more than 15 periods at once.")
        
        # Validate each period
        for idx, period_data in enumerate(value):
            # Required fields
            required_fields = ['name', 'start_date', 'end_date', 'fiscal_year', 'period_number']
            for field in required_fields:
                if field not in period_data:
                    raise serializers.ValidationError(
                        f"Period {idx + 1}: Missing required field '{field}'"
                    )
            
            # Validate dates
            try:
                start_date = date.fromisoformat(str(period_data['start_date']))
                end_date = date.fromisoformat(str(period_data['end_date']))
                
                if start_date > end_date:
                    raise serializers.ValidationError(
                        f"Period {idx + 1}: End date must be after start date"
                    )
            except (ValueError, TypeError) as e:
                raise serializers.ValidationError(
                    f"Period {idx + 1}: Invalid date format - {str(e)}"
                )
            
            # Validate period number
            period_num = period_data.get('period_number')
            if not isinstance(period_num, int) or period_num < 1 or period_num > 13:
                raise serializers.ValidationError(
                    f"Period {idx + 1}: Period number must be between 1 and 13"
                )
        
        return value
    
    def create(self, validated_data):
        """Create periods individually to trigger automatic child creation"""
        periods_data = validated_data['periods']
        
        # Create Period objects individually (not bulk_create)
        # This ensures the save() method is called and child records are created
        created_periods = []
        for period_data in periods_data:
            # Convert date strings to date objects
            start_date = period_data['start_date']
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)
            
            end_date = period_data['end_date']
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)
            
            # Create and save period (triggers automatic child creation)
            period = Period.objects.create(
                name=period_data['name'],
                start_date=start_date,
                end_date=end_date,
                fiscal_year=period_data['fiscal_year'],
                period_number=period_data['period_number'],
                is_adjustment_period=period_data.get('is_adjustment_period', False),
                description=period_data.get('description', '')
            )
            created_periods.append(period)
        
        return {
            'created_count': len(created_periods),
            'periods': created_periods
        }


class PeriodListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing periods.
    """
    class Meta:
        model = Period
        fields = [
            'id',
            'name',
            'start_date',
            'end_date',
            'fiscal_year',
            'period_number',
            'is_adjustment_period'
        ]


# ============================================================================
# Child Period Serializers (AR, AP, GL)
# ============================================================================

class AR_PeriodSerializer(serializers.ModelSerializer):
    """
    Serializer for AR Period child records.
    """
    period_name = serializers.CharField(source='period.name', read_only=True)
    fiscal_year = serializers.IntegerField(source='period.fiscal_year', read_only=True)
    period_number = serializers.IntegerField(source='period.period_number', read_only=True)
    start_date = serializers.DateField(source='period.start_date', read_only=True)
    end_date = serializers.DateField(source='period.end_date', read_only=True)
    
    class Meta:
        model = ar_period
        fields = [
            'id',
            'period',
            'period_name',
            'fiscal_year',
            'period_number',
            'start_date',
            'end_date',
            'state'
        ]
        read_only_fields = ['id', 'period']
    
    def get_state_display(self, obj):
        """Get human-readable state"""
        return obj.get_state_display()


class AP_PeriodSerializer(serializers.ModelSerializer):
    """
    Serializer for AP Period child records.
    """
    period_name = serializers.CharField(source='period.name', read_only=True)
    fiscal_year = serializers.IntegerField(source='period.fiscal_year', read_only=True)
    period_number = serializers.IntegerField(source='period.period_number', read_only=True)
    start_date = serializers.DateField(source='period.start_date', read_only=True)
    end_date = serializers.DateField(source='period.end_date', read_only=True)
    
    class Meta:
        model = ap_period
        fields = [
            'id',
            'period',
            'period_name',
            'fiscal_year',
            'period_number',
            'start_date',
            'end_date',
            'state'
        ]
        read_only_fields = ['id', 'period']
    
    def get_state_display(self, obj):
        """Get human-readable state"""
        return obj.get_state_display()


class GL_PeriodSerializer(serializers.ModelSerializer):
    """
    Serializer for GL Period child records.
    """
    period_name = serializers.CharField(source='period.name', read_only=True)
    fiscal_year = serializers.IntegerField(source='period.fiscal_year', read_only=True)
    period_number = serializers.IntegerField(source='period.period_number', read_only=True)
    start_date = serializers.DateField(source='period.start_date', read_only=True)
    end_date = serializers.DateField(source='period.end_date', read_only=True)
    
    class Meta:
        model = gl_period
        fields = [
            'id',
            'period',
            'period_name',
            'fiscal_year',
            'period_number',
            'start_date',
            'end_date',
            'state'
        ]
        read_only_fields = ['id', 'period']
    
    def get_state_display(self, obj):
        """Get human-readable state"""
        return obj.get_state_display()

