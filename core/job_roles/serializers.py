"""
Serializers for Job Roles and Permissions models.
Handles serialization/deserialization for API endpoints.
"""
from rest_framework import serializers
from .models import (
    JobRole,
    Page,
    Action,
    PageAction,
    JobRolePage,
    UserActionDenial,
)
from core.user_accounts.models import CustomUser


class ActionSerializer(serializers.ModelSerializer):
    """Serializer for Action model."""
    
    class Meta:
        model = Action
        fields = ['id', 'name', 'display_name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PageActionSerializer(serializers.ModelSerializer):
    """Serializer for PageAction model with nested action details."""
    action = ActionSerializer(read_only=True)
    action_id = serializers.PrimaryKeyRelatedField(
        queryset=Action.objects.all(),
        source='action',
        write_only=True
    )
    page_name = serializers.CharField(source='page.name', read_only=True)
    page_display_name = serializers.CharField(source='page.display_name', read_only=True)
    
    class Meta:
        model = PageAction
        fields = [
            'id', 'page', 'page_name', 'page_display_name',
            'action', 'action_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PageSerializer(serializers.ModelSerializer):
    """Serializer for Page model."""
    available_actions = PageActionSerializer(source='page_actions', many=True, read_only=True)
    
    class Meta:
        model = Page
        fields = [
            'id', 'name', 'display_name', 'description',
            'available_actions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for page lists."""
    
    class Meta:
        model = Page
        fields = ['id', 'name', 'display_name']
        read_only_fields = ['id']


class JobRolePageSerializer(serializers.ModelSerializer):
    """Serializer for JobRolePage model."""
    page = PageListSerializer(read_only=True)
    page_id = serializers.PrimaryKeyRelatedField(
        queryset=Page.objects.all(),
        source='page',
        write_only=True
    )
    job_role_name = serializers.CharField(source='job_role.name', read_only=True)
    
    class Meta:
        model = JobRolePage
        fields = ['id', 'job_role', 'job_role_name', 'page', 'page_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class JobRoleSerializer(serializers.ModelSerializer):
    """Serializer for JobRole model."""
    pages = JobRolePageSerializer(source='job_role_pages', many=True, read_only=True)
    page_count = serializers.IntegerField(source='job_role_pages.count', read_only=True)
    
    class Meta:
        model = JobRole
        fields = [
            'id', 'name', 'description', 'pages', 'page_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class JobRoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for job role lists."""
    
    class Meta:
        model = JobRole
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']


class UserActionDenialSerializer(serializers.ModelSerializer):
    """Serializer for UserActionDenial model."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    page_action_details = PageActionSerializer(source='page_action', read_only=True)
    
    class Meta:
        model = UserActionDenial
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'page_action', 'page_action_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserActionDenialCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating user action denials."""
    
    class Meta:
        model = UserActionDenial
        fields = ['id', 'user', 'page_action']
        read_only_fields = ['id']
    
    def validate(self, data):
        """
        Validate that the user's job role has access to the page
        before denying a specific action.
        """
        user = data['user']
        page_action = data['page_action']
        page = page_action.page
        
        # Check if user's job role has access to this page
        if not user.job_role:
            raise serializers.ValidationError(
                f"User {user.email} has no job role assigned."
            )
        
        has_page_access = JobRolePage.objects.filter(
            job_role=user.job_role,
            page=page
        ).exists()
        
        if not has_page_access:
            raise serializers.ValidationError(
                f"User's job role '{user.job_role.name}' does not have access to page '{page.name}'. "
                "Cannot deny an action on a page the user cannot access."
            )
        
        return data
