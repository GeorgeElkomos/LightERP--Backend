"""
HR Managers - Hierarchical Data Scope Security Implementation

Implements hierarchical User Data Scope filtering for all HR models:
- Global scope: access to everything
- Business Group scope: access to all departments/positions in BG
- Department scope: access only to specific departments (most restrictive)

Scopes are additive (OR logic) - multiple scopes grant broader access.

Usage:
    # In views or services, always use .scoped(user) to filter by data scope
    departments = Department.objects.scoped(request.user).active()
    positions = Position.objects.scoped(request.user).active()
"""
from django.db import models
from django.db.models import Q


class ScopedQuerySet(models.QuerySet):
    """
    QuerySet with hierarchical scoping logic for chainability.
    
    Implements data scope filtering based on user's assigned Business Groups and Departments.
    Filters cascade through relationships (e.g., Position → Department → BG).
    Supports three scope levels: Global > BG > Department (most restrictive).
    """
    
    def filter_by_search_params(self, query_params):
        """
        Apply standard code/name/search filters from query parameters.
        
        Handles three common filter patterns:
        - code: Exact match (case-insensitive)
        - name: Contains match (case-insensitive)
        - search: Contains match across both code and name
        
        Args:
            query_params: QueryDict or dict containing query parameters
            
        Returns:
            Filtered QuerySet
            
        Example:
            # In views
            enterprises = Enterprise.objects.scoped(user).active()
            enterprises = enterprises.filter_by_search_params(request.query_params)
        """
        queryset = self
        
        # Filter by code (exact match)
        code = query_params.get('code')
        if code:
            queryset = queryset.filter(code__iexact=code)
        
        # Filter by name (contains match)
        name = query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        # Search across code and name
        search = query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
        return queryset
    
    def scoped(self, user):
        """
        Filter QuerySet by user's hierarchical data scope.
        
        Priority:
        1. Superuser → all records
        2. Global scope (is_global=True) → all records (ignores all other scopes)
        3. Otherwise combine BG and Department scopes with OR logic
        
        Key Rule: If ANY scope has is_global=True, all other scopes are ignored.
        
        Multiple non-global scopes combine with OR logic:
        - BG1 (full) + BG2→Dept3 = all of BG1 + only Dept3 from BG2
        """
        from HR.work_structures.models.security import UserDataScope
        
        # Superusers bypass scope filtering
        if user.is_super_admin():
            return self.all()
        
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
        if model_name == 'Enterprise':
            # Can only see Enterprises that contain their accessible Business Groups
            filters = Q()
            if dept_scopes.exists():
                # Get BG IDs from department scopes
                bg_ids = dept_scopes.values_list('business_group_id', flat=True).distinct()
                filters |= Q(business_groups__id__in=bg_ids)
            if bg_scopes.exists():
                bg_ids = bg_scopes.values_list('business_group_id', flat=True)
                filters |= Q(business_groups__id__in=bg_ids)
            return self.filter(filters).distinct() if filters else self.none()
        
        elif model_name == 'BusinessGroup':
            # Can only see BGs they have scope for
            allowed_bg_ids = scopes.values_list('business_group_id', flat=True).distinct()
            return self.filter(id__in=allowed_bg_ids)
        
        elif model_name == 'Department':
            # Department visibility restricted by Data Scope
            # Includes child departments of accessible departments (recursive for any depth)
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
            # Users can only see:
            # 1. Locations belonging to their accessible BGs
            # 2. Locations used by their accessible departments
            # 3. Enterprise-level locations (only if they have access to that enterprise's BGs)
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
                # 1. BG-level locations in accessible BGs
                filters |= Q(business_group_id__in=accessible_bg_ids)
                
                # 2. Enterprise-level locations for enterprises that contain accessible BGs
                # Lazy import to avoid circular dependency
                from HR.work_structures.models import BusinessGroup
                accessible_enterprise_ids = BusinessGroup.objects.filter(
                    id__in=accessible_bg_ids
                ).values_list('enterprise_id', flat=True).distinct()
                
                filters |= Q(
                    enterprise_id__in=accessible_enterprise_ids,
                    business_group_id__isnull=True
                )
                
                # 3. Locations used by specific departments if user has department-level scope
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
                # Get BG IDs from the departments user has access to
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
        
        # Default: return all (for models without BG relationship)
        return self.all()
    
    def _get_recursive_descendants(self, parent_ids):
        """
        Recursively fetch all descendant department IDs for given parent IDs.
        Handles N-level hierarchies (grandchildren, great-grandchildren, etc.).
        
        Args:
            parent_ids: List of parent department IDs
            
        Returns:
            Set of all descendant department IDs
        """
        if self.model.__name__ != 'Department':
            return set()
        
        all_descendants = set()
        queue = list(parent_ids)
        visited = set(parent_ids)  # Prevent infinite loops in case of circular refs
        
        while queue:
            current_id = queue.pop(0)
            # Get direct children
            children = self.filter(parent_id=current_id).values_list('id', flat=True)
            
            for child_id in children:
                if child_id not in visited:
                    all_descendants.add(child_id)
                    visited.add(child_id)
                    queue.append(child_id)  # Add to queue to find its children
        
        return all_descendants


class DateTrackedQuerySet(ScopedQuerySet):
    """
    QuerySet for date-tracked records.
    
    Provides filtering methods for records based on effective dates.
    """
    
    def active(self):
        """
        Filter to currently active records only.
        
        Returns records where:
        - effective_start_date <= today
        - effective_end_date is NULL OR effective_end_date >= today
        
        This is the database-level equivalent of the computed status property.
        Use this for database queries instead of filtering by .status property.
        
        Example:
            active_departments = Department.objects.active()
            active_positions = Position.objects.scoped(user).active()
        """
        from django.utils import timezone
        today = timezone.now().date()
        return self.filter(
            Q(effective_start_date__lte=today) &
            (Q(effective_end_date__gte=today) | Q(effective_end_date__isnull=True))
        )
    
    def active_on(self, date):
        """
        Filter to records active on a specific date.
        
        Args:
            date: The date to check activity against
            
        Returns records where:
        - effective_start_date <= date
        - effective_end_date is NULL OR effective_end_date >= date
        """
        from django.db.models import Q
        return self.filter(
            Q(effective_start_date__lte=date) &
            (Q(effective_end_date__gte=date) | Q(effective_end_date__isnull=True))
        )


class DateTrackedModelManager(models.Manager.from_queryset(DateTrackedQuerySet)):
    """
    Manager for date-tracked records with data scope filtering.
    
    Use for: Department, Position, Grade, GradeRate, DepartmentManager
    Provides: .scoped(user), .active(), .active_on(date)
    """
    pass


class ScopedModelManager(models.Manager.from_queryset(ScopedQuerySet)):
    """
    Manager for non-date-tracked records with data scope filtering.
    
    Use for: BusinessGroup, Location, Enterprise
    Provides: .scoped(user)
    """
    pass
