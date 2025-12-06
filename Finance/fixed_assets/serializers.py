from rest_framework import serializers
from .models import (
    AssetCategory, AssetLocation, FixedAsset,
    DepreciationSchedule, AssetTransfer, AssetRevaluation, DepreciationRun
)


# class AssetCategorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetCategory
#         fields = [
#             'id', 'code', 'name', 'description',
#             'default_depreciation_method', 'default_useful_life_years',
#             'default_salvage_value_percentage',
#             'asset_account', 'accumulated_depreciation_account',
#             'depreciation_expense_account', 'gain_on_disposal_account',
#             'loss_on_disposal_account', 'is_active',
#             'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at']


# class AssetLocationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetLocation
#         fields = ['id', 'code', 'name', 'address', 'is_active']


# class DepreciationScheduleSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = DepreciationSchedule
#         fields = [
#             'id', 'asset', 'period_date', 'depreciation_amount',
#             'accumulated_depreciation', 'book_value',
#             'gl_entry', 'is_posted', 'posted_date', 'created_at'
#         ]
#         read_only_fields = ['created_at', 'posted_date']


# class AssetTransferSerializer(serializers.ModelSerializer):
#     from_location_name = serializers.CharField(
#         source='from_location.name', read_only=True
#     )
#     to_location_name = serializers.CharField(
#         source='to_location.name', read_only=True
#     )
    
#     class Meta:
#         model = AssetTransfer
#         fields = [
#             'id', 'asset', 'transfer_date',
#             'from_location', 'from_location_name',
#             'to_location', 'to_location_name',
#             'reason', 'created_at'
#         ]
#         read_only_fields = ['created_at']


# class FixedAssetSerializer(serializers.ModelSerializer):
#     category_name = serializers.CharField(source='category.name', read_only=True)
#     location_name = serializers.CharField(source='location.name', read_only=True)
#     supplier_name = serializers.CharField(source='supplier.name', read_only=True)
#     currency_code = serializers.CharField(source='currency.code', read_only=True)
#     status_display = serializers.CharField(source='get_status_display', read_only=True)
#     depreciation_method_display = serializers.CharField(
#         source='get_depreciation_method_display', read_only=True
#     )
#     depreciable_amount = serializers.DecimalField(
#         max_digits=14, decimal_places=2, read_only=True
#     )
#     is_fully_depreciated = serializers.BooleanField(read_only=True)
    
#     depreciation_records = DepreciationScheduleSerializer(many=True, read_only=True)
    
#     class Meta:
#         model = FixedAsset
#         fields = [
#             'id', 'asset_number', 'name', 'description', 'serial_number',
#             'category', 'category_name', 'location', 'location_name',
#             'acquisition_date', 'acquisition_cost', 'currency', 'currency_code',
#             'supplier', 'supplier_name', 'invoice_number',
#             'depreciation_method', 'depreciation_method_display',
#             'useful_life_years', 'useful_life_months', 'salvage_value',
#             'depreciation_start_date', 'total_units_capacity', 'declining_balance_rate',
#             'accumulated_depreciation', 'book_value', 'depreciable_amount',
#             'status', 'status_display', 'is_fully_depreciated',
#             'disposal_date', 'disposal_amount', 'disposal_reason',
#             'depreciation_records',
#             'created_at', 'updated_at'
#         ]
#         read_only_fields = [
#             'asset_number', 'accumulated_depreciation', 'book_value',
#             'created_at', 'updated_at'
#         ]


# class FixedAssetCreateSerializer(serializers.ModelSerializer):
#     """Serializer for creating fixed assets."""
    
#     class Meta:
#         model = FixedAsset
#         fields = [
#             'name', 'description', 'serial_number',
#             'category', 'location',
#             'acquisition_date', 'acquisition_cost', 'currency',
#             'supplier', 'invoice_number',
#             'depreciation_method', 'useful_life_years', 'useful_life_months',
#             'salvage_value', 'depreciation_start_date',
#             'total_units_capacity', 'declining_balance_rate'
#         ]


# class AssetRevaluationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssetRevaluation
#         fields = [
#             'id', 'asset', 'revaluation_date',
#             'previous_value', 'new_value', 'adjustment_amount',
#             'reason', 'gl_entry', 'created_at'
#         ]
#         read_only_fields = ['adjustment_amount', 'created_at']


# class DepreciationRunSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = DepreciationRun
#         fields = [
#             'id', 'period_date', 'run_date',
#             'total_depreciation', 'assets_processed',
#             'is_posted', 'posted_date'
#         ]
#         read_only_fields = [
#             'run_date', 'total_depreciation', 'assets_processed', 'posted_date'
#         ]


# class RunDepreciationSerializer(serializers.Serializer):
#     """Serializer for running depreciation."""
#     period_date = serializers.DateField()


# class DisposeAssetSerializer(serializers.Serializer):
#     """Serializer for disposing an asset."""
#     disposal_date = serializers.DateField()
#     disposal_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
#     reason = serializers.CharField(required=False, allow_blank=True)


# class TransferAssetSerializer(serializers.Serializer):
#     """Serializer for transferring an asset."""
#     transfer_date = serializers.DateField()
#     to_location = serializers.IntegerField()
#     reason = serializers.CharField(required=False, allow_blank=True)
