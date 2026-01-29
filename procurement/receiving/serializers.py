from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone

from .models import GoodsReceipt, GoodsReceiptLine
from procurement.po.models import POHeader, POLineItem
from Finance.BusinessPartner.models import Supplier
from procurement.catalog.models import UnitOfMeasure


# ==================== LINE ITEM SERIALIZERS ====================

class GoodsReceiptLineSerializer(serializers.ModelSerializer):
    """Serializer for displaying GRN line items."""
    
    unit_of_measure_code = serializers.CharField(source='unit_of_measure.code', read_only=True)
    po_line_number = serializers.IntegerField(source='po_line_item.line_number', read_only=True, allow_null=True)
    receipt_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = GoodsReceiptLine
        fields = [
            'id', 'line_number', 'po_line_item', 'po_line_number',
            'item_name', 'item_description',
            'quantity_ordered', 'quantity_received', 'unit_of_measure', 'unit_of_measure_code',
            'unit_price', 'line_total',
            'receiving_type', 'is_gift', 'line_notes', 'receipt_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['line_total', 'created_at', 'updated_at']
    
    def get_receipt_percentage(self, obj):
        """Get receipt percentage."""
        return obj.get_receipt_percentage()


class GoodsReceiptLineCreateSerializer(serializers.Serializer):
    """Serializer for creating GRN lines manually."""
    
    line_number = serializers.IntegerField()
    po_line_item_id = serializers.IntegerField(required=False, allow_null=True)
    item_name = serializers.CharField(max_length=255)
    item_description = serializers.CharField(required=False, allow_blank=True)
    quantity_ordered = serializers.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    quantity_received = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit_of_measure_id = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    receiving_type = serializers.ChoiceField(
        choices=['PARTIAL', 'FULLY'],
        default='PARTIAL',
        help_text="PARTIAL allows any quantity <= ordered, FULLY validates against tolerance"
    )
    is_gift = serializers.BooleanField(default=False)
    line_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_quantity_received(self, value):
        """Validate quantity received is positive."""
        if value <= 0:
            raise serializers.ValidationError("Quantity received must be greater than 0")
        return value
    
    def validate_unit_of_measure_id(self, value):
        """Validate UoM exists."""
        try:
            UnitOfMeasure.objects.get(id=value)
        except UnitOfMeasure.DoesNotExist:
            raise serializers.ValidationError(f"Unit of measure with id {value} not found")
        return value
    
    def validate(self, attrs):
        """Validate line data."""
        # If po_line_item is specified, validate it
        if attrs.get('po_line_item_id'):
            try:
                po_line = POLineItem.objects.get(id=attrs['po_line_item_id'])
                attrs['_po_line_item'] = po_line
                
                # Check if PO line is already fully received (early check)
                if po_line.is_fully_received():
                    raise serializers.ValidationError({
                        'po_line_item_id': f"PO line item {po_line.id} is already fully received. "
                        f"Received: {po_line.quantity_received}, Ordered: {po_line.quantity}"
                    })
                
                # Get receiving type
                receiving_type = attrs.get('receiving_type', 'PARTIAL')
                
                # Calculate cumulative received
                previous_received = po_line.quantity_received
                quantity_to_receive = attrs['quantity_received']
                cumulative_received = previous_received + quantity_to_receive
                
                if receiving_type == 'PARTIAL':
                    # PARTIAL: Can receive any quantity <= ordered quantity
                    if cumulative_received > po_line.quantity:
                        raise serializers.ValidationError({
                            'quantity_received': f"Partial receiving: Total cumulative ({cumulative_received}) "
                            f"would exceed ordered quantity ({po_line.quantity}). Previously received: {previous_received}"
                        })
                
                elif receiving_type == 'FULLY':
                    # FULLY: Validate against tolerance
                    max_receivable = po_line.get_max_receivable_quantity()
                    min_acceptable = po_line.get_min_acceptable_quantity()
                    
                    if cumulative_received < min_acceptable:
                        raise serializers.ValidationError({
                            'quantity_received': f"Fully receiving: Total cumulative ({cumulative_received}) "
                            f"is below minimum acceptable ({min_acceptable}). Ordered: {po_line.quantity}, "
                            f"Tolerance: {po_line.tolerance_percentage}%"
                        })
                    
                    if cumulative_received > max_receivable:
                        raise serializers.ValidationError({
                            'quantity_received': f"Fully receiving: Total cumulative ({cumulative_received}) "
                            f"exceeds maximum receivable ({max_receivable}). Ordered: {po_line.quantity}, "
                            f"Tolerance: {po_line.tolerance_percentage}%"
                        })
                
            except POLineItem.DoesNotExist:
                raise serializers.ValidationError({
                    'po_line_item_id': f"PO line item with id {attrs['po_line_item_id']} not found"
                })
        
        return attrs


class GoodsReceiptLineFromPOSerializer(serializers.Serializer):
    """Serializer for creating GRN lines from PO line items."""
    
    po_line_item_id = serializers.IntegerField()
    quantity_to_receive = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        required=False,
        help_text="Quantity to receive (defaults to remaining quantity)"
    )
    receiving_type = serializers.ChoiceField(
        choices=['PARTIAL', 'FULLY'],
        default='PARTIAL',
        help_text="PARTIAL allows any quantity <= ordered, FULLY validates against tolerance"
    )
    line_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_po_line_item_id(self, value):
        """Validate PO line item exists."""
        try:
            po_line = POLineItem.objects.get(id=value)
            return value
        except POLineItem.DoesNotExist:
            raise serializers.ValidationError(f"PO line item with id {value} not found")
    
    def validate(self, attrs):
        """Validate PO line and quantity."""
        po_line = POLineItem.objects.get(id=attrs['po_line_item_id'])
        attrs['_po_line_item'] = po_line
        
        # Check if PO line is already fully received (early check)
        if po_line.is_fully_received():
            raise serializers.ValidationError({
                'po_line_item_id': f"PO line item {po_line.id} is already fully received. "
                f"Received: {po_line.quantity_received}, Ordered: {po_line.quantity}"
            })
        
        # Get receiving type
        receiving_type = attrs.get('receiving_type', 'PARTIAL')
        
        # Calculate quantity to receive (default to remaining if not specified)
        quantity_to_receive = attrs.get('quantity_to_receive')
        if quantity_to_receive is None:
            quantity_to_receive = po_line.get_remaining_quantity()
            attrs['quantity_to_receive'] = quantity_to_receive
        
        # Calculate cumulative received
        previous_received = po_line.quantity_received
        cumulative_received = previous_received + quantity_to_receive
        
        # Validate quantity
        if quantity_to_receive <= 0:
            raise serializers.ValidationError({
                'quantity_to_receive': "Quantity must be greater than 0"
            })
        
        if receiving_type == 'PARTIAL':
            # PARTIAL: Can receive any quantity <= ordered quantity
            if cumulative_received > po_line.quantity:
                raise serializers.ValidationError({
                    'quantity_to_receive': f"Partial receiving: Total cumulative ({cumulative_received}) "
                    f"would exceed ordered quantity ({po_line.quantity}). Previously received: {previous_received}"
                })
        
        elif receiving_type == 'FULLY':
            # FULLY: Validate against tolerance
            max_receivable = po_line.get_max_receivable_quantity()
            min_acceptable = po_line.get_min_acceptable_quantity()
            
            if cumulative_received < min_acceptable:
                raise serializers.ValidationError({
                    'quantity_to_receive': f"Fully receiving: Total cumulative ({cumulative_received}) "
                    f"is below minimum acceptable ({min_acceptable}). Ordered: {po_line.quantity}, "
                    f"Tolerance: {po_line.tolerance_percentage}%"
                })
            
            if cumulative_received > max_receivable:
                raise serializers.ValidationError({
                    'quantity_to_receive': f"Fully receiving: Total cumulative ({cumulative_received}) "
                    f"exceeds maximum receivable ({max_receivable}). Ordered: {po_line.quantity}, "
                    f"Tolerance: {po_line.tolerance_percentage}%"
                })
        
        return attrs


