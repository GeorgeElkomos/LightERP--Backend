"""
Payment Serializers - API Layer for Payment Operations

These serializers handle:
1. Request validation
2. Converting JSON to Python objects
3. Response formatting
4. Nested relationships (allocations, invoices, GL entries, etc.)
"""

from rest_framework import serializers
from decimal import Decimal

from Finance.payments.models import (
    Payment,
    PaymentAllocation,
    InvoicePaymentPlan,
    PaymentPlanInstallment,
)
from Finance.Invoice.models import Invoice
from Finance.BusinessPartner.models import BusinessPartner
from Finance.core.models import Currency
from Finance.GL.models import (
    JournalEntry,
    JournalLine,
    XX_Segment_combination,
    segment_combination_detials,
)


# ==================== NESTED SERIALIZERS ====================


class SegmentDetailSerializer(serializers.Serializer):
    """Serializer for segment details in a combination"""

    segment_type_id = serializers.IntegerField(read_only=True)
    segment_type_name = serializers.CharField(read_only=True)
    segment_code = serializers.CharField(read_only=True)
    segment_alias = serializers.CharField(read_only=True)


class SegmentCombinationDetailSerializer(serializers.Serializer):
    """Serializer for displaying segment combination details"""

    id = serializers.IntegerField(read_only=True)
    description = serializers.CharField(read_only=True)
    segments = SegmentDetailSerializer(many=True, read_only=True)


class JournalLineDetailSerializer(serializers.Serializer):
    """Serializer for displaying journal line details"""

    id = serializers.IntegerField(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=5, read_only=True)
    type = serializers.CharField(read_only=True)
    segment_combination_id = serializers.IntegerField(read_only=True)
    segment_combination = SegmentCombinationDetailSerializer(read_only=True)


class JournalEntryDetailSerializer(serializers.Serializer):
    """Serializer for displaying journal entry details"""

    id = serializers.IntegerField(read_only=True)
    date = serializers.DateField(read_only=True)
    currency_id = serializers.IntegerField(read_only=True)
    currency_code = serializers.CharField(read_only=True)
    memo = serializers.CharField(read_only=True)
    posted = serializers.BooleanField(read_only=True)
    lines = JournalLineDetailSerializer(many=True, read_only=True)


class SegmentInputSerializer(serializers.Serializer):
    """Serializer for segment input in journal line creation"""

    segment_type_id = serializers.IntegerField(min_value=Decimal("1"))
 
    segment_code = serializers.CharField(max_length=50)


class JournalLineInputSerializer(serializers.Serializer):
    """Serializer for creating journal lines"""

    amount = serializers.DecimalField(
        max_digits=14, decimal_places=5, min_value=Decimal("0")
    )
    type = serializers.ChoiceField(choices=["DEBIT", "CREDIT"])
    segments = SegmentInputSerializer(many=True)

    def validate_segments(self, value):
        """Ensure at least one segment provided"""
        if not value:
            raise serializers.ValidationError("At least one segment is required")
        return value


class JournalEntryInputSerializer(serializers.Serializer):
    """Serializer for creating journal entries"""

    date = serializers.DateField()
    currency_id = serializers.IntegerField(min_value=Decimal("1"))
 
    memo = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    lines = JournalLineInputSerializer(many=True)

    def validate_lines(self, value):
        """Validate journal entry has lines and is balanced"""
        if not value:
            raise serializers.ValidationError("At least one journal line is required")

        if len(value) < 2:
            raise serializers.ValidationError(
                "Journal entry must have at least 2 lines (debit and credit)"
            )

        # Check balance
        total_debits = sum(
            Decimal(str(line["amount"])) for line in value if line["type"] == "DEBIT"
        )
        total_credits = sum(
            Decimal(str(line["amount"])) for line in value if line["type"] == "CREDIT"
        )

        if abs(total_debits - total_credits) > Decimal("0.01"):
            raise serializers.ValidationError(
                f"Journal entry is not balanced. Debits: {total_debits}, Credits: {total_credits}"
            )

        return value


class PaymentAllocationInputSerializer(serializers.Serializer):
    """Serializer for creating payment allocations"""

    invoice_id = serializers.IntegerField(min_value=Decimal("1"))
 
    amount_allocated = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate_invoice_id(self, value):
        """Validate invoice exists"""
        if not Invoice.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Invoice with ID {value} does not exist")
        return value


