"""
Generic Base Model Pattern - Reusable Architecture for Parent-Child Models

This module provides a dynamic, DRY pattern for creating "managed base class" 
architectures where:
1. Parent models store shared data but cannot be directly manipulated
2. Child models automatically proxy all parent fields as properties
3. All CRUD operations go through child models

Usage Example:
--------------
# Define your parent model
class Invoice(ManagedParentModel, models.Model):
    date = models.DateField()
    total = models.DecimalField(max_digits=14, decimal_places=2)
    
    objects = ManagedParentManager()
    
    class Meta:
        db_table = 'invoice'

# Define your child manager
class AP_InvoiceManager(ChildModelManagerMixin, models.Manager):
    parent_model = Invoice  # Specify the parent model
    
# Define your child model
class AP_Invoice(ChildModelMixin, models.Model):
    parent_model = Invoice  # Specify the parent model
    parent_field_name = 'invoice'  # Name of the FK/OneToOne field
    
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, primary_key=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    
    objects = AP_InvoiceManager()

# Now use it!
ap_invoice = AP_Invoice.objects.create(
    date=date.today(),  # Auto-handled!
    total=1000.00,      # Auto-handled!
    supplier=supplier
)
"""

from django.db import models
from django.core.exceptions import ValidationError, PermissionDenied


# ==================== PARENT MODEL COMPONENTS ====================

class ManagedParentManager(models.Manager):
    """
    Generic manager for managed parent models.
    Prevents direct creation of parent instances.
    """
    def create(self, **kwargs):
        model_name = self.model.__name__
        raise PermissionDenied(
            f"Cannot create {model_name} directly. "
            f"Use a child model's .objects.create() method instead."
        )
    
    def bulk_create(self, objs, **kwargs):
        model_name = self.model.__name__
        raise PermissionDenied(
            f"Cannot bulk create {model_name} directly. "
            f"Use child models instead."
        )


class ManagedParentModel(models.Model):
    """
    Base class for managed parent models.
    
    Provides:
    - Protection against direct save/delete operations
    - Dynamic field name extraction for child models
    - Automatic child type detection
    
    Usage:
        class YourParentModel(ManagedParentModel, models.Model):
            # Your fields here
            objects = ManagedParentManager()
            
            class Meta:
                abstract = False  # NOT abstract!
    """
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Override save to prevent direct saves unless called from child class."""
        if not getattr(self, '_allow_direct_save', False):
            raise PermissionDenied(
                f"Cannot save {self.__class__.__name__} directly. "
                f"Use child class save() method instead."
            )
        
        # Reset flag after use
        self._allow_direct_save = False
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to prevent direct deletion."""
        raise PermissionDenied(
            f"Cannot delete {self.__class__.__name__} directly. "
            f"Delete the associated child instance instead."
        )
    
    @classmethod
    def get_field_names(cls):
        """
        Get all field names from this parent model.
        Used by child classes to auto-generate properties.
        
        Returns:
            list: Field names excluding id, many-to-many, and reverse relations
        """
        return [field.name for field in cls._meta.get_fields() 
                if not field.many_to_many 
                and not field.one_to_many 
                and field.name != 'id']
    
    @classmethod
    def get_method_names(cls):
        """
        Get all public method names from this parent model.
        Used by child classes to auto-generate method proxies.
        
        Returns:
            list: Method names (excluding private/protected methods and Django internals)
        """
        # Get all attributes
        methods = []
        for attr_name in dir(cls):
            # Skip private/protected attributes
            if attr_name.startswith('_'):
                continue
            # Skip Django internal methods
            if attr_name in ['DoesNotExist', 'MultipleObjectsReturned', 'delete', 'save', 
                            'get_field_names', 'get_method_names', 'get_child_types',
                            'clean', 'clean_fields', 'full_clean', 'validate_unique',
                            'refresh_from_db', 'serializable_value', 'get_deferred_fields',
                            'check', 'from_db', 'prepare_database_save']:
                continue
            
            attr = getattr(cls, attr_name)
            # Check if it's a callable method (not a field or property)
            if callable(attr) and not isinstance(attr, property):
                methods.append(attr_name)
        
        return methods
    
    def get_child_types(self):
        """
        Dynamically detect all child types attached to this parent instance.
        
        Returns:
            str: Comma-separated list of child class names, or 'None' if no children
        """
        child_types = []
        
        # Dynamically find all OneToOne reverse relations (children)
        for related_object in self._meta.related_objects:
            if related_object.one_to_one or related_object.many_to_one:
                accessor_name = related_object.get_accessor_name()
                if hasattr(self, accessor_name):
                    # Get the child class name
                    child_types.append(related_object.related_model.__name__)
        
        if not child_types:
            return 'None'
        elif len(child_types) == 1:
            return child_types[0]
        else:
            return ', '.join(child_types)


