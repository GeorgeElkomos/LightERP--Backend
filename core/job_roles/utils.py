"""
Permission resolution logic for page-based access control
"""
from .models import Page, PageAction, JobRolePage, UserActionDenial


def user_can_perform_action(user, page_name, action_name):
    """
    Check if a user can perform a specific action on a page.
    
    Args:
        user: CustomUser instance
        page_name: str - name of the page (e.g., 'Invoice', 'Payment')
        action_name: str - name of the action (e.g., 'view', 'create', 'delete')
    
    Returns:
        tuple: (bool, str) - (allowed, reason)
    
    Logic:
        1. Check if user_type is "super_admin" → Allow everything
        2. Get user's job role → If no job role, deny
        3. Get pages linked to that job role
        4. Check if the requested page is in the job role's pages
        5. Check if the action exists for that page
        6. Check UserActionDenial → If denial exists, deny access
        7. Otherwise, allow
    """
    # Super admin bypasses all permission checks
    if user.user_type.type_name == 'super_admin':
        return (True, 'Super admin has full access')
    
    # User must have a job role
    if not user.job_role:
        return (False, 'User has no job role assigned')
    
    # Check if page exists
    try:
        page = Page.objects.get(name=page_name)
    except Page.DoesNotExist:
        return (False, f"Page '{page_name}' does not exist")
    
    # Check if page is accessible by user's job role
    job_role_has_page = JobRolePage.objects.filter(
        job_role=user.job_role,
        page=page
    ).exists()
    
    if not job_role_has_page:
        return (False, f"Page '{page_name}' not accessible with job role '{user.job_role.name}'")
    
    # Check if action exists for this page
    try:
        page_action = PageAction.objects.select_related('action').get(
            page=page, 
            action__name=action_name
        )
    except PageAction.DoesNotExist:
        return (False, f"Action '{action_name}' does not exist for page '{page_name}'")
    
    # Check if user has a denial for this action
    denial_exists = UserActionDenial.objects.filter(
        user=user,
        page_action=page_action
    ).exists()
    
    if denial_exists:
        return (False, 'Action denied for this user')
    
    # Default: allow
    return (True, 'Allowed')


def get_user_page_permissions(user):
    """
    Get all effective page-based permissions for a user.
    
    Args:
        user: CustomUser instance
    
    Returns:
        dict - Structure with all pages and actions accessible by user
    """
    result = {
        'user_id': user.id,
        'name': user.name,
        'user_type': user.user_type.type_name,
        'job_role': None,
        'pages': []
    }
    
    # Super admin has access to everything
    if user.user_type.type_name == 'super_admin':
        result['job_role'] = {'id': None, 'name': 'Super Admin'}
        # Get all pages with all actions
        pages = Page.objects.prefetch_related('page_actions__action').all()
        for page in pages:
            page_data = {
                'page_id': page.id,
                'page_name': page.name,
                'display_name': page.display_name,
                'actions': []
            }
            # Get actions through PageAction relationships
            for page_action in page.page_actions.all():
                page_data['actions'].append({
                    'action_id': page_action.action.id,
                    'name': page_action.action.name,
                    'display_name': page_action.action.display_name,
                    'allowed': True
                })
            result['pages'].append(page_data)
        return result
    
    # User must have a job role
    if not user.job_role:
        return result
    
    result['job_role'] = {
        'id': user.job_role.id,
        'name': user.job_role.name
    }
    
    # Get pages accessible by user's job role
    job_role_pages = JobRolePage.objects.filter(
        job_role=user.job_role
    ).select_related('page').prefetch_related('page__page_actions__action')
    
    # Get all user denials at once for efficiency
    user_denials = UserActionDenial.objects.filter(user=user).select_related('page_action')
    denial_map = {denial.page_action_id: denial.id for denial in user_denials}
    
    for jrp in job_role_pages:
        page = jrp.page
        page_data = {
            'page_id': page.id,
            'page_name': page.name,
            'display_name': page.display_name,
            'actions': []
        }
        
        # Get actions through PageAction relationships
        for page_action in page.page_actions.all():
            action_data = {
                'action_id': page_action.action.id,
                'name': page_action.action.name,
                'display_name': page_action.action.display_name,
                'allowed': page_action.id not in denial_map
            }
            
            if page_action.id in denial_map:
                action_data['denial_id'] = denial_map[page_action.id]
            
            page_data['actions'].append(action_data)
        
        result['pages'].append(page_data)
    
    return result


def get_user_denied_actions(user):
    """
    Get only the denied actions for a user.
    
    Args:
        user: CustomUser instance
    
    Returns:
        dict with list of denied actions
    """
    denials = UserActionDenial.objects.filter(
        user=user
    ).select_related('page_action__page', 'page_action__action').order_by('created_at')
    
    denied_actions = []
    for denial in denials:
        denied_actions.append({
            'denial_id': denial.id,
            'page_name': denial.page_action.page.name,
            'page_display_name': denial.page_action.page.display_name,
            'action_name': denial.page_action.action.name,
            'action_display_name': denial.page_action.action.display_name,
            'denied_at': denial.created_at.isoformat()
        })
    
    return {
        'user_id': user.id,
        'denied_actions': denied_actions
    }


def get_user_accessible_pages(user):
    """
    Get simplified list of pages accessible by user.
    
    Args:
        user: CustomUser instance
    
    Returns:
        list of page info
    """
    # Super admin can access all pages
    if user.user_type.type_name == 'super_admin':
        pages = Page.objects.all()
        return [{
            'name': page.name,
            'display_name': page.display_name
        } for page in pages]
    
    # User must have a job role
    if not user.job_role:
        return []
    
    # Get pages linked to user's job role
    job_role_pages = JobRolePage.objects.filter(
        job_role=user.job_role
    ).select_related('page')
    
    return [{
        'name': jrp.page.name,
        'display_name': jrp.page.display_name
    } for jrp in job_role_pages]


def require_page_action(page_name, action_name):
    """
    Decorator to check if user has permission to perform a page action.
    
    Usage:
        @require_page_action('Invoice', 'approve_invoice')
        def approve_invoice_view(request):
            ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from rest_framework.response import Response
                from rest_framework import status
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            allowed, reason = user_can_perform_action(request.user, page_name, action_name)
            if not allowed:
                from rest_framework.response import Response
                from rest_framework import status
                return Response(
                    {'error': reason},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
