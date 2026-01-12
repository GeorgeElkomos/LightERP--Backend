"""
Cash Management Serializers
Handles serialization/deserialization for PaymentType, Bank, BankBranch, BankAccount,
BankStatement, BankStatementLine, and BankStatementLineMatch models.
"""
from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone

from .models import (
    PaymentType, Bank, BankBranch, BankAccount,
    BankStatement, BankStatementLine, BankStatementLineMatch
)
from Finance.core.models import Country, Currency
from Finance.GL.models import XX_Segment_combination


# ==================== PAYMENT TYPE SERIALIZERS ====================

class PaymentTypeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing payment types/methods."""
    class Meta:
        model = PaymentType
        fields = ['id', 'payment_method_code', 'payment_method_name', 'enable_reconcile', 'is_active']
        read_only_fields = ['id']


class PaymentTypeDetailSerializer(serializers.ModelSerializer):
    """Full serializer for PaymentType with all details."""
    class Meta:
        model = PaymentType
        fields = ['id', 'payment_method_code', 'payment_method_name', 'description', 'enable_reconcile', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ==================== BANK SERIALIZERS ====================

class BankListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing banks.
    """
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True)
    total_branches = serializers.SerializerMethodField()
    total_accounts = serializers.SerializerMethodField()
    
    class Meta:
        model = Bank
        fields = [
            'id',
            'bank_name',
            'bank_code',
            'country',
            'country_name',
            'country_code',
            'swift_code',
            'is_active',
            'total_branches',
            'total_accounts',
        ]
        read_only_fields = ['id', 'country_name', 'country_code', 'total_branches', 'total_accounts']
    
    def get_total_branches(self, obj):
        """Get total number of branches"""
        return obj.get_total_branches_count()
    
    def get_total_accounts(self, obj):
        """Get total number of accounts across all branches"""
        return obj.get_total_accounts_count()


class BankDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for Bank with all details.
    """
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.email', read_only=True)
    summary = serializers.SerializerMethodField()
    
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all()
    )
    
    class Meta:
        model = Bank
        fields = [
            'id',
            'bank_name',
            'bank_code',
            'country',
            'country_name',
            'country_code',
            'address',
            'phone',
            'email',
            'website',
            'swift_code',
            'routing_number',
            'is_active',
            'notes',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
            'summary',
        ]
        read_only_fields = [
            'id',
            'country_name',
            'country_code',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
            'summary',
        ]
    
    def get_summary(self, obj):
        """Get bank summary statistics"""
        return obj.get_summary()
    
    def create(self, validated_data):
        """Create new bank with audit fields"""
        user = self.context['request'].user
        validated_data['created_by'] = user
        return Bank.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update bank with audit fields"""
        user = self.context['request'].user
        validated_data['updated_by'] = user
        
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.save()
        return instance


# ==================== BANK BRANCH SERIALIZERS ====================

class BankBranchListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing bank branches.
    """
    bank_name = serializers.CharField(source='bank.bank_name', read_only=True)
    bank_code = serializers.CharField(source='bank.bank_code', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    total_accounts = serializers.SerializerMethodField()
    
    class Meta:
        model = BankBranch
        fields = [
            'id',
            'bank',
            'bank_name',
            'bank_code',
            'branch_name',
            'branch_code',
            'city',
            'country',
            'country_name',
            'phone',
            'is_active',
            'total_accounts',
        ]
        read_only_fields = ['id', 'bank_name', 'bank_code', 'country_name', 'total_accounts']
    
    def get_total_accounts(self, obj):
        """Get total number of accounts in this branch"""
        return obj.get_accounts_count()


class BankBranchDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for BankBranch with all details.
    """
    bank_name = serializers.CharField(source='bank.bank_name', read_only=True)
    bank_code = serializers.CharField(source='bank.bank_code', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.email', read_only=True)
    full_address = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    
    bank = serializers.PrimaryKeyRelatedField(
        queryset=Bank.objects.all()
    )
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all()
    )
    
    class Meta:
        model = BankBranch
        fields = [
            'id',
            'bank',
            'bank_name',
            'bank_code',
            'branch_name',
            'branch_code',
            'address',
            'city',
            'postal_code',
            'country',
            'country_name',
            'country_code',
            'phone',
            'email',
            'manager_name',
            'manager_phone',
            'swift_code',
            'ifsc_code',
            'routing_number',
            'is_active',
            'notes',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
            'full_address',
            'summary',
        ]
        read_only_fields = [
            'id',
            'bank_name',
            'bank_code',
            'country_name',
            'country_code',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
            'full_address',
            'summary',
        ]
    
    def get_full_address(self, obj):
        """Get formatted full address"""
        return obj.get_full_address()
    
    def get_summary(self, obj):
        """Get branch summary statistics"""
        return obj.get_summary()
    
    def create(self, validated_data):
        """Create new branch with audit fields"""
        user = self.context['request'].user
        validated_data['created_by'] = user
        return BankBranch.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update branch with audit fields"""
        user = self.context['request'].user
        validated_data['updated_by'] = user
        
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.save()
        return instance


# ==================== BANK ACCOUNT SERIALIZERS ====================

class BankAccountListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing bank accounts.
    """
    bank_name = serializers.CharField(source='branch.bank.bank_name', read_only=True)
    branch_name = serializers.CharField(source='branch.branch_name', read_only=True)
    branch_code = serializers.CharField(source='branch.branch_code', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    
    class Meta:
        model = BankAccount
        fields = [
            'id',
            'account_number',
            'account_name',
            'account_type',
            'account_type_display',
            'branch',
            'bank_name',
            'branch_name',
            'branch_code',
            'currency',
            'currency_code',
            'current_balance',
            'is_active',
        ]
        read_only_fields = [
            'id',
            'bank_name',
            'branch_name',
            'branch_code',
            'currency_code',
            'account_type_display',
        ]


class BankAccountDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for BankAccount with all details.
    """
    bank_name = serializers.CharField(source='branch.bank.bank_name', read_only=True)
    bank_code = serializers.CharField(source='branch.bank.bank_code', read_only=True)
    branch_name = serializers.CharField(source='branch.branch_name', read_only=True)
    branch_code = serializers.CharField(source='branch.branch_code', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.email', read_only=True)
    
    balance_summary = serializers.SerializerMethodField()
    full_hierarchy = serializers.SerializerMethodField()
    available_balance = serializers.SerializerMethodField()
    
    branch = serializers.PrimaryKeyRelatedField(
        queryset=BankBranch.objects.all()
    )
    currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.all()
    )
    cash_GL_combination = serializers.PrimaryKeyRelatedField(
        queryset=XX_Segment_combination.objects.all()
    )
    cash_clearing_GL_combination = serializers.PrimaryKeyRelatedField(
        queryset=XX_Segment_combination.objects.all()
    )
    
    class Meta:
        model = BankAccount
        fields = [
            'id',
            'branch',
            'bank_name',
            'bank_code',
            'branch_name',
            'branch_code',
            'account_number',
            'account_name',
            'account_type',
            'account_type_display',
            'currency',
            'currency_code',
            'currency_name',
            'opening_balance',
            'current_balance',
            'available_balance',
            'iban',
            'opening_date',
            'cash_GL_combination',
            'cash_clearing_GL_combination',
            'is_active',
            'description',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
            'balance_summary',
            'full_hierarchy',
        ]
        read_only_fields = [
            'id',
            'bank_name',
            'bank_code',
            'branch_name',
            'branch_code',
            'currency_code',
            'currency_name',
            'account_type_display',
            'current_balance',
            'available_balance',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
            'balance_summary',
            'full_hierarchy',
        ]
    
    def get_balance_summary(self, obj):
        """Get balance information"""
        return obj.get_balance_summary()
    
    def get_full_hierarchy(self, obj):
        """Get complete hierarchy information"""
        return obj.get_full_hierarchy()
    
    def get_available_balance(self, obj):
        """Get available balance"""
        return float(obj.get_available_balance())
    
    def validate(self, data):
        """Custom validation"""
        # Validate opening balance is not negative (except for loan accounts)
        if 'opening_balance' in data and 'account_type' in data:
            if data['opening_balance'] < 0 and data['account_type'] not in [BankAccount.LOAN, BankAccount.OVERDRAFT]:
                raise serializers.ValidationError({
                    'opening_balance': 'Opening balance cannot be negative for this account type'
                })
        
        return data
    
    def create(self, validated_data):
        """Create new account with audit fields"""
        user = self.context['request'].user
        validated_data['created_by'] = user
        
        # Set current_balance to opening_balance initially
        if 'opening_balance' in validated_data:
            validated_data['current_balance'] = validated_data['opening_balance']
        
        return BankAccount.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update account with audit fields"""
        user = self.context['request'].user
        validated_data['updated_by'] = user
        
        # Don't allow direct update of current_balance through API
        if 'current_balance' in validated_data:
            validated_data.pop('current_balance')
        
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.save()
        return instance


# ==================== BALANCE UPDATE SERIALIZER ====================

class BankAccountBalanceUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating bank account balance.
    """
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    increase = serializers.BooleanField(default=True)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value


# ==================== BANK STATEMENT LINE SERIALIZERS ====================

class BankStatementLineListSerializer(serializers.ModelSerializer):
    """Serializer for listing bank statement lines."""
    bank_statement_number = serializers.CharField(source='bank_statement.statement_number', read_only=True)
    matched_payment_id = serializers.IntegerField(source='matched_payment.id', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.email', read_only=True)
    transaction_type = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    display_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = BankStatementLine
        fields = ['id', 'bank_statement', 'bank_statement_number', 'line_number', 'transaction_date', 'value_date', 'transaction_type', 'amount', 'display_amount', 'reference_number', 'description', 'reconciliation_status', 'matched_payment', 'matched_payment_id', 'reconciled_date', 'reconciled_by_name']
        read_only_fields = ['id', 'bank_statement_number', 'matched_payment_id', 'reconciled_by_name', 'display_amount', 'transaction_type', 'amount']
    
    def get_transaction_type(self, obj):
        return 'DEBIT' if obj.debit_amount > 0 else 'CREDIT'
    
    def get_amount(self, obj):
        return float(obj.debit_amount if obj.debit_amount > 0 else obj.credit_amount)
    
    def get_display_amount(self, obj):
        # Return formatted amount with sign
        if obj.debit_amount > 0:
            return f'-{float(obj.debit_amount)}'
        else:
            return f'+{float(obj.credit_amount)}'


class BankStatementLineDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for bank statement lines."""
    bank_statement_details = serializers.SerializerMethodField()
    matched_payment_details = serializers.SerializerMethodField()
    reconciled_by_name = serializers.CharField(source='reconciled_by.email', read_only=True)
    transaction_type = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    balance_after_transaction = serializers.DecimalField(source='balance', max_digits=14, decimal_places=2, read_only=True)
    payee_payer = serializers.CharField(max_length=255, required=False, allow_blank=True)
    display_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = BankStatementLine
        fields = ['id', 'bank_statement', 'bank_statement_details', 'line_number', 'transaction_date', 'value_date', 'transaction_type', 'amount', 'display_amount', 'balance_after_transaction', 'reference_number', 'description', 'payee_payer', 'reconciliation_status', 'matched_payment', 'matched_payment_details', 'reconciled_date', 'reconciled_by', 'reconciled_by_name', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'bank_statement_details', 'matched_payment_details', 'reconciled_by_name', 'display_amount', 'transaction_type', 'amount', 'balance_after_transaction', 'created_at', 'updated_at']
    
    def get_transaction_type(self, obj):
        return 'DEBIT' if obj.debit_amount > 0 else 'CREDIT'
    
    def get_amount(self, obj):
        return float(obj.debit_amount if obj.debit_amount > 0 else obj.credit_amount)
    
    def get_display_amount(self, obj):
        # Return formatted amount with sign
        if obj.debit_amount > 0:
            return f'-{float(obj.debit_amount)}'
        else:
            return f'+{float(obj.credit_amount)}'
    
    def get_bank_statement_details(self, obj):
        return {
            'id': obj.bank_statement.id,
            'statement_number': obj.bank_statement.statement_number,
            'statement_date': obj.bank_statement.statement_date,
            'bank_account': obj.bank_statement.bank_account.account_number,
        }
    
    def get_matched_payment_details(self, obj):
        if not obj.matched_payment:
            return None
        return {
            'id': obj.matched_payment.id,
            'date': obj.matched_payment.date,
            'payment_type': obj.matched_payment.payment_type,
            'business_partner': str(obj.matched_payment.business_partner),
            'currency': str(obj.matched_payment.currency),
            'approval_status': obj.matched_payment.approval_status,
        }


class BankStatementLineCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bank statement lines."""
    transaction_type = serializers.ChoiceField(choices=['DEBIT', 'CREDIT'], write_only=True, required=False)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, write_only=True, required=False)
    balance_after_transaction = serializers.DecimalField(max_digits=14, decimal_places=2, source='balance', required=False)
    payee_payer = serializers.CharField(max_length=255, required=False, allow_blank=True)
    bank_statement_id = serializers.PrimaryKeyRelatedField(
        queryset=BankStatement.objects.all(),
        source='bank_statement',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = BankStatementLine
        fields = ['id', 'bank_statement_id', 'line_number', 'transaction_date', 'value_date', 'transaction_type', 'amount', 'debit_amount', 'credit_amount', 'balance_after_transaction', 'reference_number', 'description', 'payee_payer', 'reconciliation_status', 'notes']
        read_only_fields = ['id', 'reconciliation_status']
        extra_kwargs = {
            'line_number': {'required': False, 'allow_null': True},
            'debit_amount': {'required': False},
            'credit_amount': {'required': False}
        }
    
    def validate(self, data):
        # Transaction_type and amount handling
        if 'transaction_type' in data and 'amount' in data:
            transaction_type = data.pop('transaction_type')
            amount = data.pop('amount')
            if transaction_type == 'DEBIT':
                data['debit_amount'] = amount
                data['credit_amount'] = Decimal('0.00')
            else:  # CREDIT
                data['credit_amount'] = amount
                data['debit_amount'] = Decimal('0.00')
        
        # Auto-generate line_number if not provided
        if 'line_number' not in data and 'bank_statement' in data:
            last_line = BankStatementLine.objects.filter(
                bank_statement=data['bank_statement']
            ).order_by('-line_number').first()
            data['line_number'] = (last_line.line_number + 1) if last_line else 1
        
        # Set audit fields
        data['created_by'] = self.context['request'].user
        data['updated_by'] = self.context['request'].user
        
        return data


# ==================== BANK STATEMENT SERIALIZERS ====================

class BankStatementListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing bank statements."""
    bank_account_number = serializers.CharField(source='bank_account.account_number', read_only=True)
    bank_name = serializers.CharField(source='bank_account.branch.bank.bank_name', read_only=True)
    reconciliation_percentage = serializers.SerializerMethodField()
    unreconciled_count = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BankStatement
        fields = ['id', 'bank_account', 'bank_account_number', 'bank_name', 'statement_number', 'statement_date', 'from_date', 'to_date', 'opening_balance', 'closing_balance', 'line_count', 'total_debits', 'total_credits', 'reconciliation_status', 'reconciliation_percentage', 'unreconciled_count', 'created_at']
        read_only_fields = ['id', 'bank_account_number', 'bank_name', 'line_count', 'reconciliation_percentage', 'unreconciled_count', 'created_at']
    
    def get_reconciliation_percentage(self, obj):
        return obj.get_reconciliation_percentage()
    
    def get_unreconciled_count(self, obj):
        return obj.get_unreconciled_lines().count()
    
    def get_line_count(self, obj):
        return obj.statement_lines.count()


class BankStatementDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for bank statements with nested lines."""
    bank_account_details = BankAccountListSerializer(source='bank_account', read_only=True)
    statement_lines = BankStatementLineListSerializer(many=True, read_only=True)
    imported_by_name = serializers.CharField(source='imported_by.email', read_only=True)
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.email', read_only=True)
    line_count = serializers.SerializerMethodField()
    reconciliation_percentage = serializers.SerializerMethodField()
    unreconciled_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = BankStatement
        fields = ['id', 'bank_account', 'bank_account_details', 'statement_number', 'statement_date', 'from_date', 'to_date', 'opening_balance', 'closing_balance', 'line_count', 'total_debits', 'total_credits', 'reconciliation_status', 'reconciliation_percentage', 'unreconciled_amount', 'import_file_name', 'import_date', 'imported_by', 'imported_by_name', 'statement_lines', 'created_by', 'created_by_name', 'updated_by', 'updated_by_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'bank_account_details', 'statement_lines', 'imported_by_name', 'created_by_name', 'updated_by_name', 'reconciliation_percentage', 'unreconciled_amount', 'created_at', 'updated_at']
    
    def get_reconciliation_percentage(self, obj):
        return obj.get_reconciliation_percentage()
    
    def get_unreconciled_amount(self, obj):
        return float(obj.unreconciled_amount)
    
    def get_line_count(self, obj):
        return obj.statement_lines.count()


class BankStatementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bank statements."""
    class Meta:
        model = BankStatement
        fields = ['id', 'bank_account', 'statement_number', 'statement_date', 'from_date', 'to_date', 'opening_balance', 'closing_balance', 'transaction_count', 'total_debits', 'total_credits', 'import_file_name']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        validated_data['updated_by'] = user
        validated_data['imported_by'] = user
        validated_data['import_date'] = timezone.now()
        return super().create(validated_data)


# ==================== BANK STATEMENT LINE MATCH SERIALIZERS ====================

class BankStatementLineMatchListSerializer(serializers.ModelSerializer):
    """Serializer for listing statement line matches."""
    statement_line_ref = serializers.CharField(source='statement_line.reference_number', read_only=True)
    statement_line_number = serializers.IntegerField(source='statement_line.line_number', read_only=True)
    payment_id = serializers.IntegerField(source='payment.id', read_only=True)
    matched_by_name = serializers.CharField(source='matched_by.email', read_only=True)
    
    class Meta:
        model = BankStatementLineMatch
        fields = ['id', 'statement_line', 'statement_line_number', 'statement_line_ref', 'payment', 'payment_id', 'match_status', 'match_type', 'confidence_score', 'discrepancy_amount', 'matched_by', 'matched_by_name', 'matched_at', 'notes']
        read_only_fields = ['id', 'statement_line_number', 'statement_line_ref', 'payment_id', 'matched_by_name', 'matched_at']


class BankStatementLineMatchDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for statement line matches."""
    statement_line_details = BankStatementLineListSerializer(source='statement_line', read_only=True)
    payment_details = serializers.SerializerMethodField()
    matched_by_name = serializers.CharField(source='matched_by.email', read_only=True)
    
    class Meta:
        model = BankStatementLineMatch
        fields = ['id', 'statement_line', 'statement_line_details', 'payment', 'payment_details', 'match_status', 'match_type', 'confidence_score', 'discrepancy_amount', 'matched_by', 'matched_by_name', 'matched_at', 'notes']
        read_only_fields = ['id', 'statement_line_details', 'payment_details', 'matched_by_name', 'matched_at']
    
    def get_payment_details(self, obj):
        if not obj.payment:
            return None
        return {
            'id': obj.payment.id,
            'date': obj.payment.date,
            'payment_type': obj.payment.payment_type,
            'business_partner': str(obj.payment.business_partner),
            'currency': str(obj.payment.currency),
            'approval_status': obj.payment.approval_status,
            'reconciliation_status': obj.payment.reconciliation_status,
        }


class BankStatementLineMatchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating statement line matches."""
    class Meta:
        model = BankStatementLineMatch
        fields = ['id', 'statement_line', 'payment', 'match_status', 'match_type', 'confidence_score', 'discrepancy_amount', 'notes']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['matched_by'] = user
        return super().create(validated_data)


# ==================== BANK STATEMENT IMPORT SERIALIZERS ====================

class BankStatementImportSerializer(serializers.Serializer):
    """
    Serializer for importing bank statements from Excel/CSV files.
    
    HOW TO USE:
    ===========
    
    1. UPLOAD FILE:
       POST /api/cash-management/statements/import_statement/
       
       Body (multipart/form-data):
       - file: Excel/CSV file
       - bank_account_id: ID of bank account
       - statement_number: Statement reference number
       - statement_date: Statement date (YYYY-MM-DD)
       - opening_balance: Starting balance (optional)
       - closing_balance: Ending balance (optional)
       
    2. FILE FORMAT:
       Excel/CSV must have columns (flexible naming):
       - Transaction Date (required)
       - Description (required)
       - Debit/Credit or Amount (required)
       - Reference Number (optional)
       - Balance (optional)
       
    3. PREVIEW FIRST:
       POST /api/cash-management/statements/import_preview/
       Same body as import, but doesn't save - just validates
    """
    
    file = serializers.FileField(
        required=True,
        help_text="Excel (.xlsx, .xls) or CSV (.csv) file containing bank statement transactions"
    )
    bank_account_id = serializers.IntegerField(
        required=True,
        help_text="ID of the bank account this statement belongs to"
    )
    statement_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
        help_text="Unique statement reference number (e.g., STMT-2026-01). Auto-generated if not provided."
    )
    statement_date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Date of the statement (YYYY-MM-DD). Auto-generated from transaction dates if not provided."
    )
    opening_balance = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        allow_null=True,
        default=Decimal('0'),
        help_text="Opening balance at start of statement period. Defaults to 0 if not provided."
    )
    closing_balance = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        allow_null=True,
        default=None,
        help_text="Closing balance at end of statement period. Auto-calculated if not provided."
    )
    
    def validate_file(self, value):
        """Validate file type and size"""
        # Check file extension
        file_name = value.name.lower()
        if not (file_name.endswith('.csv') or file_name.endswith('.xlsx') or file_name.endswith('.xls')):
            raise serializers.ValidationError(
                'Invalid file format. Please upload .csv, .xlsx, or .xls file'
            )
        
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                'File size too large. Maximum size is 10MB'
            )
        
        return value
    
    def validate_bank_account_id(self, value):
        """Validate bank account exists"""
        if not BankAccount.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                f'Bank account with ID {value} does not exist'
            )
        return value
    
    def validate_statement_number(self, value):
        """Validate statement number is unique for this account"""
        if value:  # Only validate if provided
            bank_account_id = self.initial_data.get('bank_account_id')
            if bank_account_id:
                if BankStatement.objects.filter(
                    bank_account_id=bank_account_id,
                    statement_number=value
                ).exists():
                    raise serializers.ValidationError(
                        f'Statement number "{value}" already exists for this bank account'
                    )
        return value


class BankStatementImportPreviewSerializer(serializers.Serializer):
    """
    Serializer for previewing bank statement import without saving.
    Same fields as import, but only validates and returns preview data.
    """
    
    file = serializers.FileField(
        required=True,
        help_text="Excel/CSV file to preview"
    )
    bank_account_id = serializers.IntegerField(
        required=True,
        help_text="ID of the bank account"
    )
    
    def validate_file(self, value):
        """Validate file type and size"""
        file_name = value.name.lower()
        if not (file_name.endswith('.csv') or file_name.endswith('.xlsx') or file_name.endswith('.xls')):
            raise serializers.ValidationError(
                'Invalid file format. Please upload .csv, .xlsx, or .xls file'
            )
        
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                'File size too large. Maximum size is 10MB'
            )
        
        return value
    
    def validate_bank_account_id(self, value):
        """Validate bank account exists"""
        if not BankAccount.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                f'Bank account with ID {value} does not exist'
            )
        return value

