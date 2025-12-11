"""
Job Roles and Permissions Models
Manages role-based access control with page and action-level permissions.
"""
from django.db import models
from django.core.exceptions import ValidationError


class JobRole(models.Model):
    """
    Job role model representing positions in the organization.
    Defines roles that users can be assigned to determine their page access.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'job_roles'
        verbose_name = 'Job Role'
        verbose_name_plural = 'Job Roles'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion if job role is assigned to users.
        Similar to protection pattern used in core.user_accounts models.
        """
        if self.users.exists():
            raise ValidationError(
                f"Cannot delete job role '{self.name}' because it is assigned to "
                f"{self.users.count()} user(s)"
            )
        return super().delete(*args, **kwargs)


class Page(models.Model):
    """
    Page model representing functional areas/modules of the system.
    Pages define distinct areas that users can access based on their job role.
    """
    name = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Unique identifier for the page (e.g., 'invoice_management')"
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-readable name shown in UI"
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pages'
        verbose_name = 'Page'
        verbose_name_plural = 'Pages'
        ordering = ['display_name']
    
    def __str__(self):
        return f"{self.display_name} ({self.name})"
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion if page is linked to job roles.
        Maintains referential integrity at the application level.
        """
        if self.job_roles.exists():
            raise ValidationError(
                f"Cannot delete page '{self.name}' because it is linked to "
                f"{self.job_roles.count()} job role(s)"
            )
        return super().delete(*args, **kwargs)


class Action(models.Model):
    """
    Generic action model representing operations that can be performed.
    Actions are reusable across multiple pages (e.g., 'view', 'create', 'edit', 'delete').
    This follows DRY principles by defining actions once and linking them to pages.
    """
    name = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Unique identifier for the action (e.g., 'view', 'create', 'edit', 'delete')"
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-readable name shown in UI"
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'actions'
        verbose_name = 'Action'
        verbose_name_plural = 'Actions'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.display_name} ({self.name})"
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion if action is linked to pages.
        Ensures no orphaned page-action relationships.
        """
        if self.page_actions.exists():
            raise ValidationError(
                f"Cannot delete action '{self.name}' because it is linked to "
                f"{self.page_actions.count()} page(s)"
            )
        return super().delete(*args, **kwargs)


class PageAction(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'page_actions'
        verbose_name = 'Page Action'
        verbose_name_plural = 'Page Actions'
        unique_together = ('page', 'action')
        ordering = ['page__display_name', 'action__name']
        indexes = [
            models.Index(fields=['page', 'action']),
        ]
    
    def __str__(self):
        return f"{self.page.name} - {self.action.display_name}"
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion if page action has user denials.
        Ensures permission integrity.
        """
        if self.user_denials.exists():
            raise ValidationError(
                f"Cannot delete page action '{self.page.name} - {self.action.name}' "
                f"because it has {self.user_denials.count()} user denial(s)"
            )
        return super().delete(*args, **kwargs)


class JobRolePage(models.Model):
    """
    Junction table linking job roles to their accessible pages.
    Defines which pages a job role can access.
    Users inherit page access from their job role.
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
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'job_role_pages'
        verbose_name = 'Job Role Page'
        verbose_name_plural = 'Job Role Pages'
        unique_together = ('job_role', 'page')
        ordering = ['job_role__name', 'page__display_name']
        indexes = [
            models.Index(fields=['job_role', 'page']),
        ]
    
    def __str__(self):
        return f"{self.job_role.name} - {self.page.name}"


class UserActionDenial(models.Model):
    """
    User-specific action denials for fine-grained permission control.
    
    Permission Logic:
    1. Job role grants access to a page
    2. By default, user can perform all actions on that page
    3. UserActionDenial explicitly removes specific actions for specific users
    
    Example: User has 'Accountant' role which grants 'invoice_page' access.
    By default they can view/create/edit/delete. But we can add a UserActionDenial
    to remove 'delete' permission specifically for that user.
    """
    user = models.ForeignKey(
        'core.user_accounts.CustomUser', 
        on_delete=models.CASCADE, 
        related_name='action_denials'
    )
    page_action = models.ForeignKey(
        PageAction, 
        on_delete=models.CASCADE, 
        related_name='user_denials'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_action_denials'
        verbose_name = 'User Action Denial'
        verbose_name_plural = 'User Action Denials'
        unique_together = ('user', 'page_action')
        ordering = ['user__email', 'page_action__page__display_name']
        indexes = [
            models.Index(fields=['user', 'page_action']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - DENIED - {self.page_action}"
