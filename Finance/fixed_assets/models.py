from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import Supplier
from Finance.GL.models import JournalEntry, XX_Segment_combination


# class AssetCategory(models.Model):
#     """
#     Categories for fixed assets (Buildings, Vehicles, Equipment, etc.)
#     Each category has its own depreciation settings and GL accounts.
#     """
    
#     code = models.CharField(max_length=20, unique=True)
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)
    
#     # Default depreciation settings
#     DEPRECIATION_METHODS = [
#         ('STRAIGHT_LINE', 'Straight Line'),
#         ('DECLINING_BALANCE', 'Declining Balance'),
#         ('DOUBLE_DECLINING', 'Double Declining Balance'),
#         ('SUM_OF_YEARS', 'Sum of Years Digits'),
#         ('UNITS_OF_PRODUCTION', 'Units of Production'),
#     ]
#     default_depreciation_method = models.CharField(
#         max_length=20,
#         choices=DEPRECIATION_METHODS,
#         default='STRAIGHT_LINE'
#     )
#     default_useful_life_years = models.IntegerField(
#         default=5,
#         help_text="Default useful life in years"
#     )
#     default_salvage_value_percentage = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         help_text="Default salvage value as percentage of cost"
#     )
    
#     # GL Account Configurations (segment combinations)
#     asset_account = models.ForeignKey(
#         XX_Segment_combination,
#         on_delete=models.PROTECT,
#         related_name='asset_categories',
#         null=True,
#         blank=True,
#         help_text="GL account for asset cost"
#     )
#     accumulated_depreciation_account = models.ForeignKey(
#         XX_Segment_combination,
#         on_delete=models.PROTECT,
#         related_name='asset_accum_depr_categories',
#         null=True,
#         blank=True,
#         help_text="GL account for accumulated depreciation"
#     )
#     depreciation_expense_account = models.ForeignKey(
#         XX_Segment_combination,
#         on_delete=models.PROTECT,
#         related_name='asset_depr_expense_categories',
#         null=True,
#         blank=True,
#         help_text="GL account for depreciation expense"
#     )
#     gain_on_disposal_account = models.ForeignKey(
#         XX_Segment_combination,
#         on_delete=models.PROTECT,
#         related_name='asset_gain_categories',
#         null=True,
#         blank=True,
#         help_text="GL account for gain on disposal"
#     )
#     loss_on_disposal_account = models.ForeignKey(
#         XX_Segment_combination,
#         on_delete=models.PROTECT,
#         related_name='asset_loss_categories',
#         null=True,
#         blank=True,
#         help_text="GL account for loss on disposal"
#     )
    
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'asset_category'
#         verbose_name = 'Asset Category'
#         verbose_name_plural = 'Asset Categories'
#         ordering = ['code']
    
#     def __str__(self):
#         return f"{self.code} - {self.name}"


# class AssetLocation(models.Model):
#     """Physical locations where assets are placed."""
    
#     code = models.CharField(max_length=20, unique=True)
#     name = models.CharField(max_length=100)
#     address = models.TextField(blank=True)
#     is_active = models.BooleanField(default=True)
    
#     class Meta:
#         db_table = 'asset_location'
#         verbose_name = 'Asset Location'
#         verbose_name_plural = 'Asset Locations'
    
#     def __str__(self):
#         return f"{self.code} - {self.name}"


# class FixedAsset(models.Model):
#     """
#     Fixed Asset Master Record
    
#     Lifecycle: DRAFT → ACTIVE → (FULLY_DEPRECIATED | DISPOSED)
#     """
    
#     # Status choices
#     DRAFT = 'DRAFT'
#     ACTIVE = 'ACTIVE'
#     FULLY_DEPRECIATED = 'FULLY_DEPRECIATED'
#     DISPOSED = 'DISPOSED'
#     STATUS_CHOICES = [
#         (DRAFT, 'Draft'),
#         (ACTIVE, 'Active'),
#         (FULLY_DEPRECIATED, 'Fully Depreciated'),
#         (DISPOSED, 'Disposed'),
#     ]
    
