"""
Purchase Requisition Serializers - API Layer for PR Operations

These serializers follow the Invoice pattern - thin wrappers for validation and conversion.
They handle:
1. Request validation
2. Converting JSON to model instances
3. Response formatting

Business logic is in the models themselves.
"""

from rest_framework import serializers
from decimal import Decimal
from datetime import date

from procurement.PR.models import (
    PR, PRItem, Catalog_PR, NonCatalog_PR, Service_PR
)
from procurement.catalog.models import catalogItem, UnitOfMeasure
from Finance.BusinessPartner.models import Supplier


# ==================== NESTED SERIALIZERS ====================

class PRItemSerializer(serializers.ModelSerializer):
    """Serializer for PR line items"""
    
    # Read-only fields for response
    catalog_item_name = serializers.CharField(source='catalog_item.name', read_only=True)
    unit_of_measure_code = serializers.CharField(source='unit_of_measure.code', read_only=True)
    category_name = serializers.SerializerMethodField(read_only=True)
    remaining_quantity = serializers.SerializerMethodField(read_only=True)
    conversion_percentage = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = PRItem
        fields = [
            'id', 'line_number', 'item_name', 'item_description',
            'catalog_item', 'catalog_item_name', 'quantity', 
            'unit_of_measure', 'unit_of_measure_code',
            'estimated_unit_price', 'total_price_per_item',
            'notes', 'category_name',
            # Conversion tracking fields
            'converted_to_po', 'quantity_converted', 'conversion_date',
            'remaining_quantity', 'conversion_percentage'
        ]
        read_only_fields = ['id', 'total_price_per_item', 'catalog_item_name', 
                           'unit_of_measure_code', 'category_name',
                           'converted_to_po', 'quantity_converted', 'conversion_date',
                           'remaining_quantity', 'conversion_percentage']
    
    def get_category_name(self, obj):
        """Get category from catalog item if available"""
        if obj.catalog_item:
            return obj.catalog_item.name
        return None
    
    def get_remaining_quantity(self, obj):
        """Get quantity remaining to be converted to PO"""
        return float(obj.quantity - obj.quantity_converted)
    
    def get_conversion_percentage(self, obj):
        """Get conversion progress as percentage"""
        if obj.quantity == 0:
            return 0
        return round((obj.quantity_converted / obj.quantity) * 100, 2)