# ==================== HEADER SERIALIZERS ====================

class GoodsReceiptCreateSerializer(serializers.Serializer):
    """
    Serializer for creating Goods Receipts.
    
    Supports two modes:
    1. Manual entry: Provide 'lines' array with line details
    2. From PO: Provide 'lines_from_po' array with PO line references
    """
    
    po_header_id = serializers.IntegerField()
    receipt_date = serializers.DateField(default=timezone.now)
    expected_date = serializers.DateField(required=False, allow_null=True)
    grn_type = serializers.ChoiceField(choices=GoodsReceipt.GRN_TYPE_CHOICES)
    received_by_id = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Manual line entry
    lines = GoodsReceiptLineCreateSerializer(many=True, required=False)
    
    # Lines from PO
    lines_from_po = GoodsReceiptLineFromPOSerializer(many=True, required=False)
    
    def validate_po_header_id(self, value):
        """Validate PO exists and is confirmed or partially received."""
        try:
            po = POHeader.objects.get(id=value)
            if po.status not in ['CONFIRMED', 'PARTIALLY_RECEIVED']:
                raise serializers.ValidationError(
                    f"PO must be CONFIRMED to receive goods. Current status: {po.status}"
                )
            return value
        except POHeader.DoesNotExist:
            raise serializers.ValidationError(f"PO with id {value} not found")
    
    def validate(self, attrs):
        """Validate GRN data."""
        has_lines = 'lines' in attrs and attrs['lines']
        has_lines_from_po = 'lines_from_po' in attrs and attrs['lines_from_po']
        
        # Must specify either lines or lines_from_po (not both, not neither)
        if not has_lines and not has_lines_from_po:
            raise serializers.ValidationError({
                'lines': "Must provide either 'lines' or 'lines_from_po'"
            })
        
        if has_lines and has_lines_from_po:
            raise serializers.ValidationError({
                'lines': "Cannot specify both 'lines' and 'lines_from_po'"
            })
        
        # Get PO
        po = POHeader.objects.get(id=attrs['po_header_id'])
        attrs['_po_header'] = po
        
        # Validate GRN type matches PO type
        if attrs['grn_type'] != po.po_type:
            raise serializers.ValidationError({
                'grn_type': f"GRN type must match PO type '{po.po_type}'"
            })
        
        # Store supplier from PO
        attrs['_supplier'] = Supplier.objects.get(business_partner_id=po.supplier_name_id)
        
        return attrs
    
    def create(self, validated_data):
        """Create GRN with lines."""
        lines_data = validated_data.pop('lines', None)
        lines_from_po_data = validated_data.pop('lines_from_po', None)
        
        # Get current user from context
        request = self.context.get('request')
        received_by_id = validated_data.pop('received_by_id', None)
        received_by = request.user if request and not received_by_id else None
        if received_by_id:
            from core.user_accounts.models import UserAccount as CustomUser
            received_by = CustomUser.objects.get(id=received_by_id)
        
        # Get PO and supplier
        po_header = validated_data.pop('_po_header')
        supplier = validated_data.pop('_supplier')
        
        # Create GRN Header
        grn = GoodsReceipt.objects.create(
            po_header=po_header,
            receipt_date=validated_data['receipt_date'],
            expected_date=validated_data.get('expected_date'),
            supplier=supplier,
            grn_type=validated_data['grn_type'],
            received_by=received_by or request.user,
            notes=validated_data.get('notes', ''),
            created_by=request.user if request else None
        )
        
        # Create lines from manual entry
        if lines_data:
            for line_data in lines_data:
                po_line_item = line_data.pop('_po_line_item', None)
                
                GoodsReceiptLine.objects.create(
                    goods_receipt=grn,
                    line_number=line_data['line_number'],
                    po_line_item=po_line_item,
                    item_name=line_data['item_name'],
                    item_description=line_data.get('item_description', ''),
                    quantity_ordered=line_data.get('quantity_ordered', Decimal('0.000')),
                    quantity_received=line_data['quantity_received'],
                    unit_of_measure_id=line_data['unit_of_measure_id'],
                    unit_price=line_data['unit_price'],
                    receiving_type=line_data.get('receiving_type', 'PARTIAL'),
                    is_gift=line_data.get('is_gift', False),
                    line_notes=line_data.get('line_notes', '')
                )
        
        # Create lines from PO
        if lines_from_po_data:
            for idx, line_data in enumerate(lines_from_po_data, start=1):
                po_line_item = line_data['_po_line_item']
                quantity = line_data.get('quantity_to_receive')
                receiving_type = line_data.get('receiving_type', 'PARTIAL')
                
                # Create line and populate from PO
                grn_line = GoodsReceiptLine(
                    goods_receipt=grn,
                    line_number=idx,
                    receiving_type=receiving_type
                )
                grn_line.populate_from_po_line(po_line_item, quantity)
                grn_line.line_notes = line_data.get('line_notes', '')
                grn_line.save()
        
        # Refresh to get calculated totals
        grn.refresh_from_db()
        
        return grn


