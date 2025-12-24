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
        write_only=True,
        required=False,
        allow_null=True
    )
    action_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    page_name = serializers.CharField(source='page.name', read_only=True)
    page_display_name = serializers.CharField(source='page.display_name', read_only=True)
    
    class Meta:
        model = PageAction
        fields = [
            'id', 'page', 'page_name', 'page_display_name',
            'action', 'action_id', 'action_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def to_internal_value(self, data):
        """
        Handle action_name to action_id conversion during deserialization.
        """
        # Create a mutable copy of data
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        action_name = data_copy.get('action_name')
        
        # If action_name is provided but not action_id, resolve it
        if action_name and not data_copy.get('action_id'):
            try:
                action = Action.objects.get(name=action_name)
                data_copy['action_id'] = action.id
            except Action.DoesNotExist:
                # Remove action_name to prevent it from reaching the model
                data_copy.pop('action_name', None)
                # Let validation handle the error
                pass
        
        # Always remove action_name from the data that goes to validation
        # This prevents it from being passed to the model
        data_copy.pop('action_name', None)
        
        return super().to_internal_value(data_copy)
    
    def validate(self, attrs):
        """Ensure either action_id or action_name is provided and valid."""
        # At this point, action_name should already be removed
        # If action is not in attrs, we need to check why
        
        if 'action' not in attrs:
            # Check if action_name was provided but not found
            original_data = self.initial_data
            action_name = original_data.get('action_name')
            
            if action_name:
                raise serializers.ValidationError({
                    'action_name': f"Action with name '{action_name}' does not exist."
                })
            else:
                raise serializers.ValidationError({
                    'action': 'Either action_id or action_name is required.'
                })
        
        return attrs   
    
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


class UserActionDenialCreateSerializer(serializers.Serializer):
    """Serializer for creating user action denials with flexible input options."""
    # Option 1: Use IDs directly
    user = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), 
        required=False
    )
    page_action = serializers.PrimaryKeyRelatedField(
        queryset=PageAction.objects.all(), 
        required=False
    )
    
    # Option 2: Use names/email
    user_email = serializers.EmailField(required=False)
    page_name = serializers.CharField(required=False)
    action_name = serializers.CharField(required=False)
    
    # Optional reason for denial
    denial_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    def validate(self, data):
        """
        Validate and resolve user_email, page_name, action_name to their model instances.
        Also validate that the user's job role has access to the page.
        """
        from core.user_accounts.models import CustomUser
        
        # Resolve user (either by user field or user_email)
        user_email = data.get('user_email')
        user = data.get('user')
        
        if not user and user_email:
            try:
                user = CustomUser.objects.get(email=user_email)
                data['user'] = user
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError(
                    {'user_email': f"User with email '{user_email}' does not exist."}
                )
        elif not user:
            raise serializers.ValidationError(
                'Either user or user_email is required.'
            )
        
        # Remove the email/names from data since they're not model fields
        data.pop('user_email', None)
        page_name = data.pop('page_name', None)
        action_name = data.pop('action_name', None)
        
        # Resolve page_action (either directly or via page_name + action_name)
        page_action = data.get('page_action')
        
        if not page_action:
            if not page_name or not action_name:
                raise serializers.ValidationError(
                    'Either page_action or both page_name and action_name are required.'
                )
            
            try:
                page = Page.objects.get(name=page_name)
            except Page.DoesNotExist:
                raise serializers.ValidationError(
                    {'page_name': f"Page with name '{page_name}' does not exist."}
                )
            
            try:
                action = Action.objects.get(name=action_name)
            except Action.DoesNotExist:
                raise serializers.ValidationError(
                    {'action_name': f"Action with name '{action_name}' does not exist."}
                )
            
            try:
                page_action = PageAction.objects.get(page=page, action=action)
                data['page_action'] = page_action
            except PageAction.DoesNotExist:
                raise serializers.ValidationError(
                    f"PageAction for page '{page_name}' and action '{action_name}' does not exist."
                )
        
        # Check if user's job role has access to this page
        if not user.job_role:
            raise serializers.ValidationError(
                f"User {user.email} has no job role assigned."
            )
        
        has_page_access = JobRolePage.objects.filter(
            job_role=user.job_role,
            page=page_action.page
        ).exists()
        
        if not has_page_access:
            raise serializers.ValidationError(
                f"User's job role '{user.job_role.name}' does not have access to page '{page_action.page.name}'. "
                "Cannot deny an action on a page the user cannot access."
            )
        
        return data
    
    def create(self, validated_data):
        """Create the UserActionDenial instance."""
        return UserActionDenial.objects.create(**validated_data)


class JobRoleWithPagesSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a job role with page assignments in one request.
    Handles atomic creation of JobRole and JobRolePage entries.
    Supports both page IDs and page names for flexibility.
    """
    page_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of page IDs to assign to this job role"
    )
    page_names = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of page names to assign to this job role"
    )
    pages = JobRolePageSerializer(source='job_role_pages', many=True, read_only=True)
    
    class Meta:
        model = JobRole
        fields = ['id', 'name', 'description', 'page_ids', 'page_names', 'pages', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """
        Validate page_ids or page_names and normalize them to page_ids.
        This ensures atomic operation - either all pages are valid or we fail.
        """
        page_ids = data.pop('page_ids', [])
        page_names = data.pop('page_names', [])
        
        # Convert page_names to page_ids
        if page_names:
            pages = Page.objects.filter(name__in=page_names)
            found_names = set(pages.values_list('name', flat=True))
            missing_names = set(page_names) - found_names
            
            if missing_names:
                raise serializers.ValidationError(
                    {'page_names': f"The following page names do not exist: {sorted(missing_names)}"}
                )
            
            page_ids.extend(pages.values_list('id', flat=True))
        
        # Validate page_ids
        if page_ids:
            # Check for duplicates
            if len(page_ids) != len(set(page_ids)):
                raise serializers.ValidationError(
                    {'page_ids': "Duplicate page IDs found in the list."}
                )
            
            # Verify all pages exist
            existing_page_ids = set(Page.objects.filter(id__in=page_ids).values_list('id', flat=True))
            invalid_ids = set(page_ids) - existing_page_ids
            
            if invalid_ids:
                raise serializers.ValidationError(
                    {'page_ids': f"The following page IDs do not exist: {sorted(invalid_ids)}"}
                )
        
        data['_page_ids'] = list(set(page_ids))  # Store for use in create()
        return data
    
    def create(self, validated_data):
        """
        Create job role and assign pages atomically.
        Uses transaction to ensure data consistency - if page assignment fails,
        the job role creation is rolled back.
        """
        from django.db import transaction
        
        # Extract page_ids before creating the job role
        page_ids = validated_data.pop('_page_ids', [])
        
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
