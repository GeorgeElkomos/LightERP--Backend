from django.contrib import admin
from .models import (
    ApprovalWorkflowTemplate,
    ApprovalWorkflowStageTemplate,
    ApprovalWorkflowInstance,
    ApprovalWorkflowStageInstance,
    ApprovalAssignment,
    ApprovalAction,
    ApprovalDelegation,
)


class ApprovalWorkflowStageTemplateInline(admin.TabularInline):
    """Inline admin for stages within a workflow template."""
    model = ApprovalWorkflowStageTemplate
    extra = 1
    fields = [
        'order_index', 'name', 'decision_policy', 'quorum_count',
        'required_role', 'allow_reject', 'allow_delegate'
    ]
    ordering = ['order_index']


@admin.register(ApprovalWorkflowTemplate)
class ApprovalWorkflowTemplateAdmin(admin.ModelAdmin):
    """Admin for workflow templates."""
    list_display = [
        'code', 'name', 'content_type', 
        'is_active', 'version', 'created_at'
    ]
    list_filter = ['is_active', 'content_type', 'created_at']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ApprovalWorkflowStageTemplateInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'content_type')
        }),
        ('Status', {
            'fields': ('is_active', 'version')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ApprovalWorkflowStageTemplate)
class ApprovalWorkflowStageTemplateAdmin(admin.ModelAdmin):
    """Admin for stage templates."""
    list_display = [
        'workflow_template', 'order_index', 'name', 
        'decision_policy', 'quorum_count'
    ]
    list_filter = ['decision_policy', 'workflow_template']
    search_fields = ['name', 'workflow_template__code']
    ordering = ['workflow_template', 'order_index']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('workflow_template', 'order_index', 'name')
        }),
        ('Decision Policy', {
            'fields': ('decision_policy', 'quorum_count'),
            'description': 'Define how approvals are evaluated'
        }),
        ('User Filtering', {
            'fields': ('required_role', 'dynamic_filter_json')
            # 'required_user_level' is commented out in the model
        }),
        ('Policies', {
            'fields': ('allow_reject', 'allow_delegate', 'sla_hours')
        }),
        ('Advanced', {
            'fields': ('parallel_group',),
            'classes': ('collapse',)
        }),
    )


class ApprovalWorkflowStageInstanceInline(admin.TabularInline):
    """Inline admin for stage instances."""
    model = ApprovalWorkflowStageInstance
    extra = 0
    can_delete = False
    fields = ['stage_template', 'status', 'activated_at', 'completed_at']
    readonly_fields = ['stage_template', 'status', 'activated_at', 'completed_at']


@admin.register(ApprovalWorkflowInstance)
class ApprovalWorkflowInstanceAdmin(admin.ModelAdmin):
    """Admin for workflow instances."""
    list_display = [
        'id', 'content_type', 'object_id', 'template', 
        'status', 'current_stage_template', 'started_at'
    ]
    list_filter = ['status', 'content_type', 'started_at']
    search_fields = ['object_id', 'template__code']
    readonly_fields = [
        'content_type', 'object_id', 'template', 
        'started_at', 'finished_at', 'completed_stage_count'
    ]
    inlines = [ApprovalWorkflowStageInstanceInline]
    
    fieldsets = (
        ('Workflow Information', {
            'fields': ('template', 'status', 'current_stage_template')
        }),
        ('Linked Object', {
            'fields': ('content_type', 'object_id'),
            'description': 'The object being approved'
        }),
        ('Timeline', {
            'fields': ('started_at', 'finished_at', 'completed_stage_count')
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation - use ApprovalManager instead."""
        return False


class ApprovalAssignmentInline(admin.TabularInline):
    """Inline admin for assignments."""
    model = ApprovalAssignment
    extra = 0
    can_delete = False
    fields = ['user', 'role_snapshot', 'level_snapshot', 'is_mandatory', 'status']
    readonly_fields = ['user', 'role_snapshot', 'level_snapshot', 'status']


class ApprovalActionInline(admin.TabularInline):
    """Inline admin for actions."""
    model = ApprovalAction
    extra = 0
    can_delete = False
    fields = ['user', 'action', 'comment', 'created_at']
    readonly_fields = ['user', 'action', 'comment', 'created_at']


@admin.register(ApprovalWorkflowStageInstance)
class ApprovalWorkflowStageInstanceAdmin(admin.ModelAdmin):
    """Admin for stage instances."""
    list_display = [
        'id', 'workflow_instance', 'stage_template', 
        'status', 'activated_at', 'completed_at'
    ]
    list_filter = ['status', 'stage_template', 'activated_at']
    search_fields = ['workflow_instance__id', 'stage_template__name']
    readonly_fields = [
        'workflow_instance', 'stage_template', 
        'activated_at', 'completed_at'
    ]
    inlines = [ApprovalAssignmentInline, ApprovalActionInline]
    
    def has_add_permission(self, request):
        """Prevent manual creation."""
        return False


@admin.register(ApprovalAssignment)
class ApprovalAssignmentAdmin(admin.ModelAdmin):
    """Admin for assignments."""
    list_display = [
        'id', 'user', 'stage_instance', 'status', 
        'is_mandatory', 'created_at'
    ]
    list_filter = ['status', 'is_mandatory', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = [
        'stage_instance', 'user', 'role_snapshot', 
        'level_snapshot', 'created_at'
    ]
    
    def has_add_permission(self, request):
        """Prevent manual creation."""
        return False


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    """Admin for actions (audit log)."""
    list_display = [
        'id', 'user', 'action', 'stage_instance', 
        'triggers_stage_completion', 'created_at'
    ]
    list_filter = ['action', 'triggers_stage_completion', 'created_at']
    search_fields = ['user__username', 'comment']
    readonly_fields = [
        'stage_instance', 'user', 'assignment', 'action', 
        'comment', 'created_at', 'triggers_stage_completion'
    ]
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        """Prevent manual creation."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion - audit trail."""
        return False


@admin.register(ApprovalDelegation)
class ApprovalDelegationAdmin(admin.ModelAdmin):
    """Admin for delegations."""
    list_display = [
        'id', 'from_user', 'to_user', 'stage_instance', 
        'active', 'created_at'
    ]
    list_filter = ['active', 'created_at']
    search_fields = ['from_user__username', 'to_user__username']
    readonly_fields = [
        'from_user', 'to_user', 'stage_instance', 
        'created_at', 'deactivated_at'
    ]
    
    def has_add_permission(self, request):
        """Prevent manual creation."""
        return False
