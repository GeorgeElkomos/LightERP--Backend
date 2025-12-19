from django.db import models
from django.core.exceptions import ValidationError

# Create your models here.
class UnitOfMeasure(models.Model):
    """
    Unit of Measure (UoM) master data
    Examples: PCS, KG, M, L, BOX, CASE, etc.
    """
    code = models.CharField(max_length=10, unique=True, help_text="UoM code (e.g., PCS, KG)")
    name = models.CharField(max_length=50, help_text="Full name (e.g., Pieces, Kilograms)")
    description = models.TextField(blank=True, null=True)
    
    # UoM Type
    UOM_TYPES = [
        ('QUANTITY', 'Quantity'),
        ('WEIGHT', 'Weight'),
        ('LENGTH', 'Length'),
        ('AREA', 'Area'),
        ('VOLUME', 'Volume'),
    ]
    uom_type = models.CharField(max_length=20, choices=UOM_TYPES, default='QUANTITY')
    
    # Conversion (optional - for future use)
    # base_uom = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
    #                               help_text="Base UoM for conversion")
    # conversion_factor = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True,
    #                                        help_text="Multiply by this to convert to base UoM")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = 'Unit of Measure'
        verbose_name_plural = 'Units of Measure'
    
    def __str__(self):
        return f"{self.code} - {self.name}"



class catalogItem(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    code = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Override save to ensure clean is called"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    
    def get_short_description(self, max_length=100):
        """Return a shortened description"""
        if len(self.description) <= max_length:
            return self.description
        return f"{self.description[:max_length]}..."
    @classmethod
    def get_by_code(cls, code):
        """Get a catalog item by its code"""
        try:
            return cls.objects.get(code=code.upper())
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def search_by_name(cls, search_term):
        """Search catalog items by name (case-insensitive)"""
        return cls.objects.filter(name__icontains=search_term)
    
    class Meta:
        verbose_name = 'Catalog Item'
        verbose_name_plural = 'Catalog Items'
