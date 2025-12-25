# """
# Procurement Serializers - Vendor Management
# Works with unified Supplier model (includes all vendor/procurement fields)
# """
# from rest_framework import serializers
# from .models import (
#     VendorContact, VendorDocument,
#     VendorOnboardingChecklist, VendorPerformanceReview
# )
# from ap.models import Supplier


# class VendorContactSerializer(serializers.ModelSerializer):
#     """Serializer for vendor contacts"""
#     contact_type_display = serializers.CharField(source='get_contact_type_display', read_only=True)
#     supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
#     class Meta:
#         model = VendorContact
#         fields = [
#             'id', 'supplier', 'supplier_name', 'contact_type', 'contact_type_display',
#             'name', 'title', 'email', 'phone', 'mobile', 'is_primary',
#             'is_active', 'notes', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at']


# class VendorDocumentSerializer(serializers.ModelSerializer):
#     """Serializer for vendor documents"""
#     document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
#     status_display = serializers.CharField(source='get_status_display', read_only=True)
#     is_expired = serializers.BooleanField(read_only=True)
#     supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
#     class Meta:
#         model = VendorDocument
#         fields = [
#             'id', 'supplier', 'supplier_name', 'document_type', 'document_type_display',
#             'document_name', 'document_number', 'description', 'file_path',
#             'issue_date', 'expiry_date', 'status', 'status_display',
#             'is_expired', 'verified_by', 'verified_date', 'notes',
#             'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'is_expired']


# class VendorOnboardingChecklistSerializer(serializers.ModelSerializer):
#     """Serializer for onboarding checklist items"""
#     status_display = serializers.CharField(source='get_status_display', read_only=True)
#     supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
#     class Meta:
#         model = VendorOnboardingChecklist
#         fields = [
#             'id', 'supplier', 'supplier_name', 'item_name', 'description', 'status',
#             'status_display', 'is_mandatory', 'assigned_to', 'completed_by',
#             'completed_date', 'due_date', 'notes', 'order',
#             'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at']


# class VendorPerformanceReviewSerializer(serializers.ModelSerializer):
#     """Serializer for performance reviews"""
#     review_type_display = serializers.CharField(source='get_review_type_display', read_only=True)
#     supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
#     class Meta:
#         model = VendorPerformanceReview
#         fields = [
#             'id', 'supplier', 'supplier_name', 'review_type', 'review_type_display',
#             'review_date', 'review_period_start', 'review_period_end',
#             'quality_rating', 'delivery_rating', 'price_rating',
#             'communication_rating', 'overall_rating', 'strengths',
#             'weaknesses', 'improvement_areas', 'recommendations',
#             'reviewer_name', 'reviewer_title', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at']


# class SupplierSerializer(serializers.ModelSerializer):
#     """
#     Main serializer for Supplier (Vendor) with nested procurement relationships
#     """
#     currency_code = serializers.CharField(source='currency.code', read_only=True)
#     vendor_status_display = serializers.CharField(source='get_vendor_status_display', read_only=True)
#     vendor_tier_display = serializers.CharField(source='get_vendor_tier_display', read_only=True)
#     risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    
#     # Nested relationships
#     contacts = VendorContactSerializer(many=True, read_only=True)
#     documents = VendorDocumentSerializer(many=True, read_only=True)
#     onboarding_items = VendorOnboardingChecklistSerializer(many=True, read_only=True)
#     performance_reviews = VendorPerformanceReviewSerializer(many=True, read_only=True)
    
#     supported_currency_codes = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Supplier
#         fields = [
#             # Basic Info
#             'id', 'code', 'name', 'legal_name', 'email', 'country', 
#             'currency', 'currency_code',
            
#             # Legal & Registration
#             'vat_number', 'trade_license_number', 'trn_number',
#             'registration_country', 'registration_date',
            
#             # Banking
#             'bank_name', 'bank_account_number', 'bank_swift_code',
#             'bank_iban', 'bank_branch',
            