# ==================== CHILD MODEL COMPONENTS ====================

class ChildModelManagerMixin:
    """
    Mixin for child model managers.
    Automatically extracts parent fields from kwargs and creates parent instance.
    
    Required class attributes:
        parent_model: The parent model class (e.g., Invoice, BusinessPartner)
    
    Optional class attributes:
        parent_defaults: Dict of default values for parent fields
        
    Usage:
        class AP_InvoiceManager(ChildModelManagerMixin, models.Manager):
            parent_model = Invoice
            parent_defaults = {'approval_status': 'DRAFT'}
    """
    
    parent_model = None  # Must be set by subclass
    parent_defaults = {}  # Optional defaults
    
    def create(self, **kwargs):
        """
        Create a new child instance along with its parent.
        Automatically extracts parent fields - NO MANUAL LISTING NEEDED!
        """
        if self.parent_model is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must set 'parent_model' class attribute"
            )
        
        # Get all parent field names dynamically
        parent_field_names = self.parent_model.get_field_names()
        
        # Extract parent fields from kwargs
        parent_fields = {}
        for field_name in parent_field_names:
            if field_name in kwargs:
                parent_fields[field_name] = kwargs.pop(field_name)
        
        # Apply defaults
        for key, value in self.parent_defaults.items():
            if key not in parent_fields:
                parent_fields[key] = value
        
        # Create parent (with permission)
        parent = self.parent_model(**parent_fields)
        parent._allow_direct_save = True
        parent.save()
        
        # Determine parent field name (usually the lowercase model name)
        parent_field_name = self._get_parent_field_name()
        
        # Create child with remaining fields
        kwargs[parent_field_name] = parent
        child = super().create(**kwargs)
        
        return child
    
    def active(self):
        """
        Default active() method - filters by is_active field if it exists.
        Override in subclass for custom behavior.
        """
        if self.parent_model is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must set 'parent_model' class attribute"
            )
        
        # Get parent field name
        parent_field_name = self._get_parent_field_name()
        
        # Try to filter by is_active if the field exists
        try:
            filter_key = f'{parent_field_name}__is_active'
            return self.filter(**{filter_key: True})
        except Exception:
            # If is_active doesn't exist, return all
            return self.all()
    
    def _get_parent_field_name(self):
        """
        Get the name of the parent field in the child model.
        Override this if your field name doesn't match the pattern.
        
        Returns:
            str: Field name (e.g., 'invoice', 'business_partner')
        """
        # Try to get it from the model class if it has parent_field_name
        model_class = self.model
        if hasattr(model_class, 'parent_field_name'):
            return model_class.parent_field_name
        
        # Default: lowercase parent model name with underscores
        parent_name = self.parent_model.__name__
        # Convert CamelCase to snake_case
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', parent_name).lower()


