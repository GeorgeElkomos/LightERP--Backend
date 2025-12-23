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
            'denial_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserActionDenialCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating user action denials."""
    
    class Meta:
        model = UserActionDenial
        fields = ['id', 'user', 'page_action']
        read_only_fields = ['id']
    
    # Optional reason for denial
    denial_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
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


class JobRoleWithPagesSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a job role with page assignments in one request.
    Handles atomic creation of JobRole and JobRolePage entries.
    """
    page_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of page IDs to assign to this job role"
    )
    pages = JobRolePageSerializer(source='job_role_pages', many=True, read_only=True)
    
    class Meta:
        model = JobRole
        fields = ['id', 'name', 'description', 'page_ids', 'pages', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_page_ids(self, value):
        """
        Validate that all page IDs exist before creating the job role.
        This ensures atomic operation - either all pages are valid or we fail.
        """
        if not value:
            return value
        
        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Duplicate page IDs found in the list.")
        
        # Verify all pages exist
        existing_page_ids = set(Page.objects.filter(id__in=value).values_list('id', flat=True))
        invalid_ids = set(value) - existing_page_ids
        
        if invalid_ids:
            raise serializers.ValidationError(
                f"The following page IDs do not exist: {sorted(invalid_ids)}"
            )
        
        return value
    
    def create(self, validated_data):
        """
        Create job role and assign pages atomically.
        Uses transaction to ensure data consistency - if page assignment fails,
        the job role creation is rolled back.
        """
        from django.db import transaction
        
        # Extract page_ids before creating the job role
        page_ids = validated_data.pop('page_ids', [])
        
        # Create job role and assign pages in a single transaction
        with transaction.atomic():
            # Create the job role
            job_role = JobRole.objects.create(**validated_data)
            
            # Create JobRolePage entries for each page
            if page_ids:
                job_role_pages = [
                    JobRolePage(job_role=job_role, page_id=page_id)
                    for page_id in page_ids
                ]
                JobRolePage.objects.bulk_create(job_role_pages)
        
        return job_role
