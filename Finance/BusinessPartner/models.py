"""
Business Partner Models - DRY Pattern with Mixins
Handles unified business partner data with Customer and Supplier specializations.

IMPORTANT DESIGN PATTERN:
========================
BusinessPartner is a MANAGED BASE CLASS that should NEVER be directly created, 
updated, or deleted. All operations MUST go through Customer or Supplier classes.

The magic: Child classes automatically inherit ALL BusinessPartner fields as properties!
No need to manually define getters/setters - they're auto-generated!

Usage Examples:
--------------
# CORRECT - Create a customer
customer = Customer.objects.create(
    name="Acme Corp",
    email="contact@acme.com",
    phone="+1234567890",
    address_in_details="123 Main St"
)

# CORRECT - Update customer
customer.name = "Acme Corporation"
customer.email = "info@acme.com"
customer.save()  # Auto-updates BusinessPartner!

# Add new field to BusinessPartner? No changes needed in Customer/Supplier!
"""

from django.db import models
from django.core.exceptions import ValidationError, PermissionDenied
from Finance.core.models import Country, ProtectedDeleteMixin


class BusinessPartnerManager(models.Manager):
    """
    Custom manager for BusinessPartner that prevents direct creation.
    """
    def create(self, **kwargs):
        raise PermissionDenied(
            "Cannot create BusinessPartner directly. "
            "Use Customer.objects.create() or Supplier.objects.create() instead."
        )
    
    def bulk_create(self, objs, **kwargs):
        raise PermissionDenied(
            "Cannot bulk create BusinessPartner directly. "
            "Use Customer or Supplier models instead."
        )


class BusinessPartner(ProtectedDeleteMixin, models.Model):
    """
    Business Partner - MANAGED BASE CLASS (Interface-like)
    
    ⚠️ WARNING: Do NOT create, update, or delete BusinessPartner instances directly!
    
    This model serves as a shared data container for Customer and Supplier.
    All operations should be performed through Customer or Supplier classes,
    which will automatically manage the associated BusinessPartner instance.
    """
    
    # Core fields
    name = models.CharField(max_length=128)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    country = models.ForeignKey(
        Country, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        help_text="ISO 2-letter country code",
        related_name="business_partners"
    )
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text="Internal notes")
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    # Custom manager to prevent direct creation
    objects = BusinessPartnerManager()
    
    class Meta:
        db_table = 'business_partner'
        verbose_name = 'Business Partner'
        verbose_name_plural = 'Business Partners'
    
    def __str__(self):
        return f"{self.name}"
    
    def save(self, *args, **kwargs):
        """
        Override save to prevent direct saves unless called from Customer/Supplier.
        """
        # Allow save if _allow_direct_save flag is set
        if not getattr(self, '_allow_direct_save', False):
            raise PermissionDenied(
                "Cannot save BusinessPartner directly. "
                "Use Customer or Supplier save() method instead."
            )
        
        # Reset flag after use
        self._allow_direct_save = False
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to prevent direct deletion.
        """
        raise PermissionDenied(
            "Cannot delete BusinessPartner directly. "
            "Delete the associated Customer or Supplier instead."
        )
    
    def get_partner_type(self):
        """
        Get the type of business partner based on child relationships.
        Dynamically detects all OneToOne children.
        
        Returns:
            str: Comma-separated list of child types, or 'None' if no children
        """
        child_types = []
        
        # Dynamically find all OneToOne reverse relations (children)
        for related_object in self._meta.related_objects:
            if related_object.one_to_one:
                accessor_name = related_object.get_accessor_name()
                if hasattr(self, accessor_name):
                    # Get the child class name (e.g., 'Customer', 'Supplier')
                    child_types.append(related_object.related_model.__name__)
        
        if not child_types:
            return 'None'
        elif len(child_types) == 1:
            return child_types[0]
        else:
            return ', '.join(child_types)
    
    @classmethod
    def get_field_names(cls):
        """
        Get all field names from BusinessPartner.
        This is used by child classes to auto-generate properties.
        """
        return [field.name for field in cls._meta.get_fields() 
                if not field.many_to_many and not field.one_to_many 
                and field.name != 'id']


# ==================== BASE MANAGER MIXIN ====================

class BusinessPartnerChildManagerMixin:
    """
    Mixin for child business partner managers.
    Automatically extracts BusinessPartner fields from kwargs.
    """
    
    def create(self, **kwargs):
        """
        Create a new child partner along with its BusinessPartner.
        Automatically extracts BusinessPartner fields - NO MANUAL LISTING NEEDED!
        """
        # Get all BusinessPartner field names dynamically
        bp_field_names = BusinessPartner.get_field_names()
        
        # Extract BusinessPartner fields from kwargs
        bp_fields = {}
        for field_name in bp_field_names:
            if field_name in kwargs:
                bp_fields[field_name] = kwargs.pop(field_name)
        
        # Set defaults
        if 'is_active' not in bp_fields:
            bp_fields['is_active'] = True
        
        # Create BusinessPartner (with permission)
        business_partner = BusinessPartner(**bp_fields)
        business_partner._allow_direct_save = True
        business_partner.save()
        
        # Create child with remaining fields
        kwargs['business_partner'] = business_partner
        child = super().create(**kwargs)
        
        return child
    
    def active(self):
        """Get all active partners."""
        return self.filter(business_partner__is_active=True)


# ==================== BASE MODEL MIXIN ====================

class BusinessPartnerChildModelMixin:
    """
    Mixin for child business partner models.
    Automatically creates property proxies for ALL BusinessPartner fields.
    """
    
    def save(self, *args, **kwargs):
        """
        Override save to handle BusinessPartner updates automatically.
        """
        # If business_partner doesn't exist yet, raise error
        if not self.business_partner_id:
            raise ValidationError(
                f"Use {self.__class__.__name__}.objects.create() instead of "
                f"{self.__class__.__name__}() constructor. "
                "This ensures proper BusinessPartner creation."
            )
        
        # Get all BusinessPartner field names dynamically
        bp_field_names = BusinessPartner.get_field_names()
        
        # Update BusinessPartner if any of its fields were set
        bp_updated = False
        
        for field_name in bp_field_names:
            temp_attr = f'_{field_name}_temp'
            if hasattr(self, temp_attr):
                setattr(self.business_partner, field_name, getattr(self, temp_attr))
                delattr(self, temp_attr)
                bp_updated = True
        
        if bp_updated:
            self.business_partner._allow_direct_save = True
            self.business_partner.save()
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to also delete the associated BusinessPartner.
        """
        business_partner = self.business_partner
        
        # Delete the child first
        super().delete(*args, **kwargs)
        
        # After deletion, check if BusinessPartner still has other children
        # Dynamically check for any OneToOne relationships (children)
        try:
            business_partner.refresh_from_db()
            
            # Get all OneToOne reverse relations (children)
            has_children = False
            for related_object in business_partner._meta.related_objects:
                if related_object.one_to_one:
                    # Check if this child still exists
                    if hasattr(business_partner, related_object.get_accessor_name()):
                        has_children = True
                        break
            
            # If no children left, delete the BusinessPartner
            if not has_children:
                business_partner._allow_direct_save = True
                super(BusinessPartner, business_partner).delete(*args, **kwargs)
        except BusinessPartner.DoesNotExist:
            # Already deleted, nothing to do
            pass

    def __init__(self, *args, **kwargs):
        """
        Override __init__ to dynamically create property proxies.
        """
        super().__init__(*args, **kwargs)
        
        # Dynamically create property proxies for all BusinessPartner fields
        if not hasattr(self.__class__, '_properties_created'):
            self.__class__._create_bp_properties()
            self.__class__._properties_created = True
    
    @classmethod
    def _create_bp_properties(cls):
        """
        Dynamically create property proxies for all BusinessPartner fields.
        This runs once per class and creates properties for ALL fields automatically!
        """
        bp_field_names = BusinessPartner.get_field_names()
        
        for field_name in bp_field_names:
            # Skip if property already exists
            if hasattr(cls, field_name):
                continue
            
            # Create getter and setter functions
            def make_property(fname):
                def getter(self):
                    return getattr(self.business_partner, fname)
                
                def setter(self, value):
                    setattr(self, f'_{fname}_temp', value)
                    if self.business_partner_id:
                        setattr(self.business_partner, fname, value)
                
                return property(getter, setter)
            
            # Add property to class
            setattr(cls, field_name, make_property(field_name))


