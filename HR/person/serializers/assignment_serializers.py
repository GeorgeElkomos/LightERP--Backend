"""
Serializers for Assignment model
"""
from rest_framework import serializers
from HR.person.models import Assignment, Person, Contract
from HR.work_structures.models import Organization, Job, Position, Grade
from core.lookups.models import LookupValue
from HR.person.dtos import AssignmentCreateDTO, AssignmentUpdateDTO
from HR.lookup_config import CoreLookups
from datetime import date, time
from decimal import Decimal


class AssignmentSerializer(serializers.ModelSerializer):
    """Read serializer for Assignment model"""
    person = serializers.IntegerField(source='person.id', read_only=True)
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    business_group = serializers.IntegerField(source='business_group.id', read_only=True)
    business_group_name = serializers.CharField(source='business_group.organization_name', read_only=True)
    department = serializers.IntegerField(source='department.id', read_only=True)
    department_name = serializers.CharField(source='department.organization_name', read_only=True)
    job = serializers.IntegerField(source='job.id', read_only=True)
    job_name = serializers.CharField(source='job.job_title.name', read_only=True)
    position = serializers.IntegerField(source='position.id', read_only=True)
    position_name = serializers.CharField(source='position.position_title.name', read_only=True)
    grade = serializers.IntegerField(source='grade.id', read_only=True)
    grade_name = serializers.CharField(source='grade.grade_name.name', read_only=True)
    
    payroll = serializers.IntegerField(source='payroll.id', read_only=True, allow_null=True)
    payroll_name = serializers.CharField(source='payroll.name', read_only=True, allow_null=True)
    salary_basis = serializers.IntegerField(source='salary_basis.id', read_only=True, allow_null=True)
    salary_basis_name = serializers.CharField(source='salary_basis.name', read_only=True, allow_null=True)
    assignment_action_reason = serializers.IntegerField(source='assignment_action_reason.id', read_only=True)
    assignment_action_reason_name = serializers.CharField(source='assignment_action_reason.name', read_only=True)
    assignment_status = serializers.IntegerField(source='assignment_status.id', read_only=True)
    assignment_status_name = serializers.CharField(source='assignment_status.name', read_only=True)
    
    line_manager = serializers.IntegerField(source='line_manager.id', read_only=True, allow_null=True)
    line_manager_name = serializers.CharField(source='line_manager.full_name', read_only=True, allow_null=True)
    project_manager = serializers.IntegerField(source='project_manager.id', read_only=True, allow_null=True)
    project_manager_name = serializers.CharField(source='project_manager.full_name', read_only=True, allow_null=True)
    contract = serializers.IntegerField(source='contract.id', read_only=True, allow_null=True)
    contract_ref = serializers.CharField(source='contract.contract_reference', read_only=True, allow_null=True)

    probation_period = serializers.IntegerField(source='probation_period.id', read_only=True, allow_null=True)
    probation_period_name = serializers.CharField(source='probation_period.name', read_only=True, allow_null=True)
    termination_notice_period = serializers.IntegerField(source='termination_notice_period.id', read_only=True, allow_null=True)
    termination_notice_period_name = serializers.CharField(source='termination_notice_period.name', read_only=True, allow_null=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'assignment_no', 
            'person', 'person_name',
            'business_group', 'business_group_name',
            'department', 'department_name',
            'job', 'job_name',
            'position', 'position_name',
            'grade', 'grade_name',
            'payroll', 'payroll_name',
            'salary_basis', 'salary_basis_name',
            'line_manager', 'line_manager_name',
            'assignment_action_reason', 'assignment_action_reason_name',
            'primary_assignment',
            'contract', 'contract_ref',
            'assignment_status', 'assignment_status_name',
            'project_manager', 'project_manager_name',
            'probation_period_start', 'probation_period', 'probation_period_name', 'probation_period_end',
            'termination_notice_period', 'termination_notice_period_name',
            'hourly_salaried', 'working_frequency',
            'work_start_time', 'work_end_time', 'working_hours',
            'work_from_home', 'is_manager', 'title',
            'employment_confirmation_date',
            'effective_start_date', 'effective_end_date',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 
            'person_name', 'business_group_name', 'department_name',
            'job_name', 'position_name', 'grade_name', 'probation_period_end',
            'working_hours'
        ]