#     # Identification
#     asset_number = models.CharField(max_length=50, unique=True)
#     name = models.CharField(max_length=200)
#     description = models.TextField(blank=True)
#     serial_number = models.CharField(max_length=100, blank=True)
    
#     # Classification
#     category = models.ForeignKey(
#         AssetCategory,
#         on_delete=models.PROTECT,
#         related_name='assets'
#     )
#     location = models.ForeignKey(
#         AssetLocation,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         related_name='assets'
#     )
    
#     # Acquisition details
#     acquisition_date = models.DateField()
#     acquisition_cost = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         help_text="Original cost of the asset"
#     )
#     currency = models.ForeignKey(
#         Currency,
#         on_delete=models.PROTECT,
#         related_name='fixed_assets'
#     )
#     supplier = models.ForeignKey(
#         Supplier,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         related_name='supplied_assets'
#     )
#     invoice_number = models.CharField(max_length=50, blank=True)
    
#     # Depreciation settings
#     DEPRECIATION_METHODS = [
#         ('STRAIGHT_LINE', 'Straight Line'),
#         ('DECLINING_BALANCE', 'Declining Balance'),
#         ('DOUBLE_DECLINING', 'Double Declining Balance'),
#         ('SUM_OF_YEARS', 'Sum of Years Digits'),
#         ('UNITS_OF_PRODUCTION', 'Units of Production'),
#     ]
#     depreciation_method = models.CharField(
#         max_length=20,
#         choices=DEPRECIATION_METHODS,
#         default='STRAIGHT_LINE'
#     )
#     useful_life_years = models.IntegerField(help_text="Useful life in years")
#     useful_life_months = models.IntegerField(
#         default=0,
#         help_text="Additional months beyond years"
#     )
#     salvage_value = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         help_text="Estimated value at end of useful life"
#     )
#     depreciation_start_date = models.DateField(
#         null=True,
#         blank=True,
#         help_text="Date to start calculating depreciation"
#     )
    
#     # For units of production method
#     total_units_capacity = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Total units the asset can produce (for units of production method)"
#     )
    
#     # Declining balance rate
#     declining_balance_rate = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Rate for declining balance method (e.g., 1.5 for 150%)"
#     )
    
#     # Current values (calculated/updated)
#     accumulated_depreciation = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         default=Decimal('0.00')
#     )
#     book_value = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         default=Decimal('0.00')
#     )
    
#     # Status
#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default=DRAFT
#     )
    
#     # Disposal details
#     disposal_date = models.DateField(null=True, blank=True)
#     disposal_amount = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         null=True,
#         blank=True
#     )
#     disposal_reason = models.TextField(blank=True)
    
#     # GL entries
#     acquisition_gl_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         related_name='asset_acquisitions'
#     )
#     disposal_gl_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         related_name='asset_disposals'
#     )
    
#     # Timestamps
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'fixed_asset'
#         verbose_name = 'Fixed Asset'
#         verbose_name_plural = 'Fixed Assets'
#         ordering = ['asset_number']
    
#     def __str__(self):
#         return f"{self.asset_number} - {self.name}"
    
#     def save(self, *args, **kwargs):
#         # Auto-calculate book value
#         self.book_value = self.acquisition_cost - self.accumulated_depreciation
        
#         # Auto-generate asset number if not set
#         if not self.asset_number:
#             prefix = self.category.code if self.category else 'AST'
#             last = FixedAsset.objects.filter(
#                 asset_number__startswith=prefix
#             ).order_by('-pk').first()
#             next_num = (last.pk + 1) if last else 1
#             self.asset_number = f"{prefix}-{next_num:06d}"
        
#         # Set default depreciation settings from category
#         if self.category and not self.pk:
#             if not self.depreciation_method:
#                 self.depreciation_method = self.category.default_depreciation_method
#             if not self.useful_life_years:
#                 self.useful_life_years = self.category.default_useful_life_years
#             if self.salvage_value == Decimal('0.00') and self.category.default_salvage_value_percentage > 0:
#                 self.salvage_value = self.acquisition_cost * (self.category.default_salvage_value_percentage / 100)
        
