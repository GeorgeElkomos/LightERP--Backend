from rest_framework import serializers
from .models import (
    PaymentMethod, BankAccount, Payment, 
    PaymentAllocation, PaymentPlan, PaymentPlanInstallment, PaymentPlanInvoice
)


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__'


class BankAccountSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    
    class Meta:
        model = BankAccount
        fields = '__all__'


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    total_settlement = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = PaymentAllocation
        fields = [
            'id', 'payment', 'invoice', 'invoice_number',
            'allocated_amount', 'discount_amount', 'write_off_amount',
            'total_settlement', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    partner_name = serializers.CharField(source='business_partner.name', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    total_allocated = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, source='get_total_allocated'
    )
    unallocated_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, source='get_unallocated_amount'
    )
    amount_in_base_currency = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_number', 'direction', 'partner_type',
            'business_partner', 'partner_name', 'date',
            'amount', 'currency', 'currency_code', 'exchange_rate',
            'amount_in_base_currency',
            'payment_method', 'payment_method_name', 'bank_account',
            'reference_number', 'status', 'rejection_reason',
            'is_posted', 'posted_date', 'gl_entry', 'memo',
            'allocations', 'total_allocated', 'unallocated_amount',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'payment_number', 'is_posted', 'posted_date', 'gl_entry',
            'created_at', 'updated_at'
        ]


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments with allocations."""
    allocations = PaymentAllocationSerializer(many=True, required=False)
    
    class Meta:
        model = Payment
        fields = [
            'direction', 'partner_type', 'business_partner', 'date',
            'amount', 'currency', 'exchange_rate',
            'payment_method', 'bank_account', 'reference_number',
            'memo', 'allocations'
        ]
    
    def create(self, validated_data):
        allocations_data = validated_data.pop('allocations', [])
        payment = Payment.objects.create(**validated_data)
        
        for allocation_data in allocations_data:
            PaymentAllocation.objects.create(payment=payment, **allocation_data)
        
        return payment


class PaymentPlanInstallmentSerializer(serializers.ModelSerializer):
    is_paid = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PaymentPlanInstallment
        fields = [
            'id', 'payment_plan', 'installment_number', 'due_date',
            'amount', 'payment', 'is_cancelled', 'is_paid', 'is_overdue',
            'days_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PaymentPlanInvoiceSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    
    class Meta:
        model = PaymentPlanInvoice
        fields = ['id', 'payment_plan', 'invoice', 'invoice_number', 'amount_covered']


class PaymentPlanSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='business_partner.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    installments = PaymentPlanInstallmentSerializer(many=True, read_only=True)
    plan_invoices = PaymentPlanInvoiceSerializer(many=True, read_only=True)
    installment_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    amount_paid = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    amount_remaining = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    is_complete = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PaymentPlan
        fields = [
            'id', 'plan_number', 'business_partner', 'partner_name',
            'total_amount', 'currency', 'currency_code',
            'frequency', 'number_of_installments', 'start_date',
            'status', 'notes', 'installment_amount',
            'amount_paid', 'amount_remaining', 'is_complete',
            'installments', 'plan_invoices',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['plan_number', 'created_at', 'updated_at']


class PaymentPlanCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payment plans with linked invoices."""
    invoices = serializers.ListField(
        child=serializers.DictField(), required=False, write_only=True
    )
    generate_schedule = serializers.BooleanField(default=True, write_only=True)
    
    class Meta:
        model = PaymentPlan
        fields = [
            'business_partner', 'total_amount', 'currency',
            'frequency', 'number_of_installments', 'start_date',
            'notes', 'invoices', 'generate_schedule'
        ]
    
    def create(self, validated_data):
        invoices_data = validated_data.pop('invoices', [])
        generate_schedule = validated_data.pop('generate_schedule', True)
        
        plan = PaymentPlan.objects.create(**validated_data)
        
        # Link invoices
        for inv_data in invoices_data:
            PaymentPlanInvoice.objects.create(
                payment_plan=plan,
                invoice_id=inv_data['invoice_id'],
                amount_covered=inv_data['amount_covered']
            )
        
        # Generate installment schedule
        if generate_schedule:
            plan.generate_installments()
        
        return plan


