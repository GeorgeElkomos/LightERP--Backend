# * hold off on using this file for now *
# from django.core.exceptions import PermissionDenied
# from HR.work_structures.models.security import UserDataScope
# from HR.work_structures.models import Department, BusinessGroup
#
# def validate_data_scope_on_create(user, business_group_id, department_id=None, parent_department_id=None):
#     """
#     Validate that the user has permission to create/update data in the given Business Group and optionally Department.
#
#     Args:
#         user: The user performing the action
#         business_group_id: Required - the Business Group being accessed
#         department_id: Optional - specific department being accessed/modified
#         parent_department_id: Optional - parent department (for creating child departments)
#
#     Raises:
#         PermissionDenied: If user lacks access to the specified scope
#
#     Scope Rules:
#         - Global scope (super_admin role users should have this): Full access
#         - BG-level scope: Access to entire Business Group (all departments)
#         - Department-level scope: Access only to specific department and its descendants
#     """
#     # Check for global scope (super_admin role users should have this)
#     if UserDataScope.objects.filter(user=user, is_global=True).exists():
#         return
#
#     # Get user's scopes for this Business Group
#     scopes = UserDataScope.objects.filter(user=user, business_group_id=business_group_id)
#
#     if not scopes.exists():
#         raise PermissionDenied("You do not have access to this Business Group")
#
#     # If no department-level validation needed, BG access is sufficient
#     if not department_id and not parent_department_id:
#         return
#
#     # Check if user has BG-level access (department=None means full BG access)
#     if scopes.filter(department__isnull=True).exists():
#         return  # BG-level access grants permission for all departments
#
#     # Department-level validation required
#     target_dept_id = department_id or parent_department_id
#
#     # Check if user has direct access to this department
#     if scopes.filter(department_id=target_dept_id).exists():
#         return
#
#     # Check if target department is a descendant of user's accessible departments
#     # (User can create/edit within their department's hierarchy)
#     accessible_dept_ids = scopes.filter(department__isnull=False).values_list('department_id', flat=True)
#
#     # Check if target is child of any accessible department (recursive check)
#     current_dept_id = target_dept_id
#     visited = set()  # Prevent infinite loops
#
#     while current_dept_id and current_dept_id not in visited:
#         if current_dept_id in accessible_dept_ids:
#             return  # Target is descendant of accessible department
#
#         visited.add(current_dept_id)
#         try:
#             dept = Department.objects.get(id=current_dept_id)
#             current_dept_id = dept.parent_id
#         except Department.DoesNotExist:
#             break
#
#     # No access found
#     raise PermissionDenied(
#         f"You do not have access to this department. Your scope is limited to specific departments within this Business Group."
#     )
#
# def validate_location_scope(user, business_group_id=None):
#     """
#     Validate that the user has permission to CRUD a location in the given Business Group.
#
#     Access Rules:
#     1. If business_group_id is provided: User must have access to that BG (or a dept in it).
#
#     Args:
#         user: The user performing the action
#         business_group_id: Business Group ID for the location
#
#     Raises:
#         PermissionDenied: If user lacks access to the specified scope
#     """
#     # Check for global scope (super_admin role users should have this)
#     if UserDataScope.objects.filter(user=user, is_global=True).exists():
#         return
#
#     if business_group_id:
#         # Re-use BG scope validation
#         return validate_data_scope_on_create(user, business_group_id)
#
#     raise PermissionDenied("Location must be linked to a Business Group")
