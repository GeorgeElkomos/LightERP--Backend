"""
Payment Serializers - API Layer for Payment Operations

These serializers handle:
1. Request validation
2. Converting JSON to Python objects
3. Response formatting
4. Nested relationships (allocations, invoices, etc.)
"""

from rest_framework import serializers
from decimal import Decimal

from Finance.payments.models import Payment, PaymentAllocation
from Finance.Invoice.models import Invoice
from Finance.BusinessPartner.models import BusinessPartner
from Finance.core.models import Currency


# ==================== NESTED SERIALIZERS ====================

class PaymentAllocationInputSerializer(serializers.Serializer):
    """Serializer for creating payment allocations"""
    invoice_id = serializers.IntegerField(min_value=1)
    amount_allocated = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    
    def validate_invoice_id(self, value):
        """Validate invoice exists"""
        if not Invoice.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Invoice with ID {value} does not exist")
        return value


class PaymentAllocationDetailSerializer(serializers.ModelSerializer):
    """Serializer for displaying payment allocation details"""
    invoice_id = serializers.IntegerField(source='invoice.id', read_only=True)
    invoice_date = serializers.DateField(source='invoice.date', read_only=True)
    invoice_total = serializers.DecimalField(
        source='invoice.total',
        max_digits=14,
        decimal_places=2,
        read_only=True
    )
    invoice_paid_amount = serializers.DecimalField(
        source='invoice.paid_amount',
        max_digits=14,
        decimal_places=2,
        read_only=True
    )
    invoice_payment_status = serializers.CharField(source='invoice.payment_status', read_only=True)
    
    class Meta:
        model = PaymentAllocation
        fields = [
            'id',
            'invoice_id',
            'invoice_date',
            'invoice_total',
            'invoice_paid_amount',
            'invoice_payment_status',
            'amount_allocated',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ==================== PAYMENT LIST SERIALIZER ====================

class PaymentListSerializer(serializers.ModelSerializer):
    """Serializer for listing payments (lightweight)"""
    business_partner_id = serializers.IntegerField(source='business_partner.id', read_only=True)
    business_partner_name = serializers.CharField(source='business_partner.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    allocation_count = serializers.SerializerMethodField()
    total_allocated = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'date',
            'business_partner_id',
            'business_partner_name',
            'currency_code',
            'exchange_rate',
            'approval_status',
            'allocation_count',
            'total_allocated',
            'created_at'
        ]
    
    def get_allocation_count(self, obj):
        """Get count of allocations"""
        return obj.allocations.count()
    
    def get_total_allocated(self, obj):
        """Get total allocated amount"""
        return str(obj.get_total_allocated())


# ==================== PAYMENT DETAIL SERIALIZER ====================

class PaymentDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed payment view"""
    business_partner_id = serializers.IntegerField(source='business_partner.id', read_only=True)
    business_partner_name = serializers.CharField(source='business_partner.name', read_only=True)
    currency_id = serializers.IntegerField(source='currency.id', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    allocations = PaymentAllocationDetailSerializer(many=True, read_only=True)
    total_allocated = serializers.SerializerMethodField()
    allocated_invoice_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'date',
            'business_partner_id',
            'business_partner_name',
            'currency_id',
            'currency_code',
            'currency_symbol',
            'exchange_rate',
            'approval_status',
            'rejection_reason',
            'gl_entry',
            'allocations',
            'total_allocated',
            'allocated_invoice_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_total_allocated(self, obj):
        """Get total allocated amount"""
        return str(obj.get_total_allocated())
    
    def get_allocated_invoice_count(self, obj):
        """Get count of invoices with allocations"""
        return obj.get_allocated_invoices().count()


# ==================== PAYMENT CREATE SERIALIZER ====================

class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating a new payment"""
    date = serializers.DateField()
    business_partner_id = serializers.IntegerField(min_value=1)
    currency_id = serializers.IntegerField(min_value=1)
    exchange_rate = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        required=False,
        allow_null=True
    )
    allocations = PaymentAllocationInputSerializer(many=True, required=False, default=list)
    
    def validate_business_partner_id(self, value):
        """Validate business partner exists"""
        if not BusinessPartner.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Business partner with ID {value} does not exist")
        return value
    
    def validate_currency_id(self, value):
        """Validate currency exists"""
        if not Currency.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Currency with ID {value} does not exist")
        return value
    
    def validate_allocations(self, value):
        """Validate allocations"""
        if not value:
            return value
        
        # Check for duplicate invoice allocations
        invoice_ids = [alloc['invoice_id'] for alloc in value]
        if len(invoice_ids) != len(set(invoice_ids)):
            raise serializers.ValidationError("Cannot allocate to the same invoice multiple times")
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # If allocations provided, validate they match the payment's business partner
        if data.get('allocations'):
            business_partner_id = data['business_partner_id']
            
            for allocation_data in data['allocations']:
                invoice = Invoice.objects.get(id=allocation_data['invoice_id'])
                
                if invoice.business_partner_id != business_partner_id:
                    raise serializers.ValidationError({
                        'allocations': f"Invoice {invoice.id} belongs to a different business partner"
                    })
                
                # Validate currency match
                if invoice.currency_id != data['currency_id']:
                    raise serializers.ValidationError({
                        'allocations': f"Invoice {invoice.id} has a different currency"
                    })
        
        return data
    
    def create(self, validated_data):
        """Create payment and allocations"""
        allocations_data = validated_data.pop('allocations', [])
        
        # Create payment
        payment = Payment.objects.create(
            date=validated_data['date'],
            business_partner_id=validated_data['business_partner_id'],
            currency_id=validated_data['currency_id'],
            exchange_rate=validated_data.get('exchange_rate')
        )
        
        # Create allocations
        for allocation_data in allocations_data:
            invoice = Invoice.objects.get(id=allocation_data['invoice_id'])
            payment.allocate_to_invoice(invoice, allocation_data['amount_allocated'])
        
        return payment


