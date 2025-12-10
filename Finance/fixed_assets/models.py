# from django.db import models, transaction
# from django.core.exceptions import ValidationError
# from django.utils import timezone
# from decimal import Decimal
# from Finance.core.models import Currency, Country
# from Finance.BusinessPartner.models import Supplier
# from Finance.GL.models import JournalEntry, XX_Segment, XX_SegmentType
# from django.db import models
# from decimal import Decimal


# class Fixed_assetbook(models.Model):
#     type_choices = [('capitalized', 'Capitalized'), ('CIP', 'CIP')]
#     type = models.CharField(max_length=20, choices=type_choices, default='capitalized')
#     asset_number = models.CharField(max_length=30, unique=True)
#     name = models.CharField(max_length=200)
#     #prefix_bardcode = models.CharField(max_length=100, blank=True, null=True)
#     #next_number = models.PositiveIntegerField(default=1)
    
#     # acquisition_date = models.DateField()
#     # acquisition_cost = models.DecimalField(max_digits=15, decimal_places=2)
#     # depreciation_method = models.CharField(max_length=50)
#     useful_life_years = models.PositiveIntegerField()
#     #accumulated_depreciation = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     #book_value = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     status = models.CharField(max_length=20, choices=[('active', 'Active'), ('disposed', 'Disposed')], default='active')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"{self.asset_number} - {self.name}",    

# class FA_category(models.Model):
#     code = models.CharField(max_length=20, unique=True)
#     major_name = models.CharField(max_length=100)
#     minor_name = models.CharField(max_length=100)
#     #default_depreciation_method = models.CharField(max_length=50)
#     default_useful_life_years = models.PositiveIntegerField()
#     is_active = models.BooleanField(default=True)
#     minimum_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
#     Fixed_assetbook= models.ForeignKey(Fixed_assetbook, on_delete=models.PROTECT)
#     GL_account = models.ForeignKey(XX_Segment, on_delete=models.PROTECT)
#     def __str__(self):
#         return f"{self.code} - {self.name}",    

# class location_segment_type(models.Model):
#     name=models.CharField(max_length=100)
#     code=models.CharField(max_length=20, unique=True)
#     ordering=models.PositiveIntegerField(default=0)
#     def __str__(self):
#         return f"{self.code} - {self.name}",

# class location_segment(models.Model):
#     segment_type = models.ForeignKey(location_segment_type, on_delete=models.PROTECT)
#     name=models.CharField(max_length=100)
#     code_value = models.CharField(max_length=50)
#     def __str__(self):
#         return f"{self.segment_type.name} - {self.code_value}",

# class FA_location(models.Model):
#     code = models.CharField(max_length=20, unique=True)
#     name = models.CharField(max_length=100)
#     is_active = models.BooleanField(default=True)
#     segment = models.ForeignKey(location_segment, on_delete=models.PROTECT)
#     Fixed_assetbook= models.ForeignKey(Fixed_assetbook, on_delete=models.PROTECT)
#     def __str__(self):
#         return f"{self.code} - {self.name}",    


# class AssetTransfer(models.Model):
#     """
#     Track asset location transfers with audit trail.
#     """
#     asset = models.ForeignKey(
#         Fixed_assetbook,
#         on_delete=models.PROTECT,
#         related_name='location_transfers'
#     )
#     transfer_date = models.DateField()
#     from_location = models.ForeignKey(
#         FA_location,
#         on_delete=models.PROTECT,
#         related_name='transfers_out',
#         null=True,
#         blank=True
#     )
#     to_location = models.ForeignKey(
#         FA_location,
#         on_delete=models.PROTECT,
#         related_name='transfers_in'
#     )
#     transfer_reason = models.TextField(blank=True)
#     transferred_by = models.CharField(max_length=100)
#     approved_by = models.CharField(max_length=100, blank=True)
#     is_approved = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'asset_transfer'
#         ordering = ['-transfer_date']
#         indexes = [
#             models.Index(fields=['asset', 'transfer_date']),
#             models.Index(fields=['transfer_date']),
#         ]
    