class AssignmentCreateSerializer(serializers.Serializer):
    """Write serializer for creating an assignment"""
    person_id = serializers.IntegerField()
    business_group_id = serializers.IntegerField()
    assignment_no = serializers.CharField(max_length=50)
    department_id = serializers.IntegerField()
    job_id = serializers.IntegerField()
    position_id = serializers.IntegerField()
    grade_id = serializers.IntegerField()
    
    assignment_action_reason_id = serializers.IntegerField()
    assignment_status_id = serializers.IntegerField()
    effective_start_date = serializers.DateField()
    
    payroll_id = serializers.IntegerField(required=False, allow_null=True)
    salary_basis_id = serializers.IntegerField(required=False, allow_null=True)
    line_manager_id = serializers.IntegerField(required=False, allow_null=True)
    primary_assignment = serializers.BooleanField(default=True)
    contract_id = serializers.IntegerField(required=False, allow_null=True)
    project_manager_id = serializers.IntegerField(required=False, allow_null=True)
    
    probation_period_start = serializers.DateField(required=False, allow_null=True)
    probation_period_id = serializers.IntegerField(required=False, allow_null=True)
    termination_notice_period_id = serializers.IntegerField(required=False, allow_null=True)
    
    hourly_salaried = serializers.ChoiceField(choices=Assignment.HOURLY_SALARIED_CHOICES, default='Salaried')
    working_frequency = serializers.ChoiceField(choices=Assignment.FREQUENCY_CHOICES, default='Month')
    
    work_start_time = serializers.TimeField(required=False, allow_null=True)
    work_end_time = serializers.TimeField(required=False, allow_null=True)
    
    work_from_home = serializers.BooleanField(default=False)
    is_manager = serializers.BooleanField(default=False)
    title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    employment_confirmation_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_business_group_id(self, value):
        try:
            Organization.objects.get(pk=value)
        except Organization.DoesNotExist:
            raise serializers.ValidationError("Business Group not found")
        return value

    def validate_assignment_status_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.ASSIGNMENT_STATUS, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active assignment status")
        return value
    
    def validate_assignment_action_reason_id(self, value):
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.ASSIGNMENT_ACTION_REASON, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active assignment action reason")
        return value

    def validate(self, attrs):
        # Work time validation
        start = attrs.get('work_start_time')
        end = attrs.get('work_end_time')
        if start and end and end <= start:
             raise serializers.ValidationError({"work_end_time": "Work end time must be after start time"})
             
        # Check uniqueness of assignment_no for effective_start_date
        ano = attrs.get('assignment_no')
        eff_start = attrs.get('effective_start_date')
        
        if Assignment.objects.filter(assignment_no=ano, effective_start_date=eff_start).exists():
            raise serializers.ValidationError({"assignment_no": "An assignment with this number and effective start date already exists"})
            
        return attrs

    def to_dto(self) -> AssignmentCreateDTO:
        return AssignmentCreateDTO(**self.validated_data)


class AssignmentUpdateSerializer(serializers.Serializer):
    """Write serializer for updating an assignment"""
    assignment_no = serializers.CharField(max_length=50)
    effective_start_date = serializers.DateField() # Needed for versioning logic
    
    person_id = serializers.IntegerField(required=False, allow_null=True)
    business_group_id = serializers.IntegerField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    job_id = serializers.IntegerField(required=False, allow_null=True)
    position_id = serializers.IntegerField(required=False, allow_null=True)
    grade_id = serializers.IntegerField(required=False, allow_null=True)
    
    assignment_action_reason_id = serializers.IntegerField(required=False, allow_null=True)
    assignment_status_id = serializers.IntegerField(required=False, allow_null=True)
    
    payroll_id = serializers.IntegerField(required=False, allow_null=True)
    salary_basis_id = serializers.IntegerField(required=False, allow_null=True)
    line_manager_id = serializers.IntegerField(required=False, allow_null=True)
    primary_assignment = serializers.BooleanField(required=False, allow_null=True)
    contract_id = serializers.IntegerField(required=False, allow_null=True)
    project_manager_id = serializers.IntegerField(required=False, allow_null=True)
    
    probation_period_start = serializers.DateField(required=False, allow_null=True)
    probation_period_id = serializers.IntegerField(required=False, allow_null=True)
    termination_notice_period_id = serializers.IntegerField(required=False, allow_null=True)
    
    hourly_salaried = serializers.ChoiceField(choices=Assignment.HOURLY_SALARIED_CHOICES, required=False, allow_null=True)
    working_frequency = serializers.ChoiceField(choices=Assignment.FREQUENCY_CHOICES, required=False, allow_null=True)
    
    work_start_time = serializers.TimeField(required=False, allow_null=True)
    work_end_time = serializers.TimeField(required=False, allow_null=True)
    
    work_from_home = serializers.BooleanField(required=False, allow_null=True)
    is_manager = serializers.BooleanField(required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    employment_confirmation_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_assignment_status_id(self, value):
        if value is None: return value
        try:
            LookupValue.objects.get(pk=value, lookup_type__name=CoreLookups.ASSIGNMENT_STATUS, is_active=True)
        except LookupValue.DoesNotExist:
            raise serializers.ValidationError("Invalid active assignment status")
        return value

    def to_dto(self) -> AssignmentUpdateDTO:
        return AssignmentUpdateDTO(**self.validated_data)
