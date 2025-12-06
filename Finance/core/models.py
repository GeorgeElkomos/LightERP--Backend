"""
Finance Core Models
Shared models used across all Finance sub-apps
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class ProtectedDeleteMixin:
    """
    Mixin to prevent deletion of model instances that are referenced by other models.
    
    This mixin dynamically discovers all foreign key references using Django's _meta API,
    so you never need to manually update the code when new models reference this one.
    
    Usage:
        class MyModel(ProtectedDeleteMixin, models.Model):
            # your fields here
            pass
    
    Customization:
        Override get_deletion_identifier() to customize the identifier shown in error messages.
    """
    
    def get_deletion_identifier(self):
        """
        Get a human-readable identifier for this instance to use in error messages.
        Override this method in your model to customize the identifier.
        
        Returns:
            str: A string identifying this instance (e.g., "USD", "AE - United Arab Emirates")
        """
        # Try common identifier fields in order of preference
        for field in ['code', 'name', 'pk']:
            if hasattr(self, field):
                value = getattr(self, field)
                if value:
                    return str(value)
        return str(self)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to prevent deletion if this instance is referenced by other models.
        Uses Django's meta API to dynamically discover all related objects.
        """
        # Get all related objects dynamically
        references = []
        
        # Get all reverse foreign key relations
        for related_object in self._meta.related_objects:
            # Get the related model and accessor name
            related_model = related_object.related_model
            accessor_name = related_object.get_accessor_name()
            
            try:
                # Get the related manager (e.g., self.journal_entries)
                related_manager = getattr(self, accessor_name)
                
                # Count related objects
                count = related_manager.count()
                
                if count > 0:
                    # Get a human-readable name for the related model
                    model_name = related_model._meta.verbose_name_plural or related_model.__name__
                    references.append(f"{model_name.title()} ({count} record(s))")
            except Exception:
                # Skip if there's any issue accessing the related objects
                pass
        
        # If there are any references, prevent deletion
        if references:
            identifier = self.get_deletion_identifier()
            model_name = self._meta.verbose_name or self.__class__.__name__
            
            raise ValidationError(
                f"Cannot delete {model_name} '{identifier}' because it is referenced by: "
                f"{', '.join(references)}. Please remove or update these references first."
            )
        
        # If no references, allow deletion
        super().delete(*args, **kwargs)



