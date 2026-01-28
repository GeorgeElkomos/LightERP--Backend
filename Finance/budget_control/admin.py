# """
# Django Admin Configuration for Budget Control
# """
# from django.contrib import admin
# from django.utils.html import format_html
# from django.urls import reverse
# from django.utils.safestring import mark_safe
# from .models import BudgetHeader, BudgetSegmentValue, BudgetAmount


# class BudgetSegmentValueInline(admin.TabularInline):
#     """Inline admin for Budget Segment Values"""
#     model = BudgetSegmentValue
#     extra = 1
#     fields = ('segment_value', 'control_level', 'is_active', 'notes')
#     autocomplete_fields = ['segment_value']
    
#     def has_delete_permission(self, request, obj=None):
#         """Only allow deletion if budget is DRAFT"""
#         if obj and obj.status != 'DRAFT':
#             return False
#         return super().has_delete_permission(request, obj)


# class BudgetAmountInline(admin.TabularInline):
#     """Inline admin for Budget Amounts"""
#     model = BudgetAmount
#     extra = 0
#     fields = (
#         'budget_segment_value',
#         'original_budget',
#         'adjustment_amount',
#         'total_budget_display',
#         'committed_amount',
#         'encumbered_amount',
#         'actual_amount',
#         'available_display',
#         'utilization_display'
#     )
#     readonly_fields = (
#         'total_budget_display',
#         'committed_amount',
#         'encumbered_amount',
#         'actual_amount',
#         'available_display',
#         'utilization_display',
#         'last_committed_date',
#         'last_encumbered_date',
#         'last_actual_date'
#     )
    
#     def total_budget_display(self, obj):
#         """Display total budget (original + adjustments)"""
#         if obj.id:
#             return f"{obj.get_total_budget():,.2f}"
#         return "-"
#     total_budget_display.short_description = "Total Budget"
    
#     def available_display(self, obj):
#         """Display available budget with color coding"""
#         if obj.id:
#             available = obj.get_available()
#             utilization = obj.get_utilization_percentage()
            
#             if utilization >= 100:
#                 color = 'red'
#             elif utilization >= 80:
#                 color = 'orange'
#             else:
#                 color = 'green'
            
#             return format_html(
#                 '<span style="color: {}; font-weight: bold;">{:,.2f}</span>',
#                 color,
#                 available
#             )
#         return "-"
#     available_display.short_description = "Available"
    
#     def utilization_display(self, obj):
#         """Display utilization percentage with progress bar"""
#         if obj.id:
#             utilization = obj.get_utilization_percentage()
            
#             if utilization >= 100:
#                 color = '#dc3545'  # Red
#             elif utilization >= 80:
#                 color = '#ffc107'  # Orange
#             else:
#                 color = '#28a745'  # Green
            
#             return format_html(
#                 '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
#                 '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; '
#                 'text-align: center; color: white; font-size: 11px; line-height: 20px;">'
#                 '{}%</div></div>',
#                 min(utilization, 100),
#                 color,
#                 int(utilization)
#             )
#         return "-"
#     utilization_display.short_description = "Utilization"
    
#     def has_delete_permission(self, request, obj=None):
#         """Only allow deletion if budget is DRAFT"""
#         if obj and obj.status != 'DRAFT':
#             return False
#         return super().has_delete_permission(request, obj)


# @admin.register(BudgetHeader)
# class BudgetHeaderAdmin(admin.ModelAdmin):
#     """Admin interface for Budget Header"""
    
#     list_display = (
#         'budget_code',
#         'budget_name',
#         'status_badge',
#         'start_date',
#         'end_date',
#         'total_budget_display',
#         'total_consumed_display',
#         'total_available_display',
#         'utilization_display',
#         'currency',
#         'is_active'
#     )
    
#     list_filter = (
#         'status',
#         'is_active',
#         'default_control_level',
#         'start_date',
#         'end_date',
#         'currency'
#     )
    
#     search_fields = (
#         'budget_code',
#         'budget_name',
#         'description'
#     )
    
#     readonly_fields = (
#         'status',
#         'created_at',
#         'updated_at',
#         'activated_at',
#         'activated_by',
#         'total_budget_display',
#         'total_consumed_display',
#         'total_available_display',
#         'utilization_display'
#     )
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': (
#                 'budget_code',
#                 'budget_name',
#                 'description',
#                 'currency'
#             )
#         }),
#         ('Budget Period', {
#             'fields': (
#                 'start_date',
#                 'end_date'
#             )
#         }),
#         ('Control Settings', {
#             'fields': (
#                 'default_control_level',
#                 'is_active'
#             )
#         }),
#         ('Status', {
#             'fields': (
#                 'status',
#                 'activated_by',
#                 'activated_at'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Summary', {
#             'fields': (
#                 'total_budget_display',
#                 'total_consumed_display',
#                 'total_available_display',
#                 'utilization_display'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Timestamps', {
#             'fields': (
#                 'created_at',
#                 'updated_at'
#             ),
#             'classes': ('collapse',)
#         })
#     )
    
