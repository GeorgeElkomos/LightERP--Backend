from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from Finance.core.models import Currency, ProtectedDeleteMixin
from Finance.BusinessPartner.models import BusinessPartner
from Finance.GL.models import XX_Segment_combination, JournalEntry
from core.approval.mixins import ApprovableMixin, ApprovableInterface

User = get_user_model()


class CashAccount(ProtectedDeleteMixin, models.Model):
    """
    Master data for cash and bank accounts.
    Tracks account details, balances, and GL mapping.
    """
    
    # Account Type Choices
    BANK = 'BANK'
    PETTY_CASH = 'PETTY_CASH'
    CASH_ON_HAND = 'CASH_ON_HAND'
    
    ACCOUNT_TYPE_CHOICES = [
        (BANK, 'Bank Account'),
        (PETTY_CASH, 'Petty Cash'),
        (CASH_ON_HAND, 'Cash on Hand'),
    ]
    
    # Basic Information
    account_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique account identifier (e.g., bank account number)"
    )
    
    account_name = models.CharField(
        max_length=255,
        help_text="Descriptive name for the account"
    )
    
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default=BANK
    )
    
    # Currency and Balance
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='cash_accounts',
        help_text="Currency of this account"
    )
    
    
    current_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Current balance of the account"
    )
    
    # GL Integration
    gl_account = models.ForeignKey(
        XX_Segment_combination,
        on_delete=models.PROTECT,
        related_name='cash_accounts',
        help_text="GL segment combination for this cash account"
    )
    
    # Bank-specific Information (optional)
    bank_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the bank (for bank accounts)"
    )
    
    bank_branch = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bank branch information"
    )
    
    iban = models.CharField(
        max_length=34,
        blank=True,
        help_text="International Bank Account Number"
    )
    
    swift_code = models.CharField(
        max_length=11,
        blank=True,
        help_text="SWIFT/BIC code"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this account is currently active"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cash_accounts_created'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cash_accounts_updated'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional Information
    description = models.TextField(
        blank=True,
        help_text="Additional notes or description"
    )
    
    class Meta:
        verbose_name = 'Cash Account'
        verbose_name_plural = 'Cash Accounts'
        ordering = ['account_number']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['account_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.account_number} - {self.account_name}"


class CashTransaction(ApprovableMixin, ApprovableInterface, models.Model):
    """
    Transactional data for cash movements.
    Supports receipts, payments, and transfers with approval workflow.
    """
    
    # Transaction Type Choices
    RECEIPT = 'RECEIPT'
    PAYMENT = 'PAYMENT'
    TRANSFER = 'TRANSFER'
    
    TRANSACTION_TYPE_CHOICES = [
        (RECEIPT, 'Cash Receipt'),
        (PAYMENT, 'Cash Payment'),
        (TRANSFER, 'Cash Transfer'),
    ]
    
    # Status Choices
    DRAFT = 'DRAFT'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    POSTED = 'POSTED'
    
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (POSTED, 'Posted to GL'),
    ]
    
    # Basic Information
    reference_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique transaction reference number"
    )
    
    transaction_date = models.DateField(
        help_text="Date of the transaction"
    )
    
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES
    )
    
    # Account References
    from_account = models.ForeignKey(
        CashAccount,
        on_delete=models.PROTECT,
        related_name='outgoing_transactions',
        null=True,
        blank=True,
        help_text="Source account (for payments and transfers)"
    )
    
    to_account = models.ForeignKey(
        CashAccount,
        on_delete=models.PROTECT,
        related_name='incoming_transactions',
        null=True,
        blank=True,
        help_text="Destination account (for receipts and transfers)"
    )
    
    # Amount and Currency
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Transaction amount"
    )
    
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='cash_transactions'
    )
    
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Exchange rate to base currency at transaction date"
    )
    
    base_currency_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount in base currency"
    )
    
    # Business Partner (optional - for receipts/payments from/to partners)
    business_partner = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='cash_transactions',
        null=True,
        blank=True,
        help_text="Business partner involved in this transaction"
    )
    
    # Description and Notes
    description = models.TextField(
        help_text="Description of the transaction"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or comments"
    )
    
    # Approval Status and Workflow
    approval_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT
    )
    
    submitted_for_approval_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    rejected_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    rejection_reason = models.TextField(
        blank=True
    )
    
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When transaction was posted to GL"
    )
    
    # GL Integration
    gl_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name='cash_transactions',
        null=True,
        blank=True,
        help_text="Associated journal entry in GL"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cash_transactions_created'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cash_transactions_updated'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Cash Transaction'
        verbose_name_plural = 'Cash Transactions'
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['reference_number']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['-transaction_date', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.reference_number} - {self.get_transaction_type_display()} - {self.amount} {self.currency.code}"
