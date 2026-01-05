"""
Period Validation Utilities

Centralized validation for period-based posting controls.
Ensures transactions are only created/posted during open periods.
"""
from django.core.exceptions import ValidationError
from datetime import date


class PeriodValidator:
    """
    Centralized period validation for transactional modules.
    
    Validates that transactions occur within open periods for the appropriate
    module (AR, AP, or GL). Prevents posting to closed periods.
    """
    
    @staticmethod
    def validate_ar_period_open(transaction_date):
        """
        Validate that an AR period is open for the given transaction date.
        
        Args:
            transaction_date: The date of the AR transaction (invoice date)
        
        Returns:
            Period: The matching period if validation passes
        
        Raises:
            ValidationError: If no period found or period is closed
        """
        from Finance.period.models import Period
        
        # Ensure transaction_date is a date object
        if isinstance(transaction_date, str):
            from datetime import datetime
            transaction_date = datetime.fromisoformat(transaction_date).date()
        
        # Find period containing this date
        period = Period.objects.filter(
            start_date__lte=transaction_date,
            end_date__gte=transaction_date
        ).select_related('ar_period').first()
        
        if not period:
            raise ValidationError(
                f"No accounting period found for date {transaction_date}. "
                f"Please contact your accounting administrator to set up periods."
            )
        
        # Check if AR period is open
        if period.ar_period.state != 'open':
            raise ValidationError(
                f"AR Period '{period.name}' (FY{period.fiscal_year}-P{period.period_number}) is closed. "
                f"Cannot create AR transactions for date {transaction_date}. "
                f"Contact your accounting administrator to reopen this period."
            )
        
        return period
    
    @staticmethod
    def validate_ap_period_open(transaction_date):
        """
        Validate that an AP period is open for the given transaction date.
        
        Args:
            transaction_date: The date of the AP transaction (invoice date)
        
        Returns:
            Period: The matching period if validation passes
        
        Raises:
            ValidationError: If no period found or period is closed
        """
        from Finance.period.models import Period
        
        # Ensure transaction_date is a date object
        if isinstance(transaction_date, str):
            from datetime import datetime
            transaction_date = datetime.fromisoformat(transaction_date).date()
        
        # Find period containing this date
        period = Period.objects.filter(
            start_date__lte=transaction_date,
            end_date__gte=transaction_date
        ).select_related('ap_period').first()
        
        if not period:
            raise ValidationError(
                f"No accounting period found for date {transaction_date}. "
                f"Please contact your accounting administrator to set up periods."
            )
        
        # Check if AP period is open
        if period.ap_period.state != 'open':
            raise ValidationError(
                f"AP Period '{period.name}' (FY{period.fiscal_year}-P{period.period_number}) is closed. "
                f"Cannot create AP transactions for date {transaction_date}. "
                f"Contact your accounting administrator to reopen this period."
            )
        
        return period
    
    @staticmethod
    def validate_gl_period_open(transaction_date, allow_adjustment=False):
        """
        Validate that a GL period is open for the given transaction date.
        
        Args:
            transaction_date: The date of the GL transaction (journal entry date or posting date)
            allow_adjustment: If True, allows posting to adjustment periods (for manual journal entries)
        
        Returns:
            Period: The matching period if validation passes
        
        Raises:
            ValidationError: If no period found or period is closed
        """
        from Finance.period.models import Period
        
        # Ensure transaction_date is a date object
        if isinstance(transaction_date, str):
            from datetime import datetime
            transaction_date = datetime.fromisoformat(transaction_date).date()
        
        # Find period containing this date
        period = Period.objects.filter(
            start_date__lte=transaction_date,
            end_date__gte=transaction_date
        ).select_related('gl_period').first()
        
        if not period:
            raise ValidationError(
                f"No accounting period found for date {transaction_date}. "
                f"Please contact your accounting administrator to set up periods."
            )
        
        # Check if GL period is open
        if period.gl_period.state != 'open':
            # Special handling for adjustment periods
            if allow_adjustment and period.is_adjustment_period:
                period_type = "Adjustment Period"
            else:
                period_type = "GL Period"
            
            raise ValidationError(
                f"{period_type} '{period.name}' (FY{period.fiscal_year}-P{period.period_number}) is closed. "
                f"Cannot post GL transactions for date {transaction_date}. "
                f"Contact your accounting administrator to reopen this period."
            )
        
        return period
    
    @staticmethod
    def get_open_periods(module_type='gl', fiscal_year=None):
        """
        Get list of open periods for a specific module.
        
        Args:
            module_type: 'ar', 'ap', or 'gl'
            fiscal_year: Optional fiscal year filter
        
        Returns:
            QuerySet of Period objects with open status for the specified module
        """
        from Finance.period.models import Period
        
        queryset = Period.objects.all()
        
        if fiscal_year:
            queryset = queryset.filter(fiscal_year=fiscal_year)
        
        # Filter by module type
        if module_type == 'ar':
            queryset = queryset.filter(ar_period__state='open').select_related('ar_period')
        elif module_type == 'ap':
            queryset = queryset.filter(ap_period__state='open').select_related('ap_period')
        elif module_type == 'gl':
            queryset = queryset.filter(gl_period__state='open').select_related('gl_period')
        
        return queryset.order_by('fiscal_year', 'period_number')
    
    @staticmethod
    def get_period_for_date(transaction_date):
        """
        Get the period containing a specific date (regardless of state).
        
        Args:
            transaction_date: The date to find a period for
        
        Returns:
            Period or None
        """
        from Finance.period.models import Period
        
        # Ensure transaction_date is a date object
        if isinstance(transaction_date, str):
            from datetime import datetime
            transaction_date = datetime.fromisoformat(transaction_date).date()
        
        return Period.objects.filter(
            start_date__lte=transaction_date,
            end_date__gte=transaction_date
        ).select_related('ar_period', 'ap_period', 'gl_period').first()