#     inlines = [BudgetSegmentValueInline, BudgetAmountInline]
    
#     actions = ['activate_budgets', 'close_budgets', 'deactivate_budgets']
    
#     def status_badge(self, obj):
#         """Display status with colored badge"""
#         colors = {
#             'DRAFT': 'gray',
#             'ACTIVE': 'green',
#             'CLOSED': 'red'
#         }
#         color = colors.get(obj.status, 'gray')
#         return format_html(
#             '<span style="background-color: {}; color: white; padding: 3px 10px; '
#             'border-radius: 3px; font-weight: bold;">{}</span>',
#             color,
#             obj.status
#         )
#     status_badge.short_description = "Status"
    
#     def total_budget_display(self, obj):
#         """Display total budget amount"""
#         total = obj.get_total_budget()
#         return f"{total:,.2f} {obj.currency.code}"
#     total_budget_display.short_description = "Total Budget"
    
#     def total_consumed_display(self, obj):
#         """Display total consumed amount"""
#         consumed = obj.get_total_consumed()
#         return f"{consumed:,.2f} {obj.currency.code}"
#     total_consumed_display.short_description = "Total Consumed"
    
#     def total_available_display(self, obj):
#         """Display total available amount with color"""
#         available = obj.get_total_available()
#         utilization = obj.get_utilization_percentage()
        
#         if utilization >= 100:
#             color = 'red'
#         elif utilization >= 80:
#             color = 'orange'
#         else:
#             color = 'green'
        
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{:,.2f} {}</span>',
#             color,
#             available,
#             obj.currency.code
#         )
#     total_available_display.short_description = "Total Available"
    
#     def utilization_display(self, obj):
#         """Display utilization percentage"""
#         utilization = obj.get_utilization_percentage()
        
#         if utilization >= 100:
#             color = '#dc3545'
#         elif utilization >= 80:
#             color = '#ffc107'
#         else:
#             color = '#28a745'
        
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{}%</span>',
#             color,
#             int(utilization)
#         )
#     utilization_display.short_description = "Utilization"
    
#     def activate_budgets(self, request, queryset):
#         """Bulk activate budgets"""
#         activated_count = 0
#         errors = []
        
#         for budget in queryset:
#             if budget.status == 'DRAFT':
#                 try:
#                     budget.activate(request.user.username)
#                     activated_count += 1
#                 except Exception as e:
#                     errors.append(f"{budget.budget_code}: {str(e)}")
        
#         if activated_count:
#             self.message_user(request, f"Successfully activated {activated_count} budget(s)")
        
#         if errors:
#             self.message_user(
#                 request,
#                 f"Failed to activate: {', '.join(errors)}",
#                 level='ERROR'
#             )
#     activate_budgets.short_description = "Activate selected budgets"
    
#     def close_budgets(self, request, queryset):
#         """Bulk close budgets"""
#         closed_count = 0
#         errors = []
        
#         for budget in queryset:
#             if budget.status == 'ACTIVE':
#                 try:
#                     budget.close(request.user.username)
#                     closed_count += 1
#                 except Exception as e:
#                     errors.append(f"{budget.budget_code}: {str(e)}")
        
#         if closed_count:
#             self.message_user(request, f"Successfully closed {closed_count} budget(s)")
        
#         if errors:
#             self.message_user(
#                 request,
#                 f"Failed to close: {', '.join(errors)}",
#                 level='ERROR'
#             )
#     close_budgets.short_description = "Close selected budgets"
    
#     def deactivate_budgets(self, request, queryset):
#         """Bulk deactivate budgets"""
#         deactivated_count = 0
        
#         for budget in queryset:
#             try:
#                 budget.deactivate()
#                 deactivated_count += 1
#             except Exception as e:
#                 pass
        
#         self.message_user(request, f"Successfully deactivated {deactivated_count} budget(s)")
#     deactivate_budgets.short_description = "Deactivate selected budgets"
    
#     def has_delete_permission(self, request, obj=None):
#         """Only allow deletion of DRAFT budgets"""
#         if obj and obj.status != 'DRAFT':
#             return False
#         return super().has_delete_permission(request, obj)


# @admin.register(BudgetSegmentValue)
# class BudgetSegmentValueAdmin(admin.ModelAdmin):
#     """Admin interface for Budget Segment Value"""
    
#     list_display = (
#         'budget_header',
#         'segment_value',
#         'segment_type',
#         'control_level',
#         'effective_control_display',
#         'has_budget',
#         'is_active'
#     )
    
#     list_filter = (
#         'control_level',
#         'is_active',
#         'budget_header__status'
#     )
    
