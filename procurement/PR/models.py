# """
# Purchase Requisition (PR) Models - Following Invoice Pattern

# This module implements a parent-child pattern similar to Invoice:
# - PR: Parent model (managed base class)
# - Catalog_PR: For items from the catalog
# - NonCatalog_PR: For items not in the catalog
# - Service_PR: For service requests

# All operations should be performed through child classes.
# """

# from django.db import models
# from django.core.exceptions import ValidationError
# from django.utils import timezone
# from Finance.BusinessPartner.models import Supplier
# from Finance.core.base_models import ManagedParentModel, ManagedParentManager, ChildModelManagerMixin, ChildModelMixin
# from core.approval.mixins import ApprovableMixin, ApprovableInterface
# from procurement.catalog.models import catalogItem


# # ==================== PARENT MODEL ====================

# class PR(ApprovableMixin, ApprovableInterface, ManagedParentModel, models.Model):
#     """
#     Purchase Requisition - MANAGED BASE CLASS
    
#     ⚠️ WARNING: Do NOT create, update, or delete PR instances directly!
    
#     This model serves as a shared data container for Catalog_PR, NonCatalog_PR, and Service_PR.
#     All operations should be performed through child classes.
#     """
    
#     # Status choices
#     DRAFT = 'DRAFT'
#     PENDING_APPROVAL = 'PENDING_APPROVAL'
#     APPROVED = 'APPROVED'
#     REJECTED = 'REJECTED'
#     CANCELLED = 'CANCELLED'
#     CONVERTED_TO_PO = 'CONVERTED_TO_PO'
    
#     STATUS_CHOICES = [
#         (DRAFT, 'Draft'),
#         (PENDING_APPROVAL, 'Pending Approval'),
#         (APPROVED, 'Approved'),
#         (REJECTED, 'Rejected'),
#         (CANCELLED, 'Cancelled'),
#         (CONVERTED_TO_PO, 'Converted to PO'),
#     ]
    
#     # Priority choices
#     LOW = 'LOW'
#     MEDIUM = 'MEDIUM'
#     HIGH = 'HIGH'
#     URGENT = 'URGENT'
    
#     PRIORITY_CHOICES = [
#         (LOW, 'Low'),
#         (MEDIUM, 'Medium'),
#         (HIGH, 'High'),
#         (URGENT, 'Urgent'),
#     ]
#     type =[
#         ('Catalog','Catalog'),
#         ('Non-Catalog','Non-Catalog'),
#         ('Service','Service'),
#     ]
#     # prefix_code = models.CharField(max_length=10, blank=True, null=True)
#     type_of_pr = models.CharField(
#         max_length=20,
#         choices=type,
#         default='Catalog'
#     )
#     # Core fields
#     pr_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
#     date = models.DateField()
#     required_date = models.DateField(help_text="Date when items/services are needed")

    
#     # Requester information
#     requester_name = models.CharField(max_length=255)
#     requester_department = models.CharField(max_length=255)
#     requester_email = models.EmailField(blank=True, null=True)
    
#     # Status and priority
#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default=DRAFT
#     )
#     priority = models.CharField(
#         max_length=20,
#         choices=PRIORITY_CHOICES,
#         default=MEDIUM
#     )
    
#     # Financial fields
#     total = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#     )
    
#     # Approval tracking
#     submitted_for_approval_at = models.DateTimeField(null=True, blank=True)
#     approved_at = models.DateTimeField(null=True, blank=True)
#     rejected_at = models.DateTimeField(null=True, blank=True)
#     rejection_reason = models.TextField(blank=True, default='')
    
#     # Additional fields
#     description = models.TextField(blank=True, help_text="Overall PR description")
#     notes = models.TextField(blank=True, help_text="Internal notes")
    
#     # Timestamps
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     # Custom manager
#     objects = ManagedParentManager()
    
#     class Meta:
#         db_table = 'pr'
#         verbose_name = 'Purchase Requisition'
#         verbose_name_plural = 'Purchase Requisitions'
#         ordering = ['-date']
    
#     def __str__(self):
#         return f"PR {self.pr_number or self.id} - {self.date}"
    
#     # ==================== HELPER METHODS ====================
    
#     def generate_pr_number(self):
#         """Generate unique PR number based on prefix and sequence."""
#         if not self.pr_number:
#             prefix = self.prefix_code or 'PR'
#             # Get last PR number for this prefix
#             last_pr = PR.objects.filter(
#                 pr_number__startswith=prefix
#             ).order_by('-pr_number').first()
            
#             if last_pr and last_pr.pr_number:
#                 try:
#                     last_num = int(last_pr.pr_number.split('-')[-1])
#                     new_num = last_num + 1
#                 except (ValueError, IndexError):
#                     new_num = 1
#             else:
#                 new_num = 1
            
#             self.pr_number = f"{prefix}-{new_num:06d}"
    
#     def is_approved(self):
#         """Check if PR is approved."""
#         return self.status == self.APPROVED
    
#     def is_rejected(self):
#         """Check if PR is rejected."""
#         return self.status == self.REJECTED
    
#     def is_cancelled(self):
#         """Check if PR is cancelled."""
#         return self.status == self.CANCELLED
    
#     def can_be_edited(self):
#         """Check if PR can be edited (only in DRAFT or REJECTED status)."""
#         return self.status in [self.DRAFT, self.REJECTED]
    
#     def can_be_approved(self):
#         """Check if PR can be approved (only in PENDING_APPROVAL status)."""
#         return self.status == self.PENDING_APPROVAL
    
#     def can_be_cancelled(self):
#         """Check if PR can be cancelled (not already cancelled or converted to PO)."""
#         return self.status not in [self.CANCELLED, self.CONVERTED_TO_PO]
    
#     def mark_as_converted_to_po(self):
#         """Mark PR as converted to Purchase Order."""
#         if self.status != self.APPROVED:
#             raise ValidationError("Only approved PRs can be converted to PO")
        
#         self.status = self.CONVERTED_TO_PO
#         self._allow_direct_save = True
#         self.save()
    
#     def cancel(self, reason=None):
#         """Cancel the PR."""
#         if not self.can_be_cancelled():
#             raise ValidationError(f"Cannot cancel PR in {self.status} status")
        
