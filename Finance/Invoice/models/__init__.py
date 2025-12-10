"""
Invoice Models Package

This package contains all Invoice-related models organized into separate modules:
- parent_model.py: Invoice (parent/base model) and InvoiceItem
- mixins.py: Invoice-specific mixins for child models
- ap_model.py: AP_Invoice (Accounts Payable)
- ar_model.py: AR_Invoice (Accounts Receivable)
- one_time_model.py: OneTimeSupplier (ad-hoc suppliers)

All models are re-exported here for backward compatibility and convenience.
"""

# Import mixins
from .mixins import (
    InvoiceChildManagerMixin,
    InvoiceChildModelMixin,
)

# Import parent models
from .parent_model import (
    Invoice,
    InvoiceItem,
)

# Import child models
from .ap_model import (
    AP_Invoice,
    AP_InvoiceManager,
)

from .ar_model import (
    AR_Invoice,
    AR_InvoiceManager,
)

from .one_time_model import (
    OneTimeSupplier,
    OneTimeSupplierManager,
)

# Explicit exports for clarity
__all__ = [
    # Mixins
    'InvoiceChildManagerMixin',
    'InvoiceChildModelMixin',
    
    # Parent models
    'Invoice',
    'InvoiceItem',
    
    # AP models
    'AP_Invoice',
    'AP_InvoiceManager',
    
    # AR models
    'AR_Invoice',
    'AR_InvoiceManager',
    
    # One-time supplier models
    'OneTimeSupplier',
    'OneTimeSupplierManager',
]