class PaymentAllocationDetailSerializer(serializers.ModelSerializer):
    """Serializer for displaying payment allocation details"""

    invoice_id = serializers.IntegerField(source="invoice.id", read_only=True)
    invoice_date = serializers.DateField(source="invoice.date", read_only=True)
    invoice_total = serializers.DecimalField(
        source="invoice.total", max_digits=14, decimal_places=2, read_only=True
    )
    invoice_paid_amount = serializers.DecimalField(
        source="invoice.paid_amount", max_digits=14, decimal_places=2, read_only=True
    )
    invoice_payment_status = serializers.CharField(
        source="invoice.payment_status", read_only=True
    )

    class Meta:
        model = PaymentAllocation
        fields = [
            "id",
            "invoice_id",
            "invoice_date",
            "invoice_total",
            "invoice_paid_amount",
            "invoice_payment_status",
            "amount_allocated",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ==================== PAYMENT LIST SERIALIZER ====================


class PaymentListSerializer(serializers.ModelSerializer):
    """Serializer for listing payments (lightweight)"""

    business_partner_id = serializers.IntegerField(
        source="business_partner.id", read_only=True
    )
    business_partner_name = serializers.CharField(
        source="business_partner.name", read_only=True
    )
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    allocation_count = serializers.SerializerMethodField()
    total_allocated = serializers.SerializerMethodField()
    has_gl_entry = serializers.SerializerMethodField()
    gl_entry_posted = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "date",
            "business_partner_id",
            "business_partner_name",
            "currency_code",
            "exchange_rate",
            "approval_status",
            "allocation_count",
            "total_allocated",
            "has_gl_entry",
            "gl_entry_posted",
            "created_at",
        ]

    def get_allocation_count(self, obj):
        """Get count of allocations"""
        return obj.allocations.count()

    def get_total_allocated(self, obj):
        """Get total allocated amount"""
        return str(obj.get_total_allocated())

    def get_has_gl_entry(self, obj):
        """Check if payment has GL entry"""
        return obj.gl_entry is not None

    def get_gl_entry_posted(self, obj):
        """Check if GL entry is posted"""
        return obj.gl_entry.posted if obj.gl_entry else False


