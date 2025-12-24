"""
Purchase Order Serializers - API Layer for PO Operations

These serializers follow the PR pattern - thin wrappers for validation and conversion.
They handle:
1. Request validation
2. Converting JSON to model instances
3. Response formatting
4. PR-to-PO conversion

Business logic is in the models themselves.
"""

from rest_framework import serializers
from decimal import Decimal
from datetime import date
from django.utils import timezone

from procurement.po.models import POHeader, POLineItem
from procurement.PR.models import PR, PRItem
from Finance.BusinessPartner.models import Supplier
from Finance.core.models import Currency
from procurement.catalog.models import UnitOfMeasure


# ==================== NESTED SERIALIZERS ====================

class POLineItemSerializer(serializers.ModelSerializer):
    """Serializer for PO line items"""
    
    # Read-only fields for response
    unit_of_measure_code = serializers.CharField(source='unit_of_measure.code', read_only=True)
    remaining_quantity = serializers.SerializerMethodField(read_only=True)
    receiving_percentage = serializers.SerializerMethodField(read_only=True)
    price_variance = serializers.SerializerMethodField(read_only=True)
    price_variance_percentage = serializers.SerializerMethodField(read_only=True)
    source_pr_number = serializers.CharField(source='source_pr_item.pr.pr_number', read_only=True)
    
    class Meta:
        model = POLineItem
        fields = [
            'id', 'line_number', 'line_type',
            'item_name', 'item_description',
            'quantity', 'unit_of_measure', 'unit_of_measure_code',
            'unit_price', 'line_total',
            'quantity_received', 'remaining_quantity', 'receiving_percentage',
            # PR tracking
            'source_pr_item', 'source_pr_number',
            'quantity_from_pr', 'price_from_pr',
            'price_variance', 'price_variance_percentage',
            'line_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'line_total', 'unit_of_measure_code',
            'remaining_quantity', 'receiving_percentage',
            'source_pr_number', 'price_variance', 'price_variance_percentage',
            'created_at', 'updated_at'
        ]
    
    def get_remaining_quantity(self, obj):
        """Get quantity remaining to be received"""
        return float(obj.get_remaining_quantity())
    
    def get_receiving_percentage(self, obj):
        """Get receiving progress as percentage"""
        return round(obj.get_receiving_percentage(), 2)
    
    def get_price_variance(self, obj):
        """Get price difference from PR"""
        variance = obj.get_price_variance()
        return float(variance) if variance is not None else None
    
    def get_price_variance_percentage(self, obj):
        """Get price variance as percentage"""
        variance_pct = obj.get_price_variance_percentage()
        return round(variance_pct, 2) if variance_pct is not None else None