#         super().save(*args, **kwargs)
    
#     # ==================== DEPRECIATION CALCULATIONS ====================
    
#     @property
#     def depreciable_amount(self):
#         """Amount that can be depreciated (cost - salvage value)."""
#         return self.acquisition_cost - self.salvage_value
    
#     @property
#     def total_useful_life_months(self):
#         """Total useful life in months."""
#         return (self.useful_life_years * 12) + self.useful_life_months
    
#     @property
#     def remaining_book_value(self):
#         """Current book value (cost - accumulated depreciation)."""
#         return self.acquisition_cost - self.accumulated_depreciation
    
#     @property
#     def is_fully_depreciated(self):
#         """Check if asset is fully depreciated."""
#         return self.accumulated_depreciation >= self.depreciable_amount
    
#     def calculate_monthly_depreciation(self):
#         """Calculate monthly depreciation based on method."""
#         if self.is_fully_depreciated:
#             return Decimal('0.00')
        
#         if self.depreciation_method == 'STRAIGHT_LINE':
#             return self._straight_line_depreciation()
#         elif self.depreciation_method == 'DECLINING_BALANCE':
#             return self._declining_balance_depreciation()
#         elif self.depreciation_method == 'DOUBLE_DECLINING':
#             return self._double_declining_depreciation()
#         elif self.depreciation_method == 'SUM_OF_YEARS':
#             return self._sum_of_years_depreciation()
#         else:
#             return Decimal('0.00')
    
#     def _straight_line_depreciation(self):
#         """Straight line: (Cost - Salvage) / Useful Life Months"""
#         if self.total_useful_life_months == 0:
#             return Decimal('0.00')
        
#         monthly = self.depreciable_amount / self.total_useful_life_months
        
#         # Don't exceed remaining depreciable amount
#         remaining = self.depreciable_amount - self.accumulated_depreciation
#         return min(monthly, remaining)
    
#     def _declining_balance_depreciation(self):
#         """Declining balance based on book value."""
#         rate = self.declining_balance_rate or Decimal('1.5')
#         annual_rate = rate / self.useful_life_years
#         monthly_rate = annual_rate / 12
        
#         depreciation = self.remaining_book_value * monthly_rate
        
#         # Don't depreciate below salvage value
#         max_depreciation = self.remaining_book_value - self.salvage_value
#         return min(depreciation, max(max_depreciation, Decimal('0.00')))
    
#     def _double_declining_depreciation(self):
#         """Double declining balance."""
#         if self.useful_life_years == 0:
#             return Decimal('0.00')
        
#         annual_rate = Decimal('2') / self.useful_life_years
#         monthly_rate = annual_rate / 12
        
#         depreciation = self.remaining_book_value * monthly_rate
        
#         # Don't depreciate below salvage value
#         max_depreciation = self.remaining_book_value - self.salvage_value
#         return min(depreciation, max(max_depreciation, Decimal('0.00')))
    
#     def _sum_of_years_depreciation(self):
#         """Sum of years digits method."""
#         n = self.useful_life_years
#         sum_of_years = (n * (n + 1)) / 2
        
#         # Determine which year we're in based on accumulated depreciation
#         # Simplified: assume we're calculating for current period
#         remaining_years = n  # This should be calculated based on elapsed time
        
#         annual_depreciation = (remaining_years / sum_of_years) * self.depreciable_amount
#         monthly_depreciation = annual_depreciation / 12
        
#         remaining = self.depreciable_amount - self.accumulated_depreciation
#         return min(monthly_depreciation, remaining)
    
#     # ==================== LIFECYCLE METHODS ====================
    
#     def can_activate(self):
#         """Check if asset can be activated."""
#         return self.status == self.DRAFT
    
#     @transaction.atomic
#     def activate(self):
#         """Activate the asset and create acquisition GL entry."""
#         if not self.can_activate():
#             raise ValidationError(f'Cannot activate asset with status: {self.status}')
        
