"""
Custom Response Formatter for Standardized API Responses

Ensures all API responses follow the format:
{
    "status": "success" | "error",
    "message": "string message or empty",
    "data": {...} | [] | null
}
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework.renderers import JSONRenderer


def custom_exception_handler(exc, context):
    """
    Custom exception handler that formats all error responses consistently.
    
    Converts DRF's default error format into our standard format:
    {
        "status": "error",
        "message": "Error message",
        "data": null
    }
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Format the error response
        custom_response = format_error_response(response.data, response.status_code)
        response.data = custom_response
    
    return response


def format_error_response(errors, status_code):
    """
    Format error responses into standard format.
    
    Handles various error formats:
    - {"field": ["error1", "error2"]} -> "field: error1, error2"
    - {"detail": "message"} -> "message"
    - ["error1", "error2"] -> "error1, error2"
    """
    message = ""
    
    if isinstance(errors, dict):
        # Handle field-specific errors
        error_messages = []
        for field, field_errors in errors.items():
            if field == 'detail':
                # Direct detail message
                message = str(field_errors)
            elif isinstance(field_errors, list):
                # Field validation errors
                field_msg = f"{field}: {', '.join(str(e) for e in field_errors)}"
                error_messages.append(field_msg)
            elif isinstance(field_errors, dict):
                # Nested errors
                nested_msg = f"{field}: {format_nested_errors(field_errors)}"
                error_messages.append(nested_msg)
            else:
                error_messages.append(f"{field}: {str(field_errors)}")
        
        if error_messages:
            message = "; ".join(error_messages)
    
    elif isinstance(errors, list):
        # List of errors
        message = ", ".join(str(e) for e in errors)
    
    else:
        # Single error message
        message = str(errors)
    
    return {
        "status": "error",
        "message": message,
        "data": None
    }


def format_nested_errors(errors_dict):
    """Format nested error dictionaries."""
    messages = []
    for key, value in errors_dict.items():
        if isinstance(value, list):
            messages.append(f"{key}: {', '.join(str(v) for v in value)}")
        elif isinstance(value, dict):
            messages.append(f"{key}: {format_nested_errors(value)}")
        else:
            messages.append(f"{key}: {str(value)}")
    return "; ".join(messages)


class StandardizedJSONRenderer(JSONRenderer):
    """
    Custom JSON renderer that wraps all successful responses in standard format.
    
    Automatically wraps responses that aren't already formatted.
    """
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render data into JSON, ensuring standard format.
        """
        response = renderer_context.get('response') if renderer_context else None
        # Don't wrap 204 No Content responses - they should have no body
        if response is not None and response.status_code == 204:
            return b''
        if response is not None:
            status_code = response.status_code
            
            # Check if already formatted
            if not self.is_already_formatted(data):
                # Check if it's an error response (4xx or 5xx)
                if status_code >= 400:
                    # Format error response
                    data = format_error_response(data, status_code)
                else:
                    # Format success response
                    data = self.format_success_response(data, status_code)
        
        return super().render(data, accepted_media_type, renderer_context)
    
    def is_already_formatted(self, data):
        """Check if response is already in our standard format."""
        if isinstance(data, dict):
            # Check if it has our standard keys
            has_status = 'status' in data
            has_message = 'message' in data
            has_data = 'data' in data
            
            # If it has all 3 keys, consider it formatted
            return has_status and has_message and has_data
        
        return False
    
    def format_success_response(self, data, status_code):
        """
        Format success response data into standard format.
        """
        # Handle different data types
        if isinstance(data, dict) and 'detail' in data:
            # Detail message (common in DRF responses)
            message = str(data['detail'])
            response_data = None
        elif data is None or (isinstance(data, dict) and not data):
            # Empty response
            message = ""
            response_data = None
        else:
            # Regular data response
            message = ""
            response_data = data
        
        return {
            "status": "success",
            "message": message,
            "data": response_data
        }


def success_response(data=None, message="", status_code=http_status.HTTP_200_OK):
    """
    Helper function to create standardized success responses.
    
    Usage:
        from erp_project.response_formatter import success_response
        
        return success_response(
            data=serializer.data,
            message="Invoice created successfully",
            status_code=status.HTTP_201_CREATED
        )
    """
    return Response({
        "status": "success",
        "message": message,
        "data": data
    }, status=status_code)


def error_response(message, data=None, status_code=http_status.HTTP_400_BAD_REQUEST):
    """
    Helper function to create standardized error responses.
    
    Usage:
        from erp_project.response_formatter import error_response
        
        return error_response(
            message="Invoice not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    """
    return Response({
        "status": "error",
        "message": message,
        "data": data
    }, status=status_code)
