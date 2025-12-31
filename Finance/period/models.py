from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime


class Period(models.Model):
    # Core fields
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Financial period tracking
    fiscal_year = models.IntegerField(help_text="Fiscal year for this period")
    period_number = models.IntegerField(help_text="Sequential period number within the fiscal year (e.g., 1-12 for monthly)")
    
    # Status and control
    is_closed = models.BooleanField(default=False, help_text="Whether this period is closed for transactions")
    is_adjustment_period = models.BooleanField(default=False, help_text="13th period for year-end adjustments")
    
    # Closure tracking
    closed_date = models.DateTimeField(null=True, blank=True, help_text="Date and time when period was closed")
    closed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='closed_periods')
    
    # Additional information
    description = models.TextField(blank=True, help_text="Optional notes about this period")
    

    class Meta:
        db_table = 'period'
        ordering = ['fiscal_year', 'period_number']
        unique_together = [['fiscal_year', 'period_number']]
        indexes = [
            models.Index(fields=['fiscal_year', 'period_number']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['is_closed']),
        ]

    def __str__(self):
        return f"{self.name} (FY{self.fiscal_year})"
    
    def clean(self):
        """Validate period data"""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start date must be before or equal to end date")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def close_period(self, user):
        """
        Close this period to prevent further transactions.
        
        Args:
            user: The user closing the period
            
        Raises:
            ValidationError: If period is already closed
        """
        if self.is_closed:
            raise ValidationError(f"Period {self.name} is already closed")
        
        self.is_closed = True
        self.closed_date = timezone.now()
        self.closed_by = user
        self.save()
    
    def reopen_period(self):
        """
        Reopen a closed period to allow transactions again.
        
        Raises:
            ValidationError: If period is not closed
        """
        if not self.is_closed:
            raise ValidationError(f"Period {self.name} is not closed")
        
        self.is_closed = False
        self.closed_date = None
        self.closed_by = None
        self.save()
    
    def is_date_in_period(self, date):
        """
        Check if a given date falls within this period.
        
        Args:
            date: Date to check
            
        Returns:
            bool: True if date is within period range
        """
        return self.start_date <= date <= self.end_date
    
    def can_post_transaction(self):
        """
        Check if transactions can be posted to this period.
        
        Returns:
            bool: True if period is open for transactions
        """
        return not self.is_closed
    
    def get_duration_days(self):
        """
        Get the duration of the period in days.
        
        Returns:
            int: Number of days in the period
        """
        return (self.end_date - self.start_date).days + 1
    
    @classmethod
    def get_period_for_date(cls, date):
        """
        Find the period that contains a specific date.
        
        Args:
            date: Date to find period for
            
        Returns:
            Period: The period containing the date, or None if not found
        """
        return cls.objects.filter(
            start_date__lte=date,
            end_date__gte=date
        ).first()
    
    @classmethod
    def get_open_periods(cls):
        """
        Get all open periods that can accept transactions.
        
        Returns:
            QuerySet: All open periods
        """
        return cls.objects.filter(is_closed=False)
    
    @classmethod
    def get_periods_by_fiscal_year(cls, fiscal_year):
        """
        Get all periods for a specific fiscal year.
        
        Args:
            fiscal_year: The fiscal year to filter by
            
        Returns:
            QuerySet: All periods in the fiscal year
        """
        return cls.objects.filter(fiscal_year=fiscal_year).order_by('period_number')
    
    @classmethod
    def get_current_period(cls):
        """
        Get the period for today's date.
        
        Returns:
            Period: Current period or None if not found
        """
        return cls.get_period_for_date(timezone.now().date())