class GoodsReceiptListSerializer(serializers.ModelSerializer):
    """Serializer for listing GRNs."""
    
    po_number = serializers.CharField(source='po_header.po_number', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    line_count = serializers.SerializerMethodField()
    gift_count = serializers.SerializerMethodField()
    has_invoice = serializers.SerializerMethodField()
    
    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'grn_number', 'receipt_date', 'po_header', 'po_number',
            'supplier', 'supplier_name', 'grn_type',
            'total_amount', 'line_count', 'gift_count', 'has_invoice',
            'received_by', 'notes', 'created_at'
        ]
    
    def get_line_count(self, obj):
        """Get count of line items."""
        return obj.lines.count()
    
    def get_gift_count(self, obj):
        """Get count of gift items."""
        return obj.lines.filter(is_gift=True).count()
    
    def get_has_invoice(self, obj):
        """Check if this receipt has been invoiced."""
        return obj.has_ap_invoice()


class GoodsReceiptDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed GRN view."""
    
    po_number = serializers.CharField(source='po_header.po_number', read_only=True)
    po_type = serializers.CharField(source='po_header.po_type', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)
    receipt_summary = serializers.SerializerMethodField()
    po_completion_status = serializers.SerializerMethodField()
    has_invoice = serializers.SerializerMethodField()
    invoice_ids = serializers.SerializerMethodField()
    
    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'grn_number', 'receipt_date', 'expected_date',
            'po_header', 'po_number', 'po_type',
            'supplier', 'supplier_name', 'grn_type',
            'total_amount', 'received_by', 'received_by_name',
            'notes', 'lines', 'receipt_summary', 'po_completion_status',
            'has_invoice', 'invoice_ids',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
    
    def get_receipt_summary(self, obj):
        """Get receipt summary."""
        return obj.get_receipt_summary()
    
    def get_po_completion_status(self, obj):
        """Get PO completion status."""
        return obj.get_po_completion_status()
    
    def get_has_invoice(self, obj):
        """Check if this receipt has been invoiced."""
        return obj.has_ap_invoice()
    
    def get_invoice_ids(self, obj):
        """Get IDs of associated invoices."""
        return list(obj.get_ap_invoices().values_list('invoice_id', flat=True))
