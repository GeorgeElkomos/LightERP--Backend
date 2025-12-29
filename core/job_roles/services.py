"""
Service layer for Job Roles permission checking.
Contains business logic for role-based access control.
"""
from typing import Tuple
from django.core.exceptions import ValidationError
from .models import JobRole, Page, Action, PageAction, JobRolePage, UserActionDenial


def user_can_perform_action(user, page_name: str, action_name: str) -> Tuple[bool, str]:
    """
    Check if a user can perform a specific action on a page.
    
    Args:
        user: The UserAccount instance
        page_name: The page identifier (e.g., 'hr_department')
        action_name: The action name (e.g., 'view', 'create', 'edit', 'delete')
    
    Returns:
        Tuple of (allowed: bool, reason: str)
        - (True, "Permission granted") if user can perform action
        - (False, "reason for denial") if user cannot perform action
    
    Logic:
        1. Check if page exists
        2. Check if action exists
        3. Check if the page-action combination exists
        4. Check if user has explicit denial for this action
        5. Check if user's job roles grant access to this page
    """
    # Check if page exists
    try:
        page = Page.objects.get(name=page_name)
    except Page.DoesNotExist:
        return False, f"Page '{page_name}' does not exist"
    
    # Check if action exists
    try:
        action = Action.objects.get(name=action_name)
    except Action.DoesNotExist:
        return False, f"Action '{action_name}' does not exist"
    
    # Check if this page-action combination exists
    try:
        page_action = PageAction.objects.get(page=page, action=action)
    except PageAction.DoesNotExist:
        return False, f"Action '{action_name}' is not available for page '{page_name}'"
    
    # Check for explicit user denial
    denial = UserActionDenial.objects.filter(
        user=user,
        page_action=page_action
    ).first()
    
    if denial:
        return False, f"Access explicitly denied: {denial.denial_reason or 'No reason provided'}"
    
    # Check if user has an assigned job role
    if not user.job_role:
        return False, "User has no assigned job role"
    
    user_job_role = user.job_role
    
    # Check if the user's role has access to this page
    if JobRolePage.objects.filter(job_role=user_job_role, page=page).exists():
        return True, "Permission granted"
    
    return False, f"Your role ({user_job_role.name}) does not have access to page '{page_name}'"


def get_user_page_permissions(user, page_name: str) -> dict:
    """
    Get all actions a user can perform on a specific page.
    
    Args:
        user: The UserAccount instance
        page_name: The page identifier
    
    Returns:
        dict with structure:
        {
            'page': page_name,
            'allowed_actions': ['view', 'create', ...],
            'denied_actions': ['delete'],
            'has_access': bool
        }
    """
    try:
        page = Page.objects.get(name=page_name)
    except Page.DoesNotExist:
        return {
            'page': page_name,
            'allowed_actions': [],
            'denied_actions': [],
            'has_access': False,
            'error': f"Page '{page_name}' does not exist"
        }
    
    # Get all page-actions for this page
    page_actions = PageAction.objects.filter(page=page).select_related('action')
    
    # Get user's job role
    user_job_role = user.job_role
    
    if not user_job_role:
        return {
            'page': page_name,
            'allowed_actions': [],
            'denied_actions': [],
            'has_access': False,
            'error': 'User has no assigned job role'
        }
    
    # Check if user has access to this page through their role
    has_page_access = JobRolePage.objects.filter(
        job_role=user_job_role,
        page=page
    ).exists()
    
    if not has_page_access:
        return {
            'page': page_name,
            'allowed_actions': [],
            'denied_actions': [],
            'has_access': False,
            'error': 'No role grants access to this page'
        }
    
    # Get explicitly denied actions
    denied_page_actions = UserActionDenial.objects.filter(
        user=user,
        page_action__page=page
    ).values_list('page_action__action__name', flat=True)
    
    # Build allowed actions (all page actions minus denied ones)
    allowed_actions = []
    denied_actions = list(denied_page_actions)
    
    for page_action in page_actions:
        action_name = page_action.action.name
        if action_name not in denied_actions:
            allowed_actions.append(action_name)
    
    return {
        'page': page_name,
        'allowed_actions': allowed_actions,
        'denied_actions': denied_actions,
        'has_access': True
    }


def get_user_all_permissions(user) -> list:
    """
    Get all pages and actions a user can access.
    
    Args:
        user: The UserAccount instance
    
    Returns:
        list of dicts with structure:
        [
            {
                'page': 'hr_department',
                'page_display_name': 'HR - Departments',
                'allowed_actions': ['view', 'create', 'edit'],
                'denied_actions': ['delete']
            },
            ...
        ]
    """
    user_job_role = user.job_role
    
    if not user_job_role:
        return []
    
    # Get all pages user has access to through their role
    job_role_pages = JobRolePage.objects.filter(
        job_role=user_job_role
    ).select_related('page').distinct()
    
    permissions = []
    
    for jrp in job_role_pages:
        page = jrp.page
        page_permissions = get_user_page_permissions(user, page.name)
        
        permissions.append({
            'page': page.name,
            'page_display_name': page.display_name,
            'allowed_actions': page_permissions['allowed_actions'],
            'denied_actions': page_permissions['denied_actions']
        })
    
    return permissions