# ==================== PAYMENT DETAIL SERIALIZER ====================


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed payment view"""

    business_partner_id = serializers.IntegerField(
        source="business_partner.id", read_only=True
    )
    business_partner_name = serializers.CharField(
        source="business_partner.name", read_only=True
    )
    currency_id = serializers.IntegerField(source="currency.id", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    currency_symbol = serializers.CharField(source="currency.symbol", read_only=True)
    allocations = PaymentAllocationDetailSerializer(many=True, read_only=True)
    total_allocated = serializers.SerializerMethodField()
    allocated_invoice_count = serializers.SerializerMethodField()
    gl_entry_details = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "date",
            "business_partner_id",
            "business_partner_name",
            "currency_id",
            "currency_code",
            "currency_symbol",
            "exchange_rate",
            "approval_status",
            "submitted_for_approval_at",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "gl_entry",
            "gl_entry_details",
            "allocations",
            "total_allocated",
            "allocated_invoice_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total_allocated(self, obj):
        """Get total allocated amount"""
        return str(obj.get_total_allocated())

    def get_allocated_invoice_count(self, obj):
        """Get count of invoices with allocations"""
        return obj.get_allocated_invoices().count()

    def get_gl_entry_details(self, obj):
        """Get detailed GL entry information including journal lines and segments"""
        if not obj.gl_entry:
            return None

        # Get journal entry
        journal_entry = obj.gl_entry

        # Get all journal lines with segment combinations
        lines = []
        for line in journal_entry.lines.all():
            # Get segment combination details
            segment_combination = None
            if line.segment_combination:
                combo_details = line.segment_combination.details.select_related(
                    "segment_type", "segment"
                ).all()

                segments = [
                    {
                        "segment_type_id": detail.segment_type.id,
                        "segment_type_name": detail.segment_type.segment_name,
                        "segment_code": detail.segment.code,
                        "segment_alias": detail.segment.alias or detail.segment.code,
                    }
                    for detail in combo_details
                ]

                segment_combination = {
                    "id": line.segment_combination.id,
                    "description": line.segment_combination.description,
                    "segments": segments,
                }

            lines.append(
                {
                    "id": line.id,
                    "amount": str(line.amount),
                    "type": line.type,
                    "segment_combination_id": line.segment_combination_id,
                    "segment_combination": segment_combination,
                }
            )

        return {
            "id": journal_entry.id,
            "date": journal_entry.date,
            "currency_id": journal_entry.currency_id,
            "currency_code": journal_entry.currency.code,
            "memo": journal_entry.memo,
            "posted": journal_entry.posted,
            "lines": lines,
        }


# ==================== PAYMENT CREATE SERIALIZER ====================


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating a new payment"""

    date = serializers.DateField()
    business_partner_id = serializers.IntegerField(min_value=Decimal("1"))
 
    currency_id = serializers.IntegerField(min_value=Decimal("1"))
 
    exchange_rate = serializers.DecimalField(
        max_digits=10, decimal_places=4, required=False, allow_null=True
    )
    allocations = PaymentAllocationInputSerializer(
        many=True, required=False, default=list
    )
    gl_entry = JournalEntryInputSerializer(required=False, allow_null=True)

    def validate_business_partner_id(self, value):
        """Validate business partner exists"""
        if not BusinessPartner.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                f"Business partner with ID {value} does not exist"
            )
        return value

    def validate_currency_id(self, value):
        """Validate currency exists"""
        if not Currency.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                f"Currency with ID {value} does not exist"
            )
        return value

    def validate_allocations(self, value):
        """Validate allocations"""
        if not value:
            return value

        # Check for duplicate invoice allocations
        invoice_ids = [alloc["invoice_id"] for alloc in value]
        if len(invoice_ids) != len(set(invoice_ids)):
            raise serializers.ValidationError(
                "Cannot allocate to the same invoice multiple times"
            )

        return value

    def validate(self, data):
        """Cross-field validation"""
        # If allocations provided, validate they match the payment's business partner
        if data.get("allocations"):
            business_partner_id = data["business_partner_id"]

            for allocation_data in data["allocations"]:
                invoice = Invoice.objects.get(id=allocation_data["invoice_id"])

                if invoice.business_partner_id != business_partner_id:
                    raise serializers.ValidationError(
                        {
                            "allocations": f"Invoice {invoice.id} belongs to a different business partner"
                        }
                    )

                # Validate currency match
                if invoice.currency_id != data["currency_id"]:
                    raise serializers.ValidationError(
                        {
                            "allocations": f"Invoice {invoice.id} has a different currency"
                        }
                    )

        # Validate GL entry currency matches payment currency
        if data.get("gl_entry"):
            if data["gl_entry"]["currency_id"] != data["currency_id"]:
                raise serializers.ValidationError(
                    {"gl_entry": "GL entry currency must match payment currency"}
                )

        return data

    def create(self, validated_data):
        """Create payment, GL entry, and allocations"""
        from django.db import transaction

        allocations_data = validated_data.pop("allocations", [])
        gl_entry_data = validated_data.pop("gl_entry", None)

        with transaction.atomic():
            # Create GL entry if provided
            gl_entry = None
            if gl_entry_data:
                gl_entry = self._create_gl_entry(gl_entry_data)

            # Create payment
            payment = Payment.objects.create(
                date=validated_data["date"],
                business_partner_id=validated_data["business_partner_id"],
                currency_id=validated_data["currency_id"],
                exchange_rate=validated_data.get("exchange_rate"),
                gl_entry=gl_entry,
            )

            # Create allocations
            for allocation_data in allocations_data:
                invoice = Invoice.objects.get(id=allocation_data["invoice_id"])
                payment.allocate_to_invoice(
                    invoice, allocation_data["amount_allocated"]
                )

        return payment

    def _create_gl_entry(self, gl_entry_data):
        """Helper method to create GL entry with lines and segment combinations"""
        lines_data = gl_entry_data.pop("lines", [])

        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            date=gl_entry_data["date"],
            currency_id=gl_entry_data["currency_id"],
            memo=gl_entry_data.get("memo", ""),
        )

        # Create journal lines
        for line_data in lines_data:
            segments_data = line_data.pop("segments", [])

            # Get or create segment combination
            combination_list = [
                (seg["segment_type_id"], seg["segment_code"]) for seg in segments_data
            ]
            segment_combination_id = XX_Segment_combination.get_combination_id(
                combination_list, description=f"Payment GL Entry Line"
            )

            # Create journal line
            JournalLine.objects.create(
                entry=journal_entry,
                amount=line_data["amount"],
                type=line_data["type"],
                segment_combination_id=segment_combination_id,
            )

        return journal_entry


# ==================== PAYMENT UPDATE SERIALIZER ====================