#     def __str__(self):
#         return f"{self.asset.asset_number}: {self.from_location} → {self.to_location} ({self.transfer_date})"


# class AssetRecategorization(models.Model):
#     """
#     Track asset category changes with audit trail.
#     """
#     asset = models.ForeignKey(
#         Fixed_assetbook,
#         on_delete=models.PROTECT,
#         related_name='recategorizations'
#     )
#     recategorization_date = models.DateField()
#     from_category = models.ForeignKey(
#         FA_category,
#         on_delete=models.PROTECT,
#         related_name='recategorizations_out',
#         null=True,
#         blank=True
#     )
#     to_category = models.ForeignKey(
#         FA_category,
#         on_delete=models.PROTECT,
#         related_name='recategorizations_in'
#     )
#     reason = models.TextField()
   
    
#     # Depreciation impact
#     recalculate_depreciation = models.BooleanField(default=True)
#     new_useful_life_years = models.PositiveIntegerField(null=True, blank=True)
    
#     # Approval workflow
#     requested_by = models.CharField(max_length=100)
#     approved_by = models.CharField(max_length=100, blank=True)
#     is_approved = models.BooleanField(default=False)
#     approval_date = models.DateField(null=True, blank=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'asset_recategorization'
#         ordering = ['-recategorization_date']
#         indexes = [
#             models.Index(fields=['asset', 'recategorization_date']),
#             models.Index(fields=['recategorization_date']),
#             models.Index(fields=['is_approved']),
#         ]
    
#     def __str__(self):
#         return f"{self.asset.asset_number}: {self.from_category} → {self.to_category} ({self.recategorization_date})"
    
#     def clean(self):
#         """Validate that from_category and to_category are different."""
#         if self.from_category and self.to_category and self.from_category == self.to_category:
#             raise ValidationError("From category and to category must be different.")


#     adjustment = models.ForeignKey(adjustment, on_delete=models.PROTECT)
#     description = models.CharField(max_length=200)
#     unit_amount = models.DecimalField(max_digits=15, decimal_places=2)

#     def __str__(self):
#         return f"{self.adjustment.asset.asset_number} - {self.unit_amount}"
    

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date
from GL.models import XX_SegmentType, XX_Segment


# ==================== LOOKUPS & CONFIGURATION ====================

class AssetCategory(models.Model):
    """Asset categories with hierarchical structure"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    
    # Default settings for this category
    default_useful_life_months = models.IntegerField(default=60, validators=[MinValueValidator(1)])
    default_salvage_value_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # GL Accounts (you can expand this based on your chart of accounts)
    asset_account = models.ForeignKey(XX_Segment, on_delete=models.PROTECT, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Asset Categories"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class LocationSegment(models.Model):
    """Dynamic location segments (e.g., Country, City, Building, Floor, Room)"""
    segment_name = models.CharField(max_length=100)  # e.g., "Country", "Building", "Floor"
    segment_order = models.IntegerField()  # Order in hierarchy
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['segment_order']
        unique_together = ['segment_name', 'segment_order']
    
    def __str__(self):
        return f"{self.segment_order}. {self.segment_name}"


class LocationSegmentValue(models.Model):
    """Values for each location segment"""
    segment = models.ForeignKey(LocationSegment, on_delete=models.CASCADE, related_name='values')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    parent_value = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['segment__segment_order', 'code']
        unique_together = ['segment', 'code']
    
    def __str__(self):
        return f"{self.segment.segment_name}: {self.code} - {self.name}"


class Location(models.Model):
    """Complete location built from segment values"""
    location_code = models.CharField(max_length=100, unique=True)
    location_name = models.CharField(max_length=500)
    
    # Store location as JSON for flexibility: {"Country": "EG", "City": "Cairo", "Building": "HQ"}
    location_segments = models.JSONField(default=dict)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['location_code']
    
    def __str__(self):
        return f"{self.location_code} - {self.location_name}"


class DepreciationBook(models.Model):
    """Different depreciation books (Financial, Tax, IFRS, etc.)"""
    BOOK_TYPES = [
        ('FINANCIAL', 'Financial'),
        ('TAX', 'Tax'),
        ('IFRS', 'IFRS'),
        ('MANAGEMENT', 'Management'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    book_type = models.CharField(max_length=20, choices=BOOK_TYPES)
    is_primary = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default='USD')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


# ==================== MAIN ASSET ====================

class Asset(models.Model):
    """Main asset master record"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('RETIRED', 'Retired')
        
    ]
    
    asset_number = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.CharField(max_length=500)
    
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='assets')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='assets')
    
    # Identification
    serial_number = models.CharField(max_length=200, blank=True)
    manufacturer = models.CharField(max_length=200, blank=True)
    model = models.CharField(max_length=200, blank=True)
    
    # Dates
    acquisition_date = models.DateField()
    in_service_date = models.DateField()
    
    # Cost & Depreciation (default values, actual tracked in AssetBook)
    original_cost = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0)])
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Assignment
    custodian = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='custodian_assets')
    cost_center = models.CharField(max_length=50, blank=True)
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_assets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['asset_number']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['location']),
        ]
    
    def __str__(self):
        return f"{self.asset_number} - {self.description}"