#         if not self.depreciation_start_date:
#             self.depreciation_start_date = self.acquisition_date
        
#         # Create acquisition GL entry
#         gl_entry = self._create_acquisition_gl_entry()
#         if gl_entry:
#             self.acquisition_gl_entry = gl_entry
        
#         self.status = self.ACTIVE
#         self.save()
#         return True
    
#     def _create_acquisition_gl_entry(self):
#         """Create GL entry for asset acquisition."""
#         if not self.category.asset_account:
#             return None
        
#         # DR: Asset Account
#         # CR: AP or Cash (depending on how acquired)
#         # For now, just create the asset side
#         je = JournalEntry.objects.create(
#             date=self.acquisition_date,
#             currency=self.currency,
#             memo=f"Asset Acquisition: {self.name}"
#         )
        
#         from Finance.GL.models import JournalLine
        
#         JournalLine.objects.create(
#             entry=je,
#             amount=self.acquisition_cost,
#             type='DEBIT',
#             segment_combination=self.category.asset_account
#         )
        
#         return je
    
#     def can_dispose(self):
#         """Check if asset can be disposed."""
#         return self.status in [self.ACTIVE, self.FULLY_DEPRECIATED]
    
#     @transaction.atomic
#     def dispose(self, disposal_date, disposal_amount, reason=''):
#         """Dispose of the asset."""
#         if not self.can_dispose():
#             raise ValidationError(f'Cannot dispose asset with status: {self.status}')
        
#         self.disposal_date = disposal_date
#         self.disposal_amount = Decimal(str(disposal_amount))
#         self.disposal_reason = reason
        
#         # Create disposal GL entry
#         gl_entry = self._create_disposal_gl_entry()
#         if gl_entry:
#             self.disposal_gl_entry = gl_entry
        
#         self.status = self.DISPOSED
#         self.save()
#         return True
    
#     def _create_disposal_gl_entry(self):
#         """
#         Create GL entry for asset disposal.
        
#         DR: Cash/AR (disposal amount)
#         DR: Accumulated Depreciation (full amount)
#         DR/CR: Gain or Loss on Disposal
#         CR: Asset Account (original cost)
#         """
#         if not self.category.asset_account:
#             return None
        
#         je = JournalEntry.objects.create(
#             date=self.disposal_date,
#             currency=self.currency,
#             memo=f"Asset Disposal: {self.name}"
#         )
        
#         from Finance.GL.models import JournalLine
        
#         # Calculate gain/loss
#         gain_loss = self.disposal_amount - self.remaining_book_value
        
#         # CR: Asset Account (original cost)
#         JournalLine.objects.create(
#             entry=je,
#             amount=self.acquisition_cost,
#             type='CREDIT',
#             segment_combination=self.category.asset_account
#         )
        
#         # DR: Accumulated Depreciation
#         if self.category.accumulated_depreciation_account and self.accumulated_depreciation > 0:
#             JournalLine.objects.create(
#                 entry=je,
#                 amount=self.accumulated_depreciation,
#                 type='DEBIT',
#                 segment_combination=self.category.accumulated_depreciation_account
#             )
        
#         # DR or CR: Gain/Loss
#         if gain_loss > 0 and self.category.gain_on_disposal_account:
#             JournalLine.objects.create(
#                 entry=je,
#                 amount=abs(gain_loss),
#                 type='CREDIT',
#                 segment_combination=self.category.gain_on_disposal_account
#             )
#         elif gain_loss < 0 and self.category.loss_on_disposal_account:
#             JournalLine.objects.create(
#                 entry=je,
#                 amount=abs(gain_loss),
#                 type='DEBIT',
#                 segment_combination=self.category.loss_on_disposal_account
#             )
        
#         return je
    
#     def can_modify(self):
#         """Check if asset can be modified."""
#         return self.status == self.DRAFT
    
#     def can_delete(self):
#         """Check if asset can be deleted."""
#         return self.status == self.DRAFT