#         self.status = self.CANCELLED
#         if reason:
#             self.notes = f"{self.notes}\n\nCancellation Reason: {reason}" if self.notes else f"Cancellation Reason: {reason}"
        
#         self._allow_direct_save = True
#         self.save()
    
    
    
#     def is_urgent(self):
#         """Check if PR is marked as urgent."""
#         return self.priority == self.URGENT
    
#     def days_until_required(self):
#         """Calculate days until required date."""
#         from datetime import date
#         if self.required_date:
#             delta = self.required_date - date.today()
#             return delta.days
#         return None


# # ==================== CATALOG PR MODEL ====================

# class Catalog_PRManager(ChildModelManagerMixin, models.Manager):
#     """Manager for Catalog_PR - items from catalog."""
#     parent_model = PR
#     parent_defaults = {
#         'status': 'DRAFT',
#         'prefix_code': 'PR-CAT'
#     }


# class Catalog_PR(ChildModelMixin, models.Model):
   
#     # Configuration for generic pattern
#     parent_model = PR
#     parent_field_name = 'pr'
    
#     pr = models.OneToOneField(
#         PR,
#         on_delete=models.CASCADE,
#         primary_key=True,
#         related_name="catalog_pr"
#     )
#     # Custom manager
#     objects = Catalog_PRManager()
    
#     class Meta:
#         db_table = 'catalog_pr'
#         verbose_name = 'Catalog PR'
#         verbose_name_plural = 'Catalog PRs'
    
#     def __str__(self):
#         return f"Catalog PR: {self.catalog_item.name} - Qty: {self.quantity}"
    
#     def save(self, *args, **kwargs):
#         """Auto-set unit price from catalog item if not provided."""
#         if not self.unit_price and self.catalog_item:
#             self.unit_price = self.catalog_item.price
#         super().save(*args, **kwargs)
    
#     def calculate_line_total(self):
#         """Calculate total for this line item."""
#         if self.unit_price and self.quantity:
#             return self.unit_price * self.quantity
#         return 0
    
#     # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    
#     def on_approval_started_child(self, workflow_instance):
#         """Catalog PR specific logic when approval starts."""
#         pass
    
#     def on_fully_approved_child(self, workflow_instance):
#         """Catalog PR specific logic when fully approved."""
#         # Example: Check catalog item availability
#         pass
    
#     def on_rejected_child(self, workflow_instance, stage_instance=None):
#         """Catalog PR specific logic when rejected."""
#         pass
    
#     # ==================== APPROVAL CONVENIENCE METHODS ====================
    
#     def submit_for_approval(self):
#         """Submit catalog PR for approval."""
#         return self.pr.submit_for_approval()


# # ==================== NON-CATALOG PR MODEL ====================

# class NonCatalog_PRManager(ChildModelManagerMixin, models.Manager):
#     """Manager for NonCatalog_PR - items not in catalog."""
#     parent_model = PR
#     parent_defaults = {
#         'status': 'DRAFT',
#         'prefix_code': 'PR-NC'
#     }


# class NonCatalog_PR(ChildModelMixin, models.Model):
#     """
#     Non-Catalog Purchase Requisition - for items not in the catalog.
    
#     ALL PR fields are automatically available as properties!
    
#     Usage:
#         # Create or get non-catalog item
#         item = NonCatalogItem.objects.create(
#             item_name="Custom Equipment",
#             item_description="Special equipment not in catalog"
#         )
        
#         # Create PR with the item
#         noncatalog_pr = NonCatalog_PR.objects.create(
#             date=date.today(),
#             required_date=required_date,
#             requester_name="John Doe",
#             requester_department="IT",
#             noncatalog_item=item,
#             quantity=5,
#             estimated_unit_price=500.00
#         )
#     """
    
#     # Configuration for generic pattern
#     parent_model = PR
#     parent_field_name = 'pr'
    
#     pr = models.OneToOneField(
#         PR,
#         on_delete=models.CASCADE,
#         primary_key=True,
#         related_name="noncatalog_pr"
#     )
    
#     # Non-catalog specific fields
   
#     quantity = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         help_text="Quantity requested"
#     )
#     estimated_unit_price = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Estimated price per unit"
#     )
#     suggested_supplier = models.ForeignKey(
#         Supplier,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         related_name="noncatalog_prs",
#         help_text="Suggested supplier for this item"
#     )
#     justification = models.TextField(
#         blank=True,
#         help_text="Justification for non-catalog purchase"
#     )
    
#     # Custom manager
#     objects = NonCatalog_PRManager()
    
#     class Meta:
#         db_table = 'noncatalog_pr'
#         verbose_name = 'Non-Catalog PR'
#         verbose_name_plural = 'Non-Catalog PRs'
    
#     def __str__(self):
#         return f"Non-Catalog PR: {self.noncatalog_item.item_name} - Qty: {self.quantity}"
    
#     def calculate_line_total(self):
#         """Calculate estimated total for this line item."""
#         if self.estimated_unit_price and self.quantity:
#             return self.estimated_unit_price * self.quantity
#         return 0
    
#     def requires_justification(self):
#         """Check if justification is required (for high-value items)."""
#         total = self.calculate_line_total()
#         return total > 10000  # Example threshold
    
#     # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    
#     def on_approval_started_child(self, workflow_instance):
#         """Non-catalog PR specific logic when approval starts."""
#         pass
    
#     def on_fully_approved_child(self, workflow_instance):
#         """Non-catalog PR specific logic when fully approved."""
#         # Example: Add to catalog if approved
#         pass
    
#     def on_rejected_child(self, workflow_instance, stage_instance=None):
#         """Non-catalog PR specific logic when rejected."""
#         pass
    
#     # ==================== APPROVAL CONVENIENCE METHODS ====================
    
#     def submit_for_approval(self):
#         """Submit non-catalog PR for approval."""
#         return self.pr.submit_for_approval()




# # ==================== SERVICE PR MODEL ====================

# class Service_PRManager(ChildModelManagerMixin, models.Manager):
#     """Manager for Service_PR - service requests."""
#     parent_model = PR
#     parent_defaults = {
#         'status': 'DRAFT',
#         'prefix_code': 'PR-SRV'
#     }


# class Service_PR(ChildModelMixin, models.Model):
    
