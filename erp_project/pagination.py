"""
Automatic Pagination for Function-Based Views

This module provides automatic pagination through a decorator that wraps
function-based views, eliminating the need to modify each view individually.

Works with standardized response format:
{
    "status": "success",
    "message": "",
    "data": {"count": ..., "results": [...], ...}
}
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from functools import wraps
from django.db.models import QuerySet


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class for the project.
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    
    Response format (wrapped in standard response):
    {
        "status": "success",
        "message": "",
        "data": {
            "count": 150,
            "next": "http://api.example.org/items/?page=4",
            "previous": "http://api.example.org/items/?page=2",
            "results": [...]
        }
    }
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """
        Override to wrap pagination in standard response format.
        """
        return Response({
            'status': 'success',
            'message': '',
            'data': {
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        })


def auto_paginate(view_func):
    """
    Decorator that automatically paginates list responses from function-based views.
    
    Usage:
        from erp_project.pagination import auto_paginate
        
        @api_view(['GET', 'POST'])
        @auto_paginate  # Add this decorator
        def my_list_view(request):
            if request.method == 'GET':
                queryset = MyModel.objects.all()
                # Apply filters...
                serializer = MySerializer(queryset, many=True)
                return Response(serializer.data)
            elif request.method == 'POST':
                # POST requests are not paginated
                ...
    
    How it works:
    - Detects if response.data is a list
    - Only paginates GET requests
    - Leaves non-list responses untouched (detail views, etc.)
    - Automatically wraps the response in pagination format with standard structure
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Call the original view
        response = view_func(request, *args, **kwargs)
        
        # Only paginate GET requests that return a list
        if (
            request.method == 'GET' and 
            isinstance(response, Response) and
            isinstance(response.data, list)
        ):
            paginator = StandardResultsSetPagination()
            
            # Paginate the data
            page = paginator.paginate_queryset(response.data, request)
            
            if page is not None:
                # Return paginated response (already in standard format)
                return paginator.get_paginated_response(page)
        
        # Return original response for non-list data or non-GET requests
        return response
    
    return wrapper
