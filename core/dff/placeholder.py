"""
Placeholder for Task 4: Descriptive Flexfields (DFF)

This module will implement Oracle-style Descriptive Flexfields for custom fields per entity.

Models to be implemented:
    - DFFContext: Which entities support custom fields (Employee, Department, etc.)
    - DFFStructure: A group of segments that apply based on context
    - DFFSegment: Individual custom field definition

Features (planned):
    - Context-sensitive fields: Different fields per country/department
    - Multiple field types: text, number, date, boolean, lookup, file
    - Validation rules: required, pattern, min/max values
    - Conditional visibility: show/hide based on other values
    - No schema changes: Uses JSONField for storage

Current Status: PLACEHOLDER - Not Implemented
Target: Task 4 Implementation

Integration Points from Task 1:
    - Department.extra_info JSONField
    - Position.extra_info JSONField
    - (Future) Employee.extra_info JSONField

Dependencies:
    - Task 3: LookupValue for segment_type='lookup'
"""


class DFFContext:
    """
    Task 4 Implementation: Defines which entities support custom fields.

    Fields (planned):
        - code: Unique identifier (e.g., 'EMPLOYEE', 'DEPARTMENT')
        - name: Display name
        - target_model: Django model path (e.g., 'employees.Employee')
        - target_field: JSON field name (default: 'extra_info')
        - context_field: Discriminator field path (e.g., 'country__code')
        - is_enabled: Enable/disable flag

    Example Usage:
        employee_context = DFFContext(
            code='EMPLOYEE',
            name='Employee Custom Fields',
            target_model='employees.Employee',
            context_field='business_group__code'
        )
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Task 4: DFFContext not implemented. "
            "This is a placeholder for future implementation."
        )


class DFFStructure:
    """
    Task 4 Implementation: A group of segments that apply based on context.

    Fields (planned):
        - dff_context: FK to DFFContext
        - code: Unique within context
        - name: Display name
        - context_value: Value that triggers this structure
        - priority: Order for matching (higher = first)
        - is_enabled: Enable/disable flag
        - is_default: Fallback structure

    Example Usage:
        egypt_structure = DFFStructure(
            dff_context=employee_context,
            code='EGYPT_EMP',
            name='Egypt Employee Fields',
            context_value='EGY'
        )
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Task 4: DFFStructure not implemented. "
            "This is a placeholder for future implementation."
        )


class DFFSegment:
    """
    Task 4 Implementation: Individual custom field definition.

    Fields (planned):
        - dff_structure: FK to DFFStructure
        - code: Field code (stored in JSON)
        - name: Display name
        - segment_type: text, number, date, boolean, lookup, etc.
        - lookup_type_code: For lookup fields, the LookupType code
        - display_sequence: Order in UI
        - is_required: Required field flag
        - is_readonly: Read-only field flag
        - default_value: Default value
        - validation_rules: JSONField with type-specific rules
        - visible_when: Condition for visibility
        - required_when: Condition for when required
        - is_enabled: Enable/disable flag

    Segment Types:
        - text: Free text input
        - number: Numeric value
        - date: Date picker
        - boolean: Yes/No toggle
        - lookup: Dropdown from lookup table
        - text_area: Multi-line text
        - email: Email format
        - phone: Phone format
        - url: URL format
        - file: File upload

    Example Usage:
        military_status = DFFSegment(
            dff_structure=egypt_structure,
            code='military_status',
            name='Military Status',
            segment_type='lookup',
            lookup_type_code='MILITARY_STATUS',
            is_required=True
        )
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Task 4: DFFSegment not implemented. "
            "This is a placeholder for future implementation."
        )


# =============================================================================
# STUB FUNCTIONS - Will be replaced with full implementation in Task 4
# =============================================================================

def get_dff_structure_for_instance(instance):
    """
    Determine which DFF structure applies to an instance.

    Task 4 Implementation:
        1. Find DFFContext for instance's model
        2. Get context value from instance (e.g., country code)
        3. Find matching DFFStructure
        4. Return structure or default

    Args:
        instance: Django model instance

    Returns:
        DFFStructure instance or None

    Current Behavior (Task 1):
        Returns None (no DFF).
    """
    # Task 1 fallback: No DFF yet
    return None


def get_dff_segments_for_instance(instance):
    """
    Get all DFF segments that apply to an instance.

    Task 4 Implementation:
        1. Get structure for instance
        2. Return enabled segments in order

    Args:
        instance: Django model instance

    Returns:
        List of DFFSegment instances

    Current Behavior (Task 1):
        Returns empty list.
    """
    # Task 1 fallback: No DFF yet
    return []


def validate_extra_info(instance, extra_info_data):
    """
    Validate extra_info data against DFF segment rules.

    Task 4 Implementation:
        1. Get segments for instance
        2. Validate each segment value
        3. Check required fields
        4. Check conditional rules

    Args:
        instance: Django model instance
        extra_info_data: Dict of field values

    Returns:
        Tuple (is_valid: bool, errors: list)

    Current Behavior (Task 1):
        Always returns (True, []).
    """
    # Task 1 fallback: No validation
    return True, []


def get_extra_info_schema(instance_or_model):
    """
    Get JSON schema for extra_info field based on DFF config.

    Task 4 Implementation:
        1. Get structure for instance/model
        2. Build JSON schema from segments
        3. Include validation rules

    Args:
        instance_or_model: Model instance or class

    Returns:
        Dict: JSON schema for the extra_info field

    Current Behavior (Task 1):
        Returns empty object schema.
    """
    # Task 1 fallback: Empty schema
    return {'type': 'object', 'properties': {}, 'required': []}


def get_extra_info_ui_config(instance):
    """
    Get UI configuration for rendering extra_info form.

    Task 4 Implementation:
        1. Get segments for instance
        2. Build UI config with labels, types, visibility

    Args:
        instance: Django model instance

    Returns:
        List of field configurations for UI rendering

    Current Behavior (Task 1):
        Returns empty list.
    """
    # Task 1 fallback: No UI config
    return []


def apply_dff_defaults(instance, extra_info_data):
    """
    Apply default values from DFF segments to extra_info data.

    Task 4 Implementation:
        1. Get segments for instance
        2. For each segment with default, apply if not set

    Args:
        instance: Django model instance
        extra_info_data: Dict of current values

    Returns:
        Dict with defaults applied

    Current Behavior (Task 1):
        Returns data unchanged.
    """
    # Task 1 fallback: No defaults
    return extra_info_data


# =============================================================================
# SEGMENT TYPES - Constants for reference
# =============================================================================

class SegmentTypes:
    """
    Constants for DFF segment types.
    Use these instead of hardcoding strings.
    """
    TEXT = 'text'
    NUMBER = 'number'
    DATE = 'date'
    BOOLEAN = 'boolean'
    LOOKUP = 'lookup'
    TEXT_AREA = 'text_area'
    EMAIL = 'email'
    PHONE = 'phone'
    URL = 'url'
    FILE = 'file'

    CHOICES = [
        (TEXT, 'Text'),
        (NUMBER, 'Number'),
        (DATE, 'Date'),
        (BOOLEAN, 'Yes/No'),
        (LOOKUP, 'Lookup (Dropdown)'),
        (TEXT_AREA, 'Text Area'),
        (EMAIL, 'Email'),
        (PHONE, 'Phone'),
        (URL, 'URL'),
        (FILE, 'File Upload'),
    ]
