"""
HR Managers - Hierarchical Data Scope Security Implementation

Extends core.base managers with HR-specific data scoping logic.

Implements hierarchical User Data Scope filtering for all HR models:
- Global scope: access to everything
- Business Group scope: access to all departments/positions in BG
- Department scope: access only to specific departments (most restrictive)

Scopes are additive (OR logic) - multiple scopes grant broader access.

Usage:
    from HR.work_structures.managers import VersionedScopedManager, SoftDeleteScopedManager

    class Department(VersionedMixin, models.Model):
        objects = VersionedScopedManager()

    class Location(SoftDeleteMixin, models.Model):
        objects = SoftDeleteScopedManager()

    # In views or services, always use .scoped(user) to filter by data scope
    departments = Department.objects.scoped(request.user).active_on(date.today())
    locations = Location.objects.scoped(request.user).active()
"""
from django.db import models
from django.db.models import Q

# Import base managers from core
from core.base.managers import (
    VersionedQuerySet,
    SoftDeleteQuerySet,
    VersionedManager,
    SoftDeleteManager,
)


class ScopedQuerySetMixin:
    """
    Mixin implementing hierarchical HR data scoping logic.
    
    Can be mixed into any QuerySet (Versioned, SoftDelete, or Base).
    
    Implements data scope filtering based on user's assigned Business Groups and Departments.
    Filters cascade through relationships (e.g., Position → Department → BG).
    Supports three scope levels: Global > BG > Department (most restrictive).
    """
    
    def scoped(self, user):
        """
        Filter QuerySet by user's hierarchical data scope.
        
        Priority:
        1. Global scope (is_global=True) → all records (admin role users should have this)
        2. Otherwise combine BG and Department scopes with OR logic

        Key Rule: If ANY scope has is_global=True, all other scopes are ignored.
        
        Multiple non-global scopes combine with OR logic:
        - BG1 (full) + BG2→Dept3 = all of BG1 + only Dept3 from BG2
        """
        from HR.work_structures.models.security import UserDataScope
        
        # Check for global scope - if found, grant full access and ignore all other scopes
        if UserDataScope.objects.filter(user=user, is_global=True).exists():
            return self.all()
        
        # Only consider non-global scopes (is_global=False or NULL)
        scopes = UserDataScope.objects.filter(
            user=user
        ).filter(
            Q(is_global=False) | Q(is_global__isnull=True)
        )
        
        # No scope = no access
        if not scopes.exists():
            return self.none()
        
        model_name = self.model.__name__
        
        # Separate department-level and BG-level scopes
        dept_scopes = scopes.filter(department__isnull=False)
        bg_scopes = scopes.filter(department__isnull=True, business_group__isnull=False)
        
        # Build filters based on model type
        if model_name == 'BusinessGroup':
            # Can only see BGs they have scope for
            allowed_bg_ids = scopes.values_list('business_group_id', flat=True).distinct()
            return self.filter(id__in=allowed_bg_ids)
        
        elif model_name == 'Department':
            # Department visibility restricted by Data Scope
            filters = Q()
            
            # Specific departments (most restrictive) + all their descendants
            if dept_scopes.exists():
                dept_ids = list(dept_scopes.values_list('department_id', flat=True))
                # Include the departments themselves
                filters |= Q(id__in=dept_ids)
                
                # Recursively get all descendants (handles N-level hierarchies)
                all_descendant_ids = self._get_recursive_descendants(dept_ids)
                if all_descendant_ids:
                    filters |= Q(id__in=all_descendant_ids)
            
            # All departments in allowed BGs
            if bg_scopes.exists():
                bg_ids = bg_scopes.values_list('business_group_id', flat=True)
                filters |= Q(business_group_id__in=bg_ids)
            
            return self.filter(filters) if filters else self.none()
        
        elif model_name == 'Position':
            # Position visibility restricted by Data Scope
            filters = Q()
            
            # Positions in specific departments + their descendants
            if dept_scopes.exists():
                dept_ids = list(dept_scopes.values_list('department_id', flat=True))
                
                # Include all descendants of accessible departments
                all_descendant_ids = self._get_recursive_descendants(dept_ids)
                all_dept_ids = dept_ids + list(all_descendant_ids)
                
                filters |= Q(department_id__in=all_dept_ids)
            
            # Positions in all departments of allowed BGs
            if bg_scopes.exists():
                bg_ids = bg_scopes.values_list('business_group_id', flat=True)
                filters |= Q(department__business_group_id__in=bg_ids)
            
            return self.filter(filters) if filters else self.none()
        
        elif model_name == 'Location':
            # Location access restricted by Data Scope
            filters = Q()
            
            # Get the accessible business groups for this user
            accessible_bg_ids = set()
            
            # From department scopes - get their business groups
            if dept_scopes.exists():
                accessible_bg_ids.update(
                    dept_scopes.values_list('business_group_id', flat=True).distinct()
                )
            
            # From BG scopes - directly accessible BGs
            if bg_scopes.exists():
                accessible_bg_ids.update(
                    bg_scopes.values_list('business_group_id', flat=True)
                )
            
            if accessible_bg_ids:
                # 1. Locations in accessible BGs
                filters |= Q(business_group_id__in=accessible_bg_ids)
                
                # 2. Locations used by specific departments if user has department-level scope
                if dept_scopes.exists():
                    dept_ids = list(dept_scopes.values_list('department_id', flat=True))
                    # Include all descendants of accessible departments
                    all_descendant_ids = self._get_recursive_descendants(dept_ids)
                    all_dept_ids = dept_ids + list(all_descendant_ids)
                    # Locations used by these departments
                    filters |= Q(departments__id__in=all_dept_ids)
            
            return self.filter(filters).distinct() if filters else self.none()
        
        elif model_name == 'Grade':
            # Grades are BG-level, so user with dept scope can see grades for that dept's BG
            filters = Q()
            
            if dept_scopes.exists():
                bg_ids = dept_scopes.values_list('business_group_id', flat=True).distinct()
                filters |= Q(business_group_id__in=bg_ids)
            
            if bg_scopes.exists():
                bg_ids = bg_scopes.values_list('business_group_id', flat=True)
                filters |= Q(business_group_id__in=bg_ids)
            
            return self.filter(filters).distinct() if filters else self.none()
        
        elif model_name == 'DepartmentManager':
            # Department Manager visibility follows department scope rules
            filters = Q()
            
            if dept_scopes.exists():
                dept_ids = dept_scopes.values_list('department_id', flat=True)
                filters |= Q(department_id__in=dept_ids)
            
            if bg_scopes.exists():
                bg_ids = bg_scopes.values_list('business_group_id', flat=True)
                filters |= Q(department__business_group_id__in=bg_ids)
            
            return self.filter(filters) if filters else self.none()
        
        # Default: return all (for models without specific scoping rules)
        return self.all()
    
    def _get_recursive_descendants(self, parent_ids):
        """
        Recursively fetch all descendant department IDs for given parent IDs.
        Handles N-level hierarchies.
        """
        # Ensure we are querying Department model for hierarchy
        from HR.work_structures.models.department import Department
        
        all_descendants = set()
        queue = list(parent_ids)
        visited = set(parent_ids)
        
        while queue:
            current_id = queue.pop(0)
            children = Department.objects.filter(parent_id=current_id).values_list('id', flat=True)
            
            for child_id in children:
                if child_id not in visited:
                    all_descendants.add(child_id)
                    visited.add(child_id)
                    queue.append(child_id)
        
        return all_descendants


class VersionedScopedQuerySet(VersionedQuerySet, ScopedQuerySetMixin):
    """
    VersionedQuerySet with HR data scoping.
    """
    pass


class SoftDeleteScopedQuerySet(SoftDeleteQuerySet, ScopedQuerySetMixin):
    """
    SoftDeleteQuerySet with HR data scoping.
    """
    pass


class VersionedScopedManager(VersionedManager.from_queryset(VersionedScopedQuerySet)):
    """
    Manager for VersionedMixin models in HR.
    Provides temporal features + .scoped(user).
    """
    pass


class SoftDeleteScopedManager(SoftDeleteManager.from_queryset(SoftDeleteScopedQuerySet)):
    """
    Manager for SoftDeleteMixin models in HR.
    Provides soft delete features + .scoped(user).
    """
    pass