class PRItemCreateSerializer(serializers.Serializer):
    """Serializer for creating PR items"""
    
    item_name = serializers.CharField(max_length=255)
    item_description = serializers.CharField(required=False, allow_blank=True, default='')
    catalog_item_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    unit_of_measure_id = serializers.IntegerField(min_value=1)
    estimated_unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, default=0)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    
    def validate_quantity(self, value):
        """Ensure quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value


# ==================== CATALOG PR SERIALIZERS ====================

class CatalogPRCreateSerializer(serializers.Serializer):
    """
    Serializer for creating Catalog PRs.
    
    Example Request Body:
    {
        "date": "2025-12-15",
        "required_date": "2025-12-25",
        "requester_name": "John Doe",
        "requester_department": "IT",
        "requester_email": "john.doe@company.com",
        "priority": "MEDIUM",
        "description": "Quarterly IT equipment purchase",
        "notes": "Standard procurement",
        "items": [
            {
                "item_name": "Dell Laptop XPS 15",
                "item_description": "High-performance laptop for development",
                "catalog_item_id": 5,
                "quantity": "10",
                "unit_of_measure_id": 1,
                "estimated_unit_price": "1200.00",
                "notes": "Urgent need"
            }
        ]
    }
    """
    
    # PR fields
    date = serializers.DateField()
    required_date = serializers.DateField()
    requester_name = serializers.CharField(max_length=255)
    requester_department = serializers.CharField(max_length=255)
    requester_email = serializers.EmailField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['LOW', 'MEDIUM', 'HIGH', 'URGENT'],
        default='MEDIUM'
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    
    # Nested items
    items = PRItemCreateSerializer(many=True)
    
    def validate_items(self, value):
        """Ensure at least one item and all items have catalog_item_id"""
        if not value:
            raise serializers.ValidationError("At least one item is required")
        
        for item in value:
            if not item.get('catalog_item_id'):
                raise serializers.ValidationError(
                    "All items must reference a catalog item (catalog_item_id required)"
                )
        return value
    
    def validate(self, attrs):
        """Validate required_date is after date"""
        if attrs['required_date'] < attrs['date']:
            raise serializers.ValidationError(
                "Required date must be on or after the PR date"
            )
        return attrs
    
    def create(self, validated_data):
        """Create Catalog PR with items"""
        items_data = validated_data.pop('items')
        
        # Create Catalog_PR (auto-creates parent PR)
        catalog_pr = Catalog_PR.objects.create(
            date=validated_data['date'],
            required_date=validated_data['required_date'],
            requester_name=validated_data['requester_name'],
            requester_department=validated_data['requester_department'],
            requester_email=validated_data.get('requester_email', ''),
            priority=validated_data.get('priority', 'MEDIUM'),
            description=validated_data.get('description', ''),
            notes=validated_data.get('notes', '')
        )
        
        # Create items
        for item_data in items_data:
            PRItem.objects.create(
                pr=catalog_pr.pr,
                item_name=item_data['item_name'],
                item_description=item_data.get('item_description', ''),
                catalog_item_id=item_data.get('catalog_item_id'),
                quantity=item_data['quantity'],
                unit_of_measure_id=item_data['unit_of_measure_id'],
                estimated_unit_price=item_data.get('estimated_unit_price', 0),
                notes=item_data.get('notes', '')
            )
        
        # Generate PR number
        catalog_pr.pr.generate_pr_number()
        catalog_pr.pr._allow_direct_save = True
        catalog_pr.pr.save()
        
        return catalog_pr


class CatalogPRListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing Catalog PRs"""
    
    pr_number = serializers.CharField(source='pr.pr_number', read_only=True)
    date = serializers.DateField(source='pr.date', read_only=True)
    required_date = serializers.DateField(source='pr.required_date', read_only=True)
    requester_name = serializers.CharField(source='pr.requester_name', read_only=True)
    requester_department = serializers.CharField(source='pr.requester_department', read_only=True)
    status = serializers.CharField(source='pr.status', read_only=True)
    priority = serializers.CharField(source='pr.priority', read_only=True)
    total = serializers.DecimalField(source='pr.total', max_digits=14, decimal_places=2, read_only=True)
    item_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Catalog_PR
        fields = [
            'pr_id', 'pr_number', 'date', 'required_date',
            'requester_name', 'requester_department', 'status', 
            'priority', 'total', 'item_count'
        ]
        read_only_fields = fields
    
    def get_item_count(self, obj):
        """Get number of items"""
        return obj.pr.get_item_count()


class CatalogPRDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Catalog PR with all related data"""
    
    # PR fields
    pr_number = serializers.CharField(source='pr.pr_number', read_only=True)
    date = serializers.DateField(source='pr.date', read_only=True)
    required_date = serializers.DateField(source='pr.required_date', read_only=True)
    requester_name = serializers.CharField(source='pr.requester_name', read_only=True)
    requester_department = serializers.CharField(source='pr.requester_department', read_only=True)
    requester_email = serializers.EmailField(source='pr.requester_email', read_only=True)
    status = serializers.CharField(source='pr.status', read_only=True)
    priority = serializers.CharField(source='pr.priority', read_only=True)
    total = serializers.DecimalField(source='pr.total', max_digits=14, decimal_places=2, read_only=True)
    description = serializers.CharField(source='pr.description', read_only=True)
    notes = serializers.CharField(source='pr.notes', read_only=True)
    
    # Timestamps
    created_at = serializers.DateTimeField(source='pr.created_at', read_only=True)
    updated_at = serializers.DateTimeField(source='pr.updated_at', read_only=True)
    
    # Approval tracking
    submitted_for_approval_at = serializers.DateTimeField(source='pr.submitted_for_approval_at', read_only=True)
    approved_at = serializers.DateTimeField(source='pr.approved_at', read_only=True)
    approved_by = serializers.CharField(source='pr.approved_by', read_only=True)
    rejected_at = serializers.DateTimeField(source='pr.rejected_at', read_only=True)
    rejected_by = serializers.CharField(source='pr.rejected_by', read_only=True)
    rejection_reason = serializers.CharField(source='pr.rejection_reason', read_only=True)
    
    # Nested data
    items = serializers.SerializerMethodField()
    
    class Meta:
        model = Catalog_PR
        fields = [
            'pr_id', 'pr_number', 'date', 'required_date',
            'requester_name', 'requester_department', 'requester_email',
            'status', 'priority', 'total', 'description', 'notes',
            'created_at', 'updated_at',
            'submitted_for_approval_at', 'approved_at', 'approved_by',
            'rejected_at', 'rejected_by', 'rejection_reason',
            'items'
        ]
        read_only_fields = fields
    
    def get_items(self, obj):
        """Serialize PR items"""
        items = obj.pr.items.select_related(
            'catalog_item', 'unit_of_measure'
        ).all()
        return PRItemSerializer(items, many=True).data


# ==================== NON-CATALOG PR SERIALIZERS ====================

class NonCatalogPRCreateSerializer(serializers.Serializer):
    """
    Serializer for creating Non-Catalog PRs.
    
    Example Request Body:
    {
        "date": "2025-12-15",
        "required_date": "2025-12-25",
        "requester_name": "Jane Smith",
        "requester_department": "Engineering",
        "requester_email": "jane.smith@company.com",
        "priority": "HIGH",
        "description": "Custom equipment not in catalog",
        "notes": "Special order from vendor ABC",
        "items": [
            {
                "item_name": "Custom CNC Machine Part",
                "item_description": "Specialized component for production line",
                "quantity": "5",
                "unit_of_measure_id": 1,
                "estimated_unit_price": "5000.00",
                "notes": "Contact supplier XYZ",
                "catalog_item_id": 10  // Optional: for categorization only
            }
        ]
    }
    """
    
    # PR fields
    date = serializers.DateField()
    required_date = serializers.DateField()
    requester_name = serializers.CharField(max_length=255)
    requester_department = serializers.CharField(max_length=255)
    requester_email = serializers.EmailField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['LOW', 'MEDIUM', 'HIGH', 'URGENT'],
        default='MEDIUM'
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    
    # Nested items
    items = PRItemCreateSerializer(many=True)
    
    def validate_items(self, value):
        """Ensure at least one item"""
        if not value:
            raise serializers.ValidationError("At least one item is required")
        return value
    
    def validate(self, attrs):
        """Validate required_date is after date"""
        if attrs['required_date'] < attrs['date']:
            raise serializers.ValidationError(
                "Required date must be on or after the PR date"
            )
        return attrs
    
    def create(self, validated_data):
        """Create Non-Catalog PR with items"""
        items_data = validated_data.pop('items')
        
        # Create NonCatalog_PR (auto-creates parent PR)
        noncatalog_pr = NonCatalog_PR.objects.create(
            date=validated_data['date'],
            required_date=validated_data['required_date'],
            requester_name=validated_data['requester_name'],
            requester_department=validated_data['requester_department'],
            requester_email=validated_data.get('requester_email', ''),
            priority=validated_data.get('priority', 'MEDIUM'),
            description=validated_data.get('description', ''),
            notes=validated_data.get('notes', '')
        )
        
        # Create items
        for item_data in items_data:
            PRItem.objects.create(
                pr=noncatalog_pr.pr,
                item_name=item_data['item_name'],
                item_description=item_data.get('item_description', ''),
                catalog_item_id=item_data.get('catalog_item_id'),  # Optional for categorization
                quantity=item_data['quantity'],
                unit_of_measure_id=item_data['unit_of_measure_id'],
                estimated_unit_price=item_data.get('estimated_unit_price', 0),
                notes=item_data.get('notes', '')
            )
        
        # Generate PR number
        noncatalog_pr.pr.generate_pr_number()
        noncatalog_pr.pr._allow_direct_save = True
        noncatalog_pr.pr.save()
        
        return noncatalog_pr


class NonCatalogPRListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing Non-Catalog PRs"""
    
    pr_number = serializers.CharField(source='pr.pr_number', read_only=True)
    date = serializers.DateField(source='pr.date', read_only=True)
    required_date = serializers.DateField(source='pr.required_date', read_only=True)
    requester_name = serializers.CharField(source='pr.requester_name', read_only=True)
    requester_department = serializers.CharField(source='pr.requester_department', read_only=True)
    status = serializers.CharField(source='pr.status', read_only=True)
    priority = serializers.CharField(source='pr.priority', read_only=True)
    total = serializers.DecimalField(source='pr.total', max_digits=14, decimal_places=2, read_only=True)
    item_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = NonCatalog_PR
        fields = [
            'pr_id', 'pr_number', 'date', 'required_date',
            'requester_name', 'requester_department', 'status', 
            'priority', 'total', 'item_count'
        ]
        read_only_fields = fields
    
    def get_item_count(self, obj):
        """Get number of items"""
        return obj.pr.get_item_count()


class NonCatalogPRDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Non-Catalog PR with all related data"""
    
    # PR fields
    pr_number = serializers.CharField(source='pr.pr_number', read_only=True)
    date = serializers.DateField(source='pr.date', read_only=True)
    required_date = serializers.DateField(source='pr.required_date', read_only=True)
    requester_name = serializers.CharField(source='pr.requester_name', read_only=True)
    requester_department = serializers.CharField(source='pr.requester_department', read_only=True)
    requester_email = serializers.EmailField(source='pr.requester_email', read_only=True)
    status = serializers.CharField(source='pr.status', read_only=True)
    priority = serializers.CharField(source='pr.priority', read_only=True)
    total = serializers.DecimalField(source='pr.total', max_digits=14, decimal_places=2, read_only=True)
    description = serializers.CharField(source='pr.description', read_only=True)
    notes = serializers.CharField(source='pr.notes', read_only=True)
    
    # Timestamps
    created_at = serializers.DateTimeField(source='pr.created_at', read_only=True)
    updated_at = serializers.DateTimeField(source='pr.updated_at', read_only=True)
    
    # Approval tracking
    submitted_for_approval_at = serializers.DateTimeField(source='pr.submitted_for_approval_at', read_only=True)
    approved_at = serializers.DateTimeField(source='pr.approved_at', read_only=True)
    approved_by = serializers.CharField(source='pr.approved_by', read_only=True)
    rejected_at = serializers.DateTimeField(source='pr.rejected_at', read_only=True)
    rejected_by = serializers.CharField(source='pr.rejected_by', read_only=True)
    rejection_reason = serializers.CharField(source='pr.rejection_reason', read_only=True)
    
    # Nested data
    items = serializers.SerializerMethodField()
    
    class Meta:
        model = NonCatalog_PR
        fields = [
            'pr_id', 'pr_number', 'date', 'required_date',
            'requester_name', 'requester_department', 'requester_email',
            'status', 'priority', 'total', 'description', 'notes',
            'created_at', 'updated_at',
            'submitted_for_approval_at', 'approved_at', 'approved_by',
            'rejected_at', 'rejected_by', 'rejection_reason',
            'items'
        ]
        read_only_fields = fields
    
    def get_items(self, obj):
        """Serialize PR items"""
        items = obj.pr.items.select_related(
            'catalog_item', 'unit_of_measure'
        ).all()
        return PRItemSerializer(items, many=True).data


# ==================== SERVICE PR SERIALIZERS ====================

class ServicePRCreateSerializer(serializers.Serializer):
    """
    Serializer for creating Service PRs.
    
    Example Request Body:
    {
        "date": "2025-12-15",
        "required_date": "2025-12-25",
        "requester_name": "Bob Johnson",
        "requester_department": "Facilities",
        "requester_email": "bob.johnson@company.com",
        "priority": "URGENT",
        "description": "Annual HVAC maintenance service",
        "notes": "Schedule for weekend to minimize disruption",
        "items": [
            {
                "item_name": "HVAC Maintenance Service",
                "item_description": "Complete system inspection and preventive maintenance",
                "quantity": "1",
                "unit_of_measure_id": 2,
                "estimated_unit_price": "15000.00",
                "notes": "Includes parts and labor"
            }
        ]
    }
    """
    
    # PR fields
    date = serializers.DateField()
    required_date = serializers.DateField()
    requester_name = serializers.CharField(max_length=255)
    requester_department = serializers.CharField(max_length=255)
    requester_email = serializers.EmailField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['LOW', 'MEDIUM', 'HIGH', 'URGENT'],
        default='MEDIUM'
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    
    # Nested items (services)
    items = PRItemCreateSerializer(many=True)
    
    def validate_items(self, value):
        """Ensure at least one service item"""
        if not value:
            raise serializers.ValidationError("At least one service item is required")
        return value
    
    def validate(self, attrs):
        """Validate required_date is after date"""
        if attrs['required_date'] < attrs['date']:
            raise serializers.ValidationError(
                "Required date must be on or after the PR date"
            )
        return attrs
    
    def create(self, validated_data):
        """Create Service PR with service items"""
        items_data = validated_data.pop('items')
        
        # Create Service_PR (auto-creates parent PR)
        service_pr = Service_PR.objects.create(
            date=validated_data['date'],
            required_date=validated_data['required_date'],
            requester_name=validated_data['requester_name'],
            requester_department=validated_data['requester_department'],
            requester_email=validated_data.get('requester_email', ''),
            priority=validated_data.get('priority', 'MEDIUM'),
            description=validated_data.get('description', ''),
            notes=validated_data.get('notes', '')
        )
        
        # Create service items
        for item_data in items_data:
            PRItem.objects.create(
                pr=service_pr.pr,
                item_name=item_data['item_name'],
                item_description=item_data.get('item_description', ''),
                catalog_item_id=item_data.get('catalog_item_id'),  # Optional for categorization
                quantity=item_data.get('quantity', 1),  # Default to 1 for services
                unit_of_measure_id=item_data['unit_of_measure_id'],
                estimated_unit_price=item_data.get('estimated_unit_price', 0),
                notes=item_data.get('notes', '')
            )
        
        # Generate PR number
        service_pr.pr.generate_pr_number()
        service_pr.pr._allow_direct_save = True
        service_pr.pr.save()
        
        return service_pr


class ServicePRListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing Service PRs"""
    
    pr_number = serializers.CharField(source='pr.pr_number', read_only=True)
    date = serializers.DateField(source='pr.date', read_only=True)
    required_date = serializers.DateField(source='pr.required_date', read_only=True)
    requester_name = serializers.CharField(source='pr.requester_name', read_only=True)
    requester_department = serializers.CharField(source='pr.requester_department', read_only=True)
    status = serializers.CharField(source='pr.status', read_only=True)
    priority = serializers.CharField(source='pr.priority', read_only=True)
    total = serializers.DecimalField(source='pr.total', max_digits=14, decimal_places=2, read_only=True)
    service_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Service_PR
        fields = [
            'pr_id', 'pr_number', 'date', 'required_date',
            'requester_name', 'requester_department', 'status', 
            'priority', 'total', 'service_count'
        ]
        read_only_fields = fields
    
    def get_service_count(self, obj):
        """Get number of service items"""
        return obj.pr.get_item_count()


class ServicePRDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Service PR with all related data"""
    
    # PR fields
    pr_number = serializers.CharField(source='pr.pr_number', read_only=True)
    date = serializers.DateField(source='pr.date', read_only=True)
    required_date = serializers.DateField(source='pr.required_date', read_only=True)
    requester_name = serializers.CharField(source='pr.requester_name', read_only=True)
    requester_department = serializers.CharField(source='pr.requester_department', read_only=True)
    requester_email = serializers.EmailField(source='pr.requester_email', read_only=True)
    status = serializers.CharField(source='pr.status', read_only=True)
    priority = serializers.CharField(source='pr.priority', read_only=True)
    total = serializers.DecimalField(source='pr.total', max_digits=14, decimal_places=2, read_only=True)
    description = serializers.CharField(source='pr.description', read_only=True)
    notes = serializers.CharField(source='pr.notes', read_only=True)
    
    # Timestamps
    created_at = serializers.DateTimeField(source='pr.created_at', read_only=True)
    updated_at = serializers.DateTimeField(source='pr.updated_at', read_only=True)
    
    # Approval tracking
    submitted_for_approval_at = serializers.DateTimeField(source='pr.submitted_for_approval_at', read_only=True)
    approved_at = serializers.DateTimeField(source='pr.approved_at', read_only=True)
    approved_by = serializers.CharField(source='pr.approved_by', read_only=True)
    rejected_at = serializers.DateTimeField(source='pr.rejected_at', read_only=True)
    rejected_by = serializers.CharField(source='pr.rejected_by', read_only=True)
    rejection_reason = serializers.CharField(source='pr.rejection_reason', read_only=True)
    
    # Nested data
    items = serializers.SerializerMethodField()
    
    class Meta:
        model = Service_PR
        fields = [
            'pr_id', 'pr_number', 'date', 'required_date',
            'requester_name', 'requester_department', 'requester_email',
            'status', 'priority', 'total', 'description', 'notes',
            'created_at', 'updated_at',
            'submitted_for_approval_at', 'approved_at', 'approved_by',
            'rejected_at', 'rejected_by', 'rejection_reason',
            'items'
        ]
        read_only_fields = fields
    
    def get_items(self, obj):
        """Serialize service items"""
        items = obj.pr.items.select_related(
            'catalog_item', 'unit_of_measure'
        ).all()
        return PRItemSerializer(items, many=True).data