#     # Configuration for generic pattern
#     parent_model = PR
#     parent_field_name = 'pr'
#     service_name = models.CharField(max_length=255,default="")
#     service_description = models.TextField(max_length=1000,default="")
#     pr = models.OneToOneField(
#         PR,
#         on_delete=models.CASCADE,
#         primary_key=True,
#         related_name="service_pr"
#     )
    
    
#     # Custom manager
#     objects = Service_PRManager()
    
#     class Meta:
#         db_table = 'service_pr'
#         verbose_name = 'Service PR'
#         verbose_name_plural = 'Service PRs'
    
#     def __str__(self):
#         return f"Service PR: {self.service_item.service_name}"
    
#     def get_estimated_total(self):
#         """Get estimated total cost."""
#         return self.estimated_cost or 0
    
#     def is_high_value_service(self, threshold=50000):
#         """Check if service exceeds threshold (may require special approval)."""
#         return self.estimated_cost and self.estimated_cost > threshold
    
#     # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    
#     def on_approval_started_child(self, workflow_instance):
#         """Service PR specific logic when approval starts."""
#         pass
    
#     def on_fully_approved_child(self, workflow_instance):
#         """Service PR specific logic when fully approved."""
#         # Example: Initiate contract if required
#         if self.requires_contract:
#             pass  # Trigger contract creation workflow
    
#     def on_rejected_child(self, workflow_instance, stage_instance=None):
#         """Service PR specific logic when rejected."""
#         pass
    
#     # ==================== APPROVAL CONVENIENCE METHODS ====================
    
#     def submit_for_approval(self):
#         """Submit service PR for approval."""
#         return self.pr.submit_for_approval()


# class items(models.Model):
#     pr = models.ForeignKey(
#         PR,
#         on_delete=models.CASCADE,
#         related_name="items"
#     )
#     item_name = models.CharField(max_length=255,null=True,blank=True)
#     item_description = models.TextField(null=True,blank=True)
#     unit_of_measure = models.ForeignKey(
#         'catalog.UnitOfMeasure',
#         on_delete=models.PROTECT,
#         default="EA",
#         help_text="Unit of measure (EA, KG, M, etc.)"
#     )
#     quantity = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         default=0,
#         help_text="Item amount"
#     )
#     catorgry = models.ForeignKey(
#         'catalog.CatalogItem',
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         help_text="Item category for classification"
#     )
#     estimated_price = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         default=0,
#         help_text="Estimated price per unit"
#     )
#     total_price_per_item = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         default=0,
#         help_text="Total price for this item (estimated_price * quantity)"
#     )
#     class Meta:
#         verbose_name = 'PR Item'
#         verbose_name_plural = 'PR Items'
#     def __str__(self):
#         return f"{self.item_name} - Qty: {self.quantity}"


