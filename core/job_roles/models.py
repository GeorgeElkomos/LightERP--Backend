"""
Job Roles and Permissions Models
Manages role-based access control with page and action-level permissions.
"""
from django.db import models
from django.core.exceptions import ValidationError

# Import from core.base for consistency
from core.base.models import (
    AuditMixin,
    VersionedMixin,
    StatusChoices)
from core.base.managers import VersionedManager


class JobRole(AuditMixin, models.Model):
    """
    Defines roles that users can be assigned to determine their privileges/permissions.

    Job Roles with hierarchy and inheritance support
    - parent_role_id: For role hierarchy
    - code: Unique code identifier
    - Audit fields: created_at, updated_at, created_by, updated_by (from AuditMixin)
    """

    code = models.CharField(max_length=50, blank=True, unique=True, db_index=True)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    
    # Child roles inherit all parent permissions (additive)
    parent_role = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_roles',
        help_text="Parent role for permission inheritance (child gets parent + own permissions)"
    )

    priority = models.PositiveIntegerField(
        default=0,
        help_text="Higher priority role wins in permission conflicts"
    )


    class Meta:
        db_table = 'job_roles'
        verbose_name = 'Job Role'
        verbose_name_plural = 'Job Roles'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['parent_role']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate role hierarchy to prevent circular references"""
        if self.parent_role:
            # Check for circular reference
            visited = set()
            current = self.parent_role
            while current:
                if current.pk == self.pk:
                    raise ValidationError(
                        {'parent_role': 'Circular reference detected in role hierarchy'}
                    )
                if current.pk in visited:
                    break  # Already checked this path
                visited.add(current.pk)
                current = current.parent_role


    def get_all_ancestor_roles(self):
        """
        Get all ancestor roles in the hierarchy (for permission inheritance).
        Returns list from immediate parent up to root.
        Used by permission services to aggregate inherited permissions.
        """
        ancestors = []
        current = self.parent_role
        visited = set()
        while current and current.pk not in visited:
            ancestors.append(current)
            visited.add(current.pk)
            current = current.parent_role
        return ancestors

    def delete(self, *args, **kwargs):
        """Prevent deletion if users are assigned to this role"""
        if self.user_job_roles.exists():
            raise ValidationError(
                f"Cannot delete job role '{self.name}' because users are currently assigned to it."
            )
        super().delete(*args, **kwargs)


class Page(AuditMixin, models.Model):
    """
    Page model representing functional areas/modules of the system.
    Pages define distinct areas that users can access based on their job role.

    Pages with hierarchy and module organization
    - parent_page: For module → sub-module organization (HR → Employee Mgmt → Personal Info)
    - module_code: Identifies owning module (hr, finance, procurement)
    - sort_order: For consistent UI ordering in menus
    """
    code = models.CharField(
        max_length=100,
        unique=True, 
        db_index=True,
        null=True,
        blank=True,
        help_text="Unique identifier for the page (e.g., 'hr_employee')"
    )
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Human-readable name shown in UI (e.g., 'HR - Employee Management')"
    )
    description = models.TextField(blank=True, null=True)
    
    # Page hierarchy for module organization
    # Example: 'HR Employee Personal' parent_page -> 'HR Employee' parent_page -> 'HR Module'
    parent_page = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_pages',
        help_text="Parent page for hierarchical organization"
    )

    # Module code for ownership tracking
    # Values: 'hr', 'finance', 'procurement', 'core', etc.
    module_code = models.CharField(
        max_length=50,
        db_index=True,
        blank=True,
        default='',
        help_text="Owning module code: hr, finance, procurement, core"
    )

    # Sort order for UI display
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Order for display in menus (lower = first)"
    )


    class Meta:
        db_table = 'pages'
        verbose_name = 'Page'
        verbose_name_plural = 'Pages'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['module_code']),
            models.Index(fields=['parent_page', 'sort_order']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        """Auto-generate code from name if not provided"""
        if not self.code:
            # Convert name to snake_case code
            self.code = self.name.lower().replace(' - ', '_').replace(' ', '_').replace('-', '_')
        super().save(*args, **kwargs)

    def clean(self):
        """Validate page hierarchy to prevent circular references"""
        if self.parent_page:
            # Check for circular reference
            visited = set()
            current = self.parent_page
            while current:
                if current.pk == self.pk:
                    raise ValidationError(
                        {'parent_page': 'Circular reference detected in page hierarchy'}
                    )
                if current.pk in visited:
                    break
                visited.add(current.pk)
                current = current.parent_page


    def get_all_ancestor_pages(self):
        """
        Get all ancestor pages in the hierarchy.
        Returns list from immediate parent up to root module.
        """
        ancestors = []
        current = self.parent_page
        visited = set()
        while current and current.pk not in visited:
            ancestors.append(current)
            visited.add(current.pk)
            current = current.parent_page
        return ancestors

    def get_all_descendant_pages(self):
        """
        Get all descendant pages (children, grandchildren, etc.).
        Used when inherit_to_children=True on JobRolePage.
        """
        descendants = []

        def collect_children(page):
            for child in page.child_pages.all():
                descendants.append(child)
                collect_children(child)

        collect_children(self)
        return descendants

    def delete(self, *args, **kwargs):
        """Prevent deletion if pages are linked to job roles or have children"""
        if self.job_roles.exists():
            raise ValidationError(
                f"Cannot delete page '{self.name}' because it is assigned to job roles."
            )
        if self.child_pages.exists():
            raise ValidationError(
                f"Cannot delete page '{self.name}' because it has child pages."
            )
        super().delete(*args, **kwargs)


class Action(AuditMixin, models.Model):
    """
    Generic action model representing operations that can be performed.
    Actions are reusable across multiple pages (e.g., 'view', 'create', 'edit', 'delete').
    """
    code = models.CharField(
        max_length=100,
        unique=True, 
        db_index=True,
        null=True,
        blank=True,
        help_text="Unique identifier for the action (e.g., 'view', 'create', 'edit', 'delete')"
    )
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Human-readable name shown in UI (e.g., 'View', 'Create', 'Edit', 'Delete')"
    )
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'actions'
        verbose_name = 'Action'
        verbose_name_plural = 'Actions'
        ordering = ['code']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate code from name if not provided"""
        if not self.code:
            self.code = self.name.lower().replace(' ', '_')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion if action is linked to pages"""
        if self.page_actions.exists():
            raise ValidationError(
                f"Cannot delete action '{self.name}' because it is linked to pages."
            )
        super().delete(*args, **kwargs)


class PageAction(AuditMixin, models.Model):
    """
    Junction table linking pages to available actions.
    Defines which actions are available for each page.
    Example: 'invoice_page' has actions: 'view', 'create', 'edit', 'delete'
    """
    page = models.ForeignKey(
        Page, 
        on_delete=models.CASCADE, 
        related_name='page_actions'
    )
    action = models.ForeignKey(
        Action, 
        on_delete=models.CASCADE, 
        related_name='page_actions'
    )
    
    class Meta:
        db_table = 'page_actions'
        verbose_name = 'Page Action'
        verbose_name_plural = 'Page Actions'
        unique_together = ('page', 'action')
        ordering = ['page__name', 'action__code']
        indexes = [
            models.Index(fields=['page', 'action']),
        ]
    
    def __str__(self):
        return f"{self.page.code} - {self.action.name}"

    def delete(self, *args, **kwargs):
        """Prevent deletion if page actions have user overrides"""
        if self.user_overrides.exists():
            raise ValidationError(
                f"Cannot delete page action '{self}' because it has user permission overrides."
            )
        super().delete(*args, **kwargs)


class JobRolePage(AuditMixin, models.Model):
    """
    Junction table linking job roles to their accessible pages.
    Defines which pages a job role can access.
    Users inherit page access from their job role.

    Job Role Page Access with inheritance and audit
    - inherit_to_children: If TRUE, access cascades to all descendant pages
    - Audit fields from AuditMixin: created_by, updated_by, created_at, updated_at
    """
    job_role = models.ForeignKey(
        JobRole,
        on_delete=models.CASCADE,
        related_name='job_role_pages'
    )
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name='job_roles'
    )

    # Control page hierarchy inheritance
    # TRUE: Access cascades to ALL descendant pages at any depth
    # FALSE: Only this specific page is granted
    # Example with TRUE: Granting "HR Module" → grants Employee Mgmt, Payroll, all children
    inherit_to_children = models.BooleanField(
        default=True,
        help_text="If TRUE, access cascades to all descendant pages"
    )


    class Meta:
        db_table = 'job_role_pages'
        verbose_name = 'Job Role Page'
        verbose_name_plural = 'Job Role Pages'
        unique_together = ('job_role', 'page')
        ordering = ['job_role__name', 'page__sort_order', 'page__name']
        indexes = [
            models.Index(fields=['job_role', 'page']),
            models.Index(fields=['job_role', 'inherit_to_children']),
        ]

    def __str__(self):
        suffix = " (+children)" if self.inherit_to_children else ""
        return f"{self.job_role.name} - {self.page.code}{suffix}"



class UserJobRole(VersionedMixin, AuditMixin, models.Model):
    """
    Junction table for many-to-many User ↔ JobRole relationship.
    Allows users to have MULTIPLE job roles with effective dates (versioned).

    User-Job Role Assignment (Many-to-Many with versioning)
    - A user's permissions = union of all currently active assigned roles
    - effective_start_date, effective_end_date: From VersionedMixin
    - status: Computed property from VersionedMixin (based on dates)
    - Audit fields from AuditMixin: created_by, updated_by, created_at, updated_at

    Example: Ahmed is both "Accountant" and "Project Coordinator"
    - Accountant role grants: Journal Entries, Financial Reports
    - Project Coordinator grants: Project Dashboard, Task Management
    - Ahmed can access all 4 pages (union of both roles)

    Example versioning: Temporary "Acting Manager" role from Jan 1 to Mar 31
    """
    user = models.ForeignKey(
        'user_accounts.UserAccount',
        on_delete=models.CASCADE,
        related_name='user_job_roles'
    )
    job_role = models.ForeignKey(
        JobRole,
        on_delete=models.CASCADE,
        related_name='user_job_roles'
    )

    # Manager with versioning support
    objects = VersionedManager()

    class Meta:
        db_table = 'user_job_roles'
        verbose_name = 'User Job Role'
        verbose_name_plural = 'User Job Roles'
        ordering = ['-effective_start_date', 'job_role__name']
        indexes = [
            models.Index(fields=['user', 'effective_start_date']),
            models.Index(fields=['user', 'job_role', 'effective_start_date']),
            models.Index(fields=['effective_start_date', 'effective_end_date']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.job_role.name} ({self.effective_start_date} to {self.effective_end_date or 'present'})"

    def get_version_group_field(self):
        """
        Group versions by user+job_role combination.
        Returns a composite key that uniquely identifies the versioned entity.
        VersionedMixin will automatically check for overlapping date ranges within this group.
        """
        return f"user_{self.user_id}_jobrole_{self.job_role_id}"

    def is_currently_effective(self):
        """
        Check if this role assignment is currently in effect.
        Considers effective dates.

        Returns:
            bool: True if assignment is currently effective
        """
        if self.status != StatusChoices.ACTIVE:
            return False

        return True


class UserPermissionOverride(VersionedMixin, AuditMixin, models.Model):
    """
    User-specific permission overrides for fine-grained control.
    Supports both GRANTS (add permissions) and DENIALS (remove permissions).

    User Permission Overrides (Versioned)
    - permission_type: 'deny' removes permission, 'grant' adds permission
    - effective_start_date, effective_end_date: From VersionedMixin for temporary overrides
    - status: Computed property from VersionedMixin (based on dates)
    - Audit fields from AuditMixin: created_by, updated_by, created_at, updated_at

    Permission Logic Priority (highest to lowest):
    1. Explicit denial (UserPermissionOverride with type='deny')
    2. Explicit grant (UserPermissionOverride with type='grant')
    3. Job role grants (via UserJobRole → JobRole → JobRolePage)
    4. Default: No access

    Example - Denial:
    Ahmed has 'Accountant' role which grants 'invoice_page' with all actions.
    A denial override removes 'delete' permission specifically for Ahmed.

    Example - Grant:
    Sara needs temporary 'approve' action on 'purchase_orders' beyond her role.
    A grant override with effective dates provides this temporarily.
    """
    PERMISSION_TYPES = [
        ('deny', 'Deny'),
        ('grant', 'Grant'),
    ]

    user = models.ForeignKey(
        'user_accounts.UserAccount',
        on_delete=models.CASCADE,
        related_name='permission_overrides'
    )
    page_action = models.ForeignKey(
        PageAction,
        on_delete=models.CASCADE,
        related_name='user_overrides'
    )

    # Permission type
    # 'deny' = removes this action from user even if role grants it
    # 'grant' = adds this action for user even if role doesn't grant it
    permission_type = models.CharField(
        max_length=10,
        choices=PERMISSION_TYPES,
        default='deny',
        db_index=True,
        help_text="'deny' removes permission, 'grant' adds permission"
    )

    # Reason for the override - audit/compliance
    reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for granting/denying this permission"
    )

    # Manager with versioning support
    objects = VersionedManager()

    class Meta:
        db_table = 'user_permission_overrides'
        verbose_name = 'User Permission Override'
        verbose_name_plural = 'User Permission Overrides'
        ordering = ['-effective_start_date']
        indexes = [
            models.Index(fields=['user', 'page_action', 'permission_type']),
            models.Index(fields=['user', 'permission_type', 'effective_start_date']),
            models.Index(fields=['effective_start_date', 'effective_end_date']),
        ]

    def __str__(self):
        action = "DENIED" if self.permission_type == 'deny' else "GRANTED"
        return f"{self.user.email} - {action} - {self.page_action} ({self.effective_start_date} to {self.effective_end_date or 'present'})"

    def get_version_group_field(self):
        """
        Group versions by user+page_action+permission_type combination.
        Returns a composite key that uniquely identifies the versioned entity.
        VersionedMixin will automatically check for overlapping date ranges within this group.
        """
        return f"user_{self.user_id}_pageaction_{self.page_action_id}_type_{self.permission_type}"

    def is_currently_effective(self):
        """
        Check if this override is currently in effect based on dates.

        Returns:
            bool: True if override is currently effective
        """
        return self.status == StatusChoices.ACTIVE
