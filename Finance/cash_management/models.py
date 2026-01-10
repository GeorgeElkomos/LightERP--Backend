from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from Finance.core.models import Currency, ProtectedDeleteMixin, Country
from Finance.BusinessPartner.models import BusinessPartner
from Finance.GL.models import XX_Segment_combination, JournalEntry
from core.approval.mixins import ApprovableMixin, ApprovableInterface

User = get_user_model()



# class TransctionType(models.TextChoices):
#     transction_name = models.CharField(max_length=100, unique=True)

# ==================== PAYMENT TYPE SETUP MODEL ====================

class PaymentType(ProtectedDeleteMixin, models.Model):
    """
    Setup table for payment methods/types (e.g., Cash, Check, Wire Transfer, Credit Card).
    Determines whether a payment should be reconciled against bank statements.
    """
    
    payment_method_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Unique code for the payment method (e.g., CASH, CHECK, WIRE)"
    )
    
    payment_method_name = models.CharField(
        max_length=100,
        help_text="Display name for the payment method"
    )
    
    description = models.TextField(
        blank=True,
        default='',
        help_text="Description of the payment method"
    )
    
    enable_reconcile = models.BooleanField(
        default=True,
        help_text="Whether payments using this method should be reconciled with bank statements"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this payment method is currently active"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_payment_types'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='updated_payment_types'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Payment Type'
        verbose_name_plural = 'Payment Types'
        ordering = ['payment_method_name']
        indexes = [
            models.Index(fields=['payment_method_code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.payment_method_name} ({self.payment_method_code})"


# ==================== BANK HIERARCHY MODELS ====================

class Bank(ProtectedDeleteMixin, models.Model):
    """
    Master data for banks (Level 1 - Top of hierarchy).
    Represents financial institutions.
    """
    
    # Basic Information
    bank_name = models.CharField(max_length=255,unique=True,help_text="Official name of the bank")
    bank_code = models.CharField(max_length=50,unique=True,help_text="Unique bank identification code")
    country = models.ForeignKey(Country,on_delete=models.PROTECT,related_name='banks',help_text="Country where bank is headquartered")
    # Contact Information
    address = models.TextField(blank=True,help_text="Headquarters address")
    phone = models.CharField(max_length=50,blank=True,help_text="Main contact phone number")
    email = models.EmailField(blank=True,help_text="Main contact email")        
    website = models.URLField(blank=True,help_text="Bank website URL")
    
    # Banking Codes
    swift_code = models.CharField(max_length=11,blank=True,help_text="SWIFT/BIC code for international transfers")
    routing_number = models.CharField(max_length=50,blank=True,help_text="Routing number (country-specific)")
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this bank is currently active"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='banks_created'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='banks_updated'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the bank"
    )
    
    class Meta:
        verbose_name = 'Bank'
        verbose_name_plural = 'Banks'
        ordering = ['bank_name']
        indexes = [
            models.Index(fields=['bank_code']),
            models.Index(fields=['country']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.bank_name} ({self.country.name})"
    
    # ==================== HELPER METHODS ====================
    
    def get_branches(self, active_only=False):
        """
        Get all branches for this bank.
        
        Args:
            active_only (bool): If True, return only active branches
            
        Returns:
            QuerySet: BankBranch objects
        """
        branches = self.branches.all()
        if active_only:
            branches = branches.filter(is_active=True)
        return branches
    
    def get_all_accounts(self, active_only=False):
        """
        Get all bank accounts across all branches.
        
        Args:
            active_only (bool): If True, return only active accounts
            
        Returns:
            QuerySet: BankAccount objects
        """
        accounts = BankAccount.objects.filter(branch__bank=self)
        if active_only:
            accounts = accounts.filter(is_active=True)
        return accounts
    
    def get_branch_by_code(self, branch_code):
        """
        Get a specific branch by its code.
        
        Args:
            branch_code (str): The branch code to search for
            
        Returns:
            BankBranch or None: The branch if found, None otherwise
        """
        try:
            return self.branches.get(branch_code=branch_code)
        except BankBranch.DoesNotExist:
            return None
    
    def get_total_branches_count(self, active_only=False):
        """
        Get total number of branches.
        
        Args:
            active_only (bool): If True, count only active branches
            
        Returns:
            int: Count of branches
        """
        return self.get_branches(active_only=active_only).count()
    
    def get_total_accounts_count(self, active_only=False):
        """
        Get total number of accounts across all branches.
        
        Args:
            active_only (bool): If True, count only active accounts
            
        Returns:
            int: Count of accounts
        """
        return self.get_all_accounts(active_only=active_only).count()
    
    def deactivate(self, user=None):
        """
        Deactivate this bank and optionally all its branches and accounts.
        
        Args:
            user: User performing the action (for audit)
            
        Returns:
            dict: Summary of deactivation
        """
        self.is_active = False
        if user:
            self.updated_by = user
        self.save()
        
        return {
            'bank': self.bank_name,
            'status': 'deactivated',
            'branches_count': self.get_total_branches_count(),
            'accounts_count': self.get_total_accounts_count()
        }
    
    def activate(self, user=None):
        """
        Activate this bank.
        
        Args:
            user: User performing the action (for audit)
        """
        self.is_active = True
        if user:
            self.updated_by = user
        self.save()
    
    def get_summary(self):
        """
        Get a summary of this bank's data.
        
        Returns:
            dict: Summary information
        """
        return {
            'bank_name': self.bank_name,
            'bank_code': self.bank_code,
            'country': self.country.name,
            'swift_code': self.swift_code,
            'is_active': self.is_active,
            'total_branches': self.get_total_branches_count(),
            'active_branches': self.get_total_branches_count(active_only=True),
            'total_accounts': self.get_total_accounts_count(),
            'active_accounts': self.get_total_accounts_count(active_only=True),
        }


class BankBranch(ProtectedDeleteMixin, models.Model):
    """
    Bank branches (Level 2 - Child of Bank).
    Represents physical or virtual branches of a bank.
    """
    
    # Parent Relationship
    bank = models.ForeignKey(
        Bank,
        on_delete=models.PROTECT,
        related_name='branches',
        help_text="Parent bank for this branch"
    )
    
    # Branch Information
    branch_name = models.CharField(
        max_length=255,
        help_text="Name of the branch (e.g., Downtown Branch, Airport Branch)"
    )
    
    branch_code = models.CharField(
        max_length=50,
        help_text="Unique branch code within the bank"
    )
    
    # Contact Information
    address = models.TextField(
        help_text="Branch physical address"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City where branch is located"
    )
    
    
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal/ZIP code"
    )
    
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name='bank_branches',
        help_text="Country where branch is located"
    )
    
    phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Branch phone number"
    )
    
    email = models.EmailField(
        blank=True,
        help_text="Branch email"
    )
    
    # Branch Manager
    manager_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of branch manager"
    )
    
    manager_phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Branch manager phone"
    )
    
    # Banking Codes
    swift_code = models.CharField(
        max_length=11,
        blank=True,
        help_text="Branch-specific SWIFT code (if different from main bank)"
    )
    
    ifsc_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="IFSC code (for Indian banks)"
    )
    
    routing_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Branch routing number"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this branch is currently active"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='bank_branches_created'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bank_branches_updated'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the branch"
    )
    
    class Meta:
        verbose_name = 'Bank Branch'
        verbose_name_plural = 'Bank Branches'
        ordering = ['bank', 'branch_name']
        unique_together = [['bank', 'branch_code']]
        indexes = [
            models.Index(fields=['bank', 'branch_code']),
            models.Index(fields=['country']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.bank.bank_name} - {self.branch_name} ({self.branch_code})"
    
    # ==================== HELPER METHODS ====================
    
    def get_accounts(self, active_only=False):
        """
        Get all accounts for this branch.
        
        Args:
            active_only (bool): If True, return only active accounts
            
        Returns:
            QuerySet: BankAccount objects
        """
        accounts = self.accounts.all()
        if active_only:
            accounts = accounts.filter(is_active=True)
        return accounts
    
    def get_account_by_number(self, account_number):
        """
        Get a specific account by its number.
        
        Args:
            account_number (str): The account number to search for
            
        Returns:
            BankAccount or None: The account if found, None otherwise
        """
        try:
            return self.accounts.get(account_number=account_number)
        except BankAccount.DoesNotExist:
            return None
    
    def get_total_balance(self, currency=None):
        """
        Get total balance across all accounts in this branch.
        
        Args:
            currency: Optional Currency object to filter by
            
        Returns:
            Decimal: Total balance
        """
        accounts = self.get_accounts(active_only=True)
        if currency:
            accounts = accounts.filter(currency=currency)
        
        total = sum(account.current_balance for account in accounts)
        return Decimal(str(total))
    
    def get_accounts_count(self, active_only=False):
        """
        Get total number of accounts.
        
        Args:
            active_only (bool): If True, count only active accounts
            
        Returns:
            int: Count of accounts
        """
        return self.get_accounts(active_only=active_only).count()
    
    def get_parent_bank_details(self):
        """
        Get parent bank information.
        
        Returns:
            dict: Bank details
        """
        return {
            'bank_name': self.bank.bank_name,
            'bank_code': self.bank.bank_code,
            'country': self.bank.country.name,
            'swift_code': self.bank.swift_code,
        }
    
    def deactivate(self, user=None):
        """
        Deactivate this branch.
        
        Args:
            user: User performing the action (for audit)
            
        Returns:
            dict: Summary of deactivation
        """
        self.is_active = False
        if user:
            self.updated_by = user
        self.save()
        
        return {
            'branch': self.branch_name,
            'branch_code': self.branch_code,
            'status': 'deactivated',
            'accounts_count': self.get_accounts_count()
        }
    
    def activate(self, user=None):
        """
        Activate this branch.
        
        Args:
            user: User performing the action (for audit)
        """
        self.is_active = True
        if user:
            self.updated_by = user
        self.save()
    
    def get_full_address(self):
        """
        Get formatted full address.
        
        Returns:
            str: Complete address string
        """
        parts = [self.address]
        if self.city:
            parts.append(self.city)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country.name)
        return ', '.join(parts)
    
    def get_summary(self):
        """
        Get a summary of this branch's data.
        
        Returns:
            dict: Summary information
        """
        return {
            'branch_name': self.branch_name,
            'branch_code': self.branch_code,
            'bank': self.bank.bank_name,
            'city': self.city,
            'country': self.country.name,
            'is_active': self.is_active,
            'total_accounts': self.get_accounts_count(),
            'active_accounts': self.get_accounts_count(active_only=True),
            'manager': self.manager_name,
            'phone': self.phone,
        }