"""
Purchase Requisition (PR) Models - Following Invoice Pattern

This module implements a parent-child pattern similar to Invoice:
- PR: Parent model (managed base class)
- Catalog_PR: For items from the catalog
- NonCatalog_PR: For items not in the catalog
- Service_PR: For service requests

All operations should be performed through child classes.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from Finance.BusinessPartner.models import Supplier
from Finance.core.base_models import ManagedParentModel, ManagedParentManager, ChildModelManagerMixin, ChildModelMixin
from core.approval.mixins import ApprovableMixin, ApprovableInterface
from procurement.catalog.models import catalogItem, UnitOfMeasure


# ==================== PARENT MODEL ====================

class PR(ApprovableMixin, ApprovableInterface, ManagedParentModel, models.Model):
    """
    Purchase Requisition - MANAGED BASE CLASS
    
    ⚠️ WARNING: Do NOT create, update, or delete PR instances directly!
    
    This model serves as a shared data container for Catalog_PR, NonCatalog_PR, and Service_PR.
    All operations should be performed through child classes.
    """
    
    # Status choices
    DRAFT = 'DRAFT'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    CANCELLED = 'CANCELLED'
    CONVERTED_TO_PO = 'CONVERTED_TO_PO'
    
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (CANCELLED, 'Cancelled'),
        (CONVERTED_TO_PO, 'Converted to PO'),
    ]
    
    # Priority choices
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    URGENT = 'URGENT'
    
    PRIORITY_CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (URGENT, 'Urgent'),
    ]
    
    # PR Type choices
    TYPE_CHOICES = [
        ('Catalog', 'Catalog'),
        ('Non-Catalog', 'Non-Catalog'),
        ('Service', 'Service'),
    ]
    
    # Core fields
    type_of_pr = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='Catalog',
        help_text="Type of purchase requisition"
    )
    pr_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    date = models.DateField()
    required_date = models.DateField(help_text="Date when items/services are needed")
    
    # Requester information
    requester_name = models.CharField(max_length=255)
    requester_department = models.CharField(max_length=255)
    requester_email = models.EmailField(blank=True, null=True)
    
    # Status and priority
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=MEDIUM
    )
    
    # Financial fields
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Sum of all line items before tax"
    )
    
    # Approval tracking
    submitted_for_approval_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=255, blank=True, help_text="Name of approver")
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.CharField(max_length=255, blank=True, help_text="Name of rejector")
    rejection_reason = models.TextField(blank=True, default='')
    
    # Additional fields
    description = models.TextField(blank=True, help_text="Overall PR description")
    notes = models.TextField(blank=True, help_text="Internal notes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Budget Control Integration
    segment_combination = models.ForeignKey(
        'finance_gl.XX_Segment_combination',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_requisitions',
        help_text="GL account coding for budget control - applies to ALL line items in this PR"
    )
    budget_check_status = models.CharField(
        max_length=20,
        choices=[
            ('NOT_CHECKED', 'Not Checked'),
            ('PASSED', 'Passed'),
            ('WARNING', 'Warning'),
            ('FAILED', 'Failed')
        ],
        default='NOT_CHECKED',
        help_text="Budget check result"
    )
    budget_check_message = models.TextField(
        blank=True,
        help_text="Budget check details or warnings"
    )
    budget_committed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when budget commitment was created"
    )
    
    # Custom manager
    objects = ManagedParentManager()
    
    class Meta:
        db_table = 'pr'
        verbose_name = 'Purchase Requisition'
        verbose_name_plural = 'Purchase Requisitions'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"PR {self.pr_number or self.id} - {self.requester_name} ({self.date})"
    
    # ==================== HELPER METHODS ====================
    
    def generate_pr_number(self):
        """Generate unique PR number based on type and sequence."""
        if not self.pr_number:
            # Determine prefix based on type
            prefix_map = {
                'Catalog': 'PR-CAT',
                'Non-Catalog': 'PR-NC',
                'Service': 'PR-SRV',
            }
            prefix = prefix_map.get(self.type_of_pr, 'PR')
            
            # Get last PR number for this prefix
            last_pr = PR.objects.filter(
                pr_number__startswith=prefix
            ).order_by('-pr_number').first()
            
            if last_pr and last_pr.pr_number:
                try:
                    # Extract number part (e.g., "PR-CAT-000001" -> 1)
                    last_num = int(last_pr.pr_number.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.pr_number = f"{prefix}-{new_num:06d}"
    
    def calculate_totals(self):
        """Calculate subtotal, tax, and total from line items."""
        items = self.items.all()
        
        if items.exists():
            self.total = sum(
                item.total_price_per_item or Decimal('0') 
                for item in items
            )
        else:
            self.total = Decimal('0')
            
        
        # Allow direct save for calculation
        self._allow_direct_save = True
        self.save(update_fields=['total', 'updated_at'])
    
    def is_approved(self):
        """Check if PR is approved."""
        return self.status == self.APPROVED
    
    def is_rejected(self):
        """Check if PR is rejected."""
        return self.status == self.REJECTED
    
    def is_cancelled(self):
        """Check if PR is cancelled."""
        return self.status == self.CANCELLED
    
    def can_be_edited(self):
        """Check if PR can be edited (only in DRAFT or REJECTED status)."""
        return self.status in [self.DRAFT, self.REJECTED]
    
    def can_be_approved(self):
        """Check if PR can be approved (only in PENDING_APPROVAL status)."""
        return self.status == self.PENDING_APPROVAL
    
    def can_be_edited(self):
        """Check if PR can be edited (only DRAFT or REJECTED PRs)."""
        return self.status in [self.DRAFT, self.REJECTED]
    
    def can_be_cancelled(self):
        """Check if PR can be cancelled (not already cancelled or converted to PO)."""
        return self.status not in [self.CANCELLED, self.CONVERTED_TO_PO]
    
    def mark_as_converted_to_po(self):
        """
        Mark PR as converted to Purchase Order.
        Only marks as CONVERTED_TO_PO if ALL line items are converted.
        Otherwise, keeps status as APPROVED but tracks conversion at line level.
        """
        if self.status != self.APPROVED:
            raise ValidationError("Only approved PRs can be converted to PO")
        
        # Check if all line items are converted
        total_items = self.items.count()
        converted_items = self.items.filter(converted_to_po=True).count()
        
        if total_items == 0:
            raise ValidationError("Cannot convert PR with no line items")
        
        if converted_items == total_items:
            # All items converted - mark PR as fully converted
            self.status = self.CONVERTED_TO_PO
            self._allow_direct_save = True
            self.save(update_fields=['status', 'updated_at'])
        # If only some items converted, keep status as APPROVED
        # The converted_to_po field on each line item tracks conversion
    
    @property
    def conversion_progress(self):
        """Get conversion progress as percentage."""
        total = self.items.count()
        if total == 0:
            return 0
        converted = self.items.filter(converted_to_po=True).count()
        return (converted / total) * 100
    
    @property
    def is_partially_converted(self):
        """Check if PR has some (but not all) items converted."""
        if self.status == self.CONVERTED_TO_PO:
            return False
        total = self.items.count()
        if total == 0:
            return False
        converted = self.items.filter(converted_to_po=True).count()
        return 0 < converted < total
    
    @property
    def unconverted_items(self):
        """Get PR items that haven't been converted yet."""
        return self.items.filter(converted_to_po=False)
    
    def cancel(self, reason=None):
        """Cancel the PR - includes budget release."""
        if not self.can_be_cancelled():
            raise ValidationError(f"Cannot cancel PR in {self.status} status")
        
        # Release budget commitment if it was created
        self._release_budget_commitment()
        
        self.status = self.CANCELLED
        if reason:
            self.notes = (
                f"{self.notes}\n\nCancellation Reason: {reason}" 
                if self.notes else f"Cancellation Reason: {reason}"
            )
        
        self._allow_direct_save = True
        self.save()
    
    def is_urgent(self):
        """Check if PR is marked as urgent."""
        return self.priority == self.URGENT
    
    def days_until_required(self):
        """Calculate days until required date."""
        from datetime import date
        if self.required_date:
            delta = self.required_date - date.today()
            return delta.days
        return None
    
    def is_overdue(self):
        """Check if required date has passed."""
        from datetime import date
        return self.required_date and self.required_date < date.today()
    
    def get_item_count(self):
        """Get total number of line items."""
        return self.items.count()
    
    def get_total_quantity(self):
        """Get sum of all item quantities."""
        return sum(item.quantity or Decimal('0') for item in self.items.all())
    
    # ==================== BUDGET CONTROL METHODS ====================
    
    def _check_and_consume_budget(self):
        """
        Stage 1: Check budget and consume commitment when PR is approved.
        Called automatically during PR approval workflow.
        """
        from Finance.budget_control.models import BudgetHeader
        from Finance.GL.models import XX_Segment
        from django.core.exceptions import ValidationError
        
        # Skip if no segment combination assigned
        if not self.segment_combination:
            self.budget_check_status = 'NOT_CHECKED'
            self.budget_check_message = 'No GL account assigned - budget control skipped'
            self._allow_direct_save = True
            self.save(update_fields=['budget_check_status', 'budget_check_message'])
            return
        
        # Find active or closed budget for PR date (closed budgets can still be checked)
        budget = BudgetHeader.objects.filter(
            status__in=['ACTIVE', 'CLOSED'],
            is_active=True,
            start_date__lte=self.date,
            end_date__gte=self.date
        ).first()
        
        if not budget:
            self.budget_check_status = 'NOT_CHECKED'
            self.budget_check_message = 'No active budget found for this period'
            self._allow_direct_save = True
            self.save(update_fields=['budget_check_status', 'budget_check_message'])
            return
        
        # Extract segments from combination
        segment_ids = list(
            self.segment_combination.details.values_list('segment_id', flat=True)
        )
        segment_objects = list(XX_Segment.objects.filter(id__in=segment_ids))
        
        if not segment_objects:
            self.budget_check_status = 'NOT_CHECKED'
            self.budget_check_message = 'No segments found in combination'
            self._allow_direct_save = True
            self.save(update_fields=['budget_check_status', 'budget_check_message'])
            return
        
        # Check budget availability
        check_result = budget.check_budget_for_segments(
            segment_list=segment_objects,
            transaction_amount=self.total,
            transaction_date=self.date
        )
        
        # Handle based on control level
        if not check_result['allowed']:
            if check_result['control_level'] == 'ABSOLUTE':
                self.budget_check_status = 'FAILED'
                self.budget_check_message = check_result['message']
                
                # Save before raising exception
                self._allow_direct_save = True
                self.save(update_fields=['budget_check_status', 'budget_check_message'])
                
                # Format violations for error message
                violations_detail = []
                for v in check_result['violations']:
                    violations_detail.append(
                        f"- {v['segment_type']}: {v['segment']} "
                        f"(Available: {v['available']}, Requested: {v['requested']}, "
                        f"Short: {v['shortage']})"
                    )
                
                raise ValidationError(
                    f"Budget exceeded - PR cannot be approved:\n"
                    f"{check_result['message']}\n\n"
                    f"Violations:\n" + "\n".join(violations_detail)
                )
            elif check_result['control_level'] == 'ADVISORY':
                self.budget_check_status = 'WARNING'
                self.budget_check_message = f"WARNING: {check_result['message']}"
                self._allow_direct_save = True
                self.save(update_fields=['budget_check_status', 'budget_check_message'])
        else:
            self.budget_check_status = 'PASSED'
            self.budget_check_message = check_result['message']
        
        # Consume budget commitment
        budget_amounts = budget.get_applicable_budget_amounts(segment_objects)
        
        if not budget_amounts.exists():
            self.budget_check_status = 'NOT_CHECKED'
            self.budget_check_message = 'No budget amounts found for these segments'
            self._allow_direct_save = True
            self.save(update_fields=['budget_check_status', 'budget_check_message'])
            return
        
        for budget_amt in budget_amounts:
            budget_amt.consume_commitment(
                amount=self.total,
                transaction_ref=f"PR-{self.pr_number}"
            )
        
        self.budget_committed_at = timezone.now()
        self._allow_direct_save = True
        self.save(update_fields=['budget_check_status', 'budget_check_message', 'budget_committed_at'])
    
    def _release_budget_commitment(self):
        """
        Release budget commitment when PR is rejected or cancelled.
        This frees up the budget for other transactions.
        """
        from Finance.budget_control.models import BudgetHeader
        from Finance.GL.models import XX_Segment
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Only release if budget was previously committed
        if not self.budget_committed_at or not self.segment_combination:
            return
        
        # Find the budget that was used
        budget = BudgetHeader.objects.filter(
            status__in=['ACTIVE', 'CLOSED'],
            start_date__lte=self.date,
            end_date__gte=self.date
        ).first()
        
        if not budget:
            logger.warning(f"No budget found to release commitment for PR {self.pr_number}")
            return
        
        # Extract segments
        segment_ids = list(
            self.segment_combination.details.values_list('segment_id', flat=True)
        )
        segment_objects = list(XX_Segment.objects.filter(id__in=segment_ids))
        
        if not segment_objects:
            logger.warning(f"No segments found for PR {self.pr_number} commitment release")
            return
        
        # Release commitment
        budget_amounts = budget.get_applicable_budget_amounts(segment_objects)
        for budget_amt in budget_amounts:
            try:
                budget_amt.release_commitment(amount=self.total)
                logger.info(f"Released commitment of {self.total} for PR {self.pr_number}")
            except Exception as e:
                logger.error(f"Failed to release commitment for PR {self.pr_number}: {str(e)}")
        
        # Clear commitment tracking
        self.budget_committed_at = None
        self.budget_check_status = 'NOT_CHECKED'
        self.budget_check_message = 'Budget commitment released due to PR cancellation/rejection'
    
    # ==================== APPROVAL WORKFLOW INTERFACE METHODS ====================
    
    def on_approval_started(self, workflow_instance):
        """Called when approval workflow starts."""
        self.status = self.PENDING_APPROVAL
        self.submitted_for_approval_at = timezone.now()
        self._allow_direct_save = True
        self.save(update_fields=['status', 'submitted_for_approval_at', 'updated_at'])
        
        # Delegate to child-specific logic if exists
        child = self._get_child_instance()
        if child and hasattr(child, 'on_approval_started_child'):
            child.on_approval_started_child(workflow_instance)
    
    def on_stage_approved(self, stage_instance):
        """Called when a stage is approved."""
        # Delegate to child-specific logic if exists
        child = self._get_child_instance()
        if child and hasattr(child, 'on_stage_approved_child'):
            child.on_stage_approved_child(stage_instance)
    
    def on_fully_approved(self, workflow_instance):
        """Called when all stages are approved - includes budget consumption."""
        
        # Budget integration - check and consume before marking approved
        try:
            self._check_and_consume_budget()
        except Exception as e:
            # Rollback approval if budget check fails
            self.status = self.PENDING_APPROVAL
            self.approved_at = None
            self._allow_direct_save = True
            self.save(update_fields=['status', 'approved_at', 'budget_check_status',
                                    'budget_check_message', 'updated_at'])
            raise
        
        # Mark as approved
        self.status = self.APPROVED
        self.approved_at = timezone.now()
        self._allow_direct_save = True
        self.save(update_fields=['status', 'approved_at', 'budget_check_status',
                                'budget_check_message', 'budget_committed_at', 'updated_at'])
        
        # Delegate to child-specific logic
        child = self._get_child_instance()
        if child and hasattr(child, 'on_fully_approved_child'):
            child.on_fully_approved_child(workflow_instance)
    
    def on_rejected(self, workflow_instance, stage_instance=None):
        """Called when workflow is rejected - releases budget commitment."""
        
        # Release budget commitment if it was created
        self._release_budget_commitment()
        
        self.status = self.REJECTED
        self.rejected_at = timezone.now()
        self._allow_direct_save = True
        self.save(update_fields=['status', 'rejected_at', 'budget_check_status',
                                'budget_check_message', 'budget_committed_at', 'updated_at'])
        
        # Delegate to child-specific logic
        child = self._get_child_instance()
        if child and hasattr(child, 'on_rejected_child'):
            child.on_rejected_child(workflow_instance, stage_instance)
    
    def on_cancelled(self, workflow_instance, reason=None):
        """Called when workflow is cancelled."""
        self.cancel(reason)
        
        # Delegate to child-specific logic
        child = self._get_child_instance()
        if child and hasattr(child, 'on_cancelled_child'):
            child.on_cancelled_child(workflow_instance, reason)
    
    def _get_child_instance(self):
        """Get the specific child instance (Catalog_PR, NonCatalog_PR, or Service_PR)."""
        if hasattr(self, 'catalog_pr'):
            return self.catalog_pr
        elif hasattr(self, 'noncatalog_pr'):
            return self.noncatalog_pr
        elif hasattr(self, 'service_pr'):
            return self.service_pr
        return None