class PaymentUpdateSerializer(serializers.Serializer):
    """Serializer for updating a payment"""

    date = serializers.DateField(required=False)
    exchange_rate = serializers.DecimalField(
        max_digits=10, decimal_places=4, required=False, allow_null=True
    )
    approval_status = serializers.ChoiceField(
        choices=["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED"], required=False
    )
    rejection_reason = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    def update(self, instance, validated_data):
        """Update payment fields"""
        instance.date = validated_data.get("date", instance.date)
        instance.exchange_rate = validated_data.get(
            "exchange_rate", instance.exchange_rate
        )
        instance.approval_status = validated_data.get(
            "approval_status", instance.approval_status
        )
        instance.rejection_reason = validated_data.get(
            "rejection_reason", instance.rejection_reason
        )
        instance.save()
        return instance


# ==================== ALLOCATION MANAGEMENT SERIALIZERS ====================


class AllocationCreateSerializer(serializers.Serializer):
    """Serializer for adding allocation to existing payment"""

    invoice_id = serializers.IntegerField(min_value=Decimal("1"))
 
    amount_allocated = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate_invoice_id(self, value):
        """Validate invoice exists"""
        if not Invoice.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Invoice with ID {value} does not exist")
        return value


class AllocationUpdateSerializer(serializers.Serializer):
    """Serializer for updating an allocation amount"""

    amount_allocated = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01")
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
            "id",
            "total",
            "paid_amount",
            "payment_status",
            "total_allocated",
            "remaining_amount",
            "is_paid",
            "is_partially_paid",
            "payment_allocations",
        ]

    def get_total_allocated(self, obj):
        """Get total allocated amount"""
        summary = obj.get_payment_allocations_summary()
        return str(summary["total_allocated"])

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


# ==================== PAYMENT PLAN SERIALIZERS ====================


class InstallmentInputSerializer(serializers.Serializer):
    """Serializer for creating installments within a payment plan"""

    installment_number = serializers.IntegerField(min_value=Decimal("1"))
 
    due_date = serializers.DateField()
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )


class InstallmentListSerializer(serializers.ModelSerializer):
    """Serializer for listing installments"""

    payment_plan_id = serializers.IntegerField(source="payment_plan.id", read_only=True)
    remaining_balance = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()

    class Meta:
        model = PaymentPlanInstallment
        fields = [
            "id",
            "payment_plan_id",
            "installment_number",
            "due_date",
            "amount",
            "paid_amount",
            "remaining_balance",
            "status",
            "is_overdue",
            "days_until_due",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_remaining_balance(self, obj):
        """Get remaining balance for installment"""
        return str(obj.get_remaining_balance())

    def get_is_overdue(self, obj):
        """Check if installment is overdue"""
        return obj.is_overdue()

    def get_days_until_due(self, obj):
        """Calculate days until due (negative if overdue)"""
        from django.utils import timezone

        today = timezone.now().date()
        delta = (obj.due_date - today).days
        return delta


class InstallmentDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed installment view"""

    payment_plan_id = serializers.IntegerField(source="payment_plan.id", read_only=True)
    invoice_id = serializers.IntegerField(
        source="payment_plan.invoice.id", read_only=True
    )
    invoice_number = serializers.CharField(
        source="payment_plan.invoice.id", read_only=True
    )
    business_partner_name = serializers.CharField(
        source="payment_plan.invoice.business_partner.name", read_only=True
    )
    remaining_balance = serializers.SerializerMethodField()
    is_fully_paid = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()

    class Meta:
        model = PaymentPlanInstallment
        fields = [
            "id",
            "payment_plan_id",
            "invoice_id",
            "invoice_number",
            "business_partner_name",
            "installment_number",
            "due_date",
            "amount",
            "paid_amount",
            "remaining_balance",
            "status",
            "is_fully_paid",
            "is_overdue",
            "days_until_due",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_remaining_balance(self, obj):
        """Get remaining balance for installment"""
        return str(obj.get_remaining_balance())

    def get_is_fully_paid(self, obj):
        """Check if installment is fully paid"""
        return obj.is_fully_paid()

    def get_is_overdue(self, obj):
        """Check if installment is overdue"""
        return obj.is_overdue()

    def get_days_until_due(self, obj):
        """Calculate days until due (negative if overdue)"""
        from django.utils import timezone

        today = timezone.now().date()
        delta = (obj.due_date - today).days
        return delta


class InstallmentCreateSerializer(serializers.Serializer):
    """Serializer for creating a single installment"""

    installment_number = serializers.IntegerField(min_value=Decimal("1"))
 
    due_date = serializers.DateField()
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )


class InstallmentUpdateSerializer(serializers.Serializer):
    """Serializer for updating an installment"""

    due_date = serializers.DateField(required=False)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True
    )

    def validate(self, data):
        """Validate that installment can be updated"""
        # Check if installment has been paid
        if hasattr(self, "instance") and self.instance:
            if self.instance.paid_amount > 0:
                raise serializers.ValidationError(
                    "Cannot modify installment that has received payments"
                )
        return data


class PaymentPlanListSerializer(serializers.ModelSerializer):
    """Serializer for listing payment plans"""

    invoice_id = serializers.IntegerField(source="invoice.id", read_only=True)
    invoice_date = serializers.DateField(source="invoice.date", read_only=True)
    business_partner_name = serializers.CharField(
        source="invoice.business_partner.name", read_only=True
    )
    currency_code = serializers.CharField(
        source="invoice.currency.code", read_only=True
    )
    installment_count = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()
    has_overdue = serializers.SerializerMethodField()

    class Meta:
        model = InvoicePaymentPlan
        fields = [
            "id",
            "invoice_id",
            "invoice_date",
            "business_partner_name",
            "currency_code",
            "total_amount",
            "total_paid",
            "remaining_balance",
            "status",
            "installment_count",
            "has_overdue",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_installment_count(self, obj):
        """Get count of installments"""
        return obj.installments.count()

    def get_total_paid(self, obj):
        """Get total paid amount"""
        return str(obj.get_total_paid())

    def get_remaining_balance(self, obj):
        """Get remaining balance"""
        return str(obj.get_remaining_balance())

    def get_has_overdue(self, obj):
        """Check if has overdue installments"""
        return obj.has_overdue_installments()


class PaymentPlanDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed payment plan view with installments"""

    invoice_id = serializers.IntegerField(source="invoice.id", read_only=True)
    invoice_date = serializers.DateField(source="invoice.date", read_only=True)
    invoice_total = serializers.DecimalField(
        source="invoice.total", max_digits=14, decimal_places=2, read_only=True
    )
    business_partner_id = serializers.IntegerField(
        source="invoice.business_partner.id", read_only=True
    )
    business_partner_name = serializers.CharField(
        source="invoice.business_partner.name", read_only=True
    )
    currency_code = serializers.CharField(
        source="invoice.currency.code", read_only=True
    )
    installments = InstallmentListSerializer(many=True, read_only=True)
    total_paid = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()
    is_fully_paid = serializers.SerializerMethodField()
    has_overdue_installments = serializers.SerializerMethodField()
    overdue_count = serializers.SerializerMethodField()
    next_due_installment = serializers.SerializerMethodField()

    class Meta:
        model = InvoicePaymentPlan
        fields = [
            "id",
            "invoice_id",
            "invoice_date",
            "invoice_total",
            "business_partner_id",
            "business_partner_name",
            "currency_code",
            "total_amount",
            "total_paid",
            "remaining_balance",
            "is_fully_paid",
            "status",
            "has_overdue_installments",
            "overdue_count",
            "next_due_installment",
            "description",
            "installments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total_paid(self, obj):
        """Get total paid amount"""
        return str(obj.get_total_paid())

    def get_remaining_balance(self, obj):
        """Get remaining balance"""
        return str(obj.get_remaining_balance())

    def get_is_fully_paid(self, obj):
        """Check if fully paid"""
        return obj.is_fully_paid()

    def get_has_overdue_installments(self, obj):
        """Check if has overdue installments"""
        return obj.has_overdue_installments()

    def get_overdue_count(self, obj):
        """Get count of overdue installments"""
        return obj.get_overdue_installments().count()

    def get_next_due_installment(self, obj):
        """Get next unpaid installment"""
        from django.db.models import F

        next_installment = (
            obj.installments.filter(paid_amount__lt=F("amount"))
            .order_by("due_date")
            .first()
        )

        if next_installment:
            return {
                "installment_number": next_installment.installment_number,
                "due_date": next_installment.due_date,
                "amount": str(next_installment.amount),
                "paid_amount": str(next_installment.paid_amount),
                "remaining_balance": str(next_installment.get_remaining_balance()),
            }
        return None


class PaymentPlanCreateSerializer(serializers.Serializer):
    """Serializer for creating a payment plan with installments"""

    total_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default=""
    )
    installments = InstallmentInputSerializer(many=True)

    def validate_installments(self, value):
        """Validate installments"""
        if not value:
            raise serializers.ValidationError("At least one installment is required")

        # Check for duplicate installment numbers
        installment_numbers = [inst["installment_number"] for inst in value]
        if len(installment_numbers) != len(set(installment_numbers)):
            raise serializers.ValidationError(
                "Duplicate installment numbers are not allowed"
            )

        # Validate installment numbers are sequential starting from 1
        sorted_numbers = sorted(installment_numbers)
        expected_numbers = list(range(1, len(installment_numbers) + 1))
        if sorted_numbers != expected_numbers:
            raise serializers.ValidationError(
                f"Installment numbers must be sequential starting from 1. "
                f"Expected {expected_numbers}, got {sorted_numbers}"
            )

        return value

    def validate(self, data):
        """Cross-field validation"""
        # Validate total of installments matches total_amount
        installments_total = sum(
            Decimal(str(inst["amount"])) for inst in data["installments"]
        )

        if abs(installments_total - data["total_amount"]) > Decimal("0.01"):
            raise serializers.ValidationError(
                {
                    "installments": f"Sum of installment amounts ({installments_total}) "
                    f"must equal total_amount ({data['total_amount']})"
                }
            )

        return data

    def create(self, validated_data):
        """Create payment plan with installments"""
        from django.db import transaction

        installments_data = validated_data.pop("installments")
        invoice_id = self.context["invoice_id"]

        with transaction.atomic():
            # Create payment plan
            payment_plan = InvoicePaymentPlan.objects.create(
                invoice_id=invoice_id,
                total_amount=validated_data["total_amount"],
                description=validated_data.get("description", ""),
                status="pending",
            )

            # Create installments
            for installment_data in installments_data:
                PaymentPlanInstallment.objects.create(
                    payment_plan=payment_plan,
                    installment_number=installment_data["installment_number"],
                    due_date=installment_data["due_date"],
                    amount=installment_data["amount"],
                    description=installment_data.get("description", ""),
                    status="pending",
                    paid_amount=Decimal("0.00"),
                )

        return payment_plan


class PaymentPlanUpdateSerializer(serializers.Serializer):
    """Serializer for updating payment plan (limited fields)"""

    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=["pending", "partial", "paid", "overdue", "cancelled"], required=False
    )

    def validate_status(self, value):
        """Validate status change"""
        # Only allow manual cancellation
        if value == "cancelled":
            return value
        raise serializers.ValidationError(
            "Status can only be manually changed to 'cancelled'. "
            "Other statuses are automatically managed by the system."
        )