# ==================== CUSTOMER ====================

class CustomerManager(BusinessPartnerChildManagerMixin, models.Manager):
    """
    Custom manager for Customer - inherits all auto-magic from mixin!
    """
    pass


class Customer(BusinessPartnerChildModelMixin, ProtectedDeleteMixin, models.Model):
    """
    Customer - represents a business partner who purchases from us.
    
    ALL BusinessPartner fields are automatically available as properties!
    No need to manually define them - they're auto-generated!
    
    Usage:
        # Create a customer
        customer = Customer.objects.create(
            name="Acme Corp",
            email="contact@acme.com",
            phone="+1234567890",
            address_in_details="123 Main St"
        )
        
        # Update customer
        customer.name = "Acme Corporation"
        customer.save()
        
        # Access BusinessPartner fields
        print(customer.name)  # Proxied from business_partner.name
        print(customer.email)  # Proxied from business_partner.email
    """
    
    business_partner = models.OneToOneField(
        BusinessPartner, 
        on_delete=models.PROTECT, 
        related_name="customer"
    )
    
    # Customer-specific fields
    address_in_details = models.TextField(blank=True, help_text="Detailed delivery address")
    
    # Custom manager
    objects = CustomerManager()
    
    class Meta:
        db_table = 'customer'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
    
    def __str__(self):
        return f"{self.business_partner.name}"


# ==================== SUPPLIER ====================

class SupplierManager(BusinessPartnerChildManagerMixin, models.Manager):
    """
    Custom manager for Supplier - inherits all auto-magic from mixin!
    """
    pass


class Supplier(BusinessPartnerChildModelMixin, ProtectedDeleteMixin, models.Model):
    """
    Supplier/Vendor - represents a business partner who supplies to us.
    
    ALL BusinessPartner fields are automatically available as properties!
    
    Usage:
        # Create a supplier
        supplier = Supplier.objects.create(
            name="Tech Supplies Inc",
            email="sales@techsupplies.com",
            vat_number="VAT123456",
            website="https://techsupplies.com"
        )
        
        # Update supplier
        supplier.name = "Tech Supplies International"
        supplier.save()
        
        # Access BusinessPartner fields
        print(supplier.name)  # Proxied from business_partner.name
        print(supplier.email)  # Proxied from business_partner.email
    """
    
    business_partner = models.OneToOneField(
        BusinessPartner, 
        on_delete=models.PROTECT, 
        related_name="supplier"
    )
    
    # Supplier-specific fields
    website = models.URLField(blank=True)
    vat_number = models.CharField(max_length=50, blank=True, help_text="VAT/Tax registration number (TRN)")
    tax_id = models.CharField(max_length=50, blank=True, help_text="Alternative tax ID")
    
    # Custom manager
    objects = SupplierManager()
    
    class Meta:
        db_table = 'supplier'
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
    
    def __str__(self):
        return f"{self.business_partner.name}"