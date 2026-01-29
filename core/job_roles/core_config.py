"""
Core System Configuration - Hardcoded Setup
============================================

Defines the foundational structure for the permission system:
- 4 Standard actions: view, create, edit, delete
- 3 Core pages: user_management, job_role_management, permission_override_management
- 1 Admin role with access to all pages

This data is used by the initialization script to populate the database.
No fixtures needed - this is the source of truth.

Last Updated: January 7, 2026
"""

# ============================================================================
# ACTIONS
# ============================================================================

class CoreActions:
    """Standard action identifiers."""
    VIEW = 'view'
    CREATE = 'create'
    EDIT = 'edit'
    DELETE = 'delete'


CORE_ACTIONS = [
    {'code': 'view', 'name': 'View', 'description': 'View and read records'},
    {'code': 'create', 'name': 'Create', 'description': 'Create new records'},
    {'code': 'edit', 'name': 'Edit', 'description': 'Edit and update existing records'},
    {'code': 'delete', 'name': 'Delete', 'description': 'Delete or deactivate records'},
]


# ============================================================================
# PAGES
# ============================================================================

class CorePages:
    """Core page identifiers."""
    USER_MANAGEMENT = 'user_management'
    JOB_ROLE_MANAGEMENT = 'job_role_management'
    PERMISSION_OVERRIDE_MANAGEMENT = 'permission_override_management'


CORE_PAGES = [
    {
        'code': 'user_management',
        'name': 'User Management',
        'description': 'Manage user accounts, profiles, and authentication',
        'module_code': 'core',
        'sort_order': 10,
        'parent_page': None,
        'actions': ['view', 'create', 'edit', 'delete']
    },
    {
        'code': 'job_role_management',
        'name': 'Job Role Management',
        'description': 'Manage job roles, permissions, and role assignments',
        'module_code': 'core',
        'sort_order': 20,
        'parent_page': None,
        'actions': ['view', 'create', 'edit', 'delete']
    },
    {
        'code': 'permission_override_management',
        'name': 'Permission Override Management',
        'description': 'Manage user-specific permission grants and denials',
        'module_code': 'core',
        'sort_order': 30,
        'parent_page': None,
        'actions': ['view', 'create', 'edit', 'delete']
    },
]


# ============================================================================
# JOB ROLES
# ============================================================================

class CoreRoles:
    """Core role identifiers."""
    ADMIN = 'admin'


CORE_JOB_ROLES = [
    {
        'code': 'admin',
        'name': 'Admin',
        'description': 'Administrator with full access to all core pages',
        'priority': 100,
        'parent_role': None,
        'pages': 'ALL'  # Special marker - admin gets all pages
    },
]