# ==================== PR ITEMS MODEL ====================

class PRItem(models.Model):
    """
    Line items for Purchase Requisitions.
    
    This model handles items for ALL PR types:
    - Catalog PRs: Links to catalogItem
    - Non-Catalog PRs: Custom item details
    - Service PRs: Service details
    """
    
    pr = models.ForeignKey(
        PR,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Parent PR"
    )
    
    # Line number for ordering
    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line item sequence number"
    )
    
    # Item details
    item_name = models.CharField(
        max_length=255,
        help_text="Item/Service name"
    )
    item_description = models.TextField(
        blank=True,
        help_text="Detailed description"
    )
    
    # For catalog items (optional) - also serves as category
    catalog_item = models.ForeignKey(
        catalogItem,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pr_items",
        help_text="Link to catalog item (for Catalog PRs or as category reference)"
    )
    
    # Quantity and UoM
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=1,
        help_text="Item quantity"
    )
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Unit of measure (EA, KG, M, L, etc.)"
    )
    
    # Pricing
    estimated_unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Estimated price per unit"
    )
    total_price_per_item = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        editable=False,
        help_text="Auto-calculated: estimated_unit_price * quantity"
    )
    
    
    notes = models.TextField(blank=True, help_text="Item-specific notes")
    
    # Conversion tracking - Added for PO conversion
    converted_to_po = models.BooleanField(
        default=False,
        help_text="Whether this line has been fully converted to a PO"
    )
    quantity_converted = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Total quantity converted to POs"
    )
    conversion_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this line was converted to PO"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pr_item'
        verbose_name = 'PR Item'
        verbose_name_plural = 'PR Items'
        ordering = ['pr', 'line_number']
        unique_together = [['pr', 'line_number']]
    
    def __str__(self):
        uom_display = f" {self.unit_of_measure.code}" if self.unit_of_measure else ""
        return f"{self.item_name} - Qty: {self.quantity}{uom_display}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate total price and populate from catalog if applicable."""
        # Calculate total price
        self.total_price_per_item = self.quantity * self.estimated_unit_price
        
        # Auto-populate from catalog item if linked
        if self.catalog_item:
            if not self.item_name:
                self.item_name = self.catalog_item.name
            if not self.item_description:
                self.item_description = self.catalog_item.description
            # Auto-set price from catalog if not provided and catalog has price
            if not self.estimated_unit_price and hasattr(self.catalog_item, 'price'):
                self.estimated_unit_price = self.catalog_item.price
        
        # Auto-assign line number if not set
        if not self.line_number or self.line_number == 1:
            max_line = PRItem.objects.filter(pr=self.pr).aggregate(
                models.Max('line_number')
            )['line_number__max']
            self.line_number = (max_line or 0) + 1
        
        super().save(*args, **kwargs)
        
        # Recalculate PR totals after saving item
        if self.pr:
            self.pr.calculate_totals()
    
    def delete(self, *args, **kwargs):
        """Recalculate PR totals after deleting item."""
        pr = self.pr
        super().delete(*args, **kwargs)
        if pr:
            pr.calculate_totals()
    
    def clean(self):
        """Validate item data."""
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")
        
        if self.estimated_unit_price < 0:
            raise ValidationError("Price cannot be negative")
        
        # For catalog PRs, catalog_item should be set
        if self.pr and self.pr.type_of_pr == 'Catalog' and not self.catalog_item:
            raise ValidationError("Catalog item is required for Catalog PRs")
    
    def get_formatted_unit_price(self):
        """Return formatted unit price."""
        return f"${self.estimated_unit_price:,.2f}"
    
    def get_formatted_total(self):
        """Return formatted total price."""
        return f"${self.total_price_per_item:,.2f}"
    
    def get_category(self):
        """Get category from catalog item if available."""
        if self.catalog_item:
            return self.catalog_item
        return None
    
    def mark_as_converted(self, po_line_item=None):
        """Mark this PR line as converted to PO."""
        from django.utils import timezone
        self.converted_to_po = True
        self.conversion_date = timezone.now()
        self.save(update_fields=['converted_to_po', 'conversion_date', 'updated_at'])
    
    @property
    def can_be_converted(self):
        """Check if this line can be converted to PO."""
        return (
            self.pr.status == 'APPROVED' and 
            not self.converted_to_po
        )