class BankAccount(ProtectedDeleteMixin, models.Model):
    """
    Company's bank accounts (Level 3 - Child of BankBranch).
    Represents the organization's accounts at specific bank branches.
    """
    
    # Account Type Choices
    CURRENT = 'CURRENT'
    SAVINGS = 'SAVINGS'
    FIXED_DEPOSIT = 'FIXED_DEPOSIT'
    LOAN = 'LOAN'
    OVERDRAFT = 'OVERDRAFT'
    
    ACCOUNT_TYPE_CHOICES = [
        (CURRENT, 'Current Account'),
        (SAVINGS, 'Savings Account'),
        (FIXED_DEPOSIT, 'Fixed Deposit'),
        (LOAN, 'Loan Account'),
        (OVERDRAFT, 'Overdraft Account'),
    ]
    transction = [
        ('bank transfer', 'bank transfer'),
        ('check', 'check'),
        ('online payment', 'online payment'),
    ]
    transction_type = models.CharField(
        max_length=50,  
        choices=transction,
        default='bank transfer',
        help_text="Type of transactions allowed for this account"
    )
    # Parent Relationship
    branch = models.ForeignKey(
        BankBranch,
        on_delete=models.PROTECT,
        related_name='accounts',
        help_text="Bank branch where account is held"
    )
    
    # Account Information
    account_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Bank account number"
    )
    
    account_name = models.CharField(
        max_length=255,
        help_text="Name on the account"
    )
    
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default=CURRENT
    )
    
    # Currency and Balance
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='bank_accounts',
        help_text="Currency of this account"
    )
    
    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Opening balance when account was created"
    )
    
    current_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Current balance of the account"
    )
    
    # Account Details
    iban = models.CharField(
        max_length=34,
        blank=True,
        help_text="International Bank Account Number"
    )
    
    opening_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when account was opened"
    )
    
    # GL Integration
    cash_GL_combination = models.ForeignKey(
        XX_Segment_combination,
        on_delete=models.PROTECT,
        related_name='cash_accounts',
        help_text="GL segment combination for this bank account"
    )
    cash_clearing_GL_combination = models.ForeignKey(
        XX_Segment_combination,
        on_delete=models.PROTECT,
        related_name='cash_clearing_accounts',
        help_text="GL segment combination for cash clearing account"
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
        related_name='bank_accounts_created'
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bank_accounts_updated'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional Information
    description = models.TextField(
        blank=True,
        help_text="Additional notes or description"
    )
    
    class Meta:
        verbose_name = 'Bank Account'
        verbose_name_plural = 'Bank Accounts'
        ordering = ['branch__bank', 'account_number']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['branch']),
            models.Index(fields=['account_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.account_number} - {self.account_name} ({self.branch.bank.bank_name})"
    
    # ==================== HELPER METHODS ====================
    
    def get_full_bank_details(self):
        """Returns complete bank hierarchy information"""
        return {
            'bank': self.branch.bank.bank_name,
            'bank_code': self.branch.bank.bank_code,
            'branch': self.branch.branch_name,
            'branch_code': self.branch.branch_code,
            'account': self.account_number,
            'account_name': self.account_name,
            'currency': self.currency.code,
        }
    
    def update_balance(self, amount, user=None, increase=True):
        """
        Update the account balance.
        
        Args:
            amount (Decimal): Amount to add or subtract
            user: User performing the action (for audit)
            increase (bool): True to increase balance, False to decrease
            
        Returns:
            Decimal: New balance
            
        Raises:
            ValidationError: If amount would result in negative balance
        """
        amount = Decimal(str(amount))
        
        if increase:
            new_balance = self.current_balance + amount
        else:
            new_balance = self.current_balance - amount
            
        # Allow negative balance for overdraft accounts
        if new_balance < 0 and self.account_type != self.OVERDRAFT:
            raise ValidationError(
                f"Insufficient balance. Current: {self.current_balance}, "
                f"Attempted: {amount}, Would result in: {new_balance}"
            )
        
        self.current_balance = new_balance
        if user:
            self.updated_by = user
        self.save(update_fields=['current_balance', 'updated_by', 'updated_at'])
        
        return self.current_balance
    
    def check_sufficient_balance(self, amount):
        """
        Check if account has sufficient balance for a transaction.
        
        Args:
            amount (Decimal): Amount to check
            
        Returns:
            bool: True if sufficient balance, False otherwise
        """
        amount = Decimal(str(amount))
        
        # Overdraft accounts can go negative
        if self.account_type == self.OVERDRAFT:
            return True
            
        return self.current_balance >= amount
    
    def get_available_balance(self):
        """
        Get available balance (same as current balance for now).
        Can be extended to include holds, pending transactions, etc.
        
        Returns:
            Decimal: Available balance
        """
        return self.current_balance
    
    def freeze(self, user=None):
        """
        Freeze the account (mark as inactive).
        
        Args:
            user: User performing the action (for audit)
        """
        self.is_active = False
        if user:
            self.updated_by = user
        self.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    
    def unfreeze(self, user=None):
        """
        Unfreeze the account (mark as active).
        
        Args:
            user: User performing the action (for audit)
        """
        self.is_active = True
        if user:
            self.updated_by = user
        self.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    
    def get_full_hierarchy(self):
        """
        Get complete hierarchy: Bank → Branch → Account.
        
        Returns:
            dict: Complete hierarchy information
        """
        return {
            'bank': {
                'name': self.branch.bank.bank_name,
                'code': self.branch.bank.bank_code,
                'country': self.branch.bank.country.name,
                'swift': self.branch.bank.swift_code,
            },
            'branch': {
                'name': self.branch.branch_name,
                'code': self.branch.branch_code,
                'city': self.branch.city,
                'phone': self.branch.phone,
            },
            'account': {
                'number': self.account_number,
                'name': self.account_name,
                'type': self.get_account_type_display(),
                'currency': self.currency.code,
                'balance': float(self.current_balance),
                'iban': self.iban,
            }
        }
    
    def get_balance_summary(self):
        """
        Get balance information summary.
        
        Returns:
            dict: Balance details
        """
        return {
            'account_number': self.account_number,
            'currency': self.currency.code,
            'opening_balance': float(self.opening_balance),
            'current_balance': float(self.current_balance),
            'available_balance': float(self.get_available_balance()),
            'change': float(self.current_balance - self.opening_balance),
        }
    
    def validate_transaction_amount(self, amount, transaction_type='debit'):
        """
        Validate if a transaction amount is allowed.
        
        Args:
            amount (Decimal): Transaction amount
            transaction_type (str): 'debit' or 'credit'
            
        Returns:
            tuple: (is_valid, error_message)
        """
        amount = Decimal(str(amount))
        
        if amount <= 0:
            return False, "Transaction amount must be positive"
        
        if transaction_type == 'debit':
            if not self.check_sufficient_balance(amount):
                return False, f"Insufficient balance. Available: {self.current_balance}"
        
        return True, None
    
    @classmethod
    def get_by_account_number(cls, account_number):
        """
        Get account by account number.
        
        Args:
            account_number (str): Account number to search
            
        Returns:
            BankAccount or None: Account if found
        """
        try:
            return cls.objects.get(account_number=account_number)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_active_accounts(cls, branch=None, bank=None, currency=None):
        """
        Get all active accounts with optional filters.
        
        Args:
            branch: Optional BankBranch to filter by
            bank: Optional Bank to filter by
            currency: Optional Currency to filter by
            
        Returns:
            QuerySet: Filtered BankAccount objects
        """
        accounts = cls.objects.filter(is_active=True)
        
        if branch:
            accounts = accounts.filter(branch=branch)
        elif bank:
            accounts = accounts.filter(branch__bank=bank)
            
        if currency:
            accounts = accounts.filter(currency=currency)
            
        return accounts


# ==================== BANK STATEMENT MODELS ====================

class BankStatement(ProtectedDeleteMixin, models.Model):
    """
    Represents a bank statement for a specific period.
    Contains multiple transactions and tracks reconciliation status.
    """
    
    # Reconciliation Status Choices
    PENDING = 'PENDING'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    APPROVED = 'APPROVED'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETED, 'Completed'),
        (APPROVED, 'Approved'),
    ]
    
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name='statements',
        help_text="Bank account for this statement"
    )
    
    statement_number = models.CharField(
        max_length=100,
        help_text="Bank statement reference number"
    )
    
    statement_date = models.DateField(
        help_text="Date of the bank statement"
    )
    
    from_date = models.DateField(
        help_text="Statement period start date"
    )
    
    to_date = models.DateField(
        help_text="Statement period end date"
    )
    
    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Opening balance at period start"
    )
    
    closing_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Closing balance at period end"
    )
    
    transaction_count = models.IntegerField(
        default=0,
        help_text="Number of transactions in this statement"
    )
    
    total_debits = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Total debit amount"
    )
    
    total_credits = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Total credit amount"
    )
    
    reconciliation_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        help_text="Reconciliation status"
    )
    
    # Import metadata
    import_file_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Original import file name"
    )
    
    import_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When statement was imported"
    )
    
    imported_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='imported_statements',
        help_text="User who imported this statement"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_bank_statements',
        help_text="User who created this statement"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='updated_bank_statements',
        help_text="User who last updated this statement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Bank Statement'
        verbose_name_plural = 'Bank Statements'
        ordering = ['-statement_date', '-created_at']
        indexes = [
            models.Index(fields=['bank_account', 'statement_date']),
            models.Index(fields=['reconciliation_status']),
            models.Index(fields=['from_date', 'to_date']),
        ]
        unique_together = [
            ['bank_account', 'statement_number'],
        ]
    
    def __str__(self):
        return f"Statement {self.statement_number} - {self.bank_account.account_number} ({self.statement_date})"
    
    def clean(self):
        """Validate statement data"""
        super().clean()
        
        # Validate date ranges
        if self.from_date and self.to_date:
            if self.from_date > self.to_date:
                raise ValidationError("from_date cannot be after to_date")
        
        if self.statement_date and self.to_date:
            if self.statement_date < self.to_date:
                raise ValidationError("statement_date should not be before to_date")
        
        # Validate balances
        if hasattr(self, 'opening_balance') and hasattr(self, 'closing_balance'):
            calculated_closing = self.opening_balance + self.total_credits - self.total_debits
            if abs(calculated_closing - self.closing_balance) > Decimal('0.01'):
                raise ValidationError(
                    f"Closing balance mismatch: Expected {calculated_closing}, "
                    f"got {self.closing_balance}"
                )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    # ==================== HELPER METHODS ====================
    
    def calculate_totals(self):
        """
        Calculate total debits, credits, and transaction count from related statement lines
        """
        lines = self.statement_lines.all()
        
        self.transaction_count = lines.count()
        self.total_debits = sum(
            line.debit_amount for line in lines
        ) or Decimal('0')
        self.total_credits = sum(
            line.credit_amount for line in lines
        ) or Decimal('0')
        
        # Update closing balance based on calculated totals
        self.closing_balance = self.opening_balance + self.total_credits - self.total_debits
        
        self.save()
    
    def get_unreconciled_lines(self):
        """
        Get all unreconciled statement lines in this statement
        """
        return self.statement_lines.filter(
            reconciliation_status=BankStatementLine.UNRECONCILED
        )
    
    def get_reconciled_lines(self):
        """
        Get all reconciled statement lines in this statement
        """
        return self.statement_lines.filter(
            reconciliation_status=BankStatementLine.RECONCILED
        )
    
    def get_reconciliation_percentage(self):
        """
        Calculate percentage of reconciled statement lines
        """
        total = self.transaction_count
        if total == 0:
            return 0
        
        reconciled = self.get_reconciled_lines().count()
        return (reconciled / total) * 100
    
    def mark_as_completed(self):
        """
        Mark statement reconciliation as completed
        """
        if self.get_unreconciled_lines().exists():
            raise ValidationError(
                "Cannot mark statement as completed while unreconciled lines exist"
            )
        
        self.reconciliation_status = self.COMPLETED
        self.save()
    
    def mark_as_approved(self):
        """
        Mark statement reconciliation as approved
        """
        if self.reconciliation_status != self.COMPLETED:
            raise ValidationError(
                "Statement must be completed before it can be approved"
            )
        
        self.reconciliation_status = self.APPROVED
        self.save()
    
    @property
    def is_fully_reconciled(self):
        """Check if all lines are reconciled"""
        return not self.get_unreconciled_lines().exists()
    
    @property
    def unreconciled_amount(self):
        """Calculate total unreconciled amount"""
        unreconciled = self.get_unreconciled_lines()
        return sum(
            line.get_abs_amount() for line in unreconciled
        ) or Decimal('0')


