"""
Serializers for Position model and its requirements
"""
from rest_framework import serializers
from HR.work_structures.models import (
    Position, PositionQualificationRequirement,
    Organization, Job, Location, Grade
)
from HR.person.models import PositionCompetencyRequirement
from core.lookups.models import LookupValue
from HR.work_structures.dtos import (
    PositionCreateDTO, PositionUpdateDTO,
    CompetencyRequirementDTO, QualificationRequirementDTO
)
from .job_serializers import (
    CompetencyRequirementSerializer,
    QualificationRequirementSerializer
)


class PositionCompetencyReadSerializer(serializers.ModelSerializer):
    """Read serializer for PositionCompetencyRequirement"""
    competency_id = serializers.IntegerField(source='competency.id', read_only=True)
    competency_name = serializers.CharField(source='competency.name', read_only=True)
    competency_category_id = serializers.IntegerField(source='competency.category.id', read_only=True)
    competency_category_name = serializers.CharField(source='competency.category.name', read_only=True)
    proficiency_level_id = serializers.IntegerField(source='proficiency_level.id', read_only=True)
    proficiency_level_name = serializers.CharField(source='proficiency_level.name', read_only=True)

    class Meta:
        model = PositionCompetencyRequirement
        fields = [
            'competency_id', 'competency_name', 
            'competency_category_id', 'competency_category_name',
            'proficiency_level_id', 'proficiency_level_name'
        ]


class PositionQualificationReadSerializer(serializers.ModelSerializer):
    """Read serializer for PositionQualificationRequirement"""
    qualification_type_id = serializers.IntegerField(source='qualification_type.id', read_only=True)
    qualification_type_name = serializers.CharField(source='qualification_type.name', read_only=True)
    qualification_title_id = serializers.IntegerField(source='qualification_title.id', read_only=True)
    qualification_title_name = serializers.CharField(source='qualification_title.name', read_only=True)

    class Meta:
        model = PositionQualificationRequirement
        fields = [
            'qualification_type_id', 'qualification_type_name',
            'qualification_title_id', 'qualification_title_name'
        ]


class PositionReadSerializer(serializers.ModelSerializer):
    """Read serializer for Position model"""
    organization_id = serializers.IntegerField(source='organization.id', read_only=True)
    organization_name = serializers.CharField(source='organization.organization_name', read_only=True)
    business_group_id = serializers.IntegerField(source='business_group.id', read_only=True)
    business_group_name = serializers.CharField(source='business_group.organization_name', read_only=True)
    job_id = serializers.IntegerField(source='job.id', read_only=True)
    job_title_name = serializers.CharField(source='job.job_title.name', read_only=True)
    job_code = serializers.CharField(source='job.code', read_only=True)
    location_id = serializers.IntegerField(source='location.id', read_only=True, allow_null=True)
    location_name = serializers.CharField(source='location.location_name', read_only=True, allow_null=True)
    grade_id = serializers.IntegerField(source='grade.id', read_only=True, allow_null=True)
    grade_name_id = serializers.IntegerField(source='grade.grade_name.id', read_only=True, allow_null=True)
    grade_name = serializers.CharField(source='grade.grade_name.name', read_only=True, allow_null=True)
    
    position_title_id = serializers.IntegerField(source='position_title.id', read_only=True)
    position_title_name = serializers.CharField(source='position_title.name', read_only=True)
    position_type_id = serializers.IntegerField(source='position_type.id', read_only=True)
    position_type_name = serializers.CharField(source='position_type.name', read_only=True)
    position_status_id = serializers.IntegerField(source='position_status.id', read_only=True)
    position_status_name = serializers.CharField(source='position_status.name', read_only=True)
    
    position_sync = serializers.BooleanField(read_only=True, allow_null=True)
    payroll_id = serializers.IntegerField(source='payroll.id', read_only=True, allow_null=True)
    payroll_name = serializers.CharField(source='payroll.name', read_only=True, allow_null=True)
    salary_basis_id = serializers.IntegerField(source='salary_basis.id', read_only=True, allow_null=True)
    salary_basis_name = serializers.CharField(source='salary_basis.name', read_only=True, allow_null=True)
    
    reports_to_id = serializers.IntegerField(source='reports_to.id', read_only=True, allow_null=True)
    reports_to_code = serializers.CharField(source='reports_to.code', read_only=True, allow_null=True)
    reports_to_title = serializers.CharField(source='reports_to.position_title.name', read_only=True, allow_null=True)

    competency_requirements = PositionCompetencyReadSerializer(many=True, read_only=True)
    qualification_requirements = PositionQualificationReadSerializer(many=True, read_only=True)

    class Meta:
        model = Position
        fields = [
            'id', 'code', 'organization_id', 'organization_name',
            'business_group_id', 'business_group_name',
            'job_id', 'job_title_name', 'job_code',
            'position_title_id', 'position_title_name',
            'position_type_id', 'position_type_name',
            'position_status_id', 'position_status_name',
            'location_id', 'location_name',
            'grade_id', 'grade_name_id', 'grade_name',
            'full_time_equivalent', 'head_count',
            'position_sync',
            'payroll_id', 'payroll_name',
            'salary_basis_id', 'salary_basis_name',
            'reports_to_id', 'reports_to_code', 'reports_to_title',
            'competency_requirements', 'qualification_requirements',
            'effective_start_date', 'effective_end_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'organization_name', 'job_title_name', 'job_code',
            'location_name', 'grade_name_id', 'grade_name', 'position_title_name',
            'position_type_name', 'position_status_name', 'position_sync', 'payroll_name',
            'salary_basis_name', 'reports_to_code', 'reports_to_title',
            'competency_requirements', 'qualification_requirements',
            'created_at', 'updated_at'
        ]


