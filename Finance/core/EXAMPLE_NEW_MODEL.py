"""
Example: Creating a New Parent-Child Model Using the Generic Base Pattern

This example shows how to create a new "Product" system with:
- Product (parent) - shared product data
- InventoryProduct (child) - products we stock
- ServiceProduct (child) - services we offer
- DigitalProduct (child) - digital/downloadable products
"""

from django.db import models
from Finance.core.base_models import (
    ManagedParentModel,
    ManagedParentManager,
    ChildModelManagerMixin,
    ChildModelMixin
)


# ==================== STEP 1: PARENT MODEL ====================

class Product(ManagedParentModel, models.Model):
    """
    Product - MANAGED BASE CLASS
    
    ⚠️ Do NOT create, update, or delete directly!
    Use child models: InventoryProduct, ServiceProduct, or DigitalProduct.
    """
    
    # Shared fields for all product types
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=50, unique=True, help_text="Stock Keeping Unit")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Required: ManagedParentManager prevents direct creation
    objects = ManagedParentManager()
    
    class Meta:
        db_table = 'product'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
    
    def __str__(self):
        return f"{self.sku} - {self.name}"


# ==================== STEP 2: CHILD MANAGERS ====================

class InventoryProductManager(ChildModelManagerMixin, models.Manager):
    """Manager for InventoryProduct"""
    
    # Required: Specify parent model
    parent_model = Product
    
    # Optional: Provide defaults for parent fields
    parent_defaults = {
        'is_active': True
    }
    
    # Optional: Add custom queryset methods
    def low_stock(self, threshold=10):
        """Get products with stock below threshold."""
        return self.filter(quantity_on_hand__lt=threshold)


class ServiceProductManager(ChildModelManagerMixin, models.Manager):
    """Manager for ServiceProduct"""
    parent_model = Product
    parent_defaults = {'is_active': True}
    
    def hourly_billed(self):
        """Get services billed hourly."""
        return self.filter(billing_type='HOURLY')


class DigitalProductManager(ChildModelManagerMixin, models.Manager):
    """Manager for DigitalProduct"""
    parent_model = Product
    parent_defaults = {'is_active': True}
    
    def downloadable(self):
        """Get products that are downloadable."""
        return self.filter(is_downloadable=True)


# ==================== STEP 3: CHILD MODELS ====================

class InventoryProduct(ChildModelMixin, models.Model):
    """
    Inventory Product - physical products we stock.
    
    ALL Product fields are automatically available as properties!
    """
    
    # Required: Configuration
    parent_model = Product
    parent_field_name = 'product'
    
    # Required: Relationship to parent
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='inventory_product'
    )
    
    # Child-specific fields
    quantity_on_hand = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)
    warehouse_location = models.CharField(max_length=100, blank=True)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Required: Custom manager
    objects = InventoryProductManager()
    
    class Meta:
        db_table = 'inventory_product'
        verbose_name = 'Inventory Product'
        verbose_name_plural = 'Inventory Products'
    
    def __str__(self):
        return f"Inventory: {self.name}"  # 'name' auto-proxied from Product!
    
    def needs_reorder(self):
        """Check if product needs reordering."""
        return self.quantity_on_hand <= self.reorder_level


class ServiceProduct(ChildModelMixin, models.Model):
    """
    Service Product - services we offer.
    
    ALL Product fields are automatically available as properties!
    """
    
    # Required: Configuration
    parent_model = Product
    parent_field_name = 'product'
    
    # Required: Relationship to parent
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='service_product'
    )
    
    # Child-specific fields
    HOURLY = 'HOURLY'
    FIXED = 'FIXED'
    BILLING_TYPES = [
        (HOURLY, 'Hourly'),
        (FIXED, 'Fixed Price'),
    ]
    
    billing_type = models.CharField(max_length=10, choices=BILLING_TYPES, default=FIXED)
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Required: Custom manager
    objects = ServiceProductManager()
    
    class Meta:
        db_table = 'service_product'
        verbose_name = 'Service Product'
        verbose_name_plural = 'Service Products'
    
    def __str__(self):
        return f"Service: {self.name}"


class DigitalProduct(ChildModelMixin, models.Model):
    """
    Digital Product - digital/downloadable products.
    
    ALL Product fields are automatically available as properties!
    """
    
    # Required: Configuration
    parent_model = Product
    parent_field_name = 'product'
    
    # Required: Relationship to parent
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='digital_product'
    )
    
    # Child-specific fields
    download_url = models.URLField(blank=True)
    file_size_mb = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_downloadable = models.BooleanField(default=True)
    license_key_required = models.BooleanField(default=False)
    
    # Required: Custom manager
    objects = DigitalProductManager()
    
    class Meta:
        db_table = 'digital_product'
        verbose_name = 'Digital Product'
        verbose_name_plural = 'Digital Products'
    
    def __str__(self):
        return f"Digital: {self.name}"


# ==================== USAGE EXAMPLES ====================

"""
# ✅ CORRECT - Create through child models

# Create an inventory product
laptop = InventoryProduct.objects.create(
    # Product fields (auto-handled!)
    name="Dell Laptop XPS 15",
    sku="LAPTOP-001",
    price=1299.99,
    description="High-performance laptop",
    # InventoryProduct fields
    quantity_on_hand=50,
    reorder_level=10,
    warehouse_location="A-12-3",
    weight_kg=2.5
)

# Create a service product
consulting = ServiceProduct.objects.create(
    # Product fields
    name="IT Consulting",
    sku="SVC-CONSULT",
    price=150.00,
    description="Hourly IT consulting",
    # ServiceProduct fields
    billing_type='HOURLY',
    estimated_hours=None  # Varies per project
)

# Create a digital product
ebook = DigitalProduct.objects.create(
    # Product fields
    name="Python Programming Guide",
    sku="EBOOK-PY001",
    price=29.99,
    description="Comprehensive Python guide",
    # DigitalProduct fields
    download_url="https://example.com/downloads/python-guide.pdf",
    file_size_mb=5.2,
    is_downloadable=True,
    license_key_required=False
)


# ✅ READ - All Product fields are accessible!

print(laptop.name)        # Auto-proxied from product.name
print(laptop.price)       # Auto-proxied from product.price
print(laptop.is_active)   # Auto-proxied from product.is_active
print(laptop.quantity_on_hand)  # InventoryProduct field


# ✅ UPDATE - Works seamlessly

laptop.name = "Dell XPS 15 (2024)"
laptop.price = 1399.99
laptop.quantity_on_hand = 45
laptop.save()  # Auto-updates Product!


# ✅ DELETE - Deletes child and parent

laptop.delete()  # Also deletes associated Product


# ✅ QUERYSETS - Use custom manager methods

low_stock_items = InventoryProduct.objects.low_stock(threshold=15)
hourly_services = ServiceProduct.objects.hourly_billed()
downloadable = DigitalProduct.objects.downloadable()
active_inventory = InventoryProduct.objects.active()  # Built-in!


# ❌ WRONG - Do NOT create Product directly!

product = Product.objects.create(name="Test")  # PermissionDenied!
laptop.product.name = "New Name"
laptop.product.save()  # PermissionDenied!
laptop.product.delete()  # PermissionDenied!
"""