#     search_fields = (
#         'budget_header__budget_code',
#         'budget_header__budget_name',
#         'segment_value__code',
#         'segment_value__name'
#     )
    
#     readonly_fields = (
#         'effective_control_display',
#         'has_budget',
#         'created_at',
#         'updated_at'
#     )
    
#     autocomplete_fields = ['budget_header', 'segment_value']
    
#     def segment_type(self, obj):
#         """Display segment type"""
#         return obj.segment_value.segment_type.segment_name
#     segment_type.short_description = "Segment Type"
    
#     def effective_control_display(self, obj):
#         """Display effective control level"""
#         return obj.get_effective_control_level()
#     effective_control_display.short_description = "Effective Control"
    
#     def has_budget(self, obj):
#         """Check if budget amount exists"""
#         return obj.has_budget()
#     has_budget.boolean = True
#     has_budget.short_description = "Has Budget"


# @admin.register(BudgetAmount)
# class BudgetAmountAdmin(admin.ModelAdmin):
#     """Admin interface for Budget Amount"""
    
#     list_display = (
#         'budget_header',
#         'segment_display',
#         'total_budget_display',
#         'committed_amount',
#         'encumbered_amount',
#         'actual_amount',
#         'available_display',
#         'utilization_bar'
#     )
    
#     list_filter = (
#         'budget_header__status',
#         'budget_segment_value__control_level'
#     )
    
#     search_fields = (
#         'budget_header__budget_code',
#         'budget_header__budget_name',
#         'budget_segment_value__segment_value__code',
#         'budget_segment_value__segment_value__name'
#     )
    
#     readonly_fields = (
#         'committed_amount',
#         'encumbered_amount',
#         'actual_amount',
#         'last_committed_date',
#         'last_encumbered_date',
#         'last_actual_date',
#         'last_adjustment_date',
#         'total_budget_display',
#         'available_display',
#         'consumed_total_display',
#         'utilization_display',
#         'created_at',
#         'updated_at'
#     )
    
#     fieldsets = (
#         ('Budget Assignment', {
#             'fields': (
#                 'budget_header',
#                 'budget_segment_value'
#             )
#         }),
#         ('Budget Amounts', {
#             'fields': (
#                 'original_budget',
#                 'adjustment_amount',
#                 'total_budget_display',
#                 'notes'
#             )
#         }),
#         ('Consumption Tracking', {
#             'fields': (
#                 'committed_amount',
#                 'encumbered_amount',
#                 'actual_amount',
#                 'consumed_total_display',
#                 'available_display',
#                 'utilization_display'
#             )
#         }),
#         ('Timestamps', {
#             'fields': (
#                 'last_committed_date',
#                 'last_encumbered_date',
#                 'last_actual_date',
#                 'last_adjustment_date',
#                 'created_at',
#                 'updated_at'
#             ),
#             'classes': ('collapse',)
#         })
#     )
    
#     def segment_display(self, obj):
#         """Display segment value"""
#         return str(obj.budget_segment_value.segment_value)
#     segment_display.short_description = "Segment"
    
#     def total_budget_display(self, obj):
#         """Display total budget"""
#         return f"{obj.get_total_budget():,.2f}"
#     total_budget_display.short_description = "Total Budget"
    
#     def available_display(self, obj):
#         """Display available with color"""
#         available = obj.get_available()
#         utilization = obj.get_utilization_percentage()
        
#         if utilization >= 100:
#             color = 'red'
#         elif utilization >= 80:
#             color = 'orange'
#         else:
#             color = 'green'
        
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{:,.2f}</span>',
#             color,
#             available
#         )
#     available_display.short_description = "Available"
    
#     def consumed_total_display(self, obj):
#         """Display total consumed"""
#         return f"{obj.get_consumed_total():,.2f}"
#     consumed_total_display.short_description = "Total Consumed"
    
#     def utilization_display(self, obj):
#         """Display utilization percentage"""
#         utilization = obj.get_utilization_percentage()
#         return f"{utilization:.1f}%"
#     utilization_display.short_description = "Utilization"
    
#     def utilization_bar(self, obj):
#         """Display utilization as progress bar"""
#         utilization = obj.get_utilization_percentage()
        
#         if utilization >= 100:
#             color = '#dc3545'
#         elif utilization >= 80:
#             color = '#ffc107'
#         else:
#             color = '#28a745'
        
#         return format_html(
#             '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
#             '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; '
#             'text-align: center; color: white; font-size: 11px; line-height: 20px;">'
#             '{}%</div></div>',
#             min(utilization, 100),
#             color,
#             int(utilization)
#         )
#     utilization_bar.short_description = "Utilization"
    
#     def has_delete_permission(self, request, obj=None):
#         """Only allow deletion if no consumption"""
#         if obj and (obj.committed_amount > 0 or obj.encumbered_amount > 0 or obj.actual_amount > 0):
#             return False
#         return super().has_delete_permission(request, obj)
