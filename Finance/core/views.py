"""
API Views for Finance Core models.
Provides REST API endpoints for Currency, Country, and TaxRate.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from erp_project.pagination import auto_paginate

from .models import Currency, Country, TaxRate
from .serializers import (
    CurrencySerializer,
    CurrencyListSerializer,
    CountrySerializer,
    CountryListSerializer,
    TaxRateSerializer,
    TaxRateListSerializer,
    UsageDetailsSerializer,
)


# ============================================================================
# Currency API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def currency_list(request):
    """
    List all currencies or create a new currency.
    
    GET /currencies/
    - Returns list of all currencies
    - Query params:
        - is_active: Filter by active status (true/false)
        - is_base_currency: Filter by base currency status (true/false)
        - code: Filter by currency code (exact match)
    
    POST /currencies/
    - Create a new currency
    - Request body: CurrencySerializer fields
    """
    if request.method == 'GET':
        currencies = Currency.objects.all()
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            currencies = currencies.filter(is_active=is_active_bool)
        
        is_base_currency = request.query_params.get('is_base_currency')
        if is_base_currency is not None:
            is_base_bool = is_base_currency.lower() == 'true'
            currencies = currencies.filter(is_base_currency=is_base_bool)
        
        code = request.query_params.get('code')
        if code:
            currencies = currencies.filter(code__iexact=code)
        
        serializer = CurrencyListSerializer(currencies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = CurrencySerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def currency_detail(request, pk):
    """
    Retrieve, update, or delete a specific currency.
    
    GET /currencies/{id}/
    - Returns detailed information about a currency
    
    PUT/PATCH /currencies/{id}/
    - Update a currency
    - Request body: CurrencySerializer fields
    
    DELETE /currencies/{id}/
    - Delete a currency (if not referenced by other models)
    """
    currency = get_object_or_404(Currency, pk=pk)
    
    if request.method == 'GET':
        serializer = CurrencySerializer(currency)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = CurrencySerializer(currency, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            currency.delete()
            return Response(
                {'message': f'Currency "{currency.code}" deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"Cannot delete currency: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def currency_toggle_active(request, pk):
    """
    Toggle the active status of a currency.
    
    POST /currencies/{id}/toggle-active/
    
    Returns:
        {
            "id": 1,
            "code": "USD",
            "name": "US Dollar",
            "is_active": true/false
        }
    """
    currency = get_object_or_404(Currency, pk=pk)
    currency.is_active = not currency.is_active
    currency.save()
    
    return Response({
        'id': currency.id,
        'code': currency.code,
        'name': currency.name,
        'is_active': currency.is_active
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def currency_convert_to_base(request, pk):
    """
    Convert an amount from this currency to the base currency.
    
    POST /currencies/{id}/convert-to-base/
    
    Request body:
        {
            "amount": 100.00
        }
    
    Returns:
        {
            "original_amount": 100.00,
            "original_currency": "EUR",
            "base_amount": 110.00,
            "base_currency": "USD",
            "exchange_rate": 1.1000
        }
    """
    currency = get_object_or_404(Currency, pk=pk)
    
    amount = request.data.get('amount')
    if amount is None:
        return Response(
            {'error': 'Amount is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from decimal import Decimal
        amount = Decimal(str(amount))
        base_amount = currency.convert_to_base_currency(amount)
        
        # Get base currency
        base_currency = Currency.objects.filter(is_base_currency=True).first()
        
        return Response({
            'original_amount': str(amount),
            'original_currency': currency.code,
            'base_amount': str(base_amount),
            'base_currency': base_currency.code if base_currency else None,
            'exchange_rate': str(currency.exchange_rate_to_base_currency)
        }, status=status.HTTP_200_OK)
    except (ValueError, TypeError) as e:
        return Response(
            {'error': f'Invalid amount: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
def currency_get_base(request):
    """
    Get the base currency.
    
    GET /currencies/base/
    
    Returns:
        {
            "id": 1,
            "code": "USD",
            "name": "US Dollar",
            "symbol": "$"
        }
    """
    base_currency = Currency.objects.filter(is_base_currency=True).first()
    
    if not base_currency:
        return Response(
            {'error': 'No base currency configured'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    serializer = CurrencySerializer(base_currency)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# Country API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def country_list(request):
    """
    List all countries or create a new country.
    
    GET /countries/
    - Returns list of all countries
    - Query params:
        - code: Filter by country code (exact match)
        - name: Filter by country name (case-insensitive contains)
    
    POST /countries/
    - Create a new country
    - Request body: CountrySerializer fields
    """
    if request.method == 'GET':
        countries = Country.objects.all()
        
        # Apply filters
        code = request.query_params.get('code')
        if code:
            countries = countries.filter(code__iexact=code)
        
        name = request.query_params.get('name')
        if name:
            countries = countries.filter(name__icontains=name)
        
        serializer = CountryListSerializer(countries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = CountrySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def country_detail(request, pk):
    """
    Retrieve, update, or delete a specific country.
    
    GET /countries/{id}/
    - Returns detailed information about a country
    
    PUT/PATCH /countries/{id}/
    - Update a country
    - Request body: CountrySerializer fields
    
    DELETE /countries/{id}/
    - Delete a country (if not referenced by other models)
    """
    country = get_object_or_404(Country, pk=pk)
    
    if request.method == 'GET':
        serializer = CountrySerializer(country)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = CountrySerializer(country, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            country.delete()
            return Response(
                {'message': f'Country "{country.code}" deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"Cannot delete country: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
def country_tax_rates(request, pk):
    """
    Get all tax rates for a specific country.
    
    GET /countries/{id}/tax-rates/
    
    Query params:
        - is_active: Filter by active status (true/false)
        - category: Filter by category (STANDARD/ZERO/EXEMPT/RC)
    """
    country = get_object_or_404(Country, pk=pk)
    tax_rates = country.tax_rates.all()
    
    # Apply filters
    is_active = request.query_params.get('is_active')
    if is_active is not None:
        is_active_bool = is_active.lower() == 'true'
        tax_rates = tax_rates.filter(is_active=is_active_bool)
    
    category = request.query_params.get('category')
    if category:
        tax_rates = tax_rates.filter(category=category.upper())
    
    serializer = TaxRateListSerializer(tax_rates, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# TaxRate API Views
# ============================================================================

@api_view(['GET', 'POST'])
@auto_paginate
def tax_rate_list(request):
    """
    List all tax rates or create a new tax rate.
    
    GET /tax-rates/
    - Returns list of all tax rates
    - Query params:
        - country: Filter by country ID
        - country_code: Filter by country code
        - category: Filter by category (STANDARD/ZERO/EXEMPT/RC)
        - is_active: Filter by active status (true/false)
        - name: Filter by name (case-insensitive contains)
    
    POST /tax-rates/
    - Create a new tax rate
    - Request body: TaxRateSerializer fields
    """
    if request.method == 'GET':
        tax_rates = TaxRate.objects.select_related('country').all()
        
        # Apply filters
        country_id = request.query_params.get('country')
        if country_id:
            tax_rates = tax_rates.filter(country_id=country_id)
        
        country_code = request.query_params.get('country_code')
        if country_code:
            tax_rates = tax_rates.filter(country__code__iexact=country_code)
        
        category = request.query_params.get('category')
        if category:
            tax_rates = tax_rates.filter(category=category.upper())
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            tax_rates = tax_rates.filter(is_active=is_active_bool)
        
        name = request.query_params.get('name')
        if name:
            tax_rates = tax_rates.filter(name__icontains=name)
        
        serializer = TaxRateListSerializer(tax_rates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = TaxRateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def tax_rate_detail(request, pk):
    """
    Retrieve, update, or delete a specific tax rate.
    
    GET /tax-rates/{id}/
    - Returns detailed information about a tax rate
    
    PUT/PATCH /tax-rates/{id}/
    - Update a tax rate
    - Request body: TaxRateSerializer fields
    
    DELETE /tax-rates/{id}/
    - Delete a tax rate (if not referenced by other models)
    """
    tax_rate = get_object_or_404(TaxRate.objects.select_related('country'), pk=pk)
    
    if request.method == 'GET':
        serializer = TaxRateSerializer(tax_rate)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = TaxRateSerializer(tax_rate, data=request.data, partial=partial)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response(
                    {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            tax_rate.delete()
            return Response(
                {'message': f'Tax rate "{tax_rate.name}" deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except ValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
def tax_rate_toggle_active(request, pk):
    """
    Toggle the active status of a tax rate.
    
    POST /tax-rates/{id}/toggle-active/
    
    Returns:
        {
            "id": 1,
            "name": "UAE VAT",
            "category": "STANDARD",
            "is_active": true/false
        }
    """
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    tax_rate.is_active = not tax_rate.is_active
    tax_rate.save()
    
    return Response({
        'id': tax_rate.id,
        'name': tax_rate.name,
        'category': tax_rate.category,
        'is_active': tax_rate.is_active
    }, status=status.HTTP_200_OK)
