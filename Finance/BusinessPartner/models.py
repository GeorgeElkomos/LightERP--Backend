"""
Business Partner Models - Using Generic Base Pattern
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
from Finance.core.models import Country, ProtectedDeleteMixin
from Finance.core.base_models import (
    ManagedParentModel,
    ManagedParentManager,
    ChildModelManagerMixin,
    ChildModelMixin
)



class BusinessPartner(ManagedParentModel, ProtectedDeleteMixin, models.Model):
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
    objects = ManagedParentManager()
    
    class Meta:
        db_table = 'business_partner'
        verbose_name = 'Business Partner'
        verbose_name_plural = 'Business Partners'
    
    def __str__(self):
        return f"{self.name}"
    
    def get_partner_type(self):
        """
        Get the type of business partner based on child relationships.
        Alias for get_child_types() for backward compatibility.
        """
        return self.get_child_types()



# ==================== CUSTOMER ====================

class CustomerManager(ChildModelManagerMixin, models.Manager):
    """Manager for Customer - uses generic pattern!"""
    parent_model = BusinessPartner
    parent_defaults = {'is_active': True}


class Customer(ChildModelMixin, ProtectedDeleteMixin, models.Model):
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
    
    # Configuration for generic pattern
    parent_model = BusinessPartner
    parent_field_name = 'business_partner'
    
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

class SupplierManager(ChildModelManagerMixin, models.Manager):
    """Manager for Supplier - uses generic pattern!"""
    parent_model = BusinessPartner
    parent_defaults = {'is_active': True}


class Supplier(ChildModelMixin, ProtectedDeleteMixin, models.Model):
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
    
    # Configuration for generic pattern
    parent_model = BusinessPartner
    parent_field_name = 'business_partner'
    
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


# ==================== ONE TIME SUPPLIER ====================
class OneTimeManager(ChildModelManagerMixin, models.Manager):
    """Manager for OneTime - uses generic pattern!"""
    parent_model = BusinessPartner
    parent_defaults = {'is_active': True}


class OneTime(ChildModelMixin, ProtectedDeleteMixin, models.Model):
    """
    One Time - represents a business partner who supplies to us.
    
    ALL BusinessPartner fields are automatically available as properties!
    
    Usage:
        # Create a one-time supplier
        one_time_supplier = OneTime.objects.create(
            name="Tech Supplies Inc",
            email="sales@techsupplies.com",
            vat_number="VAT123456",
            website="https://techsupplies.com"
        )
        
        # Update one-time supplier
        one_time_supplier.name = "Tech Supplies International"
        one_time_supplier.save()
        
        # Access BusinessPartner fields
        print(one_time_supplier.name)  # Proxied from business_partner.name
        print(one_time_supplier.email)  # Proxied from business_partner.email
    """
    
    # Configuration for generic pattern
    parent_model = BusinessPartner
    parent_field_name = 'business_partner'
    
    business_partner = models.OneToOneField(
        BusinessPartner, 
        on_delete=models.PROTECT, 
        related_name="one_time_supplier"
    )
    
    # OneTime-specific fields
    tax_id = models.CharField(max_length=50, blank=True, help_text="Tax ID/VAT number")
    

    # Custom manager
    objects = OneTimeManager()
    
    class Meta:
        db_table = 'one_time_supplier'
        verbose_name = 'One Time Supplier'
        verbose_name_plural = 'One Time Suppliers'
    
    def __str__(self):
        return f"{self.business_partner.name}"
