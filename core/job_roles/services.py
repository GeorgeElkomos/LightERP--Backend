"""
Service layer for Job Roles permission checking.
Contains business logic for role-based access control.
"""
from typing import Tuple, List, Dict, Set
from django.utils import timezone
from .models import (
    JobRole, Page, Action, PageAction, JobRolePage,
)


def get_effective_pages_for_job_role_page(job_role_page) -> list:
    """
    Get all pages effectively granted by a JobRolePage assignment.
    If inherit_to_children=True, includes all descendant pages.

    Args:
        job_role_page: JobRolePage instance

    Returns:
        List of Page objects (including self.page + descendants if applicable)
    """
    pages = [job_role_page.page]
    if job_role_page.inherit_to_children:
        pages.extend(job_role_page.page.get_all_descendant_pages())
    return pages


def get_user_active_roles(user) -> List[JobRole]:
    """
    Get all currently active job roles for a user.
    Considers:
    - M2M via UserJobRole (with effective dates)
    - Role status (Active only)

    Returns:
        List of JobRole objects that are currently effective
    """
    from .models import UserJobRole, JobRole
    from core.base.models import StatusChoices
    from django.utils import timezone

    if not user or not user.is_authenticated:
        return []

    today = timezone.now().date()

    # Use VersionedManager's active_on logic to get valid assignments
    active_assignments = UserJobRole.objects.active_on(today).filter(user=user)

    # Extract job_role IDs from the active assignments and return JobRole objects
    job_role_ids = active_assignments.values_list('job_role_id', flat=True)
    return JobRole.objects.filter(id__in=job_role_ids)


def get_role_with_ancestors(role: JobRole) -> List[JobRole]:
    """
    Get a role and all its ancestor roles (for inheritance).

    Returns:
        List starting with the role itself, followed by ancestors up to root.
        Example: [Senior Accountant, Accountant, Employee]
    """
    roles = [role]
    roles.extend(role.get_all_ancestor_roles())
    return roles


def get_all_effective_pages_for_roles(roles: List[JobRole]) -> Set[int]:
    """
    Get all page IDs accessible by a list of roles.

    Considers:
    - Direct page assignments (JobRolePage)
    - Page hierarchy (inherit_to_children flag)
    - Role hierarchy (inherited roles)

    Returns:
        Set of Page IDs that are accessible
    """
    page_ids = set()

    # Expand roles to include ancestors
    all_role_ids = set()
    for role in roles:
        all_role_ids.add(role.pk)
        for ancestor in role.get_all_ancestor_roles():
            all_role_ids.add(ancestor.pk)

    # Get all JobRolePage entries for these roles
    job_role_pages = JobRolePage.objects.filter(
        job_role_id__in=all_role_ids,
    ).select_related('page')

    for jrp in job_role_pages:
            page_ids.add(jrp.page.pk)

            # If inherit_to_children, add all descendant pages
            if jrp.inherit_to_children:
                for child_page in jrp.page.get_all_descendant_pages():
                    page_ids.add(child_page.pk)

    return page_ids


def get_user_permission_overrides(user, page_action_ids: List[int] = None) -> Dict:
    """
    Get all effective permission overrides for a user.

    Returns:
        Dict with structure:
        {
            'grants': set of page_action_ids that are explicitly granted,
            'denials': set of page_action_ids that are explicitly denied
        }
    """
    grants = set()
    denials = set()
    today = timezone.now().date()

    # UserPermissionOverride model (supports grants AND denials)
    # Use active_on() from VersionedManager - automatically filters by dates
    if hasattr(user, 'permission_overrides'):
        overrides_query = user.permission_overrides.active_on(today)

        if page_action_ids:
            overrides_query = overrides_query.filter(page_action_id__in=page_action_ids)

        for override in overrides_query:

            if override.permission_type == 'grant':
                grants.add(override.page_action_id)
            else:  # 'deny'
                denials.add(override.page_action_id)

    return {'grants': grants, 'denials': denials}


