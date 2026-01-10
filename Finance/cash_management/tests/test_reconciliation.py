"""
Bank Reconciliation Workflow Tests
Tests for complete reconciliation workflows including matching and approval.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone

User = get_user_model()

from Finance.cash_management.models import (
    Bank, BankBranch, BankAccount,
    BankStatement, BankStatementLine, BankStatementLineMatch, PaymentType
)
from Finance.core.models import Country, Currency
from Finance.GL.models import XX_SegmentType, XX_Segment, XX_Segment_combination
from Finance.BusinessPartner.models import Supplier
from Finance.payments.models import Payment


# Tests for BankReconciliation and BankTransaction models have been removed
# as these models do not exist in the current codebase.