# ==================== CATALOG PR MODEL ====================

class Catalog_PRManager(ChildModelManagerMixin, models.Manager):
    """Manager for Catalog_PR - items from catalog."""
    parent_model = PR
    parent_defaults = {
        'status': 'DRAFT',
        'type_of_pr': 'Catalog'
    }


class Catalog_PR(ChildModelMixin, models.Model):
    """
    Catalog Purchase Requisition - for items from the catalog.
    
    ALL PR fields are automatically available as properties!
    
    Usage:
        catalog_pr = Catalog_PR.objects.create(
            date=date.today(),
            required_date=required_date,
            requester_name="John Doe",
            requester_department="IT"
        )
        
        # Add items
        catalog_pr.add_catalog_item(
            catalog_item=my_catalog_item,
            quantity=5,
            unit_of_measure=uom_ea
        )
    """
    
    # Configuration for generic pattern
    parent_model = PR
    parent_field_name = 'pr'
    
    pr = models.OneToOneField(
        PR,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="catalog_pr"
    )
    
    # Custom manager
    objects = Catalog_PRManager()
    
    class Meta:
        db_table = 'catalog_pr'
        verbose_name = 'Catalog PR'
        verbose_name_plural = 'Catalog PRs'
    
    def __str__(self):
        item_count = self.pr.get_item_count()
        return f"Catalog PR {self.pr.pr_number or self.pr.id} - {item_count} item(s)"
    
    def add_catalog_item(self, catalog_item, quantity, unit_of_measure, **kwargs):
        """
        Helper method to add a catalog item to this PR.
        
        Args:
            catalog_item: catalogItem instance
            quantity: Quantity to order
            unit_of_measure: UnitOfMeasure instance
            **kwargs: Additional fields for PRItem
        
        Returns:
            PRItem instance
        """
        return PRItem.objects.create(
            pr=self.pr,
            catalog_item=catalog_item,
            item_name=catalog_item.name,
            item_description=catalog_item.description,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            estimated_unit_price=getattr(catalog_item, 'price', 0),
            **kwargs
        )
    
    def validate_all_items_from_catalog(self):
        """Ensure all items are linked to catalog."""
        non_catalog = self.pr.items.filter(catalog_item__isnull=True)
        if non_catalog.exists():
            raise ValidationError(
                f"All items must be from catalog. Found {non_catalog.count()} non-catalog item(s)."
            )
    
    # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    
    def on_approval_started_child(self, workflow_instance):
        """Catalog PR specific logic when approval starts."""
        self.validate_all_items_from_catalog()
    
    def on_fully_approved_child(self, workflow_instance):
        """Catalog PR specific logic when fully approved."""
        pass
    
    def on_rejected_child(self, workflow_instance, stage_instance=None):
        """Catalog PR specific logic when rejected."""
        pass
    
    # ==================== APPROVAL CONVENIENCE METHODS ====================
    
    def submit_for_approval(self):
        """Submit catalog PR for approval."""
        from core.approval.managers import ApprovalManager
        self.validate_all_items_from_catalog()
        return ApprovalManager.start_workflow(self)