class POLineItemCreateSerializer(serializers.Serializer):
    """Serializer for creating PO line items"""
    
    line_number = serializers.IntegerField(min_value=Decimal("1"))
 
    line_type = serializers.ChoiceField(choices=['Catalog', 'Non-Catalog', 'Service'])
    item_name = serializers.CharField(max_length=255)
    item_description = serializers.CharField(required=False, allow_blank=True, default='')
    quantity = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=Decimal("0.001"))
 
    unit_of_measure_id = serializers.IntegerField(min_value=Decimal("1"))
 
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal("0"))
 
    line_notes = serializers.CharField(required=False, allow_blank=True, default='')
    
    # Optional PR reference
    source_pr_item_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_quantity(self, value):
        """Ensure quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value


class POLineItemFromPRSerializer(serializers.Serializer):
    """Serializer for creating PO line items from PR items"""
    
    pr_item_id = serializers.IntegerField(min_value=Decimal("1"))
 
    quantity_to_convert = serializers.DecimalField(
        max_digits=15, 
        decimal_places=3, 
        min_value=Decimal("0.001"),
 
        required=False,
        allow_null=True,
        help_text="Quantity to convert from PR. If not specified, uses remaining quantity."
    )
    unit_price = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        min_value=Decimal("0"),
 
        help_text="Actual unit price from vendor (may differ from PR estimated price)"
    )
    line_notes = serializers.CharField(required=False, allow_blank=True, default='')
    
    def validate(self, attrs):
        """Validate PR item exists and has remaining quantity"""
        pr_item_id = attrs['pr_item_id']
        
        try:
            pr_item = PRItem.objects.get(id=pr_item_id)
        except PRItem.DoesNotExist:
            raise serializers.ValidationError({"pr_item_id": f"PR item with ID {pr_item_id} not found"})
        
        # Check if PR is approved
        if pr_item.pr.status != 'APPROVED':
            raise serializers.ValidationError(
                {"pr_item_id": f"PR {pr_item.pr.pr_number} must be APPROVED before creating PO"}
            )
        
        # Calculate remaining quantity
        remaining_qty = pr_item.quantity - pr_item.quantity_converted
        
        if remaining_qty <= 0:
            raise serializers.ValidationError(
                {"pr_item_id": f"PR item {pr_item_id} has no remaining quantity to convert"}
            )
        
        # Validate quantity_to_convert
        quantity_to_convert = attrs.get('quantity_to_convert')
        if quantity_to_convert:
            if quantity_to_convert > remaining_qty:
                raise serializers.ValidationError({
                    "quantity_to_convert": 
                    f"Requested quantity {quantity_to_convert} exceeds remaining {remaining_qty}"
                })
        else:
            # Use remaining quantity if not specified
            attrs['quantity_to_convert'] = remaining_qty
        
        # Store validated PR item for create method
        attrs['_pr_item'] = pr_item
        
        return attrs


# ==================== PO HEADER SERIALIZERS ====================

class POHeaderCreateSerializer(serializers.Serializer):
    """
    Serializer for creating Purchase Orders.
    
    Example Request Body (Manual PO):
    {
        "po_date": "2025-12-15",
        "po_type": "Catalog",
        "supplier_id": 5,
        "currency_id": 1,
        "receiving_date": "2025-12-25",
        "receiving_address": "123 Main St, City",
        "receiver_email": "receiver@company.com",
        "receiver_contact": "John Doe",
        "receiver_phone": "555-1234",
        "description": "Quarterly IT equipment purchase",
        "tax_amount": "120.00",
        "items": [
            {
                "line_number": 1,
                "line_type": "Catalog",
                "item_name": "Dell Laptop XPS 15",
                "item_description": "High-performance laptop",
                "quantity": "10",
                "unit_of_measure_id": 1,
                "unit_price": "1200.00",
                "line_notes": ""
            }
        ]
    }
    
    Example Request Body (From PR):
    {
        "po_date": "2025-12-15",
        "po_type": "Catalog",
        "supplier_id": 5,
        "currency_id": 1,
        "receiving_date": "2025-12-25",
        "receiving_address": "123 Main St, City",
        "description": "Converting PR-2025-00123",
        "tax_amount": "120.00",
        "items_from_pr": [
            {
                "pr_item_id": 45,
                "quantity_to_convert": "10",
                "unit_price": "1200.00"
            },
            {
                "pr_item_id": 46,
                "unit_price": "50.00"  // Uses remaining quantity
            }
        ]
    }
    """
    
    # PO fields
    po_date = serializers.DateField(default=date.today)
    po_type = serializers.ChoiceField(choices=['Catalog', 'Non-Catalog', 'Service'])
    supplier_id = serializers.IntegerField(min_value=Decimal("1"))
 
    currency_id = serializers.IntegerField(min_value=Decimal("1"))
 
    
    # Delivery information
    receiving_date = serializers.DateField(required=False, allow_null=True)
    receiving_address = serializers.CharField(required=False, allow_blank=True, default='')
    receiver_email = serializers.EmailField(required=False, allow_blank=True, default='')
    receiver_contact = serializers.CharField(required=False, allow_blank=True, default='')
    receiver_phone = serializers.CharField(required=False, allow_blank=True, default='')
    
    description = serializers.CharField(required=False, allow_blank=True, default='')
    tax_amount = serializers.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Nested items - use one or the other, not both
    items = POLineItemCreateSerializer(many=True, required=False)
    items_from_pr = POLineItemFromPRSerializer(many=True, required=False)
    
    def validate(self, attrs):
        """Validate that either items or items_from_pr is provided, not both"""
        has_items = bool(attrs.get('items'))
        has_items_from_pr = bool(attrs.get('items_from_pr'))
        
        if not has_items and not has_items_from_pr:
            raise serializers.ValidationError(
                "Either 'items' or 'items_from_pr' must be provided"
            )
        
        if has_items and has_items_from_pr:
            raise serializers.ValidationError(
                "Cannot specify both 'items' and 'items_from_pr'. Use one method only."
            )
        
        # Validate supplier exists
        supplier_id = attrs['supplier_id']
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            attrs['_supplier'] = supplier
        except Supplier.DoesNotExist:
            raise serializers.ValidationError(
                {"supplier_id": f"Supplier with ID {supplier_id} not found"}
            )
        
        # Validate currency exists
        currency_id = attrs['currency_id']
        try:
            Currency.objects.get(id=currency_id)
        except Currency.DoesNotExist:
            raise serializers.ValidationError(
                {"currency_id": f"Currency with ID {currency_id} not found"}
            )
        
        # Validate line types match PO type
        if has_items:
            for item in attrs['items']:
                if item['line_type'] != attrs['po_type']:
                    raise serializers.ValidationError({
                        "items": f"All line types must match PO type '{attrs['po_type']}'"
                    })
        
        # Validate PR items match PO type
        if has_items_from_pr:
            for item in attrs['items_from_pr']:
                pr_item = item['_pr_item']
                if pr_item.pr.type_of_pr != attrs['po_type']:
                    raise serializers.ValidationError({
                        "items_from_pr": 
                        f"PR item {pr_item.id} has type '{pr_item.pr.type_of_pr}' but PO type is '{attrs['po_type']}'"
                    })
        
        return attrs
    
    def create(self, validated_data):
        """Create PO with items"""
        items_data = validated_data.pop('items', None)
        items_from_pr_data = validated_data.pop('items_from_pr', None)
        
        # Get current user from context
        request = self.context.get('request')
        created_by = request.user if request else None
        
        # Get supplier's business_partner_id
        supplier = validated_data.get('_supplier')
        
        # Create PO Header
        po_header = POHeader.objects.create(
            po_date=validated_data['po_date'],
            po_type=validated_data['po_type'],
            supplier_name_id=supplier.business_partner_id,
            currency_id=validated_data['currency_id'],
            receiving_date=validated_data.get('receiving_date'),
            receiving_address=validated_data.get('receiving_address', ''),
            receiver_email=validated_data.get('receiver_email', ''),
            receiver_contact=validated_data.get('receiver_contact', ''),
            receiver_phone=validated_data.get('receiver_phone', ''),
            description=validated_data.get('description', ''),
            tax_amount=validated_data.get('tax_amount', Decimal('0.00')),
            created_by=created_by
        )
        
        # Create items from manual input
        if items_data:
            for item_data in items_data:
                POLineItem.objects.create(
                    po_header=po_header,
                    line_number=item_data['line_number'],
                    line_type=item_data['line_type'],
                    item_name=item_data['item_name'],
                    item_description=item_data.get('item_description', ''),
                    quantity=item_data['quantity'],
                    unit_of_measure_id=item_data['unit_of_measure_id'],
                    unit_price=item_data['unit_price'],
                    line_notes=item_data.get('line_notes', ''),
                    source_pr_item_id=item_data.get('source_pr_item_id')
                )
        
        # Create items from PR
        if items_from_pr_data:
            pr_headers = set()
            
            for idx, item_data in enumerate(items_from_pr_data, start=1):
                pr_item = item_data['_pr_item']
                pr_headers.add(pr_item.pr)
                
                # Create PO line item and populate from PR
                po_line = POLineItem(
                    po_header=po_header,
                    line_number=idx
                )
                po_line.populate_from_pr_item(pr_item, item_data['quantity_to_convert'])
                
                # Override unit price from request
                po_line.unit_price = item_data['unit_price']
                po_line.line_notes = item_data.get('line_notes', '')
                po_line.calculate_line_total()
                po_line.save()
                
                # Update PR item conversion tracking
                pr_item.quantity_converted += item_data['quantity_to_convert']
                if pr_item.quantity_converted >= pr_item.quantity:
                    pr_item.converted_to_po = True
                    pr_item.conversion_date = timezone.now()
                pr_item.save()
            
            # Link all source PR headers to PO
            po_header.source_pr_headers.set(pr_headers)
        
        # Recalculate totals
        po_header.calculate_totals()
        po_header.save()
        
        return po_header


class POHeaderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing POs"""
    
    supplier_name = serializers.CharField(source='supplier_name.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    item_count = serializers.SerializerMethodField(read_only=True)
    receiving_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = POHeader
        fields = [
            'id', 'po_number', 'po_date', 'po_type', 'status',
            'supplier_name', 'currency_code',
            'total_amount', 'item_count', 'receiving_summary',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_item_count(self, obj):
        """Get number of line items"""
        return obj.line_items.count()
    
    def get_receiving_summary(self, obj):
        """Get receiving status summary"""
        if obj.status in ['DRAFT', 'SUBMITTED', 'APPROVED']:
            return None
        return obj.get_receiving_summary()


class POHeaderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for PO with all related data"""
    
    # Related objects
    supplier_name = serializers.CharField(source='supplier_name.name', read_only=True)
    supplier_id = serializers.IntegerField(source='supplier_name.id', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_id = serializers.IntegerField(source='currency.id', read_only=True)
    
    # User information
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True)
    
    # Nested data
    items = POLineItemSerializer(source='line_items', many=True, read_only=True)
    source_pr_numbers = serializers.SerializerMethodField(read_only=True)
    
    # Status summaries
    receiving_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = POHeader
        fields = [
            'id', 'po_number', 'po_date', 'po_type', 'status',
            # Supplier
            'supplier_id', 'supplier_name',
            # Delivery
            'receiving_date', 'receiving_address',
            'receiver_email', 'receiver_contact', 'receiver_phone',
            # Financial
            'currency_id', 'currency_code',
            'subtotal', 'tax_amount', 'total_amount',
            # Description
            'description',
            # PR tracking
            'source_pr_numbers',
            # Workflow
            'created_by', 'created_by_name', 'created_at',
            'submitted_by', 'submitted_by_name', 'submitted_at',
            'approved_by', 'approved_by_name', 'approved_at',
            'confirmed_by', 'confirmed_by_name', 'confirmed_at',
            'cancelled_by', 'cancelled_at', 'cancellation_reason',
            'updated_at',
            # Nested
            'items',
            # Status
            'receiving_summary'
        ]
        read_only_fields = fields
    
    def get_source_pr_numbers(self, obj):
        """Get list of source PR numbers"""
        return list(obj.source_pr_headers.values_list('pr_number', flat=True))
    
    def get_receiving_summary(self, obj):
        """Get receiving status summary"""
        if obj.status in ['DRAFT', 'SUBMITTED', 'APPROVED']:
            return None
        return obj.get_receiving_summary()


# ==================== ACTION SERIALIZERS ====================

class POSubmitSerializer(serializers.Serializer):
    """Serializer for submitting PO for approval"""
    pass  # No additional fields needed


class POConfirmSerializer(serializers.Serializer):
    """Serializer for confirming PO"""
    pass  # No additional fields needed


class POCancelSerializer(serializers.Serializer):
    """Serializer for cancelling PO"""
    reason = serializers.CharField(required=True, help_text="Reason for cancellation")


class POReceiveSerializer(serializers.Serializer):
    """Serializer for recording goods receipt"""
    
    line_item_id = serializers.IntegerField(min_value=Decimal("1"))
 
    quantity_received = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=Decimal("0.001"))
 
    
    def validate(self, attrs):
        """Validate line item belongs to PO"""
        po_id = self.context.get('po_id')
        line_item_id = attrs['line_item_id']
        
        try:
            line_item = POLineItem.objects.get(id=line_item_id, po_header_id=po_id)
        except POLineItem.DoesNotExist:
            raise serializers.ValidationError({
                "line_item_id": f"Line item {line_item_id} not found in this PO"
            })
        
        # Store for create method
        attrs['_line_item'] = line_item
        
        return attrs
