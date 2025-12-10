"""
Invoice Serializers - API Layer for Invoice Operations

These serializers are THIN WRAPPERS around the service layer.
They handle:
1. Request validation
2. Converting JSON to DTOs
3. Calling service methods
4. Converting results back to JSON

Business logic is in services.py, NOT here!
"""

from rest_framework import serializers
from decimal import Decimal
from datetime import date

from Finance.Invoice.models import AP_Invoice, AR_Invoice, OneTimeSupplier, InvoiceItem
from Finance.Invoice.services import (
    InvoiceService,
    APInvoiceDTO, ARInvoiceDTO, OneTimeSupplierDTO,
    InvoiceItemDTO, JournalEntryDTO, JournalLineDTO, SegmentDTO
)
from Finance.GL.models import JournalEntry, JournalLine


# ==================== NESTED SERIALIZERS ====================

class SegmentSerializer(serializers.Serializer):
    """Serializer for segment in a combination"""
    segment_type_id = serializers.IntegerField(min_value=1)
    segment_code = serializers.CharField(max_length=50)
    
    def to_dto(self) -> SegmentDTO:
        """Convert to DTO"""
        return SegmentDTO(**self.validated_data)


class SegmentCombinationDetailSerializer(serializers.Serializer):
    """
    Serializer for displaying segment combination details.
    Used in journal line responses to show segment types and values
    instead of just the segment_combination_id.
    """
    segment_type_name = serializers.CharField()
    segment_code = serializers.CharField()


class JournalLineSerializer(serializers.Serializer):
    """Serializer for journal line"""
    amount = serializers.DecimalField(max_digits=14, decimal_places=5, min_value=0)
    type = serializers.ChoiceField(choices=['DEBIT', 'CREDIT'])
    segments = SegmentSerializer(many=True)
    
    def validate_segments(self, value):
        """Ensure at least one segment provided"""
        if not value:
            raise serializers.ValidationError("At least one segment is required")
        return value
    
    def to_dto(self) -> JournalLineDTO:
        """Convert to DTO"""
        return JournalLineDTO(
            amount=self.validated_data['amount'],
            type=self.validated_data['type'],
            segments=[SegmentSerializer(seg).to_dto() for seg in self.validated_data['segments']]
        )


class JournalEntrySerializer(serializers.Serializer):
    """Serializer for journal entry"""
    date = serializers.DateField()
    currency_id = serializers.IntegerField(min_value=1)
    memo = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    lines = JournalLineSerializer(many=True)
    
    def validate_lines(self, value):
        """Validate journal entry has lines and is balanced"""
        if not value:
            raise serializers.ValidationError("At least one journal line is required")
        
        if len(value) < 2:
            raise serializers.ValidationError("Journal entry must have at least 2 lines (debit and credit)")
        
        # Check balance
        total_debits = sum(
            Decimal(line['amount']) for line in value if line['type'] == 'DEBIT'
        )
        total_credits = sum(
            Decimal(line['amount']) for line in value if line['type'] == 'CREDIT'
        )
        
        if abs(total_debits - total_credits) > Decimal('0.01'):
            raise serializers.ValidationError(
                f"Journal entry is not balanced. Debits: {total_debits}, Credits: {total_credits}"
            )
        
        return value
    
    def to_dto(self) -> JournalEntryDTO:
        """Convert to DTO"""
        return JournalEntryDTO(
            date=self.validated_data['date'],
            currency_id=self.validated_data['currency_id'],
            memo=self.validated_data.get('memo', ''),
            lines=[JournalLineSerializer(line).to_dto() for line in self.validated_data['lines']]
        )


class InvoiceItemSerializer(serializers.Serializer):
    """Serializer for invoice line item"""
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    
    # Read-only calculated field
    line_total = serializers.SerializerMethodField()
    
    def get_line_total(self, obj):
        """Calculate line total for response"""
        if isinstance(obj, dict):
            return Decimal(obj['quantity']) * Decimal(obj['unit_price'])
        return obj.quantity * obj.unit_price
    
    def to_dto(self) -> InvoiceItemDTO:
        """Convert to DTO"""
        return InvoiceItemDTO(**self.validated_data)


# ==================== AP INVOICE SERIALIZERS ====================

