"""
Cash Management Views - API Endpoints
Provides REST API endpoints for Bank, BankBranch, and BankAccount operations.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from decimal import Decimal

from .models import Bank, BankBranch, BankAccount
from .serializers import (
    BankListSerializer,
    BankDetailSerializer,
    BankBranchListSerializer,
    BankBranchDetailSerializer,
    BankAccountListSerializer,
    BankAccountDetailSerializer,
    BankAccountBalanceUpdateSerializer,
)


# ==================== BANK VIEWSET ====================

class BankViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Bank CRUD operations.
    
    Endpoints:
    - GET /banks/ - List all banks
    - POST /banks/ - Create new bank
    - GET /banks/{id}/ - Get bank details
    - PUT/PATCH /banks/{id}/ - Update bank
    - DELETE /banks/{id}/ - Delete bank
    
    Custom Actions:
    - GET /banks/{id}/summary/ - Get bank statistics
    - POST /banks/{id}/activate/ - Activate bank
    - POST /banks/{id}/deactivate/ - Deactivate bank
    - GET /banks/{id}/branches/ - Get all branches
    - GET /banks/{id}/accounts/ - Get all accounts
    """
    queryset = Bank.objects.select_related('country').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return BankListSerializer
        return BankDetailSerializer
    
    def get_queryset(self):
        """
        Filter queryset based on query parameters.
        """
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        # Filter by country
        country_id = self.request.query_params.get('country')
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        
        country_code = self.request.query_params.get('country_code')
        if country_code:
            queryset = queryset.filter(country__code__iexact=country_code)
        
        # Search by name or code
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(bank_name__icontains=search) |
                Q(bank_code__icontains=search) |
                Q(swift_code__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Create bank with user context"""
        serializer.save()
    
    def perform_update(self, serializer):
        """Update bank with user context"""
        serializer.save()
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get comprehensive bank statistics.
        
        GET /banks/{id}/summary/
        """
        bank = self.get_object()
        summary = bank.get_summary()
        return Response(summary, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate a bank.
        
        POST /banks/{id}/activate/
        """
        bank = self.get_object()
        bank.activate(user=request.user)
        return Response(
            {'message': f'Bank "{bank.bank_name}" activated successfully'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate a bank.
        
        POST /banks/{id}/deactivate/
        """
        bank = self.get_object()
        result = bank.deactivate(user=request.user)
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def branches(self, request, pk=None):
        """
        Get all branches for this bank.
        
        GET /banks/{id}/branches/
        Query params:
        - active_only: Return only active branches (true/false)
        """
        bank = self.get_object()
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        
        branches = bank.get_branches(active_only=active_only)
        serializer = BankBranchListSerializer(branches, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def accounts(self, request, pk=None):
        """
        Get all accounts across all branches for this bank.
        
        GET /banks/{id}/accounts/
        Query params:
        - active_only: Return only active accounts (true/false)
        """
        bank = self.get_object()
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        
        accounts = bank.get_all_accounts(active_only=active_only)
        serializer = BankAccountListSerializer(accounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==================== BANK BRANCH VIEWSET ====================

class BankBranchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BankBranch CRUD operations.
    
    Endpoints:
    - GET /branches/ - List all branches
    - POST /branches/ - Create new branch
    - GET /branches/{id}/ - Get branch details
    - PUT/PATCH /branches/{id}/ - Update branch
    - DELETE /branches/{id}/ - Delete branch
    
    Custom Actions:
    - GET /branches/{id}/summary/ - Get branch statistics
    - POST /branches/{id}/activate/ - Activate branch
    - POST /branches/{id}/deactivate/ - Deactivate branch
    - GET /branches/{id}/accounts/ - Get all accounts
    - GET /branches/{id}/total_balance/ - Get total balance
    """
    queryset = BankBranch.objects.select_related('bank', 'country').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return BankBranchListSerializer
        return BankBranchDetailSerializer
    
    def get_queryset(self):
        """
        Filter queryset based on query parameters.
        """
        queryset = super().get_queryset()
        
        # Filter by bank
        bank_id = self.request.query_params.get('bank')
        if bank_id:
            queryset = queryset.filter(bank_id=bank_id)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        # Filter by country
        country_id = self.request.query_params.get('country')
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        
        # Filter by city
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(branch_name__icontains=search) |
                Q(branch_code__icontains=search) |
                Q(city__icontains=search) |
                Q(swift_code__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Create branch with user context"""
        serializer.save()
    
    def perform_update(self, serializer):
        """Update branch with user context"""
        serializer.save()
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get comprehensive branch statistics.
        
        GET /branches/{id}/summary/
        """
        branch = self.get_object()
        summary = branch.get_summary()
        return Response(summary, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate a branch.
        
        POST /branches/{id}/activate/
        """
        branch = self.get_object()
        branch.activate(user=request.user)
        return Response(
            {'message': f'Branch "{branch.branch_name}" activated successfully'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate a branch.
        
        POST /branches/{id}/deactivate/
        """
        branch = self.get_object()
        result = branch.deactivate(user=request.user)
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def accounts(self, request, pk=None):
        """
        Get all accounts for this branch.
        
        GET /branches/{id}/accounts/
        Query params:
        - active_only: Return only active accounts (true/false)
        """
        branch = self.get_object()
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        
        accounts = branch.get_accounts(active_only=active_only)
        serializer = BankAccountListSerializer(accounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def total_balance(self, request, pk=None):
        """
        Get total balance across all accounts in this branch.
        
        GET /branches/{id}/total_balance/
        Query params:
        - currency: Filter by currency ID (optional)
        """
        branch = self.get_object()
        currency_id = request.query_params.get('currency')
        
        currency = None
        if currency_id:
            from Finance.core.models import Currency
            currency = get_object_or_404(Currency, pk=currency_id)
        
        total_balance = branch.get_total_balance(currency=currency)
        
        return Response({
            'branch': branch.branch_name,
            'branch_code': branch.branch_code,
            'total_balance': float(total_balance),
            'currency': currency.code if currency else 'All currencies',
        }, status=status.HTTP_200_OK)


# ==================== BANK ACCOUNT VIEWSET ====================

class BankAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BankAccount CRUD operations.
    
    Endpoints:
    - GET /accounts/ - List all accounts
    - POST /accounts/ - Create new account
    - GET /accounts/{id}/ - Get account details
    - PUT/PATCH /accounts/{id}/ - Update account
    - DELETE /accounts/{id}/ - Delete account
    
    Custom Actions:
    - POST /accounts/{id}/update_balance/ - Update account balance
    - POST /accounts/{id}/freeze/ - Freeze account
    - POST /accounts/{id}/unfreeze/ - Unfreeze account
    - GET /accounts/{id}/balance/ - Get balance summary
    - GET /accounts/{id}/check_balance/ - Check if sufficient balance
    - GET /accounts/{id}/hierarchy/ - Get full bank hierarchy
    """
    queryset = BankAccount.objects.select_related(
        'branch__bank',
        'branch__country',
        'currency',
        'cash_GL_combination',
        'cash_clearing_GL_combination'
    ).all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return BankAccountListSerializer
        return BankAccountDetailSerializer
    
    def get_queryset(self):
        """
        Filter queryset based on query parameters.
        """
        queryset = super().get_queryset()
        
        # Filter by branch
        branch_id = self.request.query_params.get('branch')
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by bank
        bank_id = self.request.query_params.get('bank')
        if bank_id:
            queryset = queryset.filter(branch__bank_id=bank_id)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        # Filter by currency
        currency_id = self.request.query_params.get('currency')
        if currency_id:
            queryset = queryset.filter(currency_id=currency_id)
        
        # Filter by account type
        account_type = self.request.query_params.get('account_type')
        if account_type:
            queryset = queryset.filter(account_type=account_type.upper())
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(account_number__icontains=search) |
                Q(account_name__icontains=search) |
                Q(iban__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Create account with user context"""
        serializer.save()
    
    def perform_update(self, serializer):
        """Update account with user context"""
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        """
        Update account balance.
        
        POST /accounts/{id}/update_balance/
        Body:
        {
            "amount": 1000.00,
            "increase": true,
            "description": "Optional description"
        }
        """
        account = self.get_object()
        serializer = BankAccountBalanceUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                amount = serializer.validated_data['amount']
                increase = serializer.validated_data['increase']
                
                new_balance = account.update_balance(
                    amount=amount,
                    user=request.user,
                    increase=increase
                )
                
                return Response({
                    'message': 'Balance updated successfully',
                    'account_number': account.account_number,
                    'previous_balance': float(account.current_balance - (amount if increase else -amount)),
                    'amount': float(amount),
                    'increase': increase,
                    'new_balance': float(new_balance),
                }, status=status.HTTP_200_OK)
            
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def freeze(self, request, pk=None):
        """
        Freeze (deactivate) an account.
        
        POST /accounts/{id}/freeze/
        """
        account = self.get_object()
        account.freeze(user=request.user)
        return Response(
            {'message': f'Account "{account.account_number}" frozen successfully'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def unfreeze(self, request, pk=None):
        """
        Unfreeze (activate) an account.
        
        POST /accounts/{id}/unfreeze/
        """
        account = self.get_object()
        account.unfreeze(user=request.user)
        return Response(
            {'message': f'Account "{account.account_number}" unfrozen successfully'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """
        Get balance summary for account.
        
        GET /accounts/{id}/balance/
        """
        account = self.get_object()
        balance_summary = account.get_balance_summary()
        return Response(balance_summary, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def check_balance(self, request, pk=None):
        """
        Check if account has sufficient balance for a transaction.
        
        GET /accounts/{id}/check_balance/?amount=1000
        """
        account = self.get_object()
        amount_str = request.query_params.get('amount')
        
        if not amount_str:
            return Response(
                {'error': 'amount parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(amount_str)
            sufficient = account.check_sufficient_balance(amount)
            
            return Response({
                'account_number': account.account_number,
                'current_balance': float(account.current_balance),
                'requested_amount': float(amount),
                'sufficient_balance': sufficient,
                'shortfall': float(amount - account.current_balance) if not sufficient else 0,
            }, status=status.HTTP_200_OK)
        
        except (ValueError, Decimal.InvalidOperation):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """
        Get complete bank hierarchy (Bank → Branch → Account).
        
        GET /accounts/{id}/hierarchy/
        """
        account = self.get_object()
        hierarchy = account.get_full_hierarchy()
        return Response(hierarchy, status=status.HTTP_200_OK)
