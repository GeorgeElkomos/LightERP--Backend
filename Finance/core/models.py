"""
Finance Core Models
Shared models used across all Finance sub-apps
"""
from django.db import models
from django.contrib.auth.models import User


class Currency(models.Model):
    """Currency master data"""
    code = models.CharField(max_length=3, unique=True)  # USD, EUR, etc.
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    is_base_currency = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "Currencies"
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class country(models.Model):
    code = models.CharField(max_length=2, unique=True)  # AE, SA, etc.
    name = models.CharField(max_length=100)
    
    class Meta:
        verbose_name_plural = "Countries"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    

class TaxRate(models.Model):
    CATEGORY_CHOICES = [
        ("STANDARD", "Standard"),
        ("ZERO", "Zero Rated"),
        ("EXEMPT", "Exempt"),
        ("RC", "Reverse Charge"),
    ]

    name = models.CharField(max_length=64)
    rate = models.DecimalField(max_digits=6, decimal_places=3, help_text="Percent (e.g. 5 = 5%)")
    # NEW:
    country = models.ForeignKey(country, on_delete=models.PROTECT, related_name="tax_rates", default="AE")
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default="STANDARD")
    is_active = models.BooleanField(default=True, help_text="Is this rate currently active?")
  
    class Meta:
        indexes = [
           models.Index(fields=["country", "category", "code"]),
          ]
        ordering = ['country', 'category', 'code']
        unique_together = (("country", "category", "code"), )
    def __str__(self):
        return f"{self.country}-{self.category} {self.rate}%"


class ExchangeRate(models.Model):
    from_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="rates_from")
    to_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="rates_to")
    rate_date = models.DateField(db_index=True, help_text="Date this rate is effective")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-rate_date', 'from_currency', 'to_currency']
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', '-rate_date', 'is_active']),
        ]
        unique_together = [('from_currency', 'to_currency', 'rate_date')]
    
    def __str__(self):
        return f"{self.from_currency.code}/{self.to_currency.code} on {self.rate_date}"

