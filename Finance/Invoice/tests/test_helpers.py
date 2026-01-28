"""
Test helpers for Invoice testing with approval workflows.

Provides utilities to:
- Create approval workflow templates
- Set up test users with proper permissions
- Helper functions for common test scenarios
"""

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from core.approval.models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
)
from Finance.Invoice.models import Invoice

User = get_user_model()


def create_simple_approval_template_for_invoice():
    """Create a simple single-stage approval workflow template for Invoice model.
    
    This creates a template with one stage that requires:
    - Any user can approve (no user level restrictions)
    - Single approver needed
    
    Returns:
        ApprovalWorkflowTemplate: The created template
    """
    content_type = ContentType.objects.get_for_model(Invoice)
    
    # Check if template already exists
    template = ApprovalWorkflowTemplate.objects.filter(
        content_type=content_type,
        is_active=True
    ).first()
    
    if template:
        return template
    
    # Create new template
    template = ApprovalWorkflowTemplate.objects.create(
        name="Simple Invoice Approval",
        content_type=content_type,
        description="Single-stage approval for testing",
        is_active=True,
        version=1
    )
    
    # Create single stage
    ApprovalWorkflowStageTemplate.objects.create(
        workflow_template=template,
        name="Manager Approval",
        order_index=1,
        decision_policy=ApprovalWorkflowStageTemplate.POLICY_ANY,  # Any user can approve
        allow_reject=True,
        allow_delegate=False
    )
    
    return template


def get_or_create_test_user(email='testuser@test.com', **kwargs):
    """Get or create a test user for approval testing.
    
    Args:
        email: Email for the test user (used as USERNAME_FIELD)
        **kwargs: Additional fields for user creation
    
    Returns:
        User: The test user
    """
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'name': kwargs.get('name', 'Test User'),
            'phone_number': kwargs.get('phone_number', '1234567890'),
        }
    )
    
    if created and 'password' in kwargs:
        user.set_password(kwargs['password'])
        user.save()
    
    return user


def approve_invoice_for_testing(invoice_child_model, user=None):
    """Approve an invoice through the workflow system for testing.
    
    This is a helper that:
    1. Ensures workflow template exists
    2. Submits invoice for approval
    3. Approves the invoice as a user
    
    Args:
        invoice_child_model: AP_Invoice, AR_Invoice, or OneTimeSupplier instance
        user: User to approve as (creates one if None)
    
    Returns:
        User: The user who approved (useful for test assertions)
    """
    # Ensure template exists
    create_simple_approval_template_for_invoice()
    
    # Get or create user
    if user is None:
        user = get_or_create_test_user()
    
    # Submit for approval and approve
    invoice_child_model.submit_for_approval()
    invoice_child_model.approve(user, comment="Approved for testing")
    invoice_child_model.refresh_from_db()
    
    return user


def reject_invoice_for_testing(invoice_child_model, user=None, comment="Rejected for testing"):
    """Reject an invoice through the workflow system for testing.
    
    Args:
        invoice_child_model: AP_Invoice, AR_Invoice, or OneTimeSupplier instance
        user: User to reject as (creates one if None)
        comment: Rejection reason
    
    Returns:
        User: The user who rejected
    """
    # Ensure template exists
    create_simple_approval_template_for_invoice()
    
    # Get or create user
    if user is None:
        user = get_or_create_test_user()
    
    # Submit for approval and reject
    invoice_child_model.submit_for_approval()
    invoice_child_model.reject(user, comment=comment)
    invoice_child_model.refresh_from_db()
    
    return user