class PositionCreateSerializer(serializers.Serializer):
    """Write serializer for creating a position"""
    code = serializers.CharField(max_length=50)
    organization_id = serializers.IntegerField()
    job_id = serializers.IntegerField()
    position_title_id = serializers.IntegerField()
    position_type_id = serializers.IntegerField()
    position_status_id = serializers.IntegerField()
    location_id = serializers.IntegerField(required=False, allow_null=True)
    grade_id = serializers.IntegerField(required=False, allow_null=True)
    full_time_equivalent = serializers.FloatField(default=1.0)
    head_count = serializers.IntegerField(default=1)
    position_sync = serializers.BooleanField(default=False, required=False)
    payroll_id = serializers.IntegerField(required=False, allow_null=True)
    salary_basis_id = serializers.IntegerField(required=False, allow_null=True)
    reports_to_id = serializers.IntegerField(required=False, allow_null=True)
    competency_requirements = CompetencyRequirementSerializer(many=True, required=False)
    qualification_requirements = QualificationRequirementSerializer(many=True, required=False)
    effective_start_date = serializers.DateField()  # REQUIRED
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self) -> PositionCreateDTO:
        data = self.validated_data.copy()
        
        if 'competency_requirements' in data:
            data['competency_requirements'] = [
                CompetencyRequirementDTO(**item) for item in data['competency_requirements']
            ]
        
        if 'qualification_requirements' in data:
            data['qualification_requirements'] = [
                QualificationRequirementDTO(**item) for item in data['qualification_requirements']
            ]
        return PositionCreateDTO(**data)


class PositionUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a position"""
    position_id = serializers.IntegerField()  # Primary Key
    position_title_id = serializers.IntegerField(required=False)
    position_type_id = serializers.IntegerField(required=False)
    position_status_id = serializers.IntegerField(required=False)
    organization_id = serializers.IntegerField(required=False)
    job_id = serializers.IntegerField(required=False)
    location_id = serializers.IntegerField(required=False)
    grade_id = serializers.IntegerField(required=False)
    full_time_equivalent = serializers.FloatField(required=False)
    head_count = serializers.IntegerField(required=False)
    position_sync = serializers.BooleanField(default=False, required=False)
    payroll_id = serializers.IntegerField(required=False, allow_null=True)
    salary_basis_id = serializers.IntegerField(required=False, allow_null=True)
    reports_to_id = serializers.IntegerField(required=False, allow_null=True)
    competency_requirements = CompetencyRequirementSerializer(many=True, required=False)
    qualification_requirements = QualificationRequirementSerializer(many=True, required=False)
    effective_end_date = serializers.DateField(required=False, allow_null=True)
    new_start_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self) -> PositionUpdateDTO:
        data = self.validated_data.copy()
        
        if 'competency_requirements' in data:
            data['competency_requirements'] = [
                CompetencyRequirementDTO(**item) for item in data['competency_requirements']
            ]
        
        if 'qualification_requirements' in data:
            data['qualification_requirements'] = [
                QualificationRequirementDTO(**item) for item in data['qualification_requirements']
            ]
            
        return PositionUpdateDTO(**data)