# ==================== PAYMENT UPDATE SERIALIZER ====================

class PaymentUpdateSerializer(serializers.Serializer):
    """Serializer for updating a payment"""
    date = serializers.DateField(required=False)
    exchange_rate = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        required=False,
        allow_null=True
    )
    approval_status = serializers.ChoiceField(
        choices=['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'],
        required=False
    )
    rejection_reason = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
    )
    
    def update(self, instance, validated_data):
        """Update payment fields"""
        instance.date = validated_data.get('date', instance.date)
        instance.exchange_rate = validated_data.get('exchange_rate', instance.exchange_rate)
        instance.approval_status = validated_data.get('approval_status', instance.approval_status)
        instance.rejection_reason = validated_data.get('rejection_reason', instance.rejection_reason)
        instance.save()
        return instance


# ==================== ALLOCATION MANAGEMENT SERIALIZERS ====================

class AllocationCreateSerializer(serializers.Serializer):
    """Serializer for adding allocation to existing payment"""
    invoice_id = serializers.IntegerField(min_value=1)
    amount_allocated = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    
    def validate_invoice_id(self, value):
        """Validate invoice exists"""
        if not Invoice.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Invoice with ID {value} does not exist")
        return value


class AllocationUpdateSerializer(serializers.Serializer):
    """Serializer for updating an allocation amount"""
    amount_allocated = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01')
    )


# ==================== INVOICE PAYMENT INFO SERIALIZER ====================

class InvoicePaymentInfoSerializer(serializers.ModelSerializer):
    """Serializer for invoice payment information (for adding to invoice endpoints)"""
    payment_allocations = PaymentAllocationDetailSerializer(many=True, read_only=True)
    total_allocated = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()
    is_partially_paid = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id',
            'total',
            'paid_amount',
            'payment_status',
            'total_allocated',
            'remaining_amount',
            'is_paid',
            'is_partially_paid',
            'payment_allocations'
        ]
    
    def get_total_allocated(self, obj):
        """Get total allocated amount"""
        summary = obj.get_payment_allocations_summary()
        return str(summary['total_allocated'])
    
    def get_remaining_amount(self, obj):
        """Get remaining unpaid amount"""
        return str(obj.remaining_amount())
    
    def get_is_paid(self, obj):
        """Check if fully paid"""
        return obj.is_paid()
    
    def get_is_partially_paid(self, obj):
        """Check if partially paid"""
        return obj.is_partially_paid()


# ==================== BUSINESS PARTNER PAYMENT SUMMARY SERIALIZER ====================

class BusinessPartnerPaymentSummarySerializer(serializers.Serializer):
    """Serializer for business partner payment summary (for adding to BP endpoints)"""
    total_payments = serializers.IntegerField()
    total_invoices = serializers.IntegerField()
    total_invoice_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_paid_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_unpaid_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    paid_invoices_count = serializers.IntegerField()
    partially_paid_invoices_count = serializers.IntegerField()
    unpaid_invoices_count = serializers.IntegerField()