class ChildModelMixin:
    """
    Mixin for child models.
    Automatically creates property proxies for ALL parent fields.
    
    Required class attributes:
        parent_model: The parent model class
        parent_field_name: Name of the FK/OneToOne field pointing to parent
        
    Usage:
        class AP_Invoice(ChildModelMixin, models.Model):
            parent_model = Invoice
            parent_field_name = 'invoice'
            
            invoice = models.OneToOneField(Invoice, ...)
            supplier = models.ForeignKey(Supplier, ...)
    """
    
    parent_model = None  # Must be set by subclass
    parent_field_name = None  # Must be set by subclass
    
    def save(self, *args, **kwargs):
        """
        Override save to handle parent updates automatically.
        """
        if self.parent_model is None or self.parent_field_name is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must set 'parent_model' and "
                f"'parent_field_name' class attributes"
            )
        
        # Get the parent instance
        parent_id_attr = f'{self.parent_field_name}_id'
        
        # If parent doesn't exist yet, raise error
        if not getattr(self, parent_id_attr, None):
            raise ValidationError(
                f"Use {self.__class__.__name__}.objects.create() instead of "
                f"{self.__class__.__name__}() constructor. "
                "This ensures proper parent creation."
            )
        
        # Get all parent field names dynamically
        parent_field_names = self.parent_model.get_field_names()
        
        # Update parent if any of its fields were set
        parent_updated = False
        parent_instance = getattr(self, self.parent_field_name)
        
        for field_name in parent_field_names:
            temp_attr = f'_{field_name}_temp'
            if hasattr(self, temp_attr):
                setattr(parent_instance, field_name, getattr(self, temp_attr))
                delattr(self, temp_attr)
                parent_updated = True
        
        if parent_updated:
            parent_instance._allow_direct_save = True
            parent_instance.save()
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to also delete the associated parent if no other children exist.
        """
        parent_instance = getattr(self, self.parent_field_name)
        
        # Delete the child first
        super().delete(*args, **kwargs)
        
        # Check if parent still has other children
        try:
            parent_instance.refresh_from_db()
            
            # Get all reverse relations (children)
            has_children = False
            for related_object in parent_instance._meta.related_objects:
                if related_object.one_to_one or related_object.many_to_one:
                    # Check if this child still exists
                    accessor_name = related_object.get_accessor_name()
                    try:
                        if hasattr(parent_instance, accessor_name):
                            related = getattr(parent_instance, accessor_name)
                            # For ForeignKey, check if queryset has items
                            if related_object.many_to_one and not related_object.one_to_one:
                                if related.exists():
                                    has_children = True
                                    break
                            else:
                                # For OneToOne, if it exists, we have a child
                                has_children = True
                                break
                    except Exception:
                        # Child doesn't exist or error accessing
                        continue
            
            # If no children left, delete the parent
            if not has_children:
                parent_instance._allow_direct_save = True
                # Bypass ManagedParentModel.delete() and call Model.delete() directly
                models.Model.delete(parent_instance, *args, **kwargs)
        except self.parent_model.DoesNotExist:
            # Already deleted, nothing to do
            pass
    
    def __init__(self, *args, **kwargs):
        """
        Override __init__ to dynamically create property proxies.
        """
        super().__init__(*args, **kwargs)
        
        # Dynamically create property proxies for all parent fields
        if not hasattr(self.__class__, '_properties_created'):
            self.__class__._create_parent_properties()
            self.__class__._properties_created = True
    
    @classmethod
    def _create_parent_properties(cls):
        """
        Dynamically create property proxies for all parent fields AND method proxies.
        This runs once per class and creates properties for ALL fields and methods automatically!
        """
        if cls.parent_model is None or cls.parent_field_name is None:
            raise NotImplementedError(
                f"{cls.__name__} must set 'parent_model' and "
                f"'parent_field_name' class attributes"
            )
        
        # 1. Create field properties
        parent_field_names = cls.parent_model.get_field_names()
        
        for field_name in parent_field_names:
            # Skip if property already exists
            if hasattr(cls, field_name):
                continue
            
            # Create getter and setter functions with closure
            def make_property(fname, parent_attr):
                def getter(self):
                    parent = getattr(self, parent_attr)
                    return getattr(parent, fname)
                
                def setter(self, value):
                    setattr(self, f'_{fname}_temp', value)
                    parent_id_attr = f'{parent_attr}_id'
                    if getattr(self, parent_id_attr, None):
                        parent = getattr(self, parent_attr)
                        setattr(parent, fname, value)
                
                return property(getter, setter)
            
            # Add property to class
            setattr(cls, field_name, make_property(field_name, cls.parent_field_name))
        
        # 2. Create method proxies
        parent_method_names = cls.parent_model.get_method_names()
        
        for method_name in parent_method_names:
            # Skip if method already exists in child
            if hasattr(cls, method_name):
                continue
            
            # Create method proxy with closure
            def make_method_proxy(mname, parent_attr):
                def method_proxy(self, *args, **kwargs):
                    parent = getattr(self, parent_attr)
                    parent_method = getattr(parent, mname)
                    return parent_method(*args, **kwargs)
                
                # Preserve method name for debugging
                method_proxy.__name__ = mname
                return method_proxy
            
            # Add method to class
            setattr(cls, method_name, make_method_proxy(method_name, cls.parent_field_name))
