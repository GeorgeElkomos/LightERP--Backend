"""
Finance Period Models

Simple period management for tracking transactions by date ranges.
Each period represents a time interval with open/closed states for different modules (AR, AP, GL).
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date


class Period(models.Model):
    """
    Period model - represents a fiscal period for transaction tracking.
    
    A period is a time interval (e.g., January 2026) that can be opened or closed
    for different accounting modules (AR, AP, GL) independently.
    """
    
    # Basic Information
    name = models.CharField(
        max_length=100,
        help_text="Period name (e.g., 'January 2026')"
    )
    start_date = models.DateField(
        help_text="Period start date"
    )
    end_date = models.DateField(
        help_text="Period end date"
    )
    
    # Fiscal Information
    fiscal_year = models.IntegerField(
        help_text="Fiscal year (e.g., 2026)"
    )
    period_number = models.IntegerField(
        help_text="Period number within fiscal year (1-13)"
    )
    
    # Optional Fields
    is_adjustment_period = models.BooleanField(
        default=False,
        help_text="True if this is an adjustment period (typically period 13)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description"
    )
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'finance_period'
        ordering = ['fiscal_year', 'period_number']
        unique_together = [['fiscal_year', 'period_number']]
        verbose_name = 'Period'
        verbose_name_plural = 'Periods'
        indexes = [
            models.Index(fields=['fiscal_year', 'period_number']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        """String representation"""
        return f"{self.name} (FY{self.fiscal_year}-P{self.period_number})"
    
    def save(self, *args, **kwargs):
        """
        Save the period and automatically ensure child records (AR, AP, GL) exist.
        
        - On creation: Child records are created with default 'closed' state
        - On update: Ensures children exist (creates if missing)
        - Changes to parent Period are automatically reflected in children via OneToOne relationship
        """
        # Save the period first
        super().save(*args, **kwargs)
        
        # Always ensure child records exist (create if missing, no-op if they exist)
        # This handles both new records and existing records that might be missing children
        ar_period.objects.get_or_create(
            period=self,
            defaults={'state': 'closed'}
        )
        
        ap_period.objects.get_or_create(
            period=self,
            defaults={'state': 'closed'}
        )
        
        gl_period.objects.get_or_create(
            period=self,
            defaults={'state': 'closed'}
        )
    
    def ensure_children_exist(self):
        """
        Helper method to manually ensure all child records exist.
        Useful for data migration or fixing missing children.
        """
        ar_period.objects.get_or_create(
            period=self,
            defaults={'state': 'closed'}
        )
        
        ap_period.objects.get_or_create(
            period=self,
            defaults={'state': 'closed'}
        )
        
        gl_period.objects.get_or_create(
            period=self,
            defaults={'state': 'closed'}
        )
        
        return True
    
    # ========================================================================
    # Class Method for Bulk Period Generation
    # ========================================================================
    
    @classmethod
    def create_list_of_periods(cls, start_date, fiscal_year, num_periods, 
                               num_adjustment_periods=0, adjustment_period_days=1):
        """
        Generate a list of Period objects for a full fiscal year (not saved to DB).
        
        This method creates a preview list of periods that can be reviewed, edited,
        and then saved by the user, or discarded in favor of manual creation.
        
        Args:
            start_date (date): Starting date for the first period
            fiscal_year (int): Fiscal year (e.g., 2026)
            num_periods (int): Number of regular periods (typically 12)
            num_adjustment_periods (int): Number of adjustment periods (default 0, typically 0-1)
            adjustment_period_days (int): Duration in days for adjustment periods (default 1)
            
        Returns:
            list: List of unsaved Period objects
            
        Example:
            # Generate 12 monthly periods + 1 adjustment period
            periods = Period.create_list_of_periods(
                start_date=date(2026, 1, 1),
                fiscal_year=2026,
                num_periods=12,
                num_adjustment_periods=1,
                adjustment_period_days=1
            )
            
            # Review and edit periods
            for period in periods:
                print(period.name, period.start_date, period.end_date)
            
            # Save all periods
            Period.objects.bulk_create(periods)
        """
        from datetime import timedelta
        from calendar import monthrange
        
        periods = []
        current_start = start_date
        
        # Month names for automatic naming
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        # Generate regular periods
        for period_num in range(1, num_periods + 1):
            # Calculate end date (last day of the month)
            year = current_start.year
            month = current_start.month
            last_day = monthrange(year, month)[1]
            period_end = date(year, month, last_day)
            
            # Generate period name
            month_name = month_names[month - 1] if month <= 12 else f"Period {period_num}"
            period_name = f"{month_name} {fiscal_year}"
            
            # Create period object (not saved)
            period = cls(
                name=period_name,
                start_date=current_start,
                end_date=period_end,
                fiscal_year=fiscal_year,
                period_number=period_num,
                is_adjustment_period=False,
                description=f"Regular period {period_num} of fiscal year {fiscal_year}"
            )
            periods.append(period)
            
            # Move to next month
            if month == 12:
                current_start = date(year + 1, 1, 1)
            else:
                current_start = date(year, month + 1, 1)
        
        # Generate adjustment periods
        for adj_num in range(1, num_adjustment_periods + 1):
            period_num = num_periods + adj_num
            
            # Adjustment periods typically use the last day of the fiscal year
            adj_start = periods[-1].end_date if periods else current_start
            adj_end = adj_start + timedelta(days=adjustment_period_days - 1)
            
            period_name = f"FY{fiscal_year} Adjustment Period {adj_num}"
            
            # Create adjustment period object (not saved)
            period = cls(
                name=period_name,
                start_date=adj_start,
                end_date=adj_end,
                fiscal_year=fiscal_year,
                period_number=period_num,
                is_adjustment_period=True,
                description=f"Adjustment period {adj_num} for fiscal year {fiscal_year}"
            )
            periods.append(period)
        
        return periods


class ar_period(models.Model):
    """
    AR Period model - extends Period with AR module state.
    """
    period = models.OneToOneField(
        Period,
        on_delete=models.CASCADE,
        related_name='ar_period'
    )
    state = models.CharField(
        max_length=10,
        choices=[('open', 'Open'), ('closed', 'Closed')],
        default='closed',
        help_text="State of the AR module for this period"
    )
    
    class Meta:
        db_table = 'finance_ar_period'
        verbose_name = 'AR Period'
        verbose_name_plural = 'AR Periods'
    
    def __str__(self):
        """String representation"""
        return f"AR Period: {self.period} - State: {self.state}"
class ap_period(models.Model):
    """
    AP Period model - extends Period with AP module state.
    """
    period = models.OneToOneField(
        Period,
        on_delete=models.CASCADE,
        related_name='ap_period'
    )
    state = models.CharField(
        max_length=10,
        choices=[('open', 'Open'), ('closed', 'Closed')],
        default='closed',
        help_text="State of the AP module for this period"
    )
    
    class Meta:
        db_table = 'finance_ap_period'
        verbose_name = 'AP Period'
        verbose_name_plural = 'AP Periods'
    
    def __str__(self):
        """String representation"""
        return f"AP Period: {self.period} - State: {self.state}"
class gl_period(models.Model):
    """
    GL Period model - extends Period with GL module state.
    """
    period = models.OneToOneField(
        Period,
        on_delete=models.CASCADE,
        related_name='gl_period'
    )
    state = models.CharField(
        max_length=10,
        choices=[('open', 'Open'), ('closed', 'Closed')],
        default='closed',
        help_text="State of the GL module for this period"
    )
    
    class Meta:
        db_table = 'finance_gl_period'
        verbose_name = 'GL Period'
        verbose_name_plural = 'GL Periods'
    
    def __str__(self):
        """String representation"""
        return f"GL Period: {self.period} - State: {self.state}"