class ProcessPaymentSerializer(serializers.Serializer):
    """Serializer for processing a payment on a payment plan"""

    payment_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )


class PaymentPlanSummarySerializer(serializers.Serializer):
    """Serializer for payment plan summary"""

    payment_plan_id = serializers.IntegerField()
    invoice_id = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    remaining_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_fully_paid = serializers.BooleanField()
    has_overdue_installments = serializers.BooleanField()
    overdue_count = serializers.IntegerField()
    next_due_installment = serializers.DictField(allow_null=True)


class SuggestPaymentPlanSerializer(serializers.Serializer):
    """Serializer for suggesting a payment plan"""

    start_date = serializers.DateField()
    num_installments = serializers.IntegerField(min_value=Decimal("1"),
  max_value=100)
    frequency = serializers.ChoiceField(
        choices=["weekly", "monthly", "quarterly"], default="monthly"
    )


class OverdueInstallmentSerializer(serializers.ModelSerializer):
    """Serializer for overdue installments"""

    payment_plan_id = serializers.IntegerField(source="payment_plan.id", read_only=True)
    invoice_id = serializers.IntegerField(
        source="payment_plan.invoice.id", read_only=True
    )
    business_partner_name = serializers.CharField(
        source="payment_plan.invoice.business_partner.name", read_only=True
    )
    days_overdue = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()

    class Meta:
        model = PaymentPlanInstallment
        fields = [
            "id",
            "payment_plan_id",
            "invoice_id",
            "business_partner_name",
            "installment_number",
            "due_date",
            "amount",
            "paid_amount",
            "remaining_balance",
            "days_overdue",
            "status",
        ]

    def get_days_overdue(self, obj):
        """Calculate days overdue"""
        from django.utils import timezone

        today = timezone.now().date()
        if obj.due_date < today:
            return (today - obj.due_date).days
        return 0

    def get_remaining_balance(self, obj):
        """Get remaining balance"""
        return str(obj.get_remaining_balance())
