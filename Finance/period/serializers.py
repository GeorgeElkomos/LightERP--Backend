"""
Serializers for Period model.
Handles serialization/deserialization of Period for API endpoints.
"""
from rest_framework import serializers
from .models import Period
from django.contrib.auth.models import User


class PeriodSerializer(serializers.ModelSerializer):
    """
    Full serializer for Period model.
    Includes all fields with proper validation.
    """
    # Related fields for better readability
    closed_by_username = serializers.CharField(source='closed_by.username', read_only=True)
    is_open = serializers.SerializerMethodField()
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
            'is_closed',
            'is_adjustment_period',
            'closed_date',
            'closed_by',
            'closed_by_username',
            'description',
            'is_open',
            'duration_days',
        ]
        read_only_fields = ['id', 'closed_date', 'closed_by', 'closed_by_username']
    
    def get_is_open(self, obj):
        """Check if period is open for transactions"""
        return obj.can_post_transaction()
    
    def get_duration_days(self, obj):
        """Get period duration in days"""
        return obj.get_duration_days()
    
    def validate(self, data):
        """
        Validate period data:
        - Start date must be before end date
        - Fiscal year and period number combination must be unique
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after or equal to start date'
                })
        
        # Check uniqueness of fiscal_year + period_number
        fiscal_year = data.get('fiscal_year')
        period_number = data.get('period_number')
        
        if fiscal_year and period_number:
            queryset = Period.objects.filter(
                fiscal_year=fiscal_year,
                period_number=period_number
            )
            
            # Exclude current instance if updating
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise serializers.ValidationError({
                    'period_number': f'Period {period_number} already exists for fiscal year {fiscal_year}'
                })
        
        return data


class PeriodListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing periods.
    Used for list views and dropdowns.
    """
    is_open = serializers.SerializerMethodField()
    
    class Meta:
        model = Period
        fields = [
            'id',
            'name',
            'start_date',
            'end_date',
            'fiscal_year',
            'period_number',
            'is_closed',
            'is_adjustment_period',
            'is_open',
        ]
    
    def get_is_open(self, obj):
        """Check if period is open for transactions"""
        return obj.can_post_transaction()


class PeriodClosureSerializer(serializers.Serializer):
    """
    Serializer for closing/reopening periods.
    """
    action = serializers.ChoiceField(choices=['close', 'reopen'])
    
    def validate(self, data):
        """Validate closure action"""
        period = self.context.get('period')
        action = data.get('action')
        
        if action == 'close' and period.is_closed:
            raise serializers.ValidationError('Period is already closed')
        
        if action == 'reopen' and not period.is_closed:
            raise serializers.ValidationError('Period is not closed')
        
        return data