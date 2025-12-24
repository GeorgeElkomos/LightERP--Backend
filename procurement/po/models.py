from django.db import models
from django.conf import settings
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.utils import timezone
from Finance.core.models import Currency
from Finance.BusinessPartner.models import BusinessPartner
from procurement.PR.models import PR
from core.approval.mixins import ApprovableMixin

"""Purchase Order Header Model."""
class POHeader(ApprovableMixin, models.Model):    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('CONFIRMED', 'Confirmed/Sent to Vendor'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    
    
    # PO Type (must match PR TYPE_CHOICES)
    PO_TYPE_CHOICES = [
        ('Catalog', 'Catalog'),
        ('Non-Catalog', 'Non-Catalog'),
        ('Service', 'Service'),
    ]
    
    # PO Information
    po_number = models.CharField(max_length=50, unique=True, db_index=True)
    po_date = models.DateField(default=date.today)
    po_type = models.CharField(
        max_length=20,
        choices=PO_TYPE_CHOICES,
        default='Catalog',
        help_text="Type of PO: Catalog, Non-Catalog, or Service"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    
    # Source PR Headers - Track multiple PRs that contribute to this PO
    source_pr_headers = models.ManyToManyField(
        PR,
        blank=True,
        related_name='converted_pos',
        help_text="Source PR Headers that contribute to this PO"
    )
    
    # Vendor Information
    supplier_name = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, help_text="Vendor/Supplier")
    # Delivery Information
    receiving_date = models.DateField(null=True, blank=True)
    receiving_address = models.TextField(blank=True)
    receiver_email = models.EmailField(max_length=200, blank=True)
    receiver_contact = models.CharField(max_length=200, blank=True)
    receiver_phone = models.CharField(max_length=50, blank=True)
    
    
    # Financial - Transaction Currency
    # currency = models.ForeignKey(Currency, on_delete=models.PROTECT, help_text="Transaction currency")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Subtotal in transaction currency")
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Tax in transaction currency")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Total in transaction currency")
    
    # Multi-Currency Support
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, help_text="Transaction currency")
    
   # Notes
    description = models.TextField(blank=True)
   
    
    # Workflow
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='purchase_orders_created')
    created_at = models.DateTimeField(auto_now_add=True)
    
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_submitted')
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_confirmed')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_cancelled')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    # Manager - Standard manager (child classes will use ChildModelManagerMixin)
    objects = models.Manager()
    
    class Meta:
        db_table = 'po_header'
        ordering = ['-po_date', '-created_at']
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['status']),
            models.Index(fields=['po_type']),
            models.Index(fields=['supplier_name']),
        ]
        
    def __str__(self):
        return f"{self.po_number} - {self.get_po_type_display()} - {self.get_status_display()}"
    
    # ==================== VALIDATION FUNCTIONS ====================
    
    def validate_pr_types(self):
        """Validate that all source PRs match this PO's type."""
        mismatched_prs = self.source_pr_headers.exclude(type_of_pr=self.po_type)
        if mismatched_prs.exists():
            pr_numbers = ", ".join([pr.pr_number for pr in mismatched_prs])
            raise ValidationError(
                f"PO type '{self.po_type}' does not match PR types for: {pr_numbers}"
            )
    
    # ==================== CALCULATION FUNCTIONS ====================
    
    def calculate_totals(self):
        """Recalculate subtotal, tax, and total from line items."""
        line_items = self.line_items.all()
        self.subtotal = sum(item.line_total for item in line_items)
        # Tax calculation can be customized later
        self.total_amount = self.subtotal + self.tax_amount
        return {
            'subtotal': self.subtotal,
            'tax_amount': self.tax_amount,
            'total_amount': self.total_amount
        }
    
    # ==================== PR-TO-PO CONVERSION FUNCTIONS ====================
    
    def get_available_pr_items(self):
        """Get all available items from linked PRs that match PO type."""
        from procurement.PR.models import PRItem
        
        pr_items = PRItem.objects.filter(
            pr__in=self.source_pr_headers.all(),
            pr__type_of_pr=self.po_type
        ).select_related('pr', 'unit_of_measure')
        
        return pr_items
    
    # ==================== RECEIVING/STATUS FUNCTIONS ====================
    
    def is_fully_received(self):
        """Check if all line items are fully received."""
        line_items = self.line_items.all()
        if not line_items.exists():
            return False
        return all(item.is_fully_received() for item in line_items)
    
    def is_partially_received(self):
        """Check if any line items have been received."""
        return self.line_items.filter(quantity_received__gt=0).exists()
    
    def get_receiving_summary(self):
        """Get summary of received vs ordered quantities."""
        line_items = self.line_items.all()
        total_ordered = sum(item.quantity for item in line_items)
        total_received = sum(item.quantity_received for item in line_items)
        
        return {
            'total_ordered': total_ordered,
            'total_received': total_received,
            'total_pending': total_ordered - total_received,
            'receiving_percentage': (total_received / total_ordered * 100) if total_ordered > 0 else 0
        }
    
    # ==================== WORKFLOW FUNCTIONS ====================
    
    def submit_for_approval(self, submitted_by):
        """Submit PO for approval workflow."""
        if self.status != 'DRAFT':
            raise ValidationError(f"Cannot submit PO with status '{self.status}'. Must be DRAFT.")
        
        # Validate before submission
        self.validate_pr_types()
        
        if not self.line_items.exists():
            raise ValidationError("Cannot submit PO without line items.")
        
        # Update status and timestamps
        self.status = 'SUBMITTED'
        self.submitted_by = submitted_by
        self.submitted_at = timezone.now()
        self.save()
        
        # Start approval workflow (from ApprovableMixin)
        from core.approval.managers import ApprovalManager
        ApprovalManager.start_workflow(self)
    
    def confirm_po(self, confirmed_by):
        """Mark PO as confirmed and sent to vendor."""
        if self.status != 'APPROVED':
            raise ValidationError(f"Cannot confirm PO with status '{self.status}'. Must be APPROVED.")
        
        self.status = 'CONFIRMED'
        self.confirmed_by = confirmed_by
        self.confirmed_at = timezone.now()
        self.save()
    
    def cancel_po(self, reason, cancelled_by):
        """Cancel this PO with reason."""
        if self.status in ['RECEIVED', 'CANCELLED']:
            raise ValidationError(f"Cannot cancel PO with status '{self.status}'.")
        
        self.status = 'CANCELLED'
        self.cancellation_reason = reason
        self.cancelled_by = cancelled_by
        self.cancelled_at = timezone.now()
        self.save()
    
    # ==================== SAVE OVERRIDE ====================
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate totals and update receiving status."""
        # Generate PO number if not set
        if not self.po_number:
            # Simple sequential numbering - customize as needed
            last_po = POHeader.objects.order_by('-id').first()
            next_number = 1 if not last_po else last_po.id + 1
            self.po_number = f"PO-{self.po_date.year}-{next_number:05d}"
        
        # Update receiving status based on line items (only for existing POs)
        if self.pk and self.status not in ['DRAFT', 'SUBMITTED', 'CANCELLED']:
            if self.is_fully_received():
                self.status = 'RECEIVED'
            elif self.is_partially_received():
                self.status = 'PARTIALLY_RECEIVED'
        
        super().save(*args, **kwargs)
    
    # ==================== APPROVABLE INTERFACE METHODS ====================
    
    def on_approval_started(self, instance):
        """Called when approval workflow is started."""
        pass  # Status already set to SUBMITTED in submit_for_approval
    
    def on_stage_approved(self, stage):
        """Called when an approval stage is approved."""
        pass  # Continue workflow
    
    def on_fully_approved(self, instance):
        """Called when all approval stages are approved."""
        self.status = 'APPROVED'
        self.approved_at = timezone.now()
        self.save()
    
    def on_rejected(self, reason, instance):
        """Called when approval is rejected."""
        self.status = 'DRAFT'  # Return to draft for revision
        self.rejected_at = timezone.now()
        self.save()
    
    def on_cancelled(self, reason, instance):
        """Called when approval workflow is cancelled."""
        if self.status != 'CANCELLED':
            self.cancel_po(reason)


"""PO Line Item - Unified model for all PO types."""
class POLineItem(models.Model):
    po_header = models.ForeignKey(
        POHeader,
        on_delete=models.CASCADE,
        related_name='line_items',
        help_text="Parent PO Header"
    )
    line_number = models.PositiveIntegerField(help_text="Line sequence number within PO")
    
    # Line type (must match PO type)
    LINE_TYPE_CHOICES = [
        ('Catalog', 'Catalog'),
        ('Non-Catalog', 'Non-Catalog'),
        ('Service', 'Service'),
    ]
    line_type = models.CharField(
        max_length=20,
        choices=LINE_TYPE_CHOICES,
        help_text="Type of line item (must match PO header type)"
    )
    
    # Quantity and Pricing
    quantity = models.DecimalField(max_digits=15, decimal_places=3, help_text="Ordered quantity")
    from procurement.catalog.models import UnitOfMeasure
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        help_text="Unit of measure"
    )
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, help_text="Price per unit")
    line_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        editable=False,
        help_text="Auto-calculated: quantity × unit_price"
    )
    
    # Item details
    item_name = models.CharField(max_length=255, help_text="Item name")
    item_description = models.TextField(help_text="Detailed item description")
    
    # Source PR Line tracking
    from procurement.PR.models import PRItem
    source_pr_item = models.ForeignKey(
        PRItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_po_lines',
        help_text="Source PR line item"
    )
    
    # PR reference fields (for tracking original PR values)
    quantity_from_pr = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Original quantity from PR"
    )
    price_from_pr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original estimated price from PR"
    )
    
    # Receiving tracking
    quantity_received = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text="Quantity received so far"
    )
    
    # Notes
    line_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'po_line_item'
        ordering = ['po_header', 'line_number']
        unique_together = [['po_header', 'line_number']]
        indexes = [
            models.Index(fields=['po_header', 'line_number']),
        ]
    
    def __str__(self):
        return f"{self.po_header.po_number} - Line {self.line_number}: {self.item_description}"
    
    # ==================== CALCULATION FUNCTIONS ====================
    
    def calculate_line_total(self):
        """Calculate line_total = quantity × unit_price."""
        self.line_total = self.quantity * self.unit_price
        return self.line_total
    
    def get_price_variance(self):
        """Calculate difference between PO price and PR estimated price."""
        if self.price_from_pr is None:
            return None
        return self.unit_price - self.price_from_pr
    
    def get_price_variance_percentage(self):
        """Calculate price variance as percentage."""
        if self.price_from_pr is None or self.price_from_pr == 0:
            return None
        variance = self.get_price_variance()
        return (variance / self.price_from_pr) * 100
    
    # ==================== VALIDATION FUNCTIONS ====================
    
    def validate_line_type(self):
        """Ensure line_type matches po_header.po_type."""
        if self.line_type != self.po_header.po_type:
            raise ValidationError(
                f"Line type '{self.line_type}' does not match PO type '{self.po_header.po_type}'"
            )
    
    def validate_quantity_from_pr(self):
        """Ensure ordered quantity doesn't exceed available PR quantity."""
        if not self.source_pr_item:
            return  # No PR source, skip validation
        
        pr_item = self.source_pr_item
        remaining_qty = pr_item.quantity - pr_item.quantity_converted
        
        # Get quantity already in other PO lines from the same PR item (excluding current line)
        from django.db.models import Sum
        other_po_qty = POLineItem.objects.filter(
            source_pr_item=pr_item
        ).exclude(pk=self.pk).aggregate(
            total=Sum('quantity')
        )['total'] or Decimal('0.000')
        
        available_qty = pr_item.quantity - other_po_qty
        
        if self.quantity > available_qty:
            raise ValidationError(
                f"Quantity {self.quantity} exceeds available quantity {available_qty} "
                f"from PR item (Total: {pr_item.quantity}, Already converted: {other_po_qty})"
            )
    
    # ==================== RECEIVING FUNCTIONS ====================
    
    def get_remaining_quantity(self):
        """Calculate quantity not yet received."""
        return self.quantity - self.quantity_received
    
    def is_fully_received(self):
        """Check if this line is fully received."""
        return self.quantity_received >= self.quantity
    
    def get_receiving_percentage(self):
        """Calculate percentage of quantity received."""
        if self.quantity == 0:
            return 0
        return (self.quantity_received / self.quantity) * 100
    
    def record_receipt(self, quantity_received_now, received_by=None):
        """Record partial or full goods receipt."""
        if quantity_received_now <= 0:
            raise ValidationError("Receipt quantity must be positive.")
        
        remaining = self.get_remaining_quantity()
        if quantity_received_now > remaining:
            raise ValidationError(
                f"Cannot receive {quantity_received_now}. Only {remaining} remaining."
            )
        
        self.quantity_received += quantity_received_now
        self.save()
    
    # ==================== PR-TO-PO CONVERSION FUNCTIONS ====================
    
    def populate_from_pr_item(self, pr_item, quantity_to_convert=None):
        """Auto-fill fields from source PR item."""
        # Set line type to match PR type
        self.line_type = pr_item.pr.type_of_pr
        
        # Copy item details
        self.item_name = pr_item.item_name
        self.item_description = pr_item.item_description
        
        # Copy quantity and pricing
        if quantity_to_convert:
            self.quantity = quantity_to_convert
        else:
            # Use remaining quantity from PR
            self.quantity = pr_item.quantity - pr_item.quantity_converted
        
        self.unit_of_measure = pr_item.unit_of_measure
        self.unit_price = pr_item.estimated_unit_price or Decimal('0.00')
        
        # Store PR reference values
        self.source_pr_item = pr_item
        self.quantity_from_pr = pr_item.quantity
        self.price_from_pr = pr_item.estimated_unit_price
        
        # Calculate line total
        self.calculate_line_total()
    
    # ==================== SAVE OVERRIDE ====================
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate line_total and validate."""
        # Validate line type matches PO type
        self.validate_line_type()
        
        # Validate quantity against PR if source exists
        if self.source_pr_item:
            self.validate_quantity_from_pr()
        
        # Auto-calculate line total
        self.calculate_line_total()
        
        super().save(*args, **kwargs)
        
        # After saving, recalculate PO header totals
        self.po_header.calculate_totals()
        self.po_header.save()
    