"""
Serializers for Approval Workflow models.
Handles serialization/deserialization of approval models for API endpoints.
"""
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
    ApprovalAction,
    ApprovalDelegation,
)
from core.job_roles.models import JobRole


class ContentTypeSerializer(serializers.ModelSerializer):
    """Serializer for ContentType model."""
    model_name = serializers.CharField(source='model', read_only=True)
    app_label = serializers.CharField(read_only=True)
    
    class Meta:
        model = ContentType
        fields = ['id', 'app_label', 'model_name']
        read_only_fields = ['id', 'app_label', 'model_name']


class JobRoleSerializer(serializers.ModelSerializer):
    """Lightweight serializer for JobRole model."""
    
    class Meta:
        model = JobRole
        fields = ['id', 'name']
        read_only_fields = ['id', 'name']


class ApprovalWorkflowStageTemplateSerializer(serializers.ModelSerializer):
    """
    Full serializer for ApprovalWorkflowStageTemplate.
    Used for create/update/detail operations.
    """
    required_role_details = JobRoleSerializer(source='required_role', read_only=True)
    policy_display = serializers.CharField(source='get_decision_policy_display', read_only=True)
    
    class Meta:
        model = ApprovalWorkflowStageTemplate
        fields = [
            'id',
            'workflow_template',
            'order_index',
            'name',
            'decision_policy',
            'policy_display',
            'quorum_count',
            'required_role',
            'required_role_details',
            'dynamic_filter_json',
            'allow_reject',
            'allow_delegate',
            'sla_hours',
            'parallel_group',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'policy_display', 'required_role_details']
    
    def validate(self, data):
        """Validate stage template data."""
        # Validate quorum_count for QUORUM policy
        if data.get('decision_policy') == ApprovalWorkflowStageTemplate.POLICY_QUORUM:
            if not data.get('quorum_count') or data.get('quorum_count') < 1:
                raise serializers.ValidationError({
                    'quorum_count': 'quorum_count must be at least 1 for QUORUM policy'
                })
        
        return data


class ApprovalWorkflowStageTemplateNestedSerializer(serializers.ModelSerializer):
    """
    Nested serializer for creating stages within a workflow template.
    workflow_template field is not required as it will be set by parent.
    """
    required_role_details = JobRoleSerializer(source='required_role', read_only=True)
    policy_display = serializers.CharField(source='get_decision_policy_display', read_only=True)
    
    class Meta:
        model = ApprovalWorkflowStageTemplate
        fields = [
            'id',
            'order_index',
            'name',
            'decision_policy',
            'policy_display',
            'quorum_count',
            'required_role',
            'required_role_details',
            'dynamic_filter_json',
            'allow_reject',
            'allow_delegate',
            'sla_hours',
            'parallel_group',
        ]
        read_only_fields = ['id', 'policy_display', 'required_role_details']
    
    def validate(self, data):
        """Validate stage template data."""
        # Validate quorum_count for QUORUM policy
        if data.get('decision_policy') == ApprovalWorkflowStageTemplate.POLICY_QUORUM:
            if not data.get('quorum_count') or data.get('quorum_count') < 1:
                raise serializers.ValidationError({
                    'quorum_count': 'quorum_count must be at least 1 for QUORUM policy'
                })
        
        return data


class ApprovalWorkflowStageTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing stage templates.
    """
    policy_display = serializers.CharField(source='get_decision_policy_display', read_only=True)
    required_role_name = serializers.CharField(source='required_role.name', read_only=True)
    
    class Meta:
        model = ApprovalWorkflowStageTemplate
        fields = [
            'id',
            'order_index',
            'name',
            'decision_policy',
            'policy_display',
            'quorum_count',
            'required_role',
            'required_role_name',
            'allow_reject',
            'allow_delegate',
            'sla_hours',
        ]


class ApprovalWorkflowTemplateSerializer(serializers.ModelSerializer):
    """
    Full serializer for ApprovalWorkflowTemplate.
    Includes nested stages.
    """
    content_type_details = ContentTypeSerializer(source='content_type', read_only=True)
    stages = ApprovalWorkflowStageTemplateListSerializer(many=True, read_only=True)
    stage_count = serializers.SerializerMethodField()
    instance_count = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ApprovalWorkflowTemplate
        fields = [
            'id',
            'code',
            'name',
            'description',
            'content_type',
            'content_type_details',
            'is_active',
            'version',
            'stages',
            'stage_count',
            'instance_count',
            'status_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'content_type_details', 
                           'stages', 'stage_count', 'instance_count', 'status_display']
    
    def get_stage_count(self, obj):
        """Get number of stages in this template."""
        return obj.stages.count()
    
    def get_instance_count(self, obj):
        """Get number of workflow instances using this template."""
        return obj.instances.count()
    
    def get_status_display(self, obj):
        """Get human-readable status."""
        return 'Active' if obj.is_active else 'Inactive'
    
    def validate_code(self, value):
        """Validate code uniqueness."""
        if self.instance:
            # Update: check uniqueness excluding current instance
            if ApprovalWorkflowTemplate.objects.filter(code=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError(f"Template with code '{value}' already exists.")
        else:
            # Create: check uniqueness
            if ApprovalWorkflowTemplate.objects.filter(code=value).exists():
                raise serializers.ValidationError(f"Template with code '{value}' already exists.")
        return value


class ApprovalWorkflowTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing workflow templates.
    """
    content_type_details = ContentTypeSerializer(source='content_type', read_only=True)
    stage_count = serializers.SerializerMethodField()
    instance_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ApprovalWorkflowTemplate
        fields = [
            'id',
            'code',
            'name',
            'content_type',
            'content_type_details',
            'is_active',
            'version',
            'stage_count',
            'instance_count',
            'created_at',
        ]
    
    def get_stage_count(self, obj):
        """Get number of stages."""
        return obj.stages.count()
    
    def get_instance_count(self, obj):
        """Get number of instances."""
        return obj.instances.count()


class ApprovalWorkflowTemplateCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating workflow templates with nested stages.
    """
    stages = ApprovalWorkflowStageTemplateNestedSerializer(many=True, required=False)
    
    class Meta:
        model = ApprovalWorkflowTemplate
        fields = [
            'id',
            'code',
            'name',
            'description',
            'content_type',
            'is_active',
            'version',
            'stages',
        ]
        read_only_fields = ['id']
    
    def create(self, validated_data):
        """Create template with nested stages."""
        stages_data = validated_data.pop('stages', [])
        template = ApprovalWorkflowTemplate.objects.create(**validated_data)
        
        # Create stages
        for stage_data in stages_data:
            ApprovalWorkflowStageTemplate.objects.create(
                workflow_template=template,
                **stage_data
            )
        
        return template
    
    def update(self, instance, validated_data):
        """Update template (stages updated separately)."""
        stages_data = validated_data.pop('stages', None)
        
        # Update template fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Note: Stages are updated separately via stage endpoints
        # to avoid complexity with order_index management
        
        return instance


# Additional serializers for workflow instances (for monitoring/viewing)

class ApprovalAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for approval assignments."""
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = ApprovalAssignment
        fields = [
            'id',
            'user',
            'user_name',
            'user_email',
            'role_snapshot',
            'level_snapshot',
            'is_mandatory',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'user_name', 'user_email', 'created_at']


class ApprovalActionSerializer(serializers.ModelSerializer):
    """Serializer for approval actions."""
    user_name = serializers.CharField(source='user.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = ApprovalAction
        fields = [
            'id',
            'user',
            'user_name',
            'action',
            'action_display',
            'comment',
            'created_at',
            'triggers_stage_completion',
        ]
        read_only_fields = ['id', 'user_name', 'action_display', 'created_at']


class ApprovalWorkflowStageInstanceSerializer(serializers.ModelSerializer):
    """Serializer for workflow stage instances."""
    stage_name = serializers.CharField(source='stage_template.name', read_only=True)
    order_index = serializers.IntegerField(source='stage_template.order_index', read_only=True)
    assignments = ApprovalAssignmentSerializer(many=True, read_only=True)
    actions = ApprovalActionSerializer(many=True, read_only=True)
    
    class Meta:
        model = ApprovalWorkflowStageInstance
        fields = [
            'id',
            'stage_template',
            'stage_name',
            'order_index',
            'status',
            'activated_at',
            'completed_at',
            'assignments',
            'actions',
        ]
        read_only_fields = ['id', 'stage_name', 'order_index', 'assignments', 'actions']


class ApprovalWorkflowInstanceSerializer(serializers.ModelSerializer):
    """Serializer for workflow instances."""
    template_name = serializers.CharField(source='template.name', read_only=True)
    content_type_details = ContentTypeSerializer(source='content_type', read_only=True)
    stage_instances = ApprovalWorkflowStageInstanceSerializer(many=True, read_only=True)
    
    class Meta:
        model = ApprovalWorkflowInstance
        fields = [
            'id',
            'content_type',
            'content_type_details',
            'object_id',
            'template',
            'template_name',
            'current_stage_template',
            'status',
            'started_at',
            'finished_at',
            'completed_stage_count',
            'stage_instances',
        ]
        read_only_fields = ['id', 'template_name', 'content_type_details', 'stage_instances']


class ApprovalDelegationSerializer(serializers.ModelSerializer):
    """Serializer for approval delegations."""
    from_user_name = serializers.CharField(source='from_user.name', read_only=True)
    to_user_name = serializers.CharField(source='to_user.name', read_only=True)
    
    class Meta:
        model = ApprovalDelegation
        fields = [
            'id',
            'from_user',
            'from_user_name',
            'to_user',
            'to_user_name',
            'stage_instance',
            'start_date',
            'end_date',
            'reason',
            'active',
            'created_at',
            'deactivated_at',
        ]
        read_only_fields = ['id', 'from_user_name', 'to_user_name', 'created_at']
