"""
Serializers for Business Partner models.
Handles serialization/deserialization of Customer and Supplier models for API endpoints.
"""
from rest_framework import serializers
from .models import Customer, Supplier, BusinessPartner
from Finance.core.models import Country


class CustomerSerializer(serializers.ModelSerializer):
    """
    Full serializer for Customer model.
    Includes all fields from both Customer and BusinessPartner.
    """
    # BusinessPartner fields (read from business_partner relation)
    name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        required=False,
        allow_null=True
    )
    country_name = serializers.CharField(source='business_partner.country.name', read_only=True)
    country_code = serializers.CharField(source='business_partner.country.code', read_only=True)
    address = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)
    
    # Timestamps from BusinessPartner
    created_at = serializers.DateTimeField(source='business_partner.created_at', read_only=True)
    updated_at = serializers.DateTimeField(source='business_partner.updated_at', read_only=True)
    
    # Customer-specific fields
    address_in_details = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'country',
            'country_name',
            'country_code',
            'address',
            'notes',
            'is_active',
            'address_in_details',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'country_name', 'country_code', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """
        Create a new Customer using the custom manager.
        """
        return Customer.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """
        Update Customer instance.
        Updates both Customer and BusinessPartner fields.
        """
        # Update BusinessPartner fields
        bp_fields = ['name', 'email', 'phone', 'country', 'address', 'notes', 'is_active']
        for field in bp_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        
        # Update Customer-specific fields
        if 'address_in_details' in validated_data:
            instance.address_in_details = validated_data['address_in_details']
        
        instance.save()
        return instance


class CustomerListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing customers.
    """
    name = serializers.CharField(source='business_partner.name', read_only=True)
    email = serializers.CharField(source='business_partner.email', read_only=True)
    phone = serializers.CharField(source='business_partner.phone', read_only=True)
    country_code = serializers.CharField(source='business_partner.country.code', read_only=True)
    is_active = serializers.BooleanField(source='business_partner.is_active', read_only=True)
    
    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'country_code',
            'is_active',
        ]


class SupplierSerializer(serializers.ModelSerializer):
    """
    Full serializer for Supplier model.
    Includes all fields from both Supplier and BusinessPartner.
    """
    # BusinessPartner fields (read from business_partner relation)
    name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        required=False,
        allow_null=True
    )
    country_name = serializers.CharField(source='business_partner.country.name', read_only=True)
    country_code = serializers.CharField(source='business_partner.country.code', read_only=True)
    address = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)
    
    # Timestamps from BusinessPartner
    created_at = serializers.DateTimeField(source='business_partner.created_at', read_only=True)
    updated_at = serializers.DateTimeField(source='business_partner.updated_at', read_only=True)
    
    # Supplier-specific fields
    website = serializers.URLField(required=False, allow_blank=True)
    vat_number = serializers.CharField(required=False, allow_blank=True)
    tax_id = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'country',
            'country_name',
            'country_code',
            'address',
            'notes',
            'is_active',
            'website',
            'vat_number',
            'tax_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'country_name', 'country_code', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """
        Create a new Supplier using the custom manager.
        """
        return Supplier.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """
        Update Supplier instance.
        Updates both Supplier and BusinessPartner fields.
        """
        # Update BusinessPartner fields
        bp_fields = ['name', 'email', 'phone', 'country', 'address', 'notes', 'is_active']
        for field in bp_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        
        # Update Supplier-specific fields
        supplier_fields = ['website', 'vat_number', 'tax_id']
        for field in supplier_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        
        instance.save()
        return instance


class SupplierListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing suppliers.
    """
    name = serializers.CharField(source='business_partner.name', read_only=True)
    email = serializers.CharField(source='business_partner.email', read_only=True)
    phone = serializers.CharField(source='business_partner.phone', read_only=True)
    country_code = serializers.CharField(source='business_partner.country.code', read_only=True)
    is_active = serializers.BooleanField(source='business_partner.is_active', read_only=True)
    
    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'country_code',
            'is_active',
            'vat_number',
        ]
