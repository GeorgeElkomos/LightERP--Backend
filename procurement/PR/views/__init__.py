"""
PR Views Package

This package organizes PR views by type:
- catalog_views: Catalog PR views
- noncatalog_views: Non-Catalog PR views
- service_views: Service PR views

All views are exported here for convenient importing.
"""

from procurement.PR.views.catalog_views import (
    catalog_pr_list,
    catalog_pr_detail,
    catalog_pr_submit_for_approval,
    catalog_pr_pending_approvals,
    catalog_pr_approval_action,
    catalog_pr_cancel
)

from procurement.PR.views.noncatalog_views import (
    noncatalog_pr_list,
    noncatalog_pr_detail,
    noncatalog_pr_submit_for_approval,
    noncatalog_pr_pending_approvals,
    noncatalog_pr_approval_action,
    noncatalog_pr_cancel
)

from procurement.PR.views.service_views import (
    service_pr_list,
    service_pr_detail,
    service_pr_submit_for_approval,
    service_pr_pending_approvals,
    service_pr_approval_action,
    service_pr_cancel
)

__all__ = [
    # Catalog PR views
    'catalog_pr_list',
    'catalog_pr_detail',
    'catalog_pr_submit_for_approval',
    'catalog_pr_pending_approvals',
    'catalog_pr_approval_action',
    'catalog_pr_cancel',
    
    # Non-Catalog PR views
    'noncatalog_pr_list',
    'noncatalog_pr_detail',
    'noncatalog_pr_submit_for_approval',
    'noncatalog_pr_pending_approvals',
    'noncatalog_pr_approval_action',
    'noncatalog_pr_cancel',
    
    # Service PR views
    'service_pr_list',
    'service_pr_detail',
    'service_pr_submit_for_approval',
    'service_pr_pending_approvals',
    'service_pr_approval_action',
    'service_pr_cancel',
]
