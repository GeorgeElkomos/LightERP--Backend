from django.contrib import admin
# from .models import (
#     AssetCategory, AssetLocation, FixedAsset,
#     DepreciationSchedule, AssetTransfer, AssetRevaluation, DepreciationRun
# )


# @admin.register(AssetCategory)
# class AssetCategoryAdmin(admin.ModelAdmin):
#     list_display = [
#         'code', 'name', 'default_depreciation_method',
#         'default_useful_life_years', 'is_active'
#     ]
#     list_filter = ['is_active', 'default_depreciation_method']
#     search_fields = ['code', 'name']


# @admin.register(AssetLocation)
# class AssetLocationAdmin(admin.ModelAdmin):
#     list_display = ['code', 'name', 'is_active']
#     list_filter = ['is_active']
#     search_fields = ['code', 'name']


# class DepreciationScheduleInline(admin.TabularInline):
#     model = DepreciationSchedule
#     extra = 0
#     readonly_fields = [
#         'period_date', 'depreciation_amount', 
#         'accumulated_depreciation', 'book_value', 'is_posted'
#     ]
#     can_delete = False


# class AssetTransferInline(admin.TabularInline):
#     model = AssetTransfer
#     extra = 0
#     readonly_fields = ['transfer_date', 'from_location', 'to_location']


# @admin.register(FixedAsset)
# class FixedAssetAdmin(admin.ModelAdmin):
#     list_display = [
#         'asset_number', 'name', 'category', 'status',
#         'acquisition_date', 'acquisition_cost', 'book_value'
#     ]
#     list_filter = ['status', 'category', 'depreciation_method', 'location']
#     search_fields = ['asset_number', 'name', 'serial_number']
#     readonly_fields = [
#         'asset_number', 'accumulated_depreciation', 'book_value',
#         'created_at', 'updated_at'
#     ]
#     inlines = [DepreciationScheduleInline, AssetTransferInline]
    
#     fieldsets = (
#         ('Identification', {
#             'fields': ('asset_number', 'name', 'description', 'serial_number')
#         }),
#         ('Classification', {
#             'fields': ('category', 'location')
#         }),
#         ('Acquisition', {
#             'fields': (
#                 'acquisition_date', 'acquisition_cost', 'currency',
#                 'supplier', 'invoice_number'
#             )
#         }),
#         ('Depreciation', {
#             'fields': (
#                 'depreciation_method', 'useful_life_years', 'useful_life_months',
#                 'salvage_value', 'depreciation_start_date',
#                 'declining_balance_rate', 'total_units_capacity'
#             )
#         }),
#         ('Current Values', {
#             'fields': ('accumulated_depreciation', 'book_value', 'status')
#         }),
#         ('Disposal', {
#             'fields': ('disposal_date', 'disposal_amount', 'disposal_reason'),
#             'classes': ('collapse',)
#         }),
#         ('Timestamps', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )


# @admin.register(DepreciationSchedule)
# class DepreciationScheduleAdmin(admin.ModelAdmin):
#     list_display = [
#         'asset', 'period_date', 'depreciation_amount',
#         'accumulated_depreciation', 'book_value', 'is_posted'
#     ]
#     list_filter = ['is_posted', 'period_date']
#     search_fields = ['asset__asset_number', 'asset__name']
#     readonly_fields = ['created_at', 'posted_date']


# @admin.register(AssetTransfer)
# class AssetTransferAdmin(admin.ModelAdmin):
#     list_display = ['asset', 'transfer_date', 'from_location', 'to_location']
#     list_filter = ['transfer_date', 'from_location', 'to_location']
#     search_fields = ['asset__asset_number', 'asset__name']


# @admin.register(AssetRevaluation)
# class AssetRevaluationAdmin(admin.ModelAdmin):
#     list_display = [
#         'asset', 'revaluation_date', 'previous_value',
#         'new_value', 'adjustment_amount'
#     ]
#     list_filter = ['revaluation_date']
#     search_fields = ['asset__asset_number', 'asset__name']


# @admin.register(DepreciationRun)
# class DepreciationRunAdmin(admin.ModelAdmin):
#     list_display = [
#         'period_date', 'run_date', 'assets_processed',
#         'total_depreciation', 'is_posted'
#     ]
#     list_filter = ['is_posted']
#     readonly_fields = ['run_date', 'total_depreciation', 'assets_processed', 'posted_date']
