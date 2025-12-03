"""
Serializers for Finance Core models.
Handles serialization/deserialization of Currency, Country, and TaxRate models for API endpoints.
"""
from rest_framework import serializers
from .models import Currency, Country, TaxRate


class CurrencySerializer(serializers.ModelSerializer):
    """
    Serializer for Currency model.
    Includes all fields and validation.
    """
    class Meta:
        model = Currency
        fields = [
            'id',
            'code',
            'name',
            'symbol',
            'is_active',
            'is_base_currency',
            'exchange_rate_to_base_currency',
        ]
        read_only_fields = ['id']
    
    def validate_code(self, value):
        """Ensure currency code is uppercase"""
        return value.upper()


class CurrencyListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing currencies.
    """
    class Meta:
        model = Currency
        fields = [
            'id',
            'code',
            'name',
            'symbol',
            'is_active',
            'is_base_currency',
        ]


class CountrySerializer(serializers.ModelSerializer):
    """
    Serializer for Country model.
    Includes all fields and related tax rates count.
    """
    tax_rates_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Country
        fields = [
            'id',
            'code',
            'name',
            'tax_rates_count',
        ]
        read_only_fields = ['id', 'tax_rates_count']
    
    def get_tax_rates_count(self, obj):
        """Get count of tax rates for this country"""
        return obj.tax_rates.count()
    
    def validate_code(self, value):
        """Ensure country code is uppercase"""
        return value.upper()


class CountryListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing countries.
    """
    class Meta:
        model = Country
        fields = [
            'id',
            'code',
            'name',
        ]


class TaxRateSerializer(serializers.ModelSerializer):
    """
    Serializer for TaxRate model.
    Includes nested country information.
    """
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = TaxRate
        fields = [
            'id',
            'name',
            'rate',
            'country',
            'country_name',
            'country_code',
            'category',
            'category_display',
            'is_active',
        ]
        read_only_fields = ['id', 'country_name', 'country_code', 'category_display']


class TaxRateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing tax rates.
    """
    country_code = serializers.CharField(source='country.code', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = TaxRate
        fields = [
            'id',
            'name',
            'rate',
            'country_code',
            'category',
            'category_display',
            'is_active',
        ]


class UsageDetailsSerializer(serializers.Serializer):
    """
    Serializer for usage details response.
    """
    is_used = serializers.BooleanField()
    usage_details = serializers.ListField(child=serializers.CharField())