class AssetBook(models.Model):
    """Asset values per depreciation book"""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='books')
    book = models.ForeignKey(DepreciationBook, on_delete=models.PROTECT, related_name='asset_books')
    
    # Financial values
    cost = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    salvage_value = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    accumulated_depreciation = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_book_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Depreciation settings
    useful_life_months = models.IntegerField(validators=[MinValueValidator(1)])
    remaining_life_months = models.IntegerField(validators=[MinValueValidator(0)])
    
    # Depreciation tracking
    depreciation_start_date = models.DateField()
    last_depreciation_date = models.DateField(null=True, blank=True)
    next_depreciation_date = models.DateField(null=True, blank=True)
    
    is_fully_depreciated = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['asset', 'book']
        ordering = ['asset', 'book']
    
    def __str__(self):
        return f"{self.asset.asset_number} - {self.book.code}"
    
    def calculate_monthly_depreciation(self):
        """Calculate straight-line monthly depreciation"""
        if self.is_fully_depreciated or self.useful_life_months == 0:
            return Decimal('0.00')
        
        depreciable_amount = self.cost - self.salvage_value
        monthly_depreciation = depreciable_amount / self.useful_life_months
        return monthly_depreciation.quantize(Decimal('0.01'))


# ==================== TRANSACTIONS ====================

class AssetTransaction(models.Model):
    """All asset transactions for audit trail"""
    TRANSACTION_TYPES = [
        ('ACQUISITION', 'Acquisition'),
        ('DEPRECIATION', 'Depreciation'),
        ('TRANSFER', 'Transfer'),
        ('RECATEGORIZE', 'Recategorization'),
        ('COST_ADJUSTMENT', 'Cost Adjustment'),
        ('DEPRECIATION_ADJUSTMENT', 'Depreciation Adjustment'),
        ('RETIREMENT', 'Retirement'),
        ('PHYSICAL_INVENTORY', 'Physical Inventory'),
    ]
    
    APPROVAL_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    transaction_number = models.CharField(max_length=50, unique=True, db_index=True)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    transaction_date = models.DateField()
    
    # For tracking what changed
    from_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT, related_name='transactions_from')
    to_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT, related_name='transactions_to')
    
    from_category = models.ForeignKey(AssetCategory, null=True, blank=True, on_delete=models.PROTECT, related_name='transactions_from')
    to_category = models.ForeignKey(AssetCategory, null=True, blank=True, on_delete=models.PROTECT, related_name='transactions_to')
    
    # Amounts
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Additional data stored as JSON for flexibility
    transaction_details = models.JSONField(default=dict, blank=True)
    
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=200, blank=True)
    
    # Approval
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default='DRAFT')
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_transactions')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # GL Integration
    is_posted = models.BooleanField(default=False)
    journal_entry_id = models.CharField(max_length=50, blank=True)
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['asset', 'transaction_type']),
            models.Index(fields=['transaction_date']),
        ]
    
    def __str__(self):
        return f"{self.transaction_number} - {self.get_transaction_type_display()}"


