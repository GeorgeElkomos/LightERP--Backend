"""
HR-specific permission decorators for elevated operations.

Hard delete operations are restricted to super admins only, as they permanently
remove data from the database bypassing the soft delete (date tracking) pattern.
"""
from functools import wraps
from rest_framework.response import Response
from rest_framework import status


def require_super_admin(view_func):
    """
    Decorator to restrict access to super admin users only.
    
    Use this for destructive operations like hard delete that bypass
    the soft delete pattern and permanently remove records.
    
    Usage:
        @require_super_admin
        def hard_delete_view(request, pk):
            ...
    
    Returns:
        403 Forbidden if user is not a super admin
        401 Unauthorized if user is not authenticated
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not request.user.is_super_admin():
            return Response(
                {
                    'error': 'Super admin privileges required for this operation',
                    'detail': 'Hard delete operations require super admin access'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