def user_can_perform_action(user, page_code: str, action_code: str) -> Tuple[bool, str]:
    """
    Check if a user can perform a specific action on a page.

    Args:
        user: The UserAccount instance
        page_code: The page identifier (e.g., 'hr_employee')
        action_code: The action identifier (e.g., 'view', 'create', 'edit', 'delete')

    Returns:
        Tuple of (allowed: bool, reason: str)
        - (True, "Permission granted") if user can perform action
        - (False, "reason for denial") if user cannot perform action
    
    Permission Logic (priority order):
    1. Admin bypass (always allowed)
    2. Explicit denial (UserPermissionOverride with type='deny') → denied
    3. Explicit grant (UserPermissionOverride with type='grant') → allowed
    4. Role grants (via UserJobRole → JobRole → JobRolePage → PageAction) → allowed
    5. Default: denied
    """
    # 1. Admin bypass
    if hasattr(user, 'is_admin') and user.is_admin():
        return True, "Permission granted (Admin)"

    # Check if page exists
    try:
        page = Page.objects.get(code=page_code)
    except Page.DoesNotExist:
        return False, f"Page '{page_code}' does not exist"

    # Check if action exists
    try:
        action = Action.objects.get(code=action_code)
    except Action.DoesNotExist:
        return False, f"Action '{action_code}' does not exist"

    # Check if this page-action combination exists
    try:
        page_action = PageAction.objects.get(page=page, action=action)
    except PageAction.DoesNotExist:
        return False, f"Action '{action_code}' is not available for page '{page_code}'"

    # Get permission overrides for this specific page_action
    overrides = get_user_permission_overrides(user, [page_action.pk])

    # 2. Check for explicit denial (highest priority block)
    if page_action.pk in overrides['denials']:
        return False, f"Access explicitly denied for action '{action_code}' on page '{page_code}'"

    # 3. Check for explicit grant (overrides role-based access)
    if page_action.pk in overrides['grants']:
        return True, "Permission granted (explicit grant)"

    # 4. Check role-based access
    effective_roles = get_user_active_roles(user)

    if not effective_roles:
        return False, "User has no active job roles assigned"

    # Get all pages accessible by user's roles
    accessible_page_ids = get_all_effective_pages_for_roles(effective_roles)

    if page.pk in accessible_page_ids:
        return True, "Permission granted"
    
    # 5. Default: denied
    role_names = ', '.join([r.name for r in effective_roles])
    return False, f"Your roles ({role_names}) do not have access to page '{page_code}'"


