"""
Finance Period Views

Handles period management endpoints:
1. Generate period preview (GET/POST) - generates list without saving
2. Bulk save periods (POST) - saves generated periods to database
3. Single period create (POST) - manually create individual period
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Period
from .serializers import (
    PeriodSerializer,
    PeriodListSerializer,
    PeriodGenerationInputSerializer,
    PeriodGenerationOutputSerializer,
    PeriodBulkSaveSerializer
)
from erp_project.response_formatter import success_response, error_response


class PeriodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Period management.
    
    Provides:
    - List all periods
    - Retrieve single period
    - Create single period manually
    - Update period
    - Delete period
    - Generate period preview (custom action)
    - Bulk save periods (custom action)
    """
    queryset = Period.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PeriodListSerializer
        return PeriodSerializer
    
    def list(self, request, *args, **kwargs):
        """
        List all periods with optional filtering.
        
        Query Parameters:
        - fiscal_year: Filter by fiscal year
        - is_adjustment_period: Filter adjustment periods (true/false)
        """
        queryset = self.get_queryset()
        
        # Apply filters
        fiscal_year = request.query_params.get('fiscal_year')
        if fiscal_year:
            queryset = queryset.filter(fiscal_year=fiscal_year)
        
        is_adjustment = request.query_params.get('is_adjustment_period')
        if is_adjustment is not None:
            is_adj_bool = is_adjustment.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_adjustment_period=is_adj_bool)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            data=serializer.data,
            message="Periods retrieved successfully"
        )
    
    def retrieve(self, request, *args, **kwargs):
        """Get single period detail"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(
            data=serializer.data,
            message="Period retrieved successfully"
        )
    
    def create(self, request, *args, **kwargs):
        """
        Create a single period manually.
        
        Request Body:
        {
            "name": "January 2026",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "fiscal_year": 2026,
            "period_number": 1,
            "is_adjustment_period": false,
            "description": "First period of FY2026"
        }
        """
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return success_response(
                data=serializer.data,
                message="Period created successfully",
                status_code=status.HTTP_201_CREATED
            )
        
        return error_response(
            message="Failed to create period",
            data=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def update(self, request, *args, **kwargs):
        """Update an existing period"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            return success_response(
                data=serializer.data,
                message="Period updated successfully"
            )
        
        return error_response(
            message="Failed to update period",
            data=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def partial_update(self, request, *args, **kwargs):
        """Partially update an existing period"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a period"""
        instance = self.get_object()
        instance.delete()
        return success_response(
            message="Period deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=False, methods=['post'], url_path='generate-preview')
    def generate_preview(self, request):
        """
        Generate a preview list of periods without saving to database.
        
        This allows users to review the generated periods, make edits,
        and then decide to save them or create periods manually.
        
        Request Body:
        {
            "start_date": "2026-01-01",
            "fiscal_year": 2026,
            "num_periods": 12,
            "num_adjustment_periods": 1,
            "adjustment_period_days": 1
        }
        
        Response:
        {
            "status": "success",
            "message": "Period preview generated successfully",
            "data": {
                "total_periods": 13,
                "regular_periods": 12,
                "adjustment_periods": 1,
                "periods": [...]
            }
        }
        """
        input_serializer = PeriodGenerationInputSerializer(data=request.data)
        
        if not input_serializer.is_valid():
            return error_response(
                message="Invalid input parameters",
                data=input_serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate periods (not saved to DB)
        validated_data = input_serializer.validated_data
        periods = Period.create_list_of_periods(
            start_date=validated_data['start_date'],
            fiscal_year=validated_data['fiscal_year'],
            num_periods=validated_data['num_periods'],
            num_adjustment_periods=validated_data.get('num_adjustment_periods', 0),
            adjustment_period_days=validated_data.get('adjustment_period_days', 1)
        )
        
        # Serialize the generated periods
        output_serializer = PeriodGenerationOutputSerializer(periods, many=True)
        
        regular_periods = [p for p in periods if not p.is_adjustment_period]
        adjustment_periods = [p for p in periods if p.is_adjustment_period]
        
        return success_response(
            data={
                'total_periods': len(periods),
                'regular_periods': len(regular_periods),
                'adjustment_periods': len(adjustment_periods),
                'periods': output_serializer.data
            },
            message="Period preview generated successfully. Review and edit as needed, then use bulk-save endpoint to save."
        )
    
    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        """
        Bulk save multiple periods to the database.
        
        This endpoint accepts the edited list of periods from the preview
        and saves them all to the database in one transaction.
        
        Request Body:
        {
            "periods": [
                {
                    "name": "January 2026",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "fiscal_year": 2026,
                    "period_number": 1,
                    "is_adjustment_period": false,
                    "description": "First period"
                },
                ...
            ]
        }
        
        Response:
        {
            "status": "success",
            "message": "13 periods saved successfully",
            "data": {
                "created_count": 13,
                "periods": [...]
            }
        }
        """
        serializer = PeriodBulkSaveSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid period data",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Save all periods in a transaction
            with transaction.atomic():
                result = serializer.save()
                
                # Serialize the created periods for response
                periods_serializer = PeriodSerializer(result['periods'], many=True)
                
                return success_response(
                    data={
                        'created_count': result['created_count'],
                        'periods': periods_serializer.data
                    },
                    message=f"{result['created_count']} periods saved successfully",
                    status_code=status.HTTP_201_CREATED
                )
        
        except Exception as e:
            return error_response(
                message="Failed to save periods",
                data={'detail': str(e)},
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get the current period (contains today's date)"""
        from datetime import date
        
        today = date.today()
        period = Period.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        if not period:
            return error_response(
                message="No current period found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(period)
        return success_response(
            data=serializer.data,
            message="Current period retrieved successfully"
        )
