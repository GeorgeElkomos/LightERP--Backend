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
    