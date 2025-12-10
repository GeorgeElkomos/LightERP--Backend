from django.contrib import admin
from .models import CustomUser, UserType


@admin.register(UserType)
class UserTypeAdmin(admin.ModelAdmin):
    """Admin configuration for UserType model"""
    list_display = ['type_name', 'description']
    search_fields = ['type_name']


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    """Admin configuration for CustomUser model"""
    list_display = ['email', 'name', 'phone_number', 'user_type']
    list_filter = ['user_type']
    search_fields = ['email', 'name', 'phone_number']
    readonly_fields = ['last_login']
    
    fieldsets = (
        ('User Information', {
            'fields': ('email', 'name', 'phone_number')
        }),
        ('Type & Permissions', {
            'fields': ('user_type',)
        }),
        ('Authentication', {
            'fields': ('password', 'last_login')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly for super admin users"""
        readonly = list(self.readonly_fields)
        if obj and obj.is_super_admin():
            readonly.extend(['user_type', 'email'])
        return readonly
