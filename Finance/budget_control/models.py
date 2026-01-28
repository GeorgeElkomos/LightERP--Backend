"""
Budget Control Models - Segment-Based Flexible Budgeting

Design (3 Models):
1. BudgetHeader - Main budget container with default control level
2. BudgetSegmentValue - Segment values included in budget with optional control level override
3. BudgetAmount - Budget amounts per segment with encumbered/actual tracking

Key Features:
- Budget by individual segment values (not combinations)
- Each segment can override the default control level
- If no override, uses budget header's default_control_level
- Single Excel import/export per budget
- Strictest control level applied during check (implemented later in services)
- Eliminated duplicate fields from previous BudgetControlRule class
"""

from django.db import models
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal

from Finance.GL.models import XX_Segment, XX_SegmentType
from Finance.core.models import Currency


class BudgetHeader(models.Model):
    """
    Budget Header - Main budget definition and control settings
    
    Purpose:
    - Container for all budget amounts
    - Defines default control level
    - Single currency per budget
    - Active/inactive control
    
    Business Rules:
    - Only ONE active budget per fiscal year (optional constraint)
    - Cannot delete if has budget amounts
    - Status workflow: DRAFT → ACTIVE → CLOSED
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
    ]
    
    CONTROL_LEVEL_CHOICES = [
        ('NONE', 'No Control'),
        ('TRACK', 'Track'),
        ('ADVISORY', 'Advisory'),
        ('ABSOLUTE', 'Absolute Control'),
    ]
    
    budget_code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique budget code, e.g., 'FY2026-OPERATING'"
    )
    
    budget_name = models.CharField(
        max_length=200,
        help_text="Descriptive budget name, e.g., 'FY 2026 Operating Budget'"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Additional details about this budget"
    )
    
    start_date = models.DateField(
        help_text="Budget effective start date"
    )
    
    end_date = models.DateField(
        help_text="Budget effective end date"
    )
    
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        help_text="Budget currency (base currency only)"
    )
    
    default_control_level = models.CharField(
        max_length=20,
        choices=CONTROL_LEVEL_CHOICES,
        default='ABSOLUTE',
        help_text="Default budget control enforcement level (can be overridden per segment)"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    
    is_active = models.BooleanField(
        default=False,
        help_text="Is this budget currently active for budget checking?"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this budget"
    )
    
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_by = models.CharField(max_length=100, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'budget_header'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['budget_code']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.budget_code} - {self.budget_name}"
    
    # ==================== LIFECYCLE HELPER FUNCTIONS ====================
    
    def can_activate(self):
        """
        Check if budget can be activated.
        
        Returns:
            tuple: (bool, str) - (can_activate, error_message)
        """
        if self.status == 'ACTIVE':
            return False, "Budget is already active"
        
        if self.status == 'CLOSED':
            return False, "Cannot activate a closed budget"
        
        if not self.budget_segment_values.exists():
            return False, "Budget must have at least one segment value before activation"
        
        if not self.budget_amounts.exists():
            return False, "Budget must have at least one budget amount before activation"
        
        return True, ""
    
    def activate(self, activated_by):
        """
        Activate the budget.
        
        Args:
            activated_by: str - Username or user ID of person activating
        
        Raises:
            ValidationError: If budget cannot be activated
        """
        from django.core.exceptions import ValidationError
        
        can_activate, error = self.can_activate()
        if not can_activate:
            raise ValidationError(error)
        
        self.status = 'ACTIVE'
        self.is_active = True
        self.activated_by = activated_by
        self.activated_at = timezone.now()
        self.save()
    
    def close(self, closed_by=None):
        """
        Close the budget. Closed budgets cannot be reactivated.
        
        Args:
            closed_by: Optional identifier of who closed the budget
        """
        self.status = 'CLOSED'
        self.is_active = False
        self.save()
    
    def deactivate(self):
        """
        Deactivate the budget without closing it. Can be reactivated later.
        """
        self.is_active = False
        self.status = 'DRAFT'
        self.save()
    
    def can_delete(self):
        """
        Check if this budget can be deleted.
        Only DRAFT budgets with no budget amounts can be deleted.
        
        Returns:
            tuple: (can_delete: bool, error_message: str)
        """
        if self.status == 'ACTIVE':
            return False, "Cannot delete an ACTIVE budget. Deactivate it first."
        
        if self.status == 'CLOSED':
            return False, "Cannot delete a CLOSED budget."
        
        if self.budget_amounts.exists():
            return False, "Cannot delete budget with existing budget amounts."
        
        return True, None
    
    def is_date_in_range(self, check_date):
        """
        Check if a date falls within this budget's effective period.
        
        Args:
            check_date: date object to check
        
        Returns:
            bool: True if date is within budget period
        """
        return self.start_date <= check_date <= self.end_date
    
    # ==================== QUERY HELPER FUNCTIONS ====================
    
    @classmethod
    def get_active_budget_for_date(cls, check_date):
        """
        Find the active budget that covers a specific date.
        
        Args:
            check_date: date object to check
        
        Returns:
            BudgetHeader object or None
        """
        return cls.objects.filter(
            is_active=True,
            status='ACTIVE',
            start_date__lte=check_date,
            end_date__gte=check_date
        ).first()
    
    @classmethod
    def get_active_budgets(cls):
        """
        Get all currently active budgets.
        
        Returns:
            QuerySet of BudgetHeader objects
        """
        return cls.objects.filter(is_active=True, status='ACTIVE')
    
    def get_applicable_segment_values(self, segment_list):
        """
        Get budget segment values that match any of the provided segments.
        
        Args:
            segment_list: List of XX_Segment objects or segment IDs
        
        Returns:
            QuerySet of BudgetSegmentValue objects
        """
        if not segment_list:
            return self.budget_segment_values.none()
        
        # Handle both segment objects and IDs
        segment_ids = [s.id if hasattr(s, 'id') else s for s in segment_list]
        
        return self.budget_segment_values.filter(
            segment_value_id__in=segment_ids,
            is_active=True
        ).select_related('segment_value', 'segment_value__segment_type')
    
    # ==================== CALCULATION HELPER FUNCTIONS ====================
    
    def get_total_budget(self):
        """
        Calculate total budget amount across all segments.
        
        Returns:
            Decimal: Sum of all budget amounts (original + adjustments)
        """
        from django.db.models import Sum, F
        result = self.budget_amounts.aggregate(
            total=Sum(F('original_budget') + F('adjustment_amount'))
        )['total']
        return result or Decimal('0.00')
    
    def get_total_encumbered(self):
        """
        Calculate total encumbered amount across all segments.
        
        Returns:
            Decimal: Sum of all encumbered amounts
        """
        from django.db.models import Sum
        result = self.budget_amounts.aggregate(total=Sum('encumbered_amount'))['total']
        return result or Decimal('0.00')
    
    def get_total_actual(self):
        """
        Calculate total actual spending across all segments.
        
        Returns:
            Decimal: Sum of all actual amounts
        """
        from django.db.models import Sum
        result = self.budget_amounts.aggregate(total=Sum('actual_amount'))['total']
        return result or Decimal('0.00')
    
    def get_total_consumed(self):
        """
        Calculate total consumed amount (encumbered + actual) across all segments.
        
        Returns:
            Decimal: Sum of encumbered and actual amounts
        """
        return self.get_total_encumbered() + self.get_total_actual()
    
    def get_total_available(self):
        """
        Calculate total available budget across all segments.
        
        Returns:
            Decimal: Total budget minus total consumed
        """
        return self.get_total_budget() - self.get_total_consumed()
    
    def get_utilization_percentage(self):
        """
        Calculate overall budget utilization percentage.
        
        Returns:
            Decimal: Percentage of budget consumed (0-100)
        """
        total_budget = self.get_total_budget()
        if total_budget == 0:
            return Decimal('0.00')
        
        total_consumed = self.get_total_consumed()
        return (total_consumed / total_budget * 100).quantize(Decimal('0.01'))
    
    def get_applicable_budget_amounts(self, segment_list):
        """
        Get budget amounts for a list of segments.
        Returns QuerySet of BudgetAmount objects that match the given segments.
        
        Args:
            segment_list: List of XX_Segment objects from the transaction
        
        Returns:
            QuerySet: BudgetAmount objects for matching segments
        """
        segment_values = self.get_applicable_segment_values(segment_list)
        return BudgetAmount.objects.filter(
            budget_segment_value__in=segment_values,
            budget_header=self
        )
    
    # ==================== BUDGET CHECKING LOGIC ====================
    
    def check_budget_for_segments(self, segment_list, transaction_amount, transaction_date=None):
        """
        Check budget availability for a list of segments.
        This is the MAIN budget checking function called from PO/Invoice approval.
        
        Args:
            segment_list: List of XX_Segment objects from the transaction
            transaction_amount: Decimal amount to check
            transaction_date: Date of transaction (defaults to today)
        
        Returns:
            dict: {
                'allowed': bool,
                'control_level': str (NONE/TRACK/ADVISORY/ABSOLUTE),
                'violations': list of dicts with segment details,
                'message': str
            }
        """
        if transaction_date is None:
            from datetime import date
            transaction_date = date.today()
        
        # Check if transaction date is in budget period
        if not self.is_date_in_range(transaction_date):
            return {
                'allowed': False,
                'control_level': 'ABSOLUTE',
                'violations': [],
                'message': f"Transaction date {transaction_date} is outside budget period ({self.start_date} to {self.end_date})"
            }
        
        # Get applicable budget segment values
        applicable_segments = self.get_applicable_segment_values(segment_list)
        
        if not applicable_segments.exists():
            # No budget defined for these segments
            return {
                'allowed': True,
                'control_level': 'NONE',
                'violations': [],
                'message': 'No budget control defined for these segments'
            }
        
        # Check each segment's budget
        violations = []
        control_levels = []
        
        for budget_segment in applicable_segments:
            budget_amt = budget_segment.budget_amount
            control_level = budget_segment.get_effective_control_level()
            control_levels.append(control_level)
            
            # Check if sufficient budget available
            check_result = budget_amt.check_funds_available(transaction_amount)
            
            if not check_result['sufficient']:
                violations.append({
                    'segment': str(budget_segment.segment_value),
                    'segment_type': budget_segment.segment_value.segment_type.segment_name,
                    'control_level': control_level,
                    'total_budget': float(budget_amt.get_total_budget()),
                    'committed': float(budget_amt.committed_amount),
                    'encumbered': float(budget_amt.encumbered_amount),
                    'actual': float(budget_amt.actual_amount),
                    'available': float(check_result['available']),
                    'requested': float(transaction_amount),
                    'shortage': float(check_result['shortage'])
                })
        
        # Get strictest control level
        strictest_level = self.get_strictest_control_level(control_levels)
        
        # Determine if transaction is allowed based on strictest control level
        if not violations:
            return {
                'allowed': True,
                'control_level': strictest_level,
                'violations': [],
                'message': 'Budget check passed'
            }
        
        # Have violations - check control level
        if strictest_level == 'NONE':
            allowed = True
            message = 'Budget exceeded but no control enforced - transaction allowed'
        elif strictest_level == 'TRACK_ONLY':
            allowed = True
            message = 'Budget exceeded - tracked for reporting only, transaction allowed'
        elif strictest_level == 'ADVISORY':
            allowed = True
            message = 'Budget exceeded - advisory warning issued, transaction allowed'
        else:  # ABSOLUTE
            allowed = False
            message = 'Budget exceeded - transaction BLOCKED by absolute control'
        
        return {
            'allowed': allowed,
            'control_level': strictest_level,
            'violations': violations,
            'message': message
        }
    
    @staticmethod
    def get_strictest_control_level(control_levels):
        """
        Get the strictest control level from a list.
        Priority: ABSOLUTE > ADVISORY > TRACK_ONLY > NONE
        
        Args:
            control_levels: List of control level strings
        
        Returns:
            str: Strictest control level
        """
        if not control_levels:
            return 'NONE'
        
        priority = {'ABSOLUTE': 4, 'ADVISORY': 3, 'TRACK_ONLY': 2, 'NONE': 1}
        strictest = max(control_levels, key=lambda x: priority.get(x, 0))
        return strictest


class BudgetSegmentValue(models.Model):
    """
    Budget Segment Value - Defines which segment values are budgeted with optional control level override
    
    Purpose:
    - Track which segment values are included in the budget
    - Allow override control level per segment value
    - If control level not overridden, uses budget header's default_control_level
    - Eliminates duplicate fields from previous BudgetControlRule
    
    Example:
    - Segment: Account 5000, Control: ABSOLUTE
    - Segment: Department 1, Control: None (uses budget default)
    - Segment: Project PROJ1, Control: WARNING
    
    Business Rules:
    - If control_level is NULL, system uses budget_header.default_control_level
    - Cannot delete if budget amounts exist for this segment
    - Each segment value appears only once per budget
    """
    
    CONTROL_LEVEL_CHOICES = [
        ('NONE', 'No Control'),
        ('TRACK_ONLY', 'Track Only'),
        ('ADVISORY', 'Advisory'),
        ('ABSOLUTE', 'Absolute Control'),
    ]
    
    budget_header = models.ForeignKey(
        BudgetHeader,
        on_delete=models.CASCADE,
        related_name='budget_segment_values',
        help_text="Parent budget header"
    )
    
    segment_value = models.ForeignKey(
        XX_Segment,
        on_delete=models.PROTECT,
        related_name='budget_segment_values',
        help_text="Segment value to budget on (e.g., Account 5000, Department 1, Project PROJ1)"
    )
    
    control_level = models.CharField(
        max_length=20,
        choices=CONTROL_LEVEL_CHOICES,
        null=True,
        blank=True,
        help_text="Override control level for this segment. If NULL, uses budget_header.default_control_level"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Is this segment value active for budget checking?"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Notes or reason for this segment's control level"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'budget_segment_value'
        ordering = ['budget_header', 'segment_value']
        indexes = [
            models.Index(fields=['budget_header', 'segment_value']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['budget_header', 'segment_value'],
                name='unique_segment_value_per_budget'
            )
        ]
    
    def __str__(self):
        control = self.control_level or 'DEFAULT'
        return f"{self.budget_header.budget_code} - {self.segment_value} [{control}]"
    
    def get_effective_control_level(self):
        """
        Returns the effective control level for this segment.
        If control_level is set, returns it. Otherwise, returns budget header's default.
        """
        return self.control_level or self.budget_header.default_control_level
    
    def get_budget_amount(self):
        """
        Get the BudgetAmount record associated with this segment value.
        
        Returns:
            BudgetAmount object or None
        """
        try:
            return self.budget_amount
        except BudgetAmount.DoesNotExist:
            return None
    
    def has_budget(self):
        """
        Check if this segment value has a budget amount defined.
        
        Returns:
            bool: True if budget amount exists
        """
        return hasattr(self, 'budget_amount')
    
    def is_applicable_to_transaction(self, transaction_segments):
        """
        Check if this budget segment value matches any segment in a transaction.
        
        Args:
            transaction_segments: List of XX_Segment objects from PO/Invoice
        
        Returns:
            bool: True if this segment value is in the transaction
        """
        transaction_segment_ids = [s.id if hasattr(s, 'id') else s for s in transaction_segments]
        return self.segment_value_id in transaction_segment_ids


class BudgetAmount(models.Model):
    """
    Budget Amount - Budget allocated to individual segment value
    
    Purpose:
    - Store budget for each individual segment value
    - Track encumbered (committed via POs) and actual (spent via invoices)
    - Calculate available budget in real-time
    - Links to BudgetSegmentValue for control level
    
    Key Concept: INDIVIDUAL SEGMENT BUDGETING
    - Each record is for ONE segment value (not a combination)
    - Example: Account 5000 = $100,000
    - Example: Department 1 = $50,000
    - Example: Project PROJ1 = $30,000
    
    During budget check (implemented later):
    - PO with Account=5000 + Dept=1 + Project=PROJ1
    - System checks budget for EACH segment individually
    - Gets control level from BudgetSegmentValue (or default from header)
    - Applies strictest control level among all segments
    - Consumes budget from EACH applicable segment
    
    Business Rules:
    - Encumbered/Actual amounts are AUTO-UPDATED (don't edit manually)
    - Available = Budget - Encumbered - Actual
    - One budget amount per segment value per budget header
    - Must have corresponding BudgetSegmentValue record
    """
    
    budget_segment_value = models.OneToOneField(
        'BudgetSegmentValue',
        on_delete=models.CASCADE,
        related_name='budget_amount',
        help_text="Links to segment value definition (includes control level)"
    )
    
    budget_header = models.ForeignKey(
        BudgetHeader,
        on_delete=models.CASCADE,
        related_name='budget_amounts',
        help_text="Parent budget header (for easier querying)"
    )
    
    original_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Original budget allocation for this segment value"
    )
    
    adjustment_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Budget adjustments (positive or negative). AUTO-UPDATED by budget amendments."
    )
    
    committed_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount committed via approved PRs (Purchase Requisitions - Stage 1). AUTO-UPDATED by system."
    )
    
    encumbered_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount encumbered via approved POs (Purchase Orders - Stage 2). AUTO-UPDATED by system."
    )
    
    actual_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount actually spent via approved/posted invoices (Stage 3). AUTO-UPDATED by system."
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Notes or justification for this budget amount"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_committed_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time budget was committed via PR (Stage 1)"
    )
    last_encumbered_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time budget was encumbered via PO (Stage 2)"
    )
    last_actual_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time budget was consumed by actual spending via Invoice (Stage 3)"
    )
    last_adjustment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time budget was adjusted"
    )
    
    class Meta:
        db_table = 'budget_amount'
        ordering = ['budget_header']
        indexes = [
            models.Index(fields=['budget_header', 'budget_segment_value']),
            models.Index(fields=['budget_segment_value']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['budget_header', 'budget_segment_value'],
                name='unique_budget_per_segment_value'
            )
        ]
    
    def __str__(self):
        segment_value = self.budget_segment_value.segment_value
        return f"{self.budget_header.budget_code}: {segment_value} = {self.get_total_budget()}"
    
    # ==================== CALCULATION HELPER FUNCTIONS ====================
    
    def get_total_budget(self):
        """
        Calculate total budget including adjustments.
        Formula: Total = Original + Adjustments
        
        Returns:
            Decimal: Total budget amount
        """
        return Decimal(str(self.original_budget)) + Decimal(str(self.adjustment_amount))
    
    def get_available(self):
        """
        Calculate available budget.
        Formula: Available = (Original + Adjustments) - Committed - Encumbered - Actual
        
        Returns:
            Decimal: Available budget amount
        """
        return (Decimal(str(self.original_budget)) + Decimal(str(self.adjustment_amount)) - 
                Decimal(str(self.committed_amount)) - Decimal(str(self.encumbered_amount)) - Decimal(str(self.actual_amount)))
    
    def get_consumed_total(self):
        """
        Calculate total consumed budget (committed + encumbered + actual).
        
        Returns:
            Decimal: Total consumed amount
        """
        return self.committed_amount + self.encumbered_amount + self.actual_amount
    
    def get_utilization_percentage(self):
        """
        Calculate budget utilization percentage.
        
        Returns:
            Decimal: Percentage of budget consumed (0-100)
        """
        total_budget = self.get_total_budget()
        if total_budget == 0:
            return Decimal('0.00')
        
        consumed = self.get_consumed_total()
        return (consumed / total_budget * 100).quantize(Decimal('0.01'))
    
    def check_funds_available(self, amount):
        """
        Check if sufficient funds are available for a transaction.
        
        Args:
            amount: Decimal amount to check
        
        Returns:
            dict: {
                'sufficient': bool,
                'available': Decimal,
                'requested': Decimal,
                'shortage': Decimal (0 if sufficient)
            }
        """
        available = self.get_available()
        sufficient = available >= amount
        shortage = max(Decimal('0.00'), amount - available)
        
        return {
            'sufficient': sufficient,
            'available': available,
            'requested': amount,
            'shortage': shortage
        }
    
    def can_consume(self, amount):
        """
        Check if amount can be consumed from this budget.
        
        Args:
            amount: Decimal amount to consume
        
        Returns:
            tuple: (bool, str) - (can_consume, error_message)
        """
        if amount <= 0:
            return False, "Amount must be greater than zero"
        
        if not self.budget_header.is_active:
            return False, "Budget is not active"
        
        available = self.get_available()
        if available < amount:
            return False, f"Insufficient budget. Available: {available}, Requested: {amount}"
        
        return True, ""
    
    # ==================== TRANSACTION HELPER FUNCTIONS ====================
    # Stage 1: PR Commitment
    
    def consume_commitment(self, amount, transaction_ref=None):
        """
        Consume budget as commitment (for PR approval - Stage 1).
        
        Args:
            amount: Decimal amount to commit
            transaction_ref: Optional reference (PR number, etc.)
        
        Raises:
            ValidationError: If consumption not allowed
        """
        from django.core.exceptions import ValidationError
        
        can_consume, error = self.can_consume(amount)
        if not can_consume:
            raise ValidationError(error)
        
        self.committed_amount += amount
        self.last_committed_date = timezone.now()
        self.save()
    
    def release_commitment(self, amount):
        """
        Release committed budget (for PR cancellation or PO creation).
        
        Args:
            amount: Decimal amount to release
        
        Raises:
            ValidationError: If release amount exceeds committed amount
        """
        from django.core.exceptions import ValidationError
        
        if amount > self.committed_amount:
            raise ValidationError(
                f"Cannot release {amount}. Only {self.committed_amount} is committed."
            )
        
        self.committed_amount -= amount
        self.save()
    
    # Stage 2: PO Encumbrance
    
    def consume_encumbrance(self, amount, transaction_ref=None, release_commitment=True):
        """
        Consume budget as encumbrance (for PO approval - Stage 2).
        
        Args:
            amount: Decimal amount to encumber
            transaction_ref: Optional reference (PO number, etc.)
            release_commitment: bool - If True, releases same amount from commitment (PR→PO flow)
        
        Raises:
            ValidationError: If consumption not allowed
        """
        from django.core.exceptions import ValidationError
        
        if release_commitment:
            # Move from committed to encumbered (PR→PO flow)
            if amount > self.committed_amount:
                raise ValidationError(
                    f"Cannot encumber {amount}. Only {self.committed_amount} is committed."
                )
            self.committed_amount -= amount
        else:
            # Direct encumbrance (PO without PR)
            can_consume, error = self.can_consume(amount)
            if not can_consume:
                raise ValidationError(error)
        
        self.encumbered_amount += amount
        self.last_encumbered_date = timezone.now()
        self.save()
    
    def release_encumbrance(self, amount):
        """
        Release encumbered budget (for PO cancellation or invoice posting).
        
        Args:
            amount: Decimal amount to release
        
        Raises:
            ValidationError: If release amount exceeds encumbered amount
        """
        from django.core.exceptions import ValidationError
        
        if amount > self.encumbered_amount:
            raise ValidationError(
                f"Cannot release {amount}. Only {self.encumbered_amount} is encumbered."
            )
        
        self.encumbered_amount -= amount
        self.save()
    
    # Stage 3: Invoice Actual
    
    def consume_actual(self, amount, release_encumbrance=True):
        """
        Consume budget as actual spending (for Invoice approval/GL posting - Stage 3).
        
        Args:
            amount: Decimal amount to record as actual
            release_encumbrance: bool - If True, releases same amount from encumbrance (PO→Invoice flow)
        
        Raises:
            ValidationError: If consumption not allowed
        """
        from django.core.exceptions import ValidationError
        
        if release_encumbrance:
            # Move from encumbered to actual
            if amount > self.encumbered_amount:
                raise ValidationError(
                    f"Cannot consume {amount} as actual. Only {self.encumbered_amount} is encumbered."
                )
            self.encumbered_amount -= amount
        else:
            # Direct actual consumption (no prior encumbrance)
            can_consume, error = self.can_consume(amount)
            if not can_consume:
                raise ValidationError(error)
        
        self.actual_amount += amount
        self.last_actual_date = timezone.now()
        self.save()
    
    def reverse_actual(self, amount):
        """
        Reverse actual spending (for credit memos or corrections).
        
        Args:
            amount: Decimal amount to reverse
        
        Raises:
            ValidationError: If reverse amount exceeds actual amount
        """
        from django.core.exceptions import ValidationError
        
        if amount > self.actual_amount:
            raise ValidationError(
                f"Cannot reverse {amount}. Only {self.actual_amount} is recorded as actual."
            )
        
        self.actual_amount -= amount
        self.save()
    
    # Budget Adjustments
    
    def adjust_budget(self, adjustment_amount, reason=None):
        """
        Adjust the budget (increase or decrease).
        Positive adjustment increases budget, negative decreases it.
        
        Args:
            adjustment_amount: Decimal amount to adjust (positive or negative)
            reason: Optional justification for the adjustment
        
        Returns:
            Decimal: New total budget after adjustment
        """
        self.adjustment_amount += adjustment_amount
        self.last_adjustment_date = timezone.now()
        if reason:
            adjustment_note = f"[{timezone.now().date()}] Adjustment: {adjustment_amount} - {reason}"
            self.notes = f"{self.notes}\n{adjustment_note}".strip()
        self.save()
        return self.get_total_budget()
    
    def get_effective_control_level(self):
        """
        Returns the effective control level for this budget amount.
        Delegates to BudgetSegmentValue.
        """
        return self.budget_segment_value.get_effective_control_level()
    