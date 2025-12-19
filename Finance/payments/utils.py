"""
Payment utility functions for processing payment-related operations.
"""
from django.db import transaction
from django.core.exceptions import ValidationError


@transaction.atomic
def process_invoice_payment_to_plan(invoice, payment_amount):
    """
    Apply payment amount to an invoice's payment plan installments.
    
    This function handles the payment plan updates for a single invoice.
    It applies waterfall allocation: pays oldest installments first.
    
    Args:
        invoice (Invoice): The invoice with a payment plan
        payment_amount (Decimal): Amount to apply to payment plan
        
    Returns:
        dict: Processing result with structure:
            {
                'invoice_id': int,
                'allocation_amount': float,
                'status': 'success' | 'skipped',
                'payment_plan_id': int (if exists),
                'payment_plan_status': str (if processed),
                'updated_installments': list (if processed),
                'reason': str (if skipped)
            }
            
    Raises:
        ValidationError: If payment processing fails
        
    Note:
        - Only processes active payment plans (pending, partial, overdue)
        - Assumes one active payment plan per invoice
        - Silently skips invoices without payment plans
        - Uses atomic transaction for data consistency
    """
    # Get the active payment plan (should only be one)
    active_plan = invoice.payment_plans.filter(
        status__in=['pending', 'partial', 'overdue']
    ).first()
    
    if not active_plan:
        # Invoice doesn't have a payment plan - skip it
        return {
            'invoice_id': invoice.id,
            'allocation_amount': float(payment_amount),
            'status': 'skipped',
            'reason': 'No active payment plan'
        }
    
    # Apply payment to payment plan installments (waterfall allocation)
    payment_result = active_plan.process_payment(payment_amount)
    
    return {
        'invoice_id': invoice.id,
        'payment_plan_id': active_plan.id,
        'allocation_amount': float(payment_amount),
        'status': 'success',
        'payment_plan_status': payment_result['payment_plan_status'],
        'updated_installments': payment_result['updated_installments'],
        'payment_applied': payment_result['payment_applied'],
        'remaining_payment': payment_result['remaining_payment']
    }