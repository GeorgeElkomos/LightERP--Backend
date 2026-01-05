"""
Cash Management Serializers
Handles serialization/deserialization for Bank, BankBranch, and BankAccount models.
"""
from rest_framework import serializers
from decimal import Decimal

from .models import Bank, BankBranch, BankAccount
from Finance.core.models import Country, Currency
from Finance.GL.models import XX_Segment_combination


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
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
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
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
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
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
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
