"""
Serializers for Job Roles and Permissions models.
Handles serialization/deserialization for API endpoints.
"""
from rest_framework import serializers
from django.utils import timezone
from core.base.models import StatusChoices
from .models import (
    JobRole,
    Page,
    Action,
    PageAction,
    JobRolePage,
    UserJobRole,
    UserPermissionOverride,
)


# ============================================================================
# READ-ONLY SERIALIZERS FOR HARD-CODED DATA
# ============================================================================

class ActionSerializer(serializers.ModelSerializer):
    """Read-only serializer for Action model."""

    class Meta:
        model = Action
        fields = ['id', 'code', 'name', 'description']
        read_only_fields = ['id', 'code', 'name', 'description']


class PageSerializer(serializers.ModelSerializer):
    """Read-only serializer for Page model."""

    class Meta:
        model = Page
        fields = ['id', 'code', 'name', 'description']
        read_only_fields = ['id', 'code', 'name', 'description']


class PageActionSerializer(serializers.ModelSerializer):
    """Read-only serializer for PageAction model."""

    page = PageSerializer(read_only=True)
    action = ActionSerializer(read_only=True)

    class Meta:
        model = PageAction
        fields = ['id', 'page', 'action']
        read_only_fields = ['id', 'page', 'action']


# ============================================================================
# JOB ROLE SERIALIZERS
# ============================================================================

class JobRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for JobRole model with hierarchy and audit support.
    """
    parent_role_name = serializers.CharField(source='parent_role.name', read_only=True, allow_null=True)
    child_roles_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    page_count = serializers.IntegerField(source='job_role_pages.count', read_only=True)

    class Meta:
        model = JobRole
        fields = [
            'id', 'code', 'name', 'description',
            'parent_role', 'parent_role_name', 'priority', 'created_at', 'updated_at',
            'child_roles_count', 'user_count', 'page_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'child_roles_count', 'user_count']

    def get_child_roles_count(self, obj):
        """Count of direct child roles"""
        return obj.child_roles.count()

    def get_user_count(self, obj):
        """Count of users assigned to this role"""
        from datetime import date
        return obj.user_job_roles.active_on(date.today()).count() if hasattr(obj, 'user_job_roles') else 0


class JobRoleCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating job roles.
    """
    class Meta:
        model = JobRole
        fields = ['id', 'code', 'name', 'description', 'parent_role', 'priority']
        read_only_fields = ['id']


class JobRolePageSerializer(serializers.ModelSerializer):
    """
    Serializer for JobRolePage - assigning pages to job roles.
    """
    page = PageSerializer(read_only=True)
    page_id = serializers.PrimaryKeyRelatedField(
        queryset=Page.objects.all(),
        source='page',
        write_only=True
    )
    job_role_name = serializers.CharField(source='job_role.name', read_only=True)

    class Meta:
        model = JobRolePage
        fields = ['id', 'job_role', 'job_role_name', 'page', 'page_id', 'inherit_to_children']
        read_only_fields = ['id', 'created_at']


# ============================================================================
# USER JOB ROLE ASSIGNMENT SERIALIZERS
# ============================================================================

class UserJobRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for UserJobRole - user to role assignments.
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    job_role_name = serializers.CharField(source='job_role.name', read_only=True)
    job_role_code = serializers.CharField(source='job_role.code', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)
    is_currently_effective = serializers.SerializerMethodField()

    class Meta:
        model = UserJobRole
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'job_role', 'job_role_name', 'job_role_code',
            'effective_start_date', 'effective_end_date',
            'status', 'created_by', 'created_by_email',
            'created_at', 'updated_at', 'is_currently_effective'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at', 'is_currently_effective']

    def get_is_currently_effective(self, obj):
        """Check if this role assignment is currently in effect"""
        return obj.is_currently_effective()

    def validate(self, data):
        """Validate role assignment constraints"""
        # Validate effective dates
        start_date = data.get('effective_start_date')
        end_date = data.get('effective_end_date')
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {'effective_end_date': 'End date must be after start date'}
            )

        return data


class UserJobRoleCreateSerializer(serializers.ModelSerializer):
    """
    Create serializer for UserJobRole assignments.
    """
    class Meta:
        model = UserJobRole
        fields = ['user', 'job_role', 'effective_start_date', 'effective_end_date']

    def validate(self, data):
        """Validate before creation"""
        # Set default start date if not provided
        if not data.get('effective_start_date'):
            data['effective_start_date'] = timezone.now().date()

        # Validate effective dates
        start_date = data.get('effective_start_date')
        end_date = data.get('effective_end_date')
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {'effective_end_date': 'End date must be after start date'}
            )

        return data


# ============================================================================
# USER PERMISSION OVERRIDE SERIALIZERS
# ============================================================================

class UserPermissionOverrideSerializer(serializers.ModelSerializer):
    """
    Serializer for UserPermissionOverride - grants AND denials.
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    page_name = serializers.CharField(source='page_action.page.name', read_only=True)
    action_name = serializers.CharField(source='page_action.action.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)
    is_currently_effective = serializers.SerializerMethodField()

    class Meta:
        model = UserPermissionOverride
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'page_action', 'page_name', 'action_name',
            'permission_type', 'reason',
            'effective_start_date', 'effective_end_date',
            'status', 'created_by', 'created_by_email', 'created_at',
            'is_currently_effective'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'is_currently_effective']

    def get_is_currently_effective(self, obj):
        """Check if this override is currently in effect"""
        return obj.is_currently_effective()


class UserPermissionOverrideCreateSerializer(serializers.ModelSerializer):
    """
    Create serializer for permission overrides.
    """
    class Meta:
        model = UserPermissionOverride
        fields = ['user', 'page_action', 'permission_type', 'reason', 'effective_start_date', 'effective_end_date']

    def validate(self, data):
        """Validate override creation"""
        user = data.get('user')
        page_action = data.get('page_action')
        permission_type = data.get('permission_type')

        # Validate effective dates
        start_date = data.get('effective_start_date')
        end_date = data.get('effective_end_date')

        # Set default start date if not provided
        if not start_date:
            data['effective_start_date'] = timezone.now().date()
            start_date = data['effective_start_date']

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {'effective_end_date': 'End date must be after start date'}
            )

        # Validation: user must have the page assigned via their job role for denials
        if permission_type == 'deny':
            from .services import get_user_active_roles
            has_role_access = JobRolePage.objects.filter(
                job_role__in=get_user_active_roles(user),
                page=page_action.page
            ).exists()
            if not has_role_access:
                raise serializers.ValidationError(
                    f"User {user.email} does not have access to page '{page_action.page.name}' via any job role, so cannot create a denial."
                )

        return data


# ============================================================================
# UTILITY SERIALIZERS
# ============================================================================

class UserRolePermissionsSerializer(serializers.Serializer):
    """
    Serializer for user permissions endpoint - shows all permissions for a user.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    active_roles = serializers.ListField(child=serializers.CharField(), read_only=True)
    direct_permissions = serializers.DictField(read_only=True)
    effective_permissions = serializers.DictField(read_only=True)
    permission_overrides = serializers.ListField(read_only=True)

    def to_representation(self, instance):
        """Format the permissions data for the API response"""
        return {
            'user_email': instance['user'].email,
            'user_name': instance['user'].name,
            'active_roles': [role.name for role in instance['active_roles']],
            'direct_permissions': instance['direct_permissions'],
            'effective_permissions': instance['effective_permissions'],
            'permission_overrides': instance['permission_overrides']
        }