# class DepreciationSchedule(models.Model):
#     """
#     Monthly depreciation records for each asset.
#     Created when depreciation is run for a period.
#     """
    
#     asset = models.ForeignKey(
#         FixedAsset,
#         on_delete=models.PROTECT,
#         related_name='depreciation_records'
#     )
#     period_date = models.DateField(help_text="First day of the depreciation period")
#     depreciation_amount = models.DecimalField(max_digits=14, decimal_places=2)
#     accumulated_depreciation = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         help_text="Total accumulated depreciation after this period"
#     )
#     book_value = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         help_text="Book value after this depreciation"
#     )
    
#     # GL entry reference
#     gl_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         related_name='depreciation_records'
#     )
    
#     is_posted = models.BooleanField(default=False)
#     posted_date = models.DateField(null=True, blank=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         db_table = 'depreciation_schedule'
#         verbose_name = 'Depreciation Schedule'
#         verbose_name_plural = 'Depreciation Schedules'
#         unique_together = ['asset', 'period_date']
#         ordering = ['asset', 'period_date']
    
#     def __str__(self):
#         return f"{self.asset.asset_number} - {self.period_date}: {self.depreciation_amount}"
    
#     @transaction.atomic
#     def post(self):
#         """Post depreciation to GL."""
#         if self.is_posted:
#             raise ValidationError('Depreciation already posted')
        
#         # Create GL entry
#         gl_entry = self._create_gl_entry()
#         if gl_entry:
#             self.gl_entry = gl_entry
        
#         # Update asset accumulated depreciation
#         self.asset.accumulated_depreciation += self.depreciation_amount
#         self.asset.book_value = self.asset.acquisition_cost - self.asset.accumulated_depreciation
        
#         # Check if fully depreciated
#         if self.asset.is_fully_depreciated:
#             self.asset.status = FixedAsset.FULLY_DEPRECIATED
        
#         self.asset.save()
        
#         self.is_posted = True
#         self.posted_date = timezone.now().date()
#         self.save()
        
#         return True
    
#     def _create_gl_entry(self):
#         """Create GL entry for depreciation."""
#         if not self.asset.category.depreciation_expense_account:
#             return None
        
#         je = JournalEntry.objects.create(
#             date=self.period_date,
#             currency=self.asset.currency,
#             memo=f"Depreciation: {self.asset.name} - {self.period_date.strftime('%B %Y')}"
#         )
        
#         from Finance.GL.models import JournalLine
        
#         # DR: Depreciation Expense
#         JournalLine.objects.create(
#             entry=je,
#             amount=self.depreciation_amount,
#             type='DEBIT',
#             segment_combination=self.asset.category.depreciation_expense_account
#         )
        
#         # CR: Accumulated Depreciation
#         if self.asset.category.accumulated_depreciation_account:
#             JournalLine.objects.create(
#                 entry=je,
#                 amount=self.depreciation_amount,
#                 type='CREDIT',
#                 segment_combination=self.asset.category.accumulated_depreciation_account
#             )
        
#         return je


# class AssetTransfer(models.Model):
#     """Records of asset transfers between locations."""
    
#     asset = models.ForeignKey(
#         FixedAsset,
#         on_delete=models.PROTECT,
#         related_name='transfers'
#     )
#     transfer_date = models.DateField()
#     from_location = models.ForeignKey(
#         AssetLocation,
#         on_delete=models.PROTECT,
#         related_name='transfers_out',
#         null=True,
#         blank=True
#     )
#     to_location = models.ForeignKey(
#         AssetLocation,
#         on_delete=models.PROTECT,
#         related_name='transfers_in'
#     )
#     reason = models.TextField(blank=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         db_table = 'asset_transfer'
#         verbose_name = 'Asset Transfer'
#         verbose_name_plural = 'Asset Transfers'
#         ordering = ['-transfer_date']
    
#     def __str__(self):
#         return f"{self.asset.asset_number}: {self.from_location} → {self.to_location}"
    
