from django.db import models, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from decimal import Decimal
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import BusinessPartner, Customer, Supplier
from Finance.Invoice.models import Invoice, AP_Invoice, AR_Invoice
from Finance.GL.models import JournalEntry

class Payment(models.Model):
    
    # Status choices (shared by all payment types)
    DRAFT = 'DRAFT'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]
    
    date = models.DateField()
    
    business_partner = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Exchange rate to base currency at payment date"
    )
    
    # Status and workflow
    approval_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT
    )
    rejection_reason = models.TextField(null=True, blank=True)
    
    gl_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        db_table = 'payment'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"Payment {self.id} - {self.business_partner} - {self.date}"
    
    # ==================== PAYMENT ALLOCATION HELPER METHODS ====================
    
    def get_total_allocated(self):
        """
        Calculate total amount allocated from this payment to invoices.
        
        Returns:
            Decimal: Sum of all allocation amounts
        """
        total = self.allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        return total
    
    def get_allocated_invoices(self):
        """
        Get all invoices that have allocations from this payment.
        
        Returns:
            QuerySet: Invoice objects with allocations
        """
        return Invoice.objects.filter(
            payment_allocations__payment=self
        ).distinct()
    
    def can_allocate_to_invoice(self, invoice, amount):
        """
        Check if this payment can allocate a specific amount to an invoice.
        
        Args:
            invoice (Invoice): The invoice to allocate to
            amount (Decimal): The amount to allocate
            
        Returns:
            tuple: (bool, str) - (is_valid, error_message)
        """
        # Check currency match
        if self.currency_id != invoice.currency_id:
            return False, f"Currency mismatch: Payment is in {self.currency}, Invoice is in {invoice.currency}"
        
        # Check business partner match
        if self.business_partner_id != invoice.business_partner_id:
            return False, "Business partner mismatch between payment and invoice"
        
        # Check if invoice can accept this payment
        can_pay, error_msg = invoice.can_pay(amount)
        if not can_pay:
            return False, error_msg
        
        return True, ""
    
    @transaction.atomic
    def allocate_to_invoice(self, invoice, amount):
        """
        Create a payment allocation to an invoice.
        
        Args:
            invoice (Invoice): The invoice to allocate payment to
            amount (Decimal): The amount to allocate
            
        Returns:
            PaymentAllocation: The created allocation
            
        Raises:
            ValidationError: If allocation is invalid
        """
        # Validate
        can_allocate, error_msg = self.can_allocate_to_invoice(invoice, amount)
        if not can_allocate:
            raise ValidationError(error_msg)
        
        # Check if allocation already exists
        existing_allocation = self.allocations.filter(invoice=invoice).first()
        if existing_allocation:
            # Update existing allocation
            existing_allocation.amount_allocated += Decimal(str(amount))
            existing_allocation.save()
            return existing_allocation
        else:
            # Create new allocation
            allocation = PaymentAllocation.objects.create(
                payment=self,
                invoice=invoice,
                amount_allocated=amount
            )
            return allocation
    
    @transaction.atomic
    def remove_allocation(self, invoice):
        """
        Remove payment allocation from an invoice.
        
        Args:
            invoice (Invoice): The invoice to remove allocation from
            
        Returns:
            bool: True if allocation was removed, False if no allocation existed
        """
        try:
            allocation = self.allocations.get(invoice=invoice)
            allocation.delete()
            return True
        except PaymentAllocation.DoesNotExist:
            return False
    
    @transaction.atomic
    def clear_all_allocations(self):
        """
        Remove all payment allocations.
        This will decrease paid_amount on all related invoices.
        
        NOTE: We must delete allocations individually to trigger the custom
        delete() method which updates invoice.paid_amount. Bulk delete bypasses this.
        
        Returns:
            int: Number of allocations deleted
        """
        allocations = list(self.allocations.all())  # Convert to list to avoid query issues
        count = len(allocations)
        
        # Delete each allocation individually to trigger custom delete() logic
        for allocation in allocations:
            allocation.delete()
        
        return count