# ==================== NON-CATALOG PR MODEL ====================

class NonCatalog_PRManager(ChildModelManagerMixin, models.Manager):
    """Manager for NonCatalog_PR - items not in catalog."""
    parent_model = PR
    parent_defaults = {
        'status': 'DRAFT',
        'type_of_pr': 'Non-Catalog'
    }


class NonCatalog_PR(ChildModelMixin, models.Model):
    """
    Non-Catalog Purchase Requisition - for items not in the catalog.
    
    ALL PR fields are automatically available as properties!
    
    Usage:
        noncatalog_pr = NonCatalog_PR.objects.create(
            date=date.today(),
            required_date=required_date,
            requester_name="John Doe",
            requester_department="IT",
            justification="Special equipment not in standard catalog"
        )
        
        # Add items
        noncatalog_pr.add_noncatalog_item(
            item_name="Custom Server Rack",
            quantity=2,
            estimated_unit_price=5000,
            unit_of_measure=uom_ea,
            catalog_item=category_item  # Optional: link to catalog item for categorization
        )
    """
    
    # Configuration for generic pattern
    parent_model = PR
    parent_field_name = 'pr'
    
    pr = models.OneToOneField(
        PR,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="noncatalog_pr"
    )
    
    # Custom manager
    objects = NonCatalog_PRManager()
    
    class Meta:
        db_table = 'noncatalog_pr'
        verbose_name = 'Non-Catalog PR'
        verbose_name_plural = 'Non-Catalog PRs'
    
    def __str__(self):
        item_count = self.pr.get_item_count()
        return f"Non-Catalog PR {self.pr.pr_number or self.pr.id} - {item_count} item(s)"
    
    def add_noncatalog_item(self, item_name, quantity, estimated_unit_price, unit_of_measure, **kwargs):
        """
        Helper method to add a non-catalog item to this PR.
        
        Args:
            item_name: Name of the item
            quantity: Quantity to order
            estimated_unit_price: Estimated price per unit
            unit_of_measure: UnitOfMeasure instance
            **kwargs: Additional fields for PRItem (description, specifications, catalog_item for category, etc.)
        
        Returns:
            PRItem instance
        """
        return PRItem.objects.create(
            pr=self.pr,
            item_name=item_name,
            quantity=quantity,
            estimated_unit_price=estimated_unit_price,
            unit_of_measure=unit_of_measure,
            **kwargs
        )
    
    def is_high_value(self, threshold=10000):
        """Check if PR total exceeds threshold."""
        HIGH_VALUE_THRESHOLD = Decimal(str(threshold))
        return self.pr.total > HIGH_VALUE_THRESHOLD
    
    def get_estimated_total(self):
        """Get total estimated cost of all items."""
        return self.pr.total
    
    def has_items(self):
        """Check if PR has any line items."""
        return self.pr.get_item_count() > 0
    
    # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    
    def on_approval_started_child(self, workflow_instance):
        """Non-catalog PR specific logic when approval starts."""
        # Validate that PR has items
        if not self.has_items():
            raise ValidationError("Cannot submit PR without line items")
        
        # Check if high-value PRs have proper documentation in notes
        if self.is_high_value() and not self.pr.notes:
            raise ValidationError(
                f"High-value non-catalog purchases (over ${10000:,.2f}) require notes/justification in PR"
            )
    
    def on_fully_approved_child(self, workflow_instance):
        """Non-catalog PR specific logic when fully approved."""
        pass
    
    def on_rejected_child(self, workflow_instance, stage_instance=None):
        """Non-catalog PR specific logic when rejected."""
        pass
    
    # ==================== APPROVAL CONVENIENCE METHODS ====================
    
    def submit_for_approval(self):
        """Submit non-catalog PR for approval."""
        from core.approval.managers import ApprovalManager
        # Basic validation before submission
        if not self.has_items():
            raise ValidationError("Cannot submit PR without line items")
        
        return ApprovalManager.start_workflow(self)


# ==================== SERVICE PR MODEL ====================

class Service_PRManager(ChildModelManagerMixin, models.Manager):
    """Manager for Service_PR - service requests."""
    parent_model = PR
    parent_defaults = {
        'status': 'DRAFT',
        'type_of_pr': 'Service'
    }


