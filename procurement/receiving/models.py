from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

from core.user_accounts.models import CustomUser as User
from Finance.BusinessPartner.models import Supplier
from procurement.po.models import POHeader, POLineItem
from procurement.catalog.models import UnitOfMeasure


class GoodsReceipt(models.Model):
    """
    Goods Receipt Note (GRN) header.
    
    Records receipt of goods from suppliers.
    Supports partial receiving and gift items.
    """
    
    
    
    # GRN Type choices (matches PO types)
    GRN_TYPE_CHOICES = [
        ('Catalog', 'Catalog'),
        ('Non-Catalog', 'Non-Catalog'),
        ('Service', 'Service'),
    ]
    
    # Document identification
    grn_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Auto-generated GRN number"
    )
    
    # Source Purchase Order
    po_header = models.ForeignKey(
        POHeader,
        on_delete=models.PROTECT,
        related_name='goods_receipts',
        help_text="Purchase Order being received"
    )
    
    # Dates
    receipt_date = models.DateField(
        default=timezone.now,
        help_text="Date when goods were received"
    )
    expected_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected delivery date from PO"
    )
    
    # Supplier (from PO)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='goods_receipts',
        help_text="Supplier delivering the goods"
    )
    
    # GRN Type (should match PO type)
    grn_type = models.CharField(
        max_length=20,
        choices=GRN_TYPE_CHOICES,
        help_text="Type of goods receipt (matches PO type)"
    )
    
    # Total amount
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
        help_text="Total amount of goods received (calculated from lines)"
    )
    
    # Receiving personnel
    received_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='received_goods_receipts',
        help_text="Person who received the goods"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="General notes about this receipt"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_goods_receipts'
    )
    
    class Meta:
        ordering = ['-receipt_date', '-grn_number']
        verbose_name = 'Goods Receipt'
        verbose_name_plural = 'Goods Receipts'
        indexes = [
            models.Index(fields=['supplier', 'receipt_date']),
            models.Index(fields=['po_header']),
        ]
    
    def __str__(self):
        return f"{self.grn_number} - PO: {self.po_header.po_number}"
    
    # ==================== HELPER FUNCTIONS ====================
    
    def calculate_total(self):
        """Calculate total amount from all lines."""
        total = sum(line.line_total for line in self.lines.all())
        self.total_amount = total
        return total
    
    def validate_against_po(self):
        """Validate GRN matches PO type and supplier."""
        if self.grn_type != self.po_header.po_type:
            raise ValidationError(
                f"GRN type '{self.grn_type}' must match PO type '{self.po_header.po_type}'"
            )
        
        if self.supplier.business_partner_id != self.po_header.supplier_name_id:
            raise ValidationError("GRN supplier must match PO supplier")
    
    def get_receipt_summary(self):
        """Get summary of items received."""
        lines = self.lines.all()
        return {
            'total_lines': lines.count(),
            'regular_lines': lines.filter(is_gift=False).count(),
            'gift_lines': lines.filter(is_gift=True).count(),
            'total_amount': self.total_amount,
            'total_items_received': sum(line.quantity_received for line in lines)
        }
    
    def get_po_completion_status(self):
        """Check how much of the PO has been received."""
        po_lines = self.po_header.line_items.all()
        total_lines = po_lines.count()
        fully_received = sum(1 for line in po_lines if line.is_fully_received())
        partially_received = sum(1 for line in po_lines if line.quantity_received > 0 and not line.is_fully_received())
        
        return {
            'total_po_lines': total_lines,
            'fully_received_lines': fully_received,
            'partially_received_lines': partially_received,
            'pending_lines': total_lines - fully_received - partially_received,
            'completion_percentage': (fully_received / total_lines * 100) if total_lines > 0 else 0
        }
    
    def has_ap_invoice(self):
        """Check if this goods receipt already has an associated AP Invoice."""
        return self.ap_invoices.exists()
    
    def get_ap_invoices(self):
        """Get all AP Invoices associated with this goods receipt."""
        return self.ap_invoices.all()
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate GRN number and validate."""
        # Generate GRN number if not set
        if not self.grn_number:
            last_grn = GoodsReceipt.objects.order_by('-id').first()
            next_number = 1 if not last_grn else last_grn.id + 1
            self.grn_number = f"GRN-{self.receipt_date.year}-{next_number:05d}"
        
        # Validate against PO if PO exists
        if self.po_header_id:
            self.validate_against_po()
        
        super().save(*args, **kwargs)
        
        # Calculate totals after save (needs lines to exist)
        if self.pk:
            self.calculate_total()
            super().save(update_fields=['total_amount'])


class GoodsReceiptLine(models.Model):
    """
    Goods Receipt line items.
    
    Tracks individual items received, including:
    - Regular PO items (partial or full receipt)
    - Gift items (not in original PO)
    """
    
    # Header reference
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name='lines',
        help_text="Parent Goods Receipt"
    )
    
    # Line ordering
    line_number = models.PositiveIntegerField(
        help_text="Line sequence number"
    )
    
    # Source PO Line (nullable for gifts/extra items)
    po_line_item = models.ForeignKey(
        POLineItem,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='receipts',
        help_text="Source PO line item (null for gifts/extras)"
    )
    
    # Item details (populated from PO or entered manually for gifts)
    item_name = models.CharField(
        max_length=255,
        help_text="Item name"
    )
    item_description = models.TextField(
        blank=True,
        help_text="Item description"
    )
    
    # Quantities for partial receiving
    quantity_ordered = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text="Quantity ordered in PO (0 for gifts)"
    )
    quantity_received = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        help_text="Quantity actually received"
    )
    
    # Unit of Measure
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        help_text="Unit of measure"
    )
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Price per unit (from PO or entered)"
    )
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
        help_text="Line total (quantity_received * unit_price)"
    )
    
    # Gift/Extra item indicator
    is_gift = models.BooleanField(
        default=False,
        help_text="True if this is a gift/bonus item not in the original PO"
    )
    
    # Notes
    line_notes = models.TextField(
        blank=True,
        help_text="Notes about this line item"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['goods_receipt', 'line_number']
        verbose_name = 'Goods Receipt Line'
        verbose_name_plural = 'Goods Receipt Lines'
        unique_together = [('goods_receipt', 'line_number')]
        indexes = [
            models.Index(fields=['goods_receipt', 'line_number']),
            models.Index(fields=['po_line_item']),
        ]
    
    def __str__(self):
        gift_marker = " (GIFT)" if self.is_gift else ""
        return f"{self.goods_receipt.grn_number} - Line {self.line_number}: {self.item_name}{gift_marker}"
    
    # ==================== HELPER FUNCTIONS ====================
    
    def calculate_line_total(self):
        """Calculate line total from quantity and price."""
        self.line_total = self.quantity_received * self.unit_price
        return self.line_total
    
    def populate_from_po_line(self, po_line_item, quantity_to_receive=None):
        """Populate line from PO line item."""
        self.po_line_item = po_line_item
        self.item_name = po_line_item.item_name
        self.item_description = po_line_item.item_description
        self.quantity_ordered = po_line_item.quantity
        self.unit_of_measure = po_line_item.unit_of_measure
        self.unit_price = po_line_item.unit_price
        
        if quantity_to_receive:
            self.quantity_received = quantity_to_receive
        else:
            # Default to remaining quantity
            remaining = po_line_item.get_remaining_quantity()
            self.quantity_received = remaining
        
        self.calculate_line_total()
    
    def validate_quantity(self):
        """Validate received quantity against ordered quantity."""
        if self.is_gift:
            return  # No validation for gifts
        
        if self.quantity_received <= 0:
            raise ValidationError("Quantity received must be greater than 0")
        
        if self.po_line_item:
            remaining = self.po_line_item.get_remaining_quantity()
            if self.quantity_received > remaining:
                raise ValidationError(
                    f"Cannot receive {self.quantity_received} - only {remaining} remaining from PO line"
                )
    
    def get_receipt_percentage(self):
        """Calculate what percentage of ordered quantity was received."""
        if self.quantity_ordered == 0 or self.is_gift:
            return 0
        return (self.quantity_received / self.quantity_ordered) * 100
    
    def is_partial_receipt(self):
        """Check if this is a partial receipt."""
        if self.is_gift:
            return False
        return self.quantity_received < self.quantity_ordered
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate line total and validate."""
        # Validate quantity
        self.validate_quantity()
        
        # Calculate line total
        self.calculate_line_total()
        
        super().save(*args, **kwargs)
        
        # Update PO line item received quantity if linked
        if self.po_line_item and not self.is_gift:
            self.po_line_item.record_receipt(self.quantity_received)
        
        # Update parent GRN totals
        if self.goods_receipt_id:
            self.goods_receipt.calculate_total()
            self.goods_receipt.save(update_fields=['total_amount'])
    