class PaymentAllocation(models.Model):
    """
    PaymentAllocation - Links Payments to Invoices
    
    This model records how payments are allocated to specific invoices.
    Each allocation links one Payment to one Invoice with a specified amount.
    
    IMPORTANT: This model automatically syncs the Invoice.paid_amount field!
    - When an allocation is created, it increases Invoice.paid_amount
    - When an allocation is updated, it adjusts Invoice.paid_amount
    - When an allocation is deleted, it decreases Invoice.paid_amount
    """
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payment_allocations'
    )
    
    amount_allocated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Amount of the payment allocated to this invoice"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_allocation'
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'
        unique_together = ('payment', 'invoice')
    
    def __str__(self):
        return f"Payment {self.payment_id} → Invoice {self.invoice_id}: {self.amount_allocated}"
    
    def clean(self):
        """
        Validate the payment allocation before saving.
        
        Uses Invoice helper methods for validation:
        - invoice.can_pay() for amount validation
        - Validates currency and business partner match
        
        Handles both CREATE and UPDATE scenarios correctly.
        """
        super().clean()
        
        # Validate currency compatibility
        if self.payment and self.invoice:
            if self.payment.currency_id != self.invoice.currency_id:
                raise ValidationError({
                    'amount_allocated': f'Payment currency ({self.payment.currency}) does not match invoice currency ({self.invoice.currency}).'
                })
        
        # Validate business partner compatibility
        if self.payment and self.invoice:
            if self.payment.business_partner_id != self.invoice.business_partner_id:
                raise ValidationError({
                    'invoice': 'Payment business partner must match invoice business partner.'
                })
        
        # Validate the allocation amount
        if self.invoice and self.amount_allocated is not None:
            # For updates, we need to check if the NEW amount is valid
            # by temporarily removing the old amount from paid_amount
            if self.pk:
                try:
                    old_allocation = PaymentAllocation.objects.get(pk=self.pk)
                    old_amount = old_allocation.amount_allocated
                    
                    # Calculate what the paid_amount would be without this allocation
                    temp_paid = self.invoice.paid_amount - old_amount
                    
                    # Now check if we can "pay" the new amount
                    remaining = self.invoice.total - temp_paid
                    if self.amount_allocated > remaining:
                        raise ValidationError({
                            'amount_allocated': f'Allocation amount {self.amount_allocated} exceeds invoice remaining balance of {remaining}.'
                        })
                    
                    # Also validate it's positive
                    if self.amount_allocated <= 0:
                        raise ValidationError({
                            'amount_allocated': 'Allocation amount must be greater than zero.'
                        })
                        
                except PaymentAllocation.DoesNotExist:
                    # Allocation was deleted, treat as new creation
                    can_pay, error_msg = self.invoice.can_pay(self.amount_allocated)
                    if not can_pay:
                        raise ValidationError({
                            'amount_allocated': error_msg
                        })
            else:
                # For new allocations, use the invoice's can_pay() helper method
                can_pay, error_msg = self.invoice.can_pay(self.amount_allocated)
                if not can_pay:
                    raise ValidationError({
                        'amount_allocated': error_msg
                    })
    
    def get_payment_total_allocated(self):
        """
        Calculate total amount allocated from this payment (excluding current allocation if updating).
        
        Returns:
            Decimal: Total allocated amount
        """
        allocations = PaymentAllocation.objects.filter(
            payment=self.payment
        ).exclude(pk=self.pk if self.pk else None)
        
        total = allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        
        return total
    
    def get_invoice_total_allocated(self):
        """
        Calculate total amount allocated to this invoice (excluding current allocation if updating).
        
        Returns:
            Decimal: Total allocated amount
        """
        allocations = PaymentAllocation.objects.filter(
            invoice=self.invoice
        ).exclude(pk=self.pk if self.pk else None)
        
        total = allocations.aggregate(
            total=models.Sum('amount_allocated')
        )['total'] or Decimal('0')
        
        return total
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Save the allocation and update the invoice paid_amount.
        Uses database transaction to ensure data consistency.
        
        Handles three scenarios:
        1. CREATE: New allocation - adds to paid_amount
        2. UPDATE (increase): Allocation increased - adds difference
        3. UPDATE (decrease): Allocation decreased - subtracts difference
        """
        # Run validation
        self.full_clean()
        
        # Determine if this is an update by checking if pk exists AND record exists in DB
        is_update = False
        old_amount = Decimal('0')
        
        if self.pk is not None:
            try:
                old_allocation = PaymentAllocation.objects.get(pk=self.pk)
                old_amount = old_allocation.amount_allocated
                is_update = True
            except PaymentAllocation.DoesNotExist:
                is_update = False
        
        # Save the allocation first
        super().save(*args, **kwargs)
        
        # Update invoice paid_amount using the helper method
        if is_update:
            # Calculate the difference (can be positive or negative)
            amount_diff = self.amount_allocated - old_amount
            if amount_diff != 0:  # Only update if there's actually a change
                self._update_invoice_paid_amount(amount_diff)
        else:
            # New allocation - add the full amount
            self._update_invoice_paid_amount(self.amount_allocated)
    
    def _update_invoice_paid_amount(self, amount_change):
        """
        Update the invoice paid_amount by the specified amount.
        Uses Invoice.pay() or Invoice.refund() helper methods.
        
        Args:
            amount_change (Decimal): Amount to add to paid_amount (can be positive or negative)
            
        Raises:
            ValidationError: If the update would violate invoice constraints
        """
        # Skip if no change
        if amount_change == 0:
            return
        
        # Refresh invoice from database to avoid stale data
        self.invoice.refresh_from_db()
        
        # Use the appropriate Invoice helper method
        if amount_change > 0:
            # Increasing allocation: Use pay() for positive amounts
            self.invoice.pay(amount_change)
        else:
            # Decreasing allocation: Use refund() for negative amounts
            # refund() expects positive values, so we pass the absolute value
            self.invoice.refund(abs(amount_change))
    
    @transaction.atomic
    def delete(self, *args, **kwargs):
        """
        Delete the allocation and update the invoice paid_amount.
        Uses Invoice.refund() helper method to reverse the payment.
        Uses database transaction to ensure data consistency.
        """
        # Store amount before deletion
        amount_to_reverse = self.amount_allocated
        invoice = self.invoice
        
        # Delete the allocation
        super().delete(*args, **kwargs)
        
        # Reverse the payment using refund()
        invoice.refresh_from_db()
        invoice.refund(amount_to_reverse)


# ==================== SIGNAL HANDLERS ====================

# NOTE: Signal handler disabled because PaymentAllocation.save() already handles
# invoice.paid_amount synchronization correctly. Having both causes double-updates.
# 
# @receiver(post_save, sender=PaymentAllocation)
# def sync_invoice_paid_amount_on_save(sender, instance, created, **kwargs):
#     """
#     Signal handler to ensure invoice paid_amount is synced when allocation is saved.
#     This is a backup to the save() method logic.
#     """
#     print(f"DEBUG signal: post_save fired, created={created}")
#     # The save() method already handles this, but we keep this as a safety net
#     # Only recalculate if we detect inconsistency
#     if not created:  # Only for updates, creation is handled in save()
#         expected_paid = PaymentAllocation.objects.filter(
#             invoice=instance.invoice
#         ).aggregate(total=models.Sum('amount_allocated'))['total'] or Decimal('0')
#         
#         print(f"DEBUG signal: invoice.paid_amount={instance.invoice.paid_amount}, expected_paid={expected_paid}")
#         
#         if instance.invoice.paid_amount != expected_paid:
#             # Fix inconsistency
#             print(f"DEBUG signal: INCONSISTENCY DETECTED! Fixing from {instance.invoice.paid_amount} to {expected_paid}")
#             instance.invoice.paid_amount = expected_paid
#             instance.invoice.update_payment_status()
#             instance.invoice._allow_direct_save = True
#             instance.invoice.save(update_fields=['paid_amount', 'payment_status'])