"""
Business Partner Models
Handles unified business partner data with Customer and Supplier specializations.

IMPORTANT DESIGN PATTERN:
========================
BusinessPartner is a MANAGED BASE CLASS that should NEVER be directly created, 
updated, or deleted. All operations MUST go through Customer or Supplier classes.

Usage Examples:
--------------
# CORRECT - Create a customer
customer = Customer.objects.create(
    name="Acme Corp",
    email="contact@acme.com",
    phone="+1234567890",
    address_in_details="123 Main St"
)

# CORRECT - Create a supplier
supplier = Supplier.objects.create(
    name="Tech Supplies Inc",
    email="sales@techsupplies.com",
    vat_number="VAT123456"
)

# CORRECT - Update customer
customer.name = "Acme Corporation"
customer.email = "info@acme.com"
customer.save()

# CORRECT - Query customers
active_customers = Customer.objects.filter(is_active=True)

# WRONG - Don't do this!
# bp = BusinessPartner.objects.create(name="Test")  # This will raise an error!
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
    
    Fields:
        name: Business partner name (required)
        email: Contact email
        phone: Contact phone number
        country: Business partner's country
        address: Physical address
        notes: Internal notes
        is_active: Whether the business partner is active
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    
    Relationships:
        - customer: OneToOne relationship to Customer (if this BP is a customer)
        - supplier: OneToOne relationship to Supplier (if this BP is a supplier)
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
        # Check if this is being called from a child class (Customer/Supplier)
        # by looking at the call stack
        import inspect
        frame = inspect.currentframe()
        caller_locals = frame.f_back.f_locals
        
        # Allow save if it's being called from Customer or Supplier save method
        # or if _allow_direct_save flag is set
        if not getattr(self, '_allow_direct_save', False):
            # Check if caller is Customer or Supplier
            caller_self = caller_locals.get('self')
            if not isinstance(caller_self, (Customer, Supplier)):
                raise PermissionDenied(
                    "Cannot save BusinessPartner directly. "
                    "Use Customer or Supplier save() method instead."
                )
        
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
        Get the type of business partner (Customer, Supplier, or Both).
        
        Returns:
            str: 'Customer', 'Supplier', 'Both', or 'None'
        """
        is_customer = hasattr(self, 'customer') and self.customer is not None
        is_supplier = hasattr(self, 'supplier') and self.supplier is not None
        
        if is_customer and is_supplier:
            return 'Both'
        elif is_customer:
            return 'Customer'
        elif is_supplier:
            return 'Supplier'
        else:
            return 'None'

class CustomerManager(models.Manager):
    """
    Custom manager for Customer with convenience methods.
    """
    def create(self, **kwargs):
        """
        Create a new Customer along with its BusinessPartner.
        
        Automatically extracts BusinessPartner fields and creates both objects.
        """
        # Extract BusinessPartner fields
        bp_fields = {
            'name': kwargs.pop('name', ''),
            'email': kwargs.pop('email', ''),
            'phone': kwargs.pop('phone', ''),
            'country': kwargs.pop('country', None),
            'address': kwargs.pop('address', ''),
            'notes': kwargs.pop('notes', ''),
            'is_active': kwargs.pop('is_active', True),
        }
        
        # Create BusinessPartner (with permission)
        business_partner = BusinessPartner(**bp_fields)
        business_partner._allow_direct_save = True
        business_partner.save()
        
        # Create Customer with remaining fields
        kwargs['business_partner'] = business_partner
        customer = super().create(**kwargs)
        
        return customer
    
    def active(self):
        """Get all active customers."""
        return self.filter(business_partner__is_active=True)

