"""
Default Combinations Views
API views for managing default segment combinations for different transaction types
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import set_default_combinations
from .serializers import (
    DefaultCombinationsListSerializer,
    DefaultCombinationsDetailSerializer,
    DefaultCombinationsCreateSerializer,
    DefaultCombinationsUpdateSerializer,
    DefaultCombinationsValidationSerializer,
)


class DefaultCombinationsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing default segment combinations.
    
    Provides CRUD operations and additional actions for:
    - Creating/updating default combinations (ensures one per transaction type)
    - Retrieving defaults by transaction type
    - Validating segment combination completeness
    - Checking validity of all defaults
    - Activating/deactivating defaults
    """
    queryset = set_default_combinations.objects.select_related(
        'segment_combination',
        'created_by',
        'updated_by'
    ).all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return DefaultCombinationsListSerializer
        elif self.action in ['create']:
            return DefaultCombinationsCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DefaultCombinationsUpdateSerializer
        elif self.action in ['validate', 'check_validity']:
            return DefaultCombinationsValidationSerializer
        return DefaultCombinationsDetailSerializer
    
    def get_serializer_context(self):
        """Add request to serializer context for user tracking"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def list(self, request, *args, **kwargs):
        """
        List all default combinations with validation status
        
        Query Parameters:
        - is_active: Filter by active status (true/false)
        - transaction_type: Filter by transaction type (AP_INVOICE/AR_INVOICE)
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        transaction_type = request.query_params.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """
        Create or update a default combination for a transaction type.
        Automatically handles the constraint of one default per transaction type.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        # Return detailed response
        detail_serializer = DefaultCombinationsDetailSerializer(instance)
        return Response(
            detail_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Update an existing default combination"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        # Return detailed response
        detail_serializer = DefaultCombinationsDetailSerializer(instance)
        return Response(detail_serializer.data)
    
    @action(detail=False, methods=['get'], url_path='by-transaction-type/(?P<transaction_type>[^/.]+)')
    def by_transaction_type(self, request, transaction_type=None):
        """
        Get the default combination for a specific transaction type
        
        URL: /default-combinations/by-transaction-type/{AP_INVOICE|AR_INVOICE}/
        """
        if transaction_type not in dict(set_default_combinations.TRANSACTION_TYPES).keys():
            return Response(
                {'error': f'Invalid transaction type. Must be one of: {", ".join(dict(set_default_combinations.TRANSACTION_TYPES).keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            default = set_default_combinations.objects.get(transaction_type=transaction_type)
        except set_default_combinations.DoesNotExist:
            return Response(
                {'error': f'No default combination found for transaction type: {transaction_type}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DefaultCombinationsDetailSerializer(default)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='ap-invoice-default')
    def ap_invoice_default(self, request):
        """
        Get the default combination for AP Invoice
        
        URL: /default-combinations/ap-invoice-default/
        """
        try:
            default = set_default_combinations.objects.get(transaction_type='AP_INVOICE')
        except set_default_combinations.DoesNotExist:
            return Response(
                {'error': 'No default combination found for AP Invoice'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DefaultCombinationsDetailSerializer(default)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='ar-invoice-default')
    def ar_invoice_default(self, request):
        """
        Get the default combination for AR Invoice
        
        URL: /default-combinations/ar-invoice-default/
        """
        try:
            default = set_default_combinations.objects.get(transaction_type='AR_INVOICE')
        except set_default_combinations.DoesNotExist:
            return Response(
                {'error': 'No default combination found for AR Invoice'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DefaultCombinationsDetailSerializer(default)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate if the segment combination is complete
        
        URL: /default-combinations/{id}/validate/
        """
        instance = self.get_object()
        serializer = DefaultCombinationsValidationSerializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='check-all-validity')
    def check_all_validity(self, request):
        """
        Check and update validity of all default combinations
        Auto-deactivates invalid combinations
        
        URL: /default-combinations/check-all-validity/
        """
        try:
            set_default_combinations.check_all_defaults_validity()
            
            # Get all defaults with their current status
            defaults = self.get_queryset()
            serializer = DefaultCombinationsListSerializer(defaults, many=True)
            
            return Response({
                'message': 'Validity check completed successfully',
                'defaults': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': f'Error checking validity: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate a default combination (only if valid)
        
        URL: /default-combinations/{id}/activate/
        """
        instance = self.get_object()
        
        # Check if it's valid first
        is_valid, message = instance.validate_segment_combination_completeness()
        
        if not is_valid:
            return Response(
                {'error': f'Cannot activate invalid combination: {message}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.is_active = True
        instance.updated_by = request.user
        instance.save()
        
        serializer = DefaultCombinationsDetailSerializer(instance)
        return Response({
            'message': 'Default combination activated successfully',
            'data': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate a default combination
        
        URL: /default-combinations/{id}/deactivate/
        """
        instance = self.get_object()
        instance.is_active = False
        instance.updated_by = request.user
        instance.save()
        
        serializer = DefaultCombinationsDetailSerializer(instance)
        return Response({
            'message': 'Default combination deactivated successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['get'], url_path='transaction-types')
    def transaction_types(self, request):
        """
        Get list of available transaction types
        
        URL: /default-combinations/transaction-types/
        """
        types = [
            {
                'value': code,
                'label': label
            }
            for code, label in set_default_combinations.TRANSACTION_TYPES
        ]
        return Response(types)
    
    @action(detail=False, methods=['get'], url_path='gl-segments')
    def gl_segments(self, request):
        """
        Get GL segment combination details for a transaction type.
        Returns the segment types and values as a structured list.
        
        URL: /default-combinations/gl-segments/?transaction_type={AP_INVOICE|AR_INVOICE}
        
        Query Parameters:
        - transaction_type: Required. Must be AP_INVOICE or AR_INVOICE
        
        Returns:
        - transaction_type: The transaction type requested
        - transaction_type_label: Human-readable label
        - default_combination_id: ID of the default combination record
        - segment_combination_id: ID of the GL segment combination
        - is_active: Whether the default is active
        - segments: List of segment types and their values
        - created_by: User who created the default
        - created_at: Creation timestamp
        - updated_at: Last update timestamp
        """
        transaction_type = request.query_params.get('transaction_type')
        
        if not transaction_type:
            return Response(
                {'error': 'transaction_type query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if transaction_type not in dict(set_default_combinations.TRANSACTION_TYPES).keys():
            return Response(
                {
                    'error': f'Invalid transaction type. Must be one of: {", ".join(dict(set_default_combinations.TRANSACTION_TYPES).keys())}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            default = set_default_combinations.objects.select_related(
                'segment_combination',
                'created_by',
                'updated_by'
            ).prefetch_related(
                'segment_combination__details__segment_type',
                'segment_combination__details__segment'
            ).get(transaction_type=transaction_type)
        except set_default_combinations.DoesNotExist:
            return Response(
                {'error': f'No default combination found for transaction type: {transaction_type}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build segments list
        segments_list = []
        for detail in default.segment_combination.details.all().order_by('segment_type__display_order'):
            segments_list.append({
                'segment_type': detail.segment_type.segment_name,
                'segment_type_id': detail.segment_type.id,
                'display_order': detail.segment_type.display_order,
                'is_required': detail.segment_type.is_required,
                'segment_code': detail.segment.code,
                'segment_name': detail.segment.name,
                'segment_alias': detail.segment.alias or '',
                'segment_id': detail.segment.id,
            })
        
        response_data = {
            'transaction_type': default.transaction_type,
            'transaction_type_label': default.get_transaction_type_display(),
            'default_combination_id': default.id,
            'segment_combination_id': default.segment_combination.id,
            'is_active': default.is_active,
            'segments': segments_list,
            'created_by': default.created_by.name if default.created_by else None,
            'created_at': default.created_at,
            'updated_at': default.updated_at,
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'], url_path='ap-invoice-segments')
    def ap_invoice_segments(self, request):
        """
        Convenience endpoint to get AP Invoice GL segments.
        
        URL: /default-combinations/ap-invoice-segments/
        """
        request.query_params._mutable = True
        request.query_params['transaction_type'] = 'AP_INVOICE'
        request.query_params._mutable = False
        return self.gl_segments(request)
    
    @action(detail=False, methods=['get'], url_path='ar-invoice-segments')
    def ar_invoice_segments(self, request):
        """
        Convenience endpoint to get AR Invoice GL segments.
        
        URL: /default-combinations/ar-invoice-segments/
        """
        request.query_params._mutable = True
        request.query_params['transaction_type'] = 'AR_INVOICE'
        request.query_params._mutable = False
        return self.gl_segments(request)