#             # Currencies
#             'supported_currencies', 'supported_currency_codes',
            
#             # Status & Classification
#             'is_active', 'vendor_status', 'vendor_status_display',
#             'vendor_tier', 'vendor_tier_display', 'is_preferred_supplier',
            
#             # Risk
#             'risk_level', 'risk_level_display', 'risk_notes',
#             'last_risk_assessment_date',
            
#             # Performance
#             'performance_score', 'quality_score', 'delivery_score',
#             'price_competitiveness_score', 'average_delivery_days',
#             'on_time_delivery_rate',
            
#             # Blacklist/Hold
#             'is_blacklisted', 'blacklist_reason', 'blacklisted_date',
#             'blacklisted_by', 'is_on_hold', 'hold_reason', 'hold_date',
#             'hold_released_date',
            
#             # Onboarding
#             'onboarding_completed', 'onboarding_completed_date',
            
#             # Additional
#             'payment_terms', 'credit_limit', 'notes',
            
#             # Nested data
#             'contacts', 'documents', 'onboarding_items', 'performance_reviews',
            
#             # Metadata
#             'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'performance_score']
    
#     def get_supported_currency_codes(self, obj):
#         """Get list of supported currency codes"""
#         return [currency.code for currency in obj.supported_currencies.all()]


# class SupplierListSerializer(serializers.ModelSerializer):
#     """Simplified serializer for list views"""
#     currency_code = serializers.CharField(source='currency.code', read_only=True)
#     vendor_status_display = serializers.CharField(source='get_vendor_status_display', read_only=True)
#     vendor_tier_display = serializers.CharField(source='get_vendor_tier_display', read_only=True)
#     risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    
#     class Meta:
#         model = Supplier
#         fields = [
#             'id', 'code', 'name', 'legal_name', 'email',
#             'vendor_status', 'vendor_status_display', 'vendor_tier',
#             'vendor_tier_display', 'is_preferred_supplier', 'risk_level',
#             'risk_level_display', 'performance_score', 'onboarding_completed',
#             'is_blacklisted', 'is_on_hold', 'is_active',
#             'currency_code', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'performance_score']


# class SupplierCreateUpdateSerializer(serializers.ModelSerializer):
#     """Serializer for creating/updating suppliers"""
    
#     class Meta:
#         model = Supplier
#         fields = [
#             # Basic Info
#             'code', 'name', 'legal_name', 'email', 'country', 'currency',
            
#             # Legal & Registration
#             'vat_number', 'trade_license_number', 'trn_number',
#             'registration_country', 'registration_date',
            
#             # Banking
#             'bank_name', 'bank_account_number', 'bank_swift_code',
#             'bank_iban', 'bank_branch',
            
#             # Currencies
#             'supported_currencies',
            
#             # Status & Classification
#             'is_active', 'vendor_status', 'vendor_tier', 'is_preferred_supplier',
            
#             # Risk
#             'risk_level', 'risk_notes', 'last_risk_assessment_date',
            
#             # Performance Scores
#             'quality_score', 'delivery_score', 'price_competitiveness_score',
#             'average_delivery_days', 'on_time_delivery_rate',
            
#             # Blacklist/Hold
#             'is_blacklisted', 'blacklist_reason', 'blacklisted_date',
#             'blacklisted_by', 'is_on_hold', 'hold_reason', 'hold_date',
#             'hold_released_date',
            
#             # Additional
#             'payment_terms', 'credit_limit', 'notes'
#         ]
    
#     def create(self, validated_data):
#         """Create supplier and calculate initial performance score"""
#         supplier = super().create(validated_data)
#         supplier.calculate_overall_score()
#         supplier.save()
#         return supplier
    
#     def update(self, instance, validated_data):
#         """Update supplier and recalculate performance score"""
#         supplier = super().update(instance, validated_data)
#         supplier.calculate_overall_score()
#         supplier.save()
#         return supplier
