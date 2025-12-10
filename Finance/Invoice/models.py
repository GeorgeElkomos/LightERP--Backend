"""
Invoice Models - BACKWARD COMPATIBILITY LAYER

This file now imports all models from the new modular structure.
All models have been split into separate files within the 'models' package:

- models/mixins.py: Invoice-specific mixins
- models/parent_model.py: Invoice and InvoiceItem
- models/ap_model.py: AP_Invoice
- models/ar_model.py: AR_Invoice
- models/one_time_model.py: OneTimeSupplier

IMPORTANT DESIGN PATTERN:
========================
Invoice is a MANAGED BASE CLASS that should NEVER be directly created, 
updated, or deleted. All operations MUST go through child classes (AP_Invoice, AR_Invoice, etc.).

The magic: Child classes automatically inherit ALL Invoice fields as properties!
No need to manually define getters/setters - they're auto-generated!

Usage Examples:
--------------
# CORRECT - Create an AP invoice
ap_invoice = AP_Invoice.objects.create(
    # Invoice fields (auto-handled!)
    date=date.today(),
    currency=currency,
    subtotal=1000.00,
    total=1100.00,
    gl_distributions=journal_entry,
    # AP_Invoice fields
    supplier=supplier  # business_partner auto-set!
)

# CORRECT - Update works automatically
ap_invoice.total = 1200.00
ap_invoice.save()  # Auto-updates Invoice!

# Update supplier - business_partner auto-syncs!
ap_invoice.supplier = new_supplier
ap_invoice.save()  # business_partner updated automatically!
"""

# Import all models from the new modular structure
from .models import (
    # Mixins
    InvoiceChildManagerMixin,
    InvoiceChildModelMixin,
    
    # Parent models
    Invoice,
    InvoiceItem,
    
    # AP models
    AP_Invoice,
    AP_InvoiceManager,
    
    # AR models
    AR_Invoice,
    AR_InvoiceManager,
    
    # One-time supplier models
    OneTimeSupplier,
    OneTimeSupplierManager,
)

# Explicit exports for backward compatibility
__all__ = [
    'InvoiceChildManagerMixin',
    'InvoiceChildModelMixin',
    'Invoice',
    'InvoiceItem',
    'AP_Invoice',
    'AP_InvoiceManager',
    'AR_Invoice',
    'AR_InvoiceManager',
    'OneTimeSupplier',
    'OneTimeSupplierManager',
]