class APInvoiceCreateSerializer(serializers.Serializer):
    """
    Serializer for creating AP Invoices.
    
    Example Request Body:
    {
        "date": "2025-12-06",
        "currency_id": 1,
        "country_id": 1,
        "supplier_id": 5,
        "tax_amount": "100.00",
        "items": [
            {
                "name": "Laptops",
                "description": "Dell XPS 15",
                "quantity": "10",
                "unit_price": "1000.00"
            }
        ],
        "journal_entry": {
            "date": "2025-12-06",
            "currency_id": 1,
            "memo": "IT equipment purchase",
            "lines": [
                {
                    "amount": "10100.00",
                    "type": "DEBIT",
                    "segments": [
                        {"segment_type_id": 1, "segment_code": "100"},
                        {"segment_type_id": 2, "segment_code": "6100"}
                    ]
                },
                {
                    "amount": "10100.00",
                    "type": "CREDIT",
                    "segments": [
                        {"segment_type_id": 1, "segment_code": "100"},
                        {"segment_type_id": 2, "segment_code": "2100"}
                    ]
                }
            ]
        }
    }
    """
    
    # Invoice fields
    date = serializers.DateField()
    currency_id = serializers.IntegerField(min_value=1)
    country_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    
    # Calculated fields (optional - will be calculated from items if not provided)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True, default=Decimal('0.00'))
    total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    
    # Status fields
    approval_status = serializers.ChoiceField(
        choices=['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'],
        default='DRAFT'
    )
    payment_status = serializers.ChoiceField(
        choices=['UNPAID', 'PARTIALLY_PAID', 'PAID'],
        default='UNPAID'
    )
    
    # AP specific
    supplier_id = serializers.IntegerField(min_value=1)
    
    # Nested data
    items = InvoiceItemSerializer(many=True)
    journal_entry = JournalEntrySerializer()
    
    def validate_items(self, value):
        """Ensure at least one item"""
        if not value:
            raise serializers.ValidationError("At least one invoice item is required")
        return value
    
    def create(self, validated_data):
        """Create AP Invoice using service layer"""
        # Convert nested items to DTOs
        items = [InvoiceItemDTO(**item) for item in validated_data['items']]
        
        # Convert journal entry to DTO
        journal_data = validated_data['journal_entry']
        journal_lines = [
            JournalLineDTO(
                amount=line['amount'],
                type=line['type'],
                segments=[SegmentDTO(**seg) for seg in line['segments']]
            )
            for line in journal_data['lines']
        ]
        journal_entry = JournalEntryDTO(
            date=journal_data['date'],
            currency_id=journal_data['currency_id'],
            memo=journal_data.get('memo', ''),
            lines=journal_lines
        )
        
        # Convert to DTO
        dto = APInvoiceDTO(
            date=validated_data['date'],
            currency_id=validated_data['currency_id'],
            country_id=validated_data.get('country_id'),
            subtotal=validated_data.get('subtotal'),
            tax_amount=validated_data.get('tax_amount'),
            total=validated_data.get('total'),
            approval_status=validated_data.get('approval_status', 'DRAFT'),
            payment_status=validated_data.get('payment_status', 'UNPAID'),
            supplier_id=validated_data['supplier_id'],
            items=items,
            journal_entry=journal_entry
        )
        
        # Call service
        return InvoiceService.create_ap_invoice(dto)


class APInvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing AP invoices"""
    
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    currency_code = serializers.CharField(source='invoice.currency.code', read_only=True)
    
    # Invoice fields (proxied through properties)
    date = serializers.DateField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    approval_status = serializers.CharField()
    payment_status = serializers.CharField()
    
    class Meta:
        model = AP_Invoice
        fields = [
            'invoice_id', 'date', 'supplier_id', 'supplier_name', 
            'currency_code', 'total', 
            'approval_status', 'payment_status'
        ]
        read_only_fields = fields


class APInvoiceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for AP invoice with all related data"""
    
    # Supplier info
    supplier = serializers.SerializerMethodField()
    
    # Invoice fields
    date = serializers.DateField()
    currency_code = serializers.CharField(source='invoice.currency.code', read_only=True)
    country_code = serializers.CharField(source='invoice.country.code', read_only=True, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    approval_status = serializers.CharField()
    payment_status = serializers.CharField()
    
    # Nested data
    items = serializers.SerializerMethodField()
    journal_entry = serializers.SerializerMethodField()
    
    class Meta:
        model = AP_Invoice
        fields = [
            'invoice_id', 'date', 'supplier', 
            'currency_code', 'country_code',
            'subtotal', 'tax_amount', 'total',
            'approval_status', 'payment_status',
            'items', 'journal_entry'
        ]
        read_only_fields = fields
    
    def get_supplier(self, obj):
        """Serialize supplier info"""
        return {
            'id': obj.supplier.business_partner_id,
            'name': obj.supplier.name,
            'email': obj.supplier.email,
            'vat_number': obj.supplier.vat_number
        }
    
    def get_items(self, obj):
        """Serialize invoice items"""
        items = obj.invoice.items.all()
        return InvoiceItemSerializer(items, many=True).data
    
    def get_journal_entry(self, obj):
        """Serialize journal entry with lines"""
        je = obj.gl_distributions
        lines = je.lines.select_related(
            'segment_combination'
        ).prefetch_related(
            'segment_combination__details__segment_type',
            'segment_combination__details__segment'
        ).all()
        
        journal_lines = []
        for line in lines:
            # Get segment combination details
            segments = []
            if line.segment_combination:
                for detail in line.segment_combination.details.all():
                    segments.append({
                        'segment_type_name': detail.segment_type.segment_name,
                        'segment_code': detail.segment.code
                    })
            
            journal_lines.append({
                'id': line.id,
                'amount': line.amount,
                'type': line.type,
                'segments': segments
            })
        
        return {
            'id': je.id,
            'date': je.date,
            'memo': je.memo,
            'posted': je.posted,
            'lines': journal_lines
        }


# ==================== AR INVOICE SERIALIZERS ====================

class ARInvoiceCreateSerializer(serializers.Serializer):
    """Serializer for creating AR Invoices - similar structure to AP"""
    
    # Invoice fields
    date = serializers.DateField()
    currency_id = serializers.IntegerField(min_value=1)
    country_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True, default=Decimal('0.00'))
    total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    
    approval_status = serializers.ChoiceField(
        choices=['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'],
        default='DRAFT'
    )
    payment_status = serializers.ChoiceField(
        choices=['UNPAID', 'PARTIALLY_PAID', 'PAID'],
        default='UNPAID'
    )
    
    # AR specific
    customer_id = serializers.IntegerField(min_value=1)
    
    # Nested data
    items = InvoiceItemSerializer(many=True)
    journal_entry = JournalEntrySerializer()
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one invoice item is required")
        return value
    
    def create(self, validated_data):
        """Create AR Invoice using service layer"""
        # Convert nested items to DTOs
        items = [InvoiceItemDTO(**item) for item in validated_data['items']]
        
        # Convert journal entry to DTO
        journal_data = validated_data['journal_entry']
        journal_lines = [
            JournalLineDTO(
                amount=line['amount'],
                type=line['type'],
                segments=[SegmentDTO(**seg) for seg in line['segments']]
            )
            for line in journal_data['lines']
        ]
        journal_entry = JournalEntryDTO(
            date=journal_data['date'],
            currency_id=journal_data['currency_id'],
            memo=journal_data.get('memo', ''),
            lines=journal_lines
        )
        
        # Convert to DTO
        dto = ARInvoiceDTO(
            date=validated_data['date'],
            currency_id=validated_data['currency_id'],
            country_id=validated_data.get('country_id'),
            subtotal=validated_data.get('subtotal'),
            tax_amount=validated_data.get('tax_amount'),
            total=validated_data.get('total'),
            approval_status=validated_data.get('approval_status', 'DRAFT'),
            payment_status=validated_data.get('payment_status', 'UNPAID'),
            customer_id=validated_data['customer_id'],
            items=items,
            journal_entry=journal_entry
        )
        
        return InvoiceService.create_ar_invoice(dto)


class ARInvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing AR invoices"""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    currency_code = serializers.CharField(source='invoice.currency.code', read_only=True)
    
    date = serializers.DateField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    approval_status = serializers.CharField()
    payment_status = serializers.CharField()
    
    class Meta:
        model = AR_Invoice
        fields = [
            'invoice_id', 'date', 'customer_id', 'customer_name', 
            'currency_code', 'total', 
            'approval_status', 'payment_status'
        ]
        read_only_fields = fields


class ARInvoiceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for AR invoice with all related data"""
    
    # Customer info
    customer = serializers.SerializerMethodField()
    
    # Invoice fields
    date = serializers.DateField()
    currency_code = serializers.CharField(source='invoice.currency.code', read_only=True)
    country_code = serializers.CharField(source='invoice.country.code', read_only=True, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    approval_status = serializers.CharField()
    payment_status = serializers.CharField()
    
    # Nested data
    items = serializers.SerializerMethodField()
    journal_entry = serializers.SerializerMethodField()
    
    class Meta:
        model = AR_Invoice
        fields = [
            'invoice_id', 'date', 'customer', 
            'currency_code', 'country_code',
            'subtotal', 'tax_amount', 'total',
            'approval_status', 'payment_status',
            'items', 'journal_entry'
        ]
        read_only_fields = fields
    
    def get_customer(self, obj):
        """Serialize customer info"""
        return {
            'id': obj.customer.business_partner_id,
            'name': obj.customer.name,
            'email': obj.customer.email
        }
    
    def get_items(self, obj):
        """Serialize invoice items"""
        items = obj.invoice.items.all()
        return InvoiceItemSerializer(items, many=True).data
    
    def get_journal_entry(self, obj):
        """Serialize journal entry with lines"""
        je = obj.gl_distributions
        lines = je.lines.select_related(
            'segment_combination'
        ).prefetch_related(
            'segment_combination__details__segment_type',
            'segment_combination__details__segment'
        ).all()
        
        journal_lines = []
        for line in lines:
            # Get segment combination details
            segments = []
            if line.segment_combination:
                for detail in line.segment_combination.details.all():
                    segments.append({
                        'segment_type_name': detail.segment_type.segment_name,
                        'segment_code': detail.segment.code
                    })
            
            journal_lines.append({
                'id': line.id,
                'amount': line.amount,
                'type': line.type,
                'segments': segments
            })
        
        return {
            'id': je.id,
            'date': je.date,
            'memo': je.memo,
            'posted': je.posted,
            'lines': journal_lines
        }


# ==================== ONE-TIME SUPPLIER SERIALIZERS ====================

class OneTimeSupplierCreateSerializer(serializers.Serializer):
    """Serializer for creating one-time supplier invoices"""
    
    # Invoice fields
    date = serializers.DateField()
    currency_id = serializers.IntegerField(min_value=1)
    country_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True, default=Decimal('0.00'))
    total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    
    approval_status = serializers.ChoiceField(
        choices=['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'],
        default='DRAFT'
    )
    payment_status = serializers.ChoiceField(
        choices=['UNPAID', 'PARTIALLY_PAID', 'PAID'],
        default='UNPAID'
    )
    
    # One-time supplier specific (either provide one_time_supplier_id OR supplier_name to create new)
    one_time_supplier_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    supplier_name = serializers.CharField(max_length=255, required=False, allow_null=True)
    supplier_email = serializers.EmailField(required=False, allow_blank=True, default="")
    supplier_phone = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    supplier_tax_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    
    def validate(self, attrs):
        """Ensure either one_time_supplier_id or supplier_name is provided"""
        if not attrs.get('one_time_supplier_id') and not attrs.get('supplier_name'):
            raise serializers.ValidationError(
                "Either 'one_time_supplier_id' or 'supplier_name' must be provided"
            )
        return attrs
    
    # Nested data
    items = InvoiceItemSerializer(many=True)
    journal_entry = JournalEntrySerializer()
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one invoice item is required")
        return value
    
    def create(self, validated_data):
        """Create one-time supplier invoice using service layer"""
        # Convert nested items to DTOs
        items = [InvoiceItemDTO(**item) for item in validated_data['items']]
        
        # Convert journal entry to DTO
        journal_data = validated_data['journal_entry']
        journal_lines = [
            JournalLineDTO(
                amount=line['amount'],
                type=line['type'],
                segments=[SegmentDTO(**seg) for seg in line['segments']]
            )
            for line in journal_data['lines']
        ]
        journal_entry = JournalEntryDTO(
            date=journal_data['date'],
            currency_id=journal_data['currency_id'],
            memo=journal_data.get('memo', ''),
            lines=journal_lines
        )
        
        # Convert to DTO
        dto = OneTimeSupplierDTO(
            date=validated_data['date'],
            currency_id=validated_data['currency_id'],
            country_id=validated_data.get('country_id'),
            subtotal=validated_data.get('subtotal'),
            tax_amount=validated_data.get('tax_amount'),
            total=validated_data.get('total'),
            approval_status=validated_data.get('approval_status', 'DRAFT'),
            payment_status=validated_data.get('payment_status', 'UNPAID'),
            one_time_supplier_id=validated_data.get('one_time_supplier_id'),
            supplier_name=validated_data.get('supplier_name'),
            supplier_email=validated_data.get('supplier_email', ''),
            supplier_phone=validated_data.get('supplier_phone', ''),
            supplier_tax_id=validated_data.get('supplier_tax_id', ''),
            items=items,
            journal_entry=journal_entry
        )
        
        return InvoiceService.create_one_time_supplier_invoice(dto)


class OneTimeSupplierListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing one-time supplier invoices"""
    
    supplier_name = serializers.CharField(source='one_time_supplier.name', read_only=True)
    currency_code = serializers.CharField(source='invoice.currency.code', read_only=True)
    
    # Invoice fields (proxied through properties)
    date = serializers.DateField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    approval_status = serializers.CharField()
    payment_status = serializers.CharField()
    
    class Meta:
        model = OneTimeSupplier
        fields = [
            'invoice_id', 'date', 'supplier_name', 
            'currency_code', 'total', 
            'approval_status', 'payment_status'
        ]
        read_only_fields = fields


class OneTimeSupplierDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for one-time supplier invoice"""
    
    # Supplier info
    supplier_name = serializers.CharField(source='one_time_supplier.name', read_only=True)
    supplier_email = serializers.CharField(source='one_time_supplier.email', read_only=True)
    supplier_phone = serializers.CharField(source='one_time_supplier.phone', read_only=True)
    supplier_tax_id = serializers.CharField(source='one_time_supplier.tax_id', read_only=True)
    
    # Invoice fields
    date = serializers.DateField()
    currency_code = serializers.CharField(source='invoice.currency.code', read_only=True)
    country_code = serializers.CharField(source='invoice.country.code', read_only=True, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    approval_status = serializers.CharField()
    payment_status = serializers.CharField()
    
    # Nested data
    items = serializers.SerializerMethodField()
    journal_entry = serializers.SerializerMethodField()
    
    class Meta:
        model = OneTimeSupplier
        fields = [
            'invoice_id', 'date', 'supplier_name',
            'supplier_email', 'supplier_phone', 'supplier_tax_id',
            'currency_code', 'country_code',
            'subtotal', 'tax_amount', 'total',
            'approval_status', 'payment_status',
            'items', 'journal_entry'
        ]
        read_only_fields = fields
    
    def get_items(self, obj):
        """Serialize invoice items"""
        items = InvoiceItem.objects.filter(invoice=obj.invoice_id)
        return [{
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'quantity': str(item.quantity),
            'unit_price': str(item.unit_price),
            'line_total': str(item.quantity * item.unit_price)
        } for item in items]
    
    def get_journal_entry(self, obj):
        """Serialize journal entry if exists"""
        if not hasattr(obj, 'invoice') or not obj.invoice or not obj.invoice.gl_distributions:
            return None
            
        journal = obj.invoice.gl_distributions
        lines = journal.lines.select_related(
            'segment_combination'
        ).prefetch_related(
            'segment_combination__details__segment_type',
            'segment_combination__details__segment'
        ).all()
        
        journal_lines = []
        for line in lines:
            # Get segment combination details
            segments = []
            if line.segment_combination:
                for detail in line.segment_combination.details.all():
                    segments.append({
                        'segment_type_name': detail.segment_type.segment_name,
                        'segment_code': detail.segment.code
                    })
            
            journal_lines.append({
                'id': line.id,
                'amount': str(line.amount),
                'type': line.type,
                'segments': segments
            })
        
        return {
            'id': journal.id,
            'date': journal.date,
            'memo': journal.memo,
            'posted': journal.posted,
            'lines': journal_lines
        }