class Customer(ProtectedDeleteMixin, models.Model):
    """
    Customer - represents a business partner who purchases from us.
    
    This class automatically manages the associated BusinessPartner instance.
    All BusinessPartner fields are accessible as properties on the Customer.
    
    Usage:
        # Create a customer
        customer = Customer.objects.create(
            name="Acme Corp",
            email="contact@acme.com",
            phone="+1234567890",
            address_in_details="Detailed delivery address"
        )
        
        # Update customer
        customer.name = "Acme Corporation"  # Updates BusinessPartner.name
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
    
    def save(self, *args, **kwargs):
        """
        Override save to handle BusinessPartner updates.
        """
        # If business_partner doesn't exist yet, create it
        if not self.business_partner_id:
            # This happens when creating via Customer() constructor instead of Customer.objects.create()
            raise ValidationError(
                "Use Customer.objects.create() instead of Customer() constructor. "
                "This ensures proper BusinessPartner creation."
            )
        
        # Update BusinessPartner if any of its fields were set on this Customer instance
        bp_fields = ['name', 'email', 'phone', 'country', 'address', 'notes', 'is_active']
        bp_updated = False
        
        for field in bp_fields:
            if hasattr(self, f'_{field}_temp'):
                setattr(self.business_partner, field, getattr(self, f'_{field}_temp'))
                delattr(self, f'_{field}_temp')
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
        super().delete(*args, **kwargs)
        
        # Delete BusinessPartner if it's not used by any other entity
        if not hasattr(business_partner, 'supplier'):
            business_partner._allow_direct_save = True
            # Use the parent class delete to bypass our restriction
            super(BusinessPartner, business_partner).delete(*args, **kwargs)
    
    # Property proxies for BusinessPartner fields (for easy access)
    @property
    def name(self):
        return self.business_partner.name
    
    @name.setter
    def name(self, value):
        self._name_temp = value
        if self.business_partner_id:
            self.business_partner.name = value
    
    @property
    def email(self):
        return self.business_partner.email
    
    @email.setter
    def email(self, value):
        self._email_temp = value
        if self.business_partner_id:
            self.business_partner.email = value
    
    @property
    def phone(self):
        return self.business_partner.phone
    
    @phone.setter
    def phone(self, value):
        self._phone_temp = value
        if self.business_partner_id:
            self.business_partner.phone = value
    
    @property
    def country(self):
        return self.business_partner.country
    
    @country.setter
    def country(self, value):
        self._country_temp = value
        if self.business_partner_id:
            self.business_partner.country = value
    
    @property
    def address(self):
        return self.business_partner.address
    
    @address.setter
    def address(self, value):
        self._address_temp = value
        if self.business_partner_id:
            self.business_partner.address = value
    
    @property
    def notes(self):
        return self.business_partner.notes
    
    @notes.setter
    def notes(self, value):
        self._notes_temp = value
        if self.business_partner_id:
            self.business_partner.notes = value
    
    @property
    def is_active(self):
        return self.business_partner.is_active
    
    @is_active.setter
    def is_active(self, value):
        self._is_active_temp = value
        if self.business_partner_id:
            self.business_partner.is_active = value

class SupplierManager(models.Manager):
    """
    Custom manager for Supplier with convenience methods.
    """
    def create(self, **kwargs):
        """
        Create a new Supplier along with its BusinessPartner.
        
        Automatically extracts BusinessPartner fields and creates both objects.
        """
        # Extract BusinessPartner fields
        bp_fields = {
            'name': kwargs.pop('name', ''),
            'email': kwargs.pop('email', ''),
            'phone': kwargs.pop('phone', ''),
            'country': kwargs.pop('country', None),
            'address': kwargs.pop('address', ''),
            'notes': kwargs.pop('notes', ''),
            'is_active': kwargs.pop('is_active', True),
        }
        
        # Create BusinessPartner (with permission)
        business_partner = BusinessPartner(**bp_fields)
        business_partner._allow_direct_save = True
        business_partner.save()
        
        # Create Supplier with remaining fields
        kwargs['business_partner'] = business_partner
        supplier = super().create(**kwargs)
        
        return supplier
    
    def active(self):
        """Get all active suppliers."""
        return self.filter(business_partner__is_active=True)

class Supplier(ProtectedDeleteMixin, models.Model):
    """
    Supplier/Vendor - represents a business partner who supplies to us.
    
    This class automatically manages the associated BusinessPartner instance.
    All BusinessPartner fields are accessible as properties on the Supplier.
    
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
    
    def save(self, *args, **kwargs):
        """
        Override save to handle BusinessPartner updates.
        """
        # If business_partner doesn't exist yet, create it
        if not self.business_partner_id:
            raise ValidationError(
                "Use Supplier.objects.create() instead of Supplier() constructor. "
                "This ensures proper BusinessPartner creation."
            )
        
        # Update BusinessPartner if any of its fields were set on this Supplier instance
        bp_fields = ['name', 'email', 'phone', 'country', 'address', 'notes', 'is_active']
        bp_updated = False
        
        for field in bp_fields:
            if hasattr(self, f'_{field}_temp'):
                setattr(self.business_partner, field, getattr(self, f'_{field}_temp'))
                delattr(self, f'_{field}_temp')
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
        super().delete(*args, **kwargs)
        
        # Delete BusinessPartner if it's not used by any other entity
        if not hasattr(business_partner, 'customer'):
            business_partner._allow_direct_save = True
            # Use the parent class delete to bypass our restriction
            super(BusinessPartner, business_partner).delete(*args, **kwargs)
    
    # Property proxies for BusinessPartner fields (for easy access)
    @property
    def name(self):
        return self.business_partner.name
    
    @name.setter
    def name(self, value):
        self._name_temp = value
        if self.business_partner_id:
            self.business_partner.name = value
    
    @property
    def email(self):
        return self.business_partner.email
    
    @email.setter
    def email(self, value):
        self._email_temp = value
        if self.business_partner_id:
            self.business_partner.email = value
    
    @property
    def phone(self):
        return self.business_partner.phone
    
    @phone.setter
    def phone(self, value):
        self._phone_temp = value
        if self.business_partner_id:
            self.business_partner.phone = value
    
    @property
    def country(self):
        return self.business_partner.country
    
    @country.setter
    def country(self, value):
        self._country_temp = value
        if self.business_partner_id:
            self.business_partner.country = value
    
    @property
    def address(self):
        return self.business_partner.address
    
    @address.setter
    def address(self, value):
        self._address_temp = value
        if self.business_partner_id:
            self.business_partner.address = value
    
    @property
    def notes(self):
        return self.business_partner.notes
    
    @notes.setter
    def notes(self, value):
        self._notes_temp = value
        if self.business_partner_id:
            self.business_partner.notes = value
    
    @property
    def is_active(self):
        return self.business_partner.is_active
    
    @is_active.setter
    def is_active(self, value):
        self._is_active_temp = value
        if self.business_partner_id:
            self.business_partner.is_active = value