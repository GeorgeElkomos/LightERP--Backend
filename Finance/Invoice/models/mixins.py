"""
Invoice-specific mixins for child models.

These mixins extend the base patterns from Finance.core.base_models
with Invoice-specific functionality, particularly auto-syncing business_partner
from supplier/customer/one_time_supplier fields.
"""

from django.core.exceptions import ValidationError
from Finance.core.base_models import ChildModelManagerMixin, ChildModelMixin


class InvoiceChildManagerMixin(ChildModelManagerMixin):
    """
    Invoice-specific manager mixin that auto-sets business_partner.
    
    Extend this instead of ChildModelManagerMixin for Invoice child models.
    Set 'bp_source_field' to specify which field contains the business partner source
    (e.g., 'supplier', 'customer', 'one_time_supplier')
    """
    bp_source_field = None  # Must be set in child manager (e.g., 'supplier')
    
    def create(self, **kwargs):
        """Auto-set business_partner from the source field (supplier/customer/etc)"""
        if self.bp_source_field and self.bp_source_field in kwargs:
            if 'business_partner' not in kwargs:
                source_obj = kwargs[self.bp_source_field]
                kwargs['business_partner'] = source_obj.business_partner
        return super().create(**kwargs)


class InvoiceChildModelMixin(ChildModelMixin):
    """
    Invoice-specific child model mixin that auto-syncs business_partner.
    
    Extend this instead of ChildModelMixin for Invoice child models.
    Set 'bp_source_field' to specify which field contains the business partner source
    (e.g., 'supplier', 'customer', 'one_time_supplier')
    """
    bp_source_field = None  # Must be set in child model (e.g., 'supplier')
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Auto-sync business_partner with the source field"""
        if self.bp_source_field:
            source_field_id = f"{self.bp_source_field}_id"
            if getattr(self, source_field_id, None) and hasattr(self, 'invoice'):
                source_obj = getattr(self, self.bp_source_field)
                expected_bp = source_obj.business_partner
                # Auto-update business_partner to match source
                if self.invoice.business_partner_id != expected_bp.id:
                    self.invoice.business_partner = expected_bp
                    # Save the parent Invoice to persist the change
                    self.invoice._allow_direct_save = True
                    self.invoice.save()
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validation: Ensure business_partner matches source field"""
        super().clean()
        if self.bp_source_field:
            source_field_id = f"{self.bp_source_field}_id"
            if getattr(self, source_field_id, None) and hasattr(self, 'invoice'):
                source_obj = getattr(self, self.bp_source_field)
                if self.invoice.business_partner_id != source_obj.business_partner_id:
                    raise ValidationError({
                        self.bp_source_field: f'{self.bp_source_field.replace("_", " ").title()}\'s business partner must match invoice business partner.'
                    })