class Service_PR(ChildModelMixin, models.Model):
    """
    Service Purchase Requisition - for service requests.
    
    ALL PR fields are automatically available as properties!
    
    Usage:
        service_pr = Service_PR.objects.create(
            date=date.today(),
            required_date=required_date,
            requester_name="John Doe",
            requester_department="IT",
            service_scope="Annual IT infrastructure audit",
            requires_contract=True
        )
        
        # Add service items
        service_pr.add_service_item(
            service_name="IT Audit Service",
            estimated_cost=25000,
            catalog_item=service_category_item  # Optional: for categorization
        )
    """
    
    # Configuration for generic pattern
    parent_model = PR
    parent_field_name = 'pr'
    
    pr = models.OneToOneField(
        PR,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="service_pr"
    )
    
    # Service specific fields
    # service_scope = models.TextField(
    #     blank=True,
    #     help_text="Detailed scope of work for the service"
    # )
    # service_location = models.CharField(
    #     max_length=255,
    #     blank=True,
    #     help_text="Service delivery location"
    # )
    # requires_contract = models.BooleanField(
    #     default=False,
    #     help_text="Indicates if formal contract/MSA is required"
    # )
    # contract_type = models.CharField(
    #     max_length=50,
    #     blank=True,
    #     choices=[
    #         ('FIXED_PRICE', 'Fixed Price'),
    #         ('TIME_MATERIAL', 'Time & Material'),
    #         ('RETAINER', 'Retainer'),
    #         ('MILESTONE', 'Milestone-based'),
    #     ],
    #     help_text="Type of contract/pricing model"
    # )
    # expected_start_date = models.DateField(
    #     null=True,
    #     blank=True,
    #     help_text="Expected service start date"
    # )
    # expected_completion_date = models.DateField(
    #     null=True,
    #     blank=True,
    #     help_text="Expected service completion date"
    # )
    
    # Custom manager
    objects = Service_PRManager()
    
    class Meta:
        db_table = 'service_pr'
        verbose_name = 'Service PR'
        verbose_name_plural = 'Service PRs'
    
    def __str__(self):
        item_count = self.pr.get_item_count()
        return f"Service PR {self.pr.pr_number or self.pr.id} - {item_count} service(s)"
    
    def add_service_item(self, service_name, estimated_cost, unit_of_measure=None, **kwargs):
        """
        Helper method to add a service to this PR.
        
        Args:
            service_name: Name of the service
            estimated_cost: Estimated total cost for the service
            unit_of_measure: UnitOfMeasure instance (defaults to a service UoM if not provided)
            **kwargs: Additional fields for PRItem (description, catalog_item for category, etc.)
        
        Returns:
            PRItem instance
        """
        # Get or create a default "Service" UoM if not provided
        if not unit_of_measure:
            unit_of_measure, _ = UnitOfMeasure.objects.get_or_create(
                code='SRV',
                defaults={
                    'name': 'Service',
                    'uom_type': 'QUANTITY'
                }
            )
        
        return PRItem.objects.create(
            pr=self.pr,
            item_name=service_name,
            quantity=1,  # Services typically have quantity of 1
            estimated_unit_price=estimated_cost,
            unit_of_measure=unit_of_measure,
            **kwargs
        )
    
    def is_high_value_service(self, threshold=50000):
        """Check if service exceeds threshold (may require special approval)."""
        return self.pr.total > Decimal(str(threshold))
    
    def get_estimated_total(self):
        """Get total estimated cost of all services."""
        return self.pr.total
    
    def has_services(self):
        """Check if PR has any service items."""
        return self.pr.get_item_count() > 0
    
    def get_service_count(self):
        """Get number of services in this PR."""
        return self.pr.get_item_count()
    
    # ==================== APPROVAL WORKFLOW CHILD HOOKS ====================
    
    def on_approval_started_child(self, workflow_instance):
        """Service PR specific logic when approval starts."""
        # Validate that PR has service items
        if not self.has_services():
            raise ValidationError("Cannot submit service PR without service items")
        
        # Can add validation for high-value services
        if self.is_high_value_service():
            # Check if proper documentation exists in PR notes or description
            if not self.pr.description and not self.pr.notes:
                raise ValidationError(
                    f"High-value services (over ${50000:,.2f}) require detailed description or notes"
                )
    
    def on_fully_approved_child(self, workflow_instance):
        """Service PR specific logic when fully approved."""
        # Example: Trigger notification for high-value service PRs
        if self.is_high_value_service():
            # Could trigger contract creation workflow or notification
            pass
    
    def on_rejected_child(self, workflow_instance, stage_instance=None):
        """Service PR specific logic when rejected."""
        pass
    
    # ==================== APPROVAL CONVENIENCE METHODS ====================
    
    def submit_for_approval(self):
        """Submit service PR for approval."""
        from core.approval.managers import ApprovalManager
        # Basic validation before submission
        if not self.has_services():
            raise ValidationError("Cannot submit service PR without service items")
        
        return ApprovalManager.start_workflow(self)


"""PR Attachment Model - Store file attachments as BLOBs for Purchase Requisitions."""
class PRAttachment(models.Model):
    """Model to store file attachments as BLOBs for purchase requisitions"""
    
    attachment_id = models.AutoField(primary_key=True)
    pr = models.ForeignKey(
        PR,
        on_delete=models.CASCADE,
        related_name="attachments",
        help_text="Parent PR"
    )
    file_name = models.CharField(max_length=255, help_text="Original file name")
    file_type = models.CharField(max_length=100, help_text="MIME type or file extension")
    file_size = models.IntegerField(help_text="File size in bytes")
    file_data = models.BinaryField(help_text="Binary file data (BLOB)")
    upload_date = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of user who uploaded the attachment"
    )
    description = models.TextField(blank=True, help_text="Optional description of the attachment")
    
    class Meta:
        db_table = 'pr_attachment'
        ordering = ['-upload_date']
        indexes = [
            models.Index(fields=['pr', '-upload_date']),
        ]
    
    def __str__(self):
        return f"Attachment {self.attachment_id}: {self.file_name} for PR {self.pr.pr_number}"
    
    def get_file_size_display(self):
        """Return human-readable file size."""
        size_bytes = self.file_size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"