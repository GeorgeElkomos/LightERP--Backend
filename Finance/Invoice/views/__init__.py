"""
Invoice Views Package

This package organizes invoice views by type:
- ap_views: Accounts Payable invoice views
- ar_views: Accounts Receivable invoice views  
- one_time_views: One-Time Supplier invoice views

All views are exported here for convenient importing.
"""

from Finance.Invoice.views.ap_views import (
    ap_invoice_list,
    ap_invoice_detail,
    ap_invoice_post_to_gl,
    ap_invoice_submit_for_approval,
    ap_invoice_pending_approvals,
    ap_invoice_approval_action,
    ap_invoice_create_from_receipt,
    ap_invoice_variance_preview
)

from Finance.Invoice.views.ar_views import (
    ar_invoice_list,
    ar_invoice_detail,
    ar_invoice_post_to_gl,
    ar_invoice_submit_for_approval,
    ar_invoice_pending_approvals,
    ar_invoice_approval_action
)

from Finance.Invoice.views.one_time_views import (
    one_time_supplier_invoice_list,
    one_time_supplier_invoice_detail,
    one_time_supplier_invoice_post_to_gl,
    one_time_supplier_invoice_submit_for_approval,
    one_time_supplier_invoice_pending_approvals,
    one_time_supplier_invoice_approval_action
)

__all__ = [
    # AP Invoice views
    'ap_invoice_list',
    'ap_invoice_detail',
    'ap_invoice_post_to_gl',
    'ap_invoice_submit_for_approval',
    'ap_invoice_pending_approvals',
    'ap_invoice_approval_action',
    'ap_invoice_create_from_receipt',
    'ap_invoice_variance_preview',
    
    # AR Invoice views
    'ar_invoice_list',
    'ar_invoice_detail',
    'ar_invoice_post_to_gl',
    'ar_invoice_submit_for_approval',
    'ar_invoice_pending_approvals',
    'ar_invoice_approval_action',
    
    # One-Time Supplier views
    'one_time_supplier_invoice_list',
    'one_time_supplier_invoice_detail',
    'one_time_supplier_invoice_post_to_gl',
    'one_time_supplier_invoice_submit_for_approval',
    'one_time_supplier_invoice_pending_approvals',
    'one_time_supplier_invoice_approval_action',
]