def get_user_page_permissions(user, page_code: str) -> dict:
    """
    Get all actions a user can perform on a specific page.
    
    Args:
        user: The UserAccount instance
        page_code: The page identifier (e.g., 'hr_employee')

    Returns:
        dict with structure:
        {
            'page': page_code,
            'allowed_actions': ['view', 'create', ...],
            'denied_actions': ['delete'],
            'granted_actions': ['approve'],  # Explicit grants beyond role
            'has_access': bool
        }
    """
    try:
        page = Page.objects.get(code=page_code)
    except Page.DoesNotExist:
        return {
            'page': page_code,
            'allowed_actions': [],
            'denied_actions': [],
            'granted_actions': [],
            'has_access': False,
            'error': f"Page '{page_code}' does not exist"
        }
    
    # Get all page-actions for this page
    page_actions = PageAction.objects.filter(page=page).select_related('action')
    page_action_ids = [pa.pk for pa in page_actions]

    # Get user's effective roles
    effective_roles = get_user_active_roles(user)

    if not effective_roles and not (hasattr(user, 'is_admin') and user.is_admin()):
        return {
            'page': page_code,
            'allowed_actions': [],
            'denied_actions': [],
            'granted_actions': [],
            'has_access': False,
            'error': 'User has no active job roles assigned'
        }
    
    # Check if user has access to this page through their roles
    accessible_page_ids = get_all_effective_pages_for_roles(effective_roles)
    has_page_access = page.pk in accessible_page_ids

    # Get permission overrides
    overrides = get_user_permission_overrides(user, page_action_ids)

    # Build permission lists
    allowed_actions = []
    denied_actions = []
    granted_actions = []

    for page_action in page_actions:
        action_code = page_action.action.code

        # Check explicit denial first
        if page_action.pk in overrides['denials']:
            denied_actions.append(action_code)
            continue

        # Check explicit grant
        if page_action.pk in overrides['grants']:
            granted_actions.append(action_code)
            allowed_actions.append(action_code)
            continue

        # Check role-based access
        if has_page_access:
            allowed_actions.append(action_code)

    return {
        'page': page_code,
        'allowed_actions': allowed_actions,
        'denied_actions': denied_actions,
        'granted_actions': granted_actions,  # Subset of allowed that came from explicit grants
        'has_access': has_page_access or bool(granted_actions)
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
                'denied_actions': ['delete'],
                'granted_actions': [],
                'access_source': 'role'  # or 'grant' if via explicit grant
            },
            ...
        ]
    """
    # Admin gets all pages
    if hasattr(user, 'is_admin') and user.is_admin():
        return _get_all_pages_permissions()

    effective_roles = get_user_active_roles(user)

    if not effective_roles:
        # Check for explicit grants even without roles
        return _get_granted_only_permissions(user)

    # Get all pages user has access to through their roles
    accessible_page_ids = get_all_effective_pages_for_roles(effective_roles)

    # Get explicit grants that might give access to additional pages
    all_overrides = get_user_permission_overrides(user)
    granted_page_action_ids = all_overrides['grants']

    # Find pages from explicit grants that aren't in role-based access
    if granted_page_action_ids:
        granted_page_actions = PageAction.objects.filter(
            pk__in=granted_page_action_ids
        ).select_related('page')
        for pa in granted_page_actions:
            accessible_page_ids.add(pa.page.pk)

    # Build permissions for each accessible page
    pages = Page.objects.filter(pk__in=accessible_page_ids).order_by('sort_order', 'name')

    permissions = []
    for page in pages:
        page_permissions = get_user_page_permissions(user, page.code)

        # Determine access source
        access_source = 'role'
        if page_permissions['granted_actions'] and not page.pk in get_all_effective_pages_for_roles(effective_roles):
            access_source = 'grant'

        permissions.append({
            'page': page.name,
            'page_display_name': page.display_name,
            'module_code': page.module_code,
            'allowed_actions': page_permissions['allowed_actions'],
            'denied_actions': page_permissions['denied_actions'],
            'granted_actions': page_permissions['granted_actions'],
            'access_source': access_source
        })

    return permissions


def _get_all_pages_permissions():
    """Get all pages with all actions (for admin)"""
    pages = Page.objects.all().prefetch_related('page_actions__action')

    permissions = []
    for page in pages:
        actions = [pa.action.code for pa in page.page_actions.all()]
        permissions.append({
            'page': page.code,
            'page_name': page.name,
            'module_code': page.module_code,
            'allowed_actions': actions,
            'denied_actions': [],
            'granted_actions': [],
            'access_source': 'admin'
        })
    
    return permissions


def _get_granted_only_permissions(user):
    """Get permissions only from explicit grants (for users without roles)"""
    overrides = get_user_permission_overrides(user)
    granted_page_action_ids = overrides['grants'] - overrides['denials']

    if not granted_page_action_ids:
        return []

    # Group by page
    page_actions = PageAction.objects.filter(
        pk__in=granted_page_action_ids
    ).select_related('page', 'action')

    page_permissions = {}
    for pa in page_actions:
        if pa.page.pk not in page_permissions:
            page_permissions[pa.page.pk] = {
                'page': pa.page.name,
                'page_display_name': pa.page.display_name,
                'module_code': pa.page.module_code,
                'allowed_actions': [],
                'denied_actions': [],
                'granted_actions': [],
                'access_source': 'grant'
            }
        page_permissions[pa.page.pk]['allowed_actions'].append(pa.action.name)
        page_permissions[pa.page.pk]['granted_actions'].append(pa.action.name)

    return list(page_permissions.values())


