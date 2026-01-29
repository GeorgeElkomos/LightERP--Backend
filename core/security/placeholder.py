"""
Placeholder for Task 2: Security Policies (Data Security & Field Security)

This module will implement Oracle-style three-layer security:
- Layer 1: Function Security (already in core/job_roles) - WHAT can user do
- Layer 2: Data Security - WHICH records can user see
- Layer 3: Field Security - WHICH fields can user access

Models to be implemented:
    - DataSecurityPolicy: Rules for record-level access
    - FieldSecurityPolicy: Rules for field-level access
    - JobRoleDataPolicy: Links JobRole to DataSecurityPolicy
    - JobRoleFieldAccess: Links JobRole to FieldSecurityPolicy

Functions to be implemented:
    - get_scoped_queryset(user, model_class, action) -> QuerySet
    - get_field_access(user, model_class, field_name, record) -> str
    - apply_field_security(user, serializer_class, instance) -> Serializer

Current Status: PLACEHOLDER - Not Implemented
Target: Task 2 Implementation

Integration Points from Task 1:
    - Imports: JobRole from core.job_roles
    - Imports: UserAccount from core.user_accounts
    - Targets: BusinessGroup, Department, Position from HR.work_structures
    - Extends: UserDataScope functionality
"""


class DataSecurityPolicy:
    """
    Task 2 Implementation: Defines data access rules for specific objects/pages.

    Fields (planned):
        - code: Unique identifier
        - name: Display name
        - target_model: Django model path (e.g., 'employees.Employee')
        - condition_type: self, department, business_group, hierarchy, global, custom
        - custom_filter: Python dict for queryset filter
        - is_active: Enable/disable flag

    Example Usage:
        policy = DataSecurityPolicy(
            code='emp_by_bg',
            name='Employees by Business Group',
            target_model='employees.Employee',
            condition_type='business_group'
        )
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Task 2: DataSecurityPolicy not implemented. "
            "This is a placeholder for future implementation."
        )


class FieldSecurityPolicy:
    """
    Task 2 Implementation: Defines field-level access rules.

    Fields (planned):
        - code: Unique identifier
        - name: Display name
        - target_model: Django model path
        - field_name: Field name on the model
        - default_access: hidden, masked, readonly, editable
        - mask_pattern: Pattern for masked fields (e.g., '***-**-{last4}')
        - is_active: Enable/disable flag

    Example Usage:
        policy = FieldSecurityPolicy(
            target_model='employees.Employee',
            field_name='salary',
            default_access='hidden'
        )
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Task 2: FieldSecurityPolicy not implemented. "
            "This is a placeholder for future implementation."
        )


class JobRoleDataPolicy:
    """
    Task 2 Implementation: Links job roles to data security policies.

    Fields (planned):
        - job_role: FK to JobRole
        - data_policy: FK to DataSecurityPolicy
        - can_read: Boolean
        - can_create: Boolean
        - can_update: Boolean
        - can_delete: Boolean

    Example Usage:
        JobRoleDataPolicy(
            job_role=hr_specialist,
            data_policy=emp_by_bg_policy,
            can_read=True,
            can_update=True
        )
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Task 2: JobRoleDataPolicy not implemented. "
            "This is a placeholder for future implementation."
        )


class JobRoleFieldAccess:
    """
    Task 2 Implementation: Grants field access to job roles.

    Fields (planned):
        - job_role: FK to JobRole
        - field_policy: FK to FieldSecurityPolicy
        - access_level: hidden, masked, readonly, editable
        - self_only: Boolean - only for own records

    Example Usage:
        JobRoleFieldAccess(
            job_role=employee_role,
            field_policy=salary_policy,
            access_level='readonly',
            self_only=True  # Can only see own salary
        )
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Task 2: JobRoleFieldAccess not implemented. "
            "This is a placeholder for future implementation."
        )


# =============================================================================
# STUB FUNCTIONS - Will be replaced with full implementation in Task 2
# =============================================================================

def get_scoped_queryset(user, model_class, action='read'):
    """
    Apply data security policies to filter queryset.

    Task 2 Implementation:
        1. Get user's roles
        2. Find applicable data policies for model
        3. Apply policy conditions based on user's data scope
        4. Return filtered queryset

    Args:
        user: UserAccount instance
        model_class: Django model class
        action: 'read', 'create', 'update', 'delete'

    Returns:
        Filtered QuerySet based on user's data scope and policies

    Current Behavior (Task 1):
        Delegates to existing .scoped(user) manager if available,
        otherwise returns all records.
    """
    # Task 1 fallback: Use existing scoped manager
    if hasattr(model_class, 'objects') and hasattr(model_class.objects, 'scoped'):
        return model_class.objects.scoped(user)
    return model_class.objects.all()


def get_field_access(user, model_class, field_name, record=None):
    """
    Determine user's access level for a specific field.

    Task 2 Implementation:
        1. Find FieldSecurityPolicy for model+field
        2. Get user's roles
        3. Find highest access level granted
        4. Check self_only conditions
        5. Return access level

    Args:
        user: UserAccount instance
        model_class: Django model class
        field_name: Name of the field
        record: Optional model instance (for self_only checks)

    Returns:
        str: 'hidden', 'masked', 'readonly', or 'editable'

    Current Behavior (Task 1):
        Returns 'editable' for all fields (no field security).
    """
    # Task 1 fallback: Full access to all fields
    return 'editable'


def apply_field_security(user, serializer_class, instance=None):
    """
    Modify serializer fields based on field security policies.

    Task 2 Implementation:
        1. For each field in serializer
        2. Get field access level
        3. Remove hidden fields
        4. Mark readonly fields
        5. Apply masking to masked fields
        6. Return modified serializer class

    Args:
        user: UserAccount instance
        serializer_class: DRF Serializer class
        instance: Optional model instance

    Returns:
        Modified Serializer class with field security applied

    Current Behavior (Task 1):
        Returns original serializer unchanged.
    """
    # Task 1 fallback: No field security
    return serializer_class


def mask_field_value(value, mask_pattern):
    """
    Apply masking pattern to sensitive field value.

    Task 2 Implementation:
        Parse mask_pattern and apply to value.
        Example: '***-**-{last4}' for SSN

    Args:
        value: Original field value
        mask_pattern: Pattern string with placeholders

    Returns:
        Masked string value

    Current Behavior (Task 1):
        Returns original value unchanged.
    """
    # Task 1 fallback: No masking
    return value


def is_own_record(user, record):
    """
    Check if record belongs to the user (for self_only policies).

    Task 2 Implementation:
        Determine ownership based on model type:
        - Employee: record.user == user
        - Person: record.employee.user == user
        - Assignment: record.employee.user == user

    Args:
        user: UserAccount instance
        record: Model instance

    Returns:
        bool: True if record belongs to user

    Current Behavior (Task 1):
        Returns False (conservative default).
    """
    # Task 1 fallback: Conservative default
    if hasattr(record, 'user'):
        return record.user == user
    return False