class Currency(ProtectedDeleteMixin, models.Model):
    """Currency master data"""
    code = models.CharField(max_length=3, unique=True)  # USD, EUR, etc.
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    is_base_currency = models.BooleanField(default=False)
    exchange_rate_to_base_currency = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    
    class Meta:
        verbose_name_plural = "Currencies"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def clean(self):
        """
        Validate that only one base currency exists.
        """
        # If this currency is being set as base currency
        if self.is_base_currency:
            # Check if another base currency already exists (excluding this instance)
            existing_base = Currency.objects.filter(is_base_currency=True).exclude(pk=self.pk)
            
            if existing_base.exists():
                raise ValidationError(
                    f"Cannot set {self.code} as base currency. "
                    f"{existing_base.first().code} is already set as the base currency. "
                    f"Please remove the base currency flag from {existing_base.first().code} first."
                )
        else:
            # If this is the current base currency being changed to non-base
            if self.pk:  # Only check if this is an existing record
                try:
                    old_instance = Currency.objects.get(pk=self.pk)
                    if old_instance.is_base_currency and not self.is_base_currency:
                        # Check if there are other currencies - we need at least one base currency
                        other_currencies = Currency.objects.exclude(pk=self.pk).exists()
                        if other_currencies:
                            raise ValidationError(
                                f"Cannot remove base currency flag from {self.code}. "
                                f"There must always be one base currency. "
                                f"Please set another currency as base currency first."
                            )
                except Currency.DoesNotExist:
                    pass
    
    def save(self, *args, **kwargs):
        """
        Override save to:
        1. Validate base currency rules
        2. Update exchange rates when base currency changes
        """
        # Run validation
        self.full_clean()
        
        # Check if this is a new base currency being set
        is_new_base_currency = False
        old_base_currency_code = None
        
        if self.pk:  # Existing record
            try:
                old_instance = Currency.objects.get(pk=self.pk)
                # Check if we're changing TO base currency
                if not old_instance.is_base_currency and self.is_base_currency:
                    is_new_base_currency = True
                    # Get the old base currency
                    old_base = Currency.objects.filter(is_base_currency=True).exclude(pk=self.pk).first()
                    if old_base:
                        old_base_currency_code = old_base.code
            except Currency.DoesNotExist:
                pass
        else:  # New record
            if self.is_base_currency:
                is_new_base_currency = True
        
        # If this is the base currency, set exchange rate to 1
        if self.is_base_currency:
            self.exchange_rate_to_base_currency = 1
        
        # Save the instance
        super().save(*args, **kwargs)
        
        # If we're setting a new base currency, update all other currencies' exchange rates
        if is_new_base_currency:
            self._update_all_exchange_rates(old_base_currency_code)
    
    def _update_all_exchange_rates(self, old_base_currency_code=None):
        """
        Update exchange rates for all currencies when base currency changes.
        
        Args:
            old_base_currency_code: The code of the previous base currency (if any)
        """
        # Get all currencies except this one (the new base)
        all_currencies = Currency.objects.exclude(pk=self.pk)
        
        for currency in all_currencies:
            # Fetch the exchange rate from API
            exchange_rate = self._fetch_exchange_rate_from_api(
                from_currency=currency.code,
                to_currency=self.code
            )
            
            # Update the currency's exchange rate
            currency.exchange_rate_to_base_currency = exchange_rate
            # Use update to avoid triggering save() recursion
            Currency.objects.filter(pk=currency.pk).update(
                exchange_rate_to_base_currency=exchange_rate,
                is_base_currency=False  # Ensure old base is no longer base
            )
    
    @staticmethod
    def _fetch_exchange_rate_from_api(from_currency, to_currency):
        """
        Fetch exchange rate from external API.
        
        Args:
            from_currency: Currency code to convert from (e.g., 'EUR')
            to_currency: Currency code to convert to (e.g., 'USD')
        
        Returns:
            Decimal: Exchange rate (1 unit of from_currency = X units of to_currency)
        
        Example:
            rate = _fetch_exchange_rate_from_api('EUR', 'USD')
            # Returns: Decimal('1.1000') meaning 1 EUR = 1.1 USD
        
        TODO: Implement actual API call to fetch exchange rates
        Possible APIs:
        - https://exchangerate-api.com/
        - https://openexchangerates.org/
        - https://fixer.io/
        - Central bank APIs
        """
        from decimal import Decimal
        
        # PLACEHOLDER: Return 1.0 for now
        # When implementing, replace this with actual API call
        # Example implementation:
        # import requests
        # response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{from_currency}')
        # data = response.json()
        # rate = Decimal(str(data['rates'][to_currency]))
        # return rate
        
        print(f"[PLACEHOLDER] Fetching exchange rate: {from_currency} -> {to_currency}")
        print(f"[TODO] Implement actual API call to get exchange rate")
        
        # Return 1.0 as placeholder
        return Decimal('1.0000')
    
    def convert_to_base_currency(self, amount):
        """
        Convert an amount in this currency to the base currency.
        
        Args:
            amount: The amount in this currency (Decimal or float)
        
        Returns:
            Decimal: The equivalent amount in the base currency
        
        Example:
            # If USD is base currency and EUR exchange_rate_to_base_currency = 1.1
            # (meaning 1 EUR = 1.1 USD)
            eur_currency = Currency.objects.get(code='EUR')
            amount_in_eur = Decimal('100.00')
            amount_in_usd = eur_currency.convert_to_base_currency(amount_in_eur)
            # Returns: Decimal('110.00')
            
            # If USD is base currency:
            usd_currency = Currency.objects.get(code='USD')
            amount_in_usd = Decimal('100.00')
            same_amount = usd_currency.convert_to_base_currency(amount_in_usd)
            # Returns: Decimal('100.00') (no conversion needed)
        """
        from decimal import Decimal
        
        # Convert amount to Decimal if it isn't already
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        # If this is the base currency, return the amount as-is
        if self.is_base_currency:
            return amount
        
        # Convert to base currency using the exchange rate
        # exchange_rate_to_base_currency represents: 1 unit of this currency = X units of base currency
        base_amount = amount * self.exchange_rate_to_base_currency
        
        return base_amount
    
class Country(ProtectedDeleteMixin, models.Model):
    code = models.CharField(max_length=2, unique=True)  # AE, SA, etc.
    name = models.CharField(max_length=100)
    class Meta:
        verbose_name_plural = "Countries"
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class TaxRate(ProtectedDeleteMixin, models.Model):
    CATEGORY_CHOICES = [
        ("STANDARD", "Standard"),
        ("ZERO", "Zero Rated"),
        ("EXEMPT", "Exempt"),
        ("RC", "Reverse Charge"),
    ]

    name = models.CharField(max_length=64)
    rate = models.DecimalField(max_digits=6, decimal_places=2, help_text="Percent (e.g. 5 = 5%)")
    # NEW:
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="tax_rates", default="AE")
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default="STANDARD")
    is_active = models.BooleanField(default=True, help_text="Is this rate currently active?")
  
    class Meta:
        indexes = [
           models.Index(fields=["country", "category"]),
          ]
        ordering = ['country', 'category']
        unique_together = (("country", "category"), )
    def __str__(self):
        return f"{self.country}-{self.category} {self.rate}%"
    
    def get_deletion_identifier(self):
        """Custom identifier for deletion error messages"""
        return f"{self.name} ({self.country}-{self.category})"

