"""
Permission decorators for function-based views.
"""
from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from core.job_roles.services import user_can_perform_action


def require_page_action(page_name, action_name=None):
    """
    Decorator to check page-action permissions for function-based views.
    
    Args:
        page_name: The page identifier (e.g., 'hr_department')
        action_name: The action to check. If None, auto-detects from HTTP method
    
    Usage:
        # Explicit action
        @require_page_action('hr_department', 'view')
        @api_view(['GET'])
        def list_departments(request):
            ...
        
        # Auto-detect action from HTTP method
        @require_page_action('hr_department')
        @api_view(['GET', 'POST'])
        def departments_handler(request):
            # GET = 'view', POST = 'create'
            ...
        
        # Multiple endpoints, different actions
        @require_page_action('hr_employee', 'edit')
        @api_view(['PUT', 'PATCH'])
        def update_employee(request, pk):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check authentication
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Determine action
            determined_action = action_name or _get_action_from_method(request.method)
            
            # Check permission
            allowed, reason = user_can_perform_action(
                request.user,
                page_name,
                determined_action
            )
            
            if not allowed:
                return Response(
                    {
                        'error': 'Permission denied',
                        'detail': reason,
                        'required_permission': {
                            'page': page_name,
                            'action': determined_action
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Permission granted, execute view
            return view_func(request, *args, **kwargs)
        
        # Add metadata for introspection/documentation
        wrapper.page_name = page_name
        wrapper.action_name = action_name
        
        return wrapper
    return decorator


def require_any_permission(*page_action_pairs):
    """
    Decorator that checks if user has ANY of the specified permissions (OR logic).
    
    Usage:
        @require_any_permission(
            ('hr_department', 'view'),
            ('hr_employee', 'view'),
        )
        @api_view(['GET'])
        def dashboard(request):
            # User needs EITHER hr_department view OR hr_employee view
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check if user has ANY of the permissions
            reasons = []
            for page_name, action_name in page_action_pairs:
                determined_action = action_name or _get_action_from_method(request.method)
                allowed, reason = user_can_perform_action(
                    request.user,
                    page_name,
                    determined_action
                )
                if allowed:
                    # Found a matching permission, proceed
                    return view_func(request, *args, **kwargs)
                reasons.append(f"{page_name}.{determined_action}: {reason}")

            # No matching permission found
            return Response(
                {
                    'error': 'Permission denied',
                    'detail': 'You need at least one of the following permissions',
                    'required_permissions': [
                        {'page': page, 'action': action or _get_action_from_method(request.method)}
                        for page, action in page_action_pairs
                    ],
                    'reasons': reasons
                },
                status=status.HTTP_403_FORBIDDEN
            )
        return wrapper
    return decorator


def require_all_permissions(*page_action_pairs):
    """
    Decorator that checks if user has ALL of the specified permissions (AND logic).

    Usage:
        @require_all_permissions(
            ('hr_department', 'view'),
            ('hr_employee', 'view'),
        )
        @api_view(['GET'])
        def consolidated_report(request):
            # User needs BOTH hr_department view AND hr_employee view
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Check if user has ALL permissions
            missing_permissions = []
            for page_name, action_name in page_action_pairs:
                determined_action = action_name or _get_action_from_method(request.method)
                allowed, reason = user_can_perform_action(
                    request.user,
                    page_name,
                    determined_action
                )
                if not allowed:
                    missing_permissions.append({
                        'page': page_name,
                        'action': determined_action,
                        'reason': reason
                    })

            if missing_permissions:
                return Response(
                    {
                        'error': 'Permission denied',
                        'detail': 'You need all of the following permissions',
                        'missing_permissions': missing_permissions
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # All permissions granted
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _get_action_from_method(http_method):
    """Map HTTP method to action name"""
    method_action_map = {
        'GET': 'view',
        'POST': 'create',
        'PUT': 'edit',
        'PATCH': 'edit',
        'DELETE': 'delete',
    }
    return method_action_map.get(http_method, 'view')

# ============================================================================
# Self-or-Admin Decorator (for user-specific data access)
# ============================================================================

def require_self_or_admin(user_id_param='user_id'):
    """
    Decorator for endpoints where users can access their own data,
    but admins can access anyone's data.

    Args:
        user_id_param: Name of the URL parameter containing the target user ID

    Usage:
        @require_self_or_admin('user_id')
        @api_view(['GET'])
        def get_user_profile(request, user_id):
            # User can view their own profile, admin can view any
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Get target user ID from kwargs
            target_user_id = kwargs.get(user_id_param)

            # Allow if user is accessing their own data
            if target_user_id is not None and str(request.user.pk) == str(target_user_id):
                return view_func(request, *args, **kwargs)

            # Allow if user is admin
            if hasattr(request.user, 'is_admin') and request.user.is_admin():
                return view_func(request, *args, **kwargs)

            # Check for admin role
            from core.job_roles.services import get_user_active_roles
            effective_roles = get_user_active_roles(request.user)
            user_role_codes = [role.code for role in effective_roles]

            if 'admin' in user_role_codes or 'super_admin' in user_role_codes:
                return view_func(request, *args, **kwargs)

            return Response(
                {
                    'error': 'Permission denied',
                    'detail': 'You can only access your own data'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        return wrapper
    return decorator