class BankStatementLine(ProtectedDeleteMixin, models.Model):
    """
    Represents individual lines from imported bank statements.
    These are the actual transactions reported by the bank.
    """
    
    # Reconciliation Status Choices
    UNRECONCILED = 'UNRECONCILED'
    RECONCILED = 'RECONCILED'
    DISCREPANCY = 'DISCREPANCY'
    RECONCILIATION_STATUS_CHOICES = [
        (UNRECONCILED, 'Unreconciled'),
        (RECONCILED, 'Reconciled'),
        (DISCREPANCY, 'Discrepancy'),
    ]
    
    bank_statement = models.ForeignKey(
        BankStatement,
        on_delete=models.PROTECT,
        related_name='statement_lines',
        help_text="Bank statement this line belongs to"
    )
    
    line_number = models.IntegerField(
        help_text="Line number in the statement"
    )
    
    transaction_date = models.DateField(
        help_text="Date transaction was initiated"
    )
    
    value_date = models.DateField(
        help_text="Date transaction was valued/cleared"
    )
    
    description = models.TextField(
        blank=True,
        default='',
        help_text="Transaction description from bank"
    )
    
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Bank reference or transaction ID"
    )
    
    debit_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Debit amount (if applicable)"
    )
    
    credit_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Credit amount (if applicable)"
    )
    
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Balance after this transaction"
    )
    
    # Reconciliation fields
    reconciliation_status = models.CharField(
        max_length=20,
        choices=RECONCILIATION_STATUS_CHOICES,
        default=UNRECONCILED,
        help_text="Reconciliation status of this line"
    )
    
    matched_payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='matched_statement_lines',
        help_text="System payment matched to this statement line"
    )
    
    reconciled_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this line was reconciled"
    )
    
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reconciled_statement_lines',
        help_text="User who reconciled this line"
    )
    
    notes = models.TextField(
        blank=True,
        default='',
        help_text="Additional notes about this line"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_statement_lines',
        help_text="User who created/imported this line"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='updated_statement_lines',
        help_text="User who last updated this line"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Bank Statement Line'
        verbose_name_plural = 'Bank Statement Lines'
        ordering = ['bank_statement', 'line_number']
        indexes = [
            models.Index(fields=['bank_statement', 'line_number']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['reconciliation_status']),
            models.Index(fields=['reference_number']),
        ]
        unique_together = [
            ['bank_statement', 'line_number'],
        ]
    
    def __str__(self):
        amount = self.debit_amount if self.debit_amount > 0 else self.credit_amount
        txn_type = 'Debit' if self.debit_amount > 0 else 'Credit'
        return f"Line {self.line_number}: {txn_type} {amount} on {self.transaction_date}"
    
    def clean(self):
        """Validate statement line data"""
        super().clean()
        
        # Validate that either debit or credit is set, but not both
        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValidationError("A line cannot have both debit and credit amounts")
        
        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValidationError("A line must have either a debit or credit amount")
        
        # Validate value_date is not before transaction_date
        if self.value_date and self.transaction_date:
            if self.value_date < self.transaction_date:
                raise ValidationError("Value date cannot be before transaction date")
        
        # Validate reconciliation fields consistency
        if self.reconciliation_status == self.RECONCILED:
            if not self.matched_payment:
                raise ValidationError("Reconciled lines must have a matched payment")
            if not self.reconciled_date or not self.reconciled_by:
                raise ValidationError("Reconciled lines must have reconciled_date and reconciled_by")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    # ==================== HELPER METHODS ====================
    
    def get_amount(self):
        """Get transaction amount (positive for credit, negative for debit)"""
        if self.credit_amount > 0:
            return self.credit_amount
        return -self.debit_amount
    
    def get_abs_amount(self):
        """Get absolute transaction amount"""
        return self.credit_amount if self.credit_amount > 0 else self.debit_amount
    
    def mark_as_reconciled(self, payment, user, reconciliation_date=None):
        """
        Mark statement line as reconciled with a system payment.
        Updates both the line and the matched payment.
        
        Args:
            payment (Payment): System payment to match
            user (User): User performing reconciliation
            reconciliation_date (datetime): Optional reconciliation date
        """
        if self.reconciliation_status == self.RECONCILED:
            raise ValidationError("Statement line is already reconciled")
        
        # Update statement line
        self.reconciliation_status = self.RECONCILED
        self.matched_payment = payment
        self.reconciled_date = reconciliation_date or timezone.now()
        self.reconciled_by = user
        self.save()
        
        # Update matched payment
        payment.reconciliation_status = 'RECONCILED'
        payment.reconciled_date = self.reconciled_date
        payment.reconciled_by = user
        payment.save(update_fields=['reconciliation_status', 'reconciled_date', 'reconciled_by'])
    
    def mark_as_unreconciled(self):
        """
        Mark statement line as unreconciled (undo reconciliation).
        """
        if self.reconciliation_status != self.RECONCILED:
            raise ValidationError("Statement line is not reconciled")
        
        # Update matched payment if exists
        if self.matched_payment:
            payment = self.matched_payment
            payment.reconciliation_status = 'UNRECONCILED'
            payment.reconciled_date = None
            payment.reconciled_by = None
            payment.save(update_fields=['reconciliation_status', 'reconciled_date', 'reconciled_by'])
        
        # Update statement line
        self.reconciliation_status = self.UNRECONCILED
        self.matched_payment = None
        self.reconciled_date = None
        self.reconciled_by = None
        self.save()


class BankStatementLineMatch(models.Model):
    """
    Represents a match between a bank statement line and a payment.
    Direct reconciliation flow: Statement Line <-> Payment
    """
    
    # Match Status Choices
    MATCHED = 'MATCHED'
    PARTIAL = 'PARTIAL'
    UNMATCHED = 'UNMATCHED'
    MANUAL = 'MANUAL'
    MATCH_STATUS_CHOICES = [
        (MATCHED, 'Matched'),
        (PARTIAL, 'Partial Match'),
        (UNMATCHED, 'Unmatched'),
        (MANUAL, 'Manual Match'),
    ]
    
    # Match Type Choices
    EXACT = 'EXACT'
    AMOUNT_DATE = 'AMOUNT_DATE'
    REFERENCE = 'REFERENCE'
    DESCRIPTION = 'DESCRIPTION'
    MANUAL_TYPE = 'MANUAL'
    MATCH_TYPE_CHOICES = [
        (EXACT, 'Exact Match'),
        (AMOUNT_DATE, 'Amount and Date'),
        (REFERENCE, 'Reference Number'),
        (DESCRIPTION, 'Description Match'),
        (MANUAL_TYPE, 'Manual'),
    ]
    
    statement_line = models.ForeignKey(
        BankStatementLine,
        on_delete=models.PROTECT,
        related_name='matches',
        help_text="Bank statement line from import"
    )
    
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.PROTECT,
        related_name='statement_matches',
        help_text="System payment transaction"
    )
    
    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default=MATCHED,
        help_text="Match status"
    )
    
    match_type = models.CharField(
        max_length=20,
        choices=MATCH_TYPE_CHOICES,
        help_text="How the match was determined"
    )
    
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00,
        help_text="Match confidence percentage (0-100)"
    )
    
    discrepancy_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Amount difference between statement line and transaction"
    )
    
    # Match metadata
    matched_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_statement_matches',
        help_text="User who created this match"
    )
    
    matched_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When match was created"
    )
    
    notes = models.TextField(
        blank=True,
        default='',
        help_text="Match notes or explanation"
    )
    
    class Meta:
        verbose_name = 'Bank Statement Line Match'
        verbose_name_plural = 'Bank Statement Line Matches'
        ordering = ['-matched_at']
        indexes = [
            models.Index(fields=['statement_line']),
            models.Index(fields=['payment']),
            models.Index(fields=['match_status']),
        ]
    
    def __str__(self):
        return f"Match: Line {self.statement_line.line_number} -> Payment {self.payment.id}"
    
    def clean(self):
        """Validate match data"""
        super().clean()
        
        # Validate confidence score range
        if self.confidence_score < 0 or self.confidence_score > 100:
            raise ValidationError("Confidence score must be between 0 and 100")
        
        # Validate amount match is reasonable
        line_amount = self.statement_line.get_abs_amount()
        payment_amount = self.payment.get_total_amount() if hasattr(self.payment, 'get_total_amount') else Decimal('0')
        diff = abs(line_amount - payment_amount)
        
        if diff > (line_amount * Decimal('0.10')):  # More than 10% difference
            if self.match_status == self.MATCHED and self.match_type != self.MANUAL_TYPE:
                raise ValidationError(
                    f"Amount difference ({diff}) is too large for automatic match. Use manual match."
                )
    
    def save(self, *args, **kwargs):
        self.clean()
        
        # Calculate discrepancy before saving
        line_amount = self.statement_line.get_abs_amount()
        payment_amount = self.payment.get_total_amount() if hasattr(self.payment, 'get_total_amount') else Decimal('0')
        self.discrepancy_amount = abs(line_amount - payment_amount)
        
        super().save(*args, **kwargs)
        
        # Update both reconciliation statuses
        if self.match_status == self.MATCHED:
            # Mark statement line as reconciled
            if self.statement_line.reconciliation_status != BankStatementLine.RECONCILED:
                self.statement_line.reconciliation_status = BankStatementLine.RECONCILED
                self.statement_line.matched_payment = self.payment
                self.statement_line.reconciled_date = timezone.now()
                self.statement_line.reconciled_by = self.matched_by
                self.statement_line.save()
            
            # Mark payment as reconciled
            if self.payment.reconciliation_status != 'RECONCILED':
                self.payment.reconciliation_status = 'RECONCILED'
                self.payment.reconciled_date = timezone.now()
                self.payment.reconciled_by = self.matched_by
                self.payment.save(update_fields=['reconciliation_status', 'reconciled_date', 'reconciled_by'])
    
    # ==================== HELPER METHODS ====================
    
    def unmatch(self):
        """
        Remove this match and mark both entities as unreconciled
        """
        # Mark statement line as unreconciled
        if self.statement_line.reconciliation_status == BankStatementLine.RECONCILED:
            self.statement_line.reconciliation_status = BankStatementLine.UNRECONCILED
            self.statement_line.matched_payment = None
            self.statement_line.reconciled_date = None
            self.statement_line.reconciled_by = None
            self.statement_line.save()
        
        # Mark payment as unreconciled
        if self.payment.reconciliation_status == 'RECONCILED':
            self.payment.reconciliation_status = 'UNRECONCILED'
            self.payment.reconciled_date = None
            self.payment.reconciled_by = None
            self.payment.save(update_fields=['reconciliation_status', 'reconciled_date', 'reconciled_by'])
        
        self.delete()
    
    @property
    def is_exact_match(self):
        """Check if this is an exact match with no discrepancy"""
        return self.match_status == self.MATCHED and self.discrepancy_amount == 0
    
    @property
    def has_discrepancy(self):
        """Check if match has amount discrepancy"""
        return self.discrepancy_amount > 0