class DepreciationSchedule(models.Model):
    """Depreciation history per book"""
    asset_book = models.ForeignKey(AssetBook, on_delete=models.CASCADE, related_name='depreciation_schedules')
    period_date = models.DateField()  # Usually month-end
    
    depreciation_amount = models.DecimalField(max_digits=15, decimal_places=2)
    accumulated_depreciation = models.DecimalField(max_digits=15, decimal_places=2)
    net_book_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    is_posted = models.BooleanField(default=False)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='posted_depreciations')
    
    journal_entry_id = models.CharField(max_length=50, blank=True)
    transaction = models.ForeignKey(AssetTransaction, null=True, blank=True, on_delete=models.SET_NULL)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['asset_book', 'period_date']
        ordering = ['asset_book', 'period_date']
        indexes = [
            models.Index(fields=['period_date', 'is_posted']),
        ]
    
    def __str__(self):
        return f"{self.asset_book.asset.asset_number} - {self.period_date}"


class PhysicalInventory(models.Model):
    """Physical inventory header"""
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    inventory_number = models.CharField(max_length=50, unique=True)
    inventory_date = models.DateField()
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT, related_name='inventories')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    
    description = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_inventories')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Physical Inventories"
        ordering = ['-inventory_date']
    
    def __str__(self):
        return f"{self.inventory_number} - {self.inventory_date}"


class PhysicalInventoryLine(models.Model):
    """Physical inventory lines"""
    LINE_STATUS = [
        ('FOUND', 'Found'),
        ('MISSING', 'Missing'),
        ('DAMAGED', 'Damaged'),
        ('UNRECORDED', 'Unrecorded'),
    ]
    
    inventory = models.ForeignKey(PhysicalInventory, on_delete=models.CASCADE, related_name='lines')
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='inventory_lines')
    
    expected_location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='expected_lines')
    actual_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT, related_name='actual_lines')
    
    expected_custodian = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='expected_custody')
    actual_custodian = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='actual_custody')
    
    status = models.CharField(max_length=20, choices=LINE_STATUS)
    notes = models.TextField(blank=True)
    
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_lines')
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Link to adjustment transaction if created
    adjustment_transaction = models.ForeignKey(AssetTransaction, null=True, blank=True, on_delete=models.SET_NULL)
    
    class Meta:
        ordering = ['inventory', 'asset']
        unique_together = ['inventory', 'asset']
    
    def __str__(self):
        return f"{self.inventory.inventory_number} - {self.asset.asset_number}"


# ==================== RETIREMENT ====================

class AssetRetirement(models.Model):
    """Asset retirement/disposal details"""
    RETIREMENT_TYPES = [
        ('SALE', 'Sale'),
        ('SCRAP', 'Scrap'),
        ('DONATION', 'Donation'),
        ('TRADE_IN', 'Trade-in'),
        ('THEFT', 'Theft/Loss'),
    ]
    
    asset = models.OneToOneField(Asset, on_delete=models.PROTECT, related_name='retirement')
    transaction = models.OneToOneField(AssetTransaction, on_delete=models.PROTECT, related_name='retirement_detail')
    
    retirement_type = models.CharField(max_length=20, choices=RETIREMENT_TYPES)
    retirement_date = models.DateField()
    
    # Financial details per book stored in JSON
    # {book_id: {cost, accumulated_dep, nbv, proceeds, gain_loss}}
    book_details = models.JSONField(default=dict)
    
    proceeds = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    removal_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    buyer_vendor = models.CharField(max_length=200, blank=True)
    disposal_reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    
    is_posted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-retirement_date']
    
    def __str__(self):
        return f"Retirement: {self.asset.asset_number} - {self.retirement_date}"