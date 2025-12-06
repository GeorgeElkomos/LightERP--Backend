from django.contrib import admin
from .models import (
    PaymentMethod, BankAccount, Payment, 
    PaymentAllocation, PaymentPlan, PaymentPlanInstallment, PaymentPlanInvoice
)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'requires_reference', 'requires_bank_account']
    list_filter = ['is_active', 'requires_reference', 'requires_bank_account']
    search_fields = ['code', 'name']


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_number', 'bank_name', 'currency', 'is_active']
    list_filter = ['is_active', 'currency']
    search_fields = ['name', 'account_number', 'bank_name']


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 1
    readonly_fields = ['created_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_number', 'direction', 'partner_type', 'business_partner',
        'date', 'amount', 'currency', 'status', 'is_posted'
    ]
    list_filter = ['direction', 'partner_type', 'status', 'is_posted', 'payment_method', 'currency']
    search_fields = ['payment_number', 'reference_number', 'memo', 'business_partner__name']
    readonly_fields = ['payment_number', 'created_at', 'updated_at', 'posted_date']
    inlines = [PaymentAllocationInline]
    
    fieldsets = (
        ('Payment Info', {
            'fields': ('payment_number', 'direction', 'partner_type', 'business_partner', 'date', 'status')
        }),
        ('Amount', {
            'fields': ('amount', 'currency', 'exchange_rate')
        }),
        ('Payment Method', {
            'fields': ('payment_method', 'bank_account', 'reference_number')
        }),
        ('Notes', {
            'fields': ('memo', 'rejection_reason')
        }),
        ('Posting', {
            'fields': ('is_posted', 'posted_date', 'gl_entry')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class PaymentPlanInstallmentInline(admin.TabularInline):
    model = PaymentPlanInstallment
    extra = 0
    readonly_fields = ['installment_number', 'due_date', 'amount', 'payment', 'is_cancelled']
    can_delete = False


class PaymentPlanInvoiceInline(admin.TabularInline):
    model = PaymentPlanInvoice
    extra = 1


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = [
        'plan_number', 'business_partner', 'total_amount', 'currency',
        'frequency', 'number_of_installments', 'status', 'start_date'
    ]
    list_filter = ['status', 'frequency', 'currency']
    search_fields = ['plan_number', 'business_partner__name']
    readonly_fields = ['plan_number', 'created_at', 'updated_at', 'amount_paid', 'amount_remaining']
    inlines = [PaymentPlanInvoiceInline, PaymentPlanInstallmentInline]
    
    fieldsets = (
        ('Plan Info', {
            'fields': ('plan_number', 'business_partner', 'status')
        }),
        ('Amount', {
            'fields': ('total_amount', 'currency', 'amount_paid', 'amount_remaining')
        }),
        ('Schedule', {
            'fields': ('frequency', 'number_of_installments', 'start_date')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['generate_installments_action']
    
    @admin.action(description='Generate installment schedule')
    def generate_installments_action(self, request, queryset):
        for plan in queryset:
            if not plan.installments.exists():
                plan.generate_installments()
        self.message_user(request, f'Generated installments for {queryset.count()} plans.')


@admin.register(PaymentPlanInstallment)
class PaymentPlanInstallmentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_plan', 'installment_number', 'due_date', 
        'amount', 'is_paid', 'is_overdue', 'is_cancelled'
    ]
    list_filter = ['is_cancelled', 'payment_plan__status']
    search_fields = ['payment_plan__plan_number', 'payment_plan__business_partner__name']
    readonly_fields = ['created_at', 'updated_at', 'is_paid', 'is_overdue', 'days_overdue']