#     def save(self, *args, **kwargs):
#         # Update asset location
#         self.asset.location = self.to_location
#         self.asset.save(update_fields=['location', 'updated_at'])
#         super().save(*args, **kwargs)


# class AssetRevaluation(models.Model):
#     """Records of asset revaluations."""
    
#     asset = models.ForeignKey(
#         FixedAsset,
#         on_delete=models.PROTECT,
#         related_name='revaluations'
#     )
#     revaluation_date = models.DateField()
#     previous_value = models.DecimalField(max_digits=14, decimal_places=2)
#     new_value = models.DecimalField(max_digits=14, decimal_places=2)
#     adjustment_amount = models.DecimalField(max_digits=14, decimal_places=2)
#     reason = models.TextField()
    
#     gl_entry = models.ForeignKey(
#         JournalEntry,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         related_name='asset_revaluations'
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         db_table = 'asset_revaluation'
#         verbose_name = 'Asset Revaluation'
#         verbose_name_plural = 'Asset Revaluations'
#         ordering = ['-revaluation_date']
    
#     def __str__(self):
#         return f"{self.asset.asset_number}: {self.previous_value} → {self.new_value}"
    
#     def save(self, *args, **kwargs):
#         self.adjustment_amount = self.new_value - self.previous_value
#         super().save(*args, **kwargs)


# class DepreciationRun(models.Model):
#     """
#     Batch depreciation run for a period.
#     Groups all depreciation entries for a month.
#     """
    
#     period_date = models.DateField(unique=True)
#     run_date = models.DateTimeField(auto_now_add=True)
#     total_depreciation = models.DecimalField(
#         max_digits=14,
#         decimal_places=2,
#         default=Decimal('0.00')
#     )
#     assets_processed = models.IntegerField(default=0)
#     is_posted = models.BooleanField(default=False)
#     posted_date = models.DateField(null=True, blank=True)
    
#     class Meta:
#         db_table = 'depreciation_run'
#         verbose_name = 'Depreciation Run'
#         verbose_name_plural = 'Depreciation Runs'
#         ordering = ['-period_date']
    
#     def __str__(self):
#         return f"Depreciation Run: {self.period_date.strftime('%B %Y')}"
    
#     @classmethod
#     @transaction.atomic
#     def run_depreciation(cls, period_date):
#         """
#         Calculate and create depreciation records for all active assets.
        
#         Args:
#             period_date: First day of the month to run depreciation for
#         Returns:
#             DepreciationRun: The created depreciation run record
#         """
#         # Check if already run for this period
#         if cls.objects.filter(period_date=period_date).exists():
#             raise ValidationError(f'Depreciation already run for {period_date}')
        
#         # Get all active assets
#         active_assets = FixedAsset.objects.filter(
#             status=FixedAsset.ACTIVE,
#             depreciation_start_date__lte=period_date
#         )
        
#         run = cls.objects.create(period_date=period_date)
#         total = Decimal('0.00')
#         count = 0
        
#         for asset in active_assets:
#             depreciation = asset.calculate_monthly_depreciation()
            
#             if depreciation > 0:
#                 new_accumulated = asset.accumulated_depreciation + depreciation
#                 new_book_value = asset.acquisition_cost - new_accumulated
                
#                 DepreciationSchedule.objects.create(
#                     asset=asset,
#                     period_date=period_date,
#                     depreciation_amount=depreciation,
#                     accumulated_depreciation=new_accumulated,
#                     book_value=new_book_value
#                 )
                
#                 total += depreciation
#                 count += 1
        
#         run.total_depreciation = total
#         run.assets_processed = count
#         run.save()
        
#         return run
    
#     @transaction.atomic
#     def post_all(self):
#         """Post all depreciation records for this run."""
#         if self.is_posted:
#             raise ValidationError('Depreciation run already posted')
        
#         schedules = DepreciationSchedule.objects.filter(
#             period_date=self.period_date,
#             is_posted=False
#         )
        
#         for schedule in schedules:
#             schedule.post()
        
#         self.is_posted = True
#         self.posted_date = timezone.now().date()
#         self.save()
        
#         return True
