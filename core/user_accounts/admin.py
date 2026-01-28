from django.contrib import admin
from .models import UserAccount


@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    """
    Admin configuration for UserAccount model.

    Note: Job roles are now managed via UserJobRole M2M (see job_roles app).
    Users can have multiple roles with effective dates.
    """
    list_display = ['email', 'name', 'phone_number', 'get_roles_display']
    search_fields = ['email', 'name', 'phone_number']
    readonly_fields = ['last_login']
    
    fieldsets = (
        ('User Information', {
            'fields': ('email', 'name', 'phone_number')
        }),
        ('Authentication', {
            'fields': ('password', 'last_login')
        }),
    )

    def get_roles_display(self, obj):
        """Display user's active job roles"""
        from core.job_roles.services import get_user_active_roles
        roles = get_user_active_roles(obj)
        if roles:
            return ', '.join([role.name for role in roles[:3]])  # Show first 3 roles
        return '(No roles)'
    get_roles_display.short_description = 'Roles'

