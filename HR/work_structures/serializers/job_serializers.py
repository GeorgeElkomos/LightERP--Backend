"""
Serializers for Job model and its requirements
"""
from rest_framework import serializers
from HR.work_structures.models import (
    Job, JobQualificationRequirement, 
    Organization, Grade
)
from HR.person.models import Competency, JobCompetencyRequirement
from core.lookups.models import LookupValue
from HR.work_structures.dtos import (
    JobCreateDTO, JobUpdateDTO,
    CompetencyRequirementDTO, QualificationRequirementDTO
)


class JobCompetencyReadSerializer(serializers.ModelSerializer):
    """Read serializer for JobCompetencyRequirement"""
    competency_id = serializers.IntegerField(source='competency.id', read_only=True)
    competency_name = serializers.CharField(source='competency.name', read_only=True)
    competency_category_id = serializers.IntegerField(source='competency.category.id', read_only=True)
    competency_category_name = serializers.CharField(source='competency.category.name', read_only=True)
    proficiency_level_id = serializers.IntegerField(source='proficiency_level.id', read_only=True)
    proficiency_level_name = serializers.CharField(source='proficiency_level.name', read_only=True)

    class Meta:
        model = JobCompetencyRequirement
        fields = [
            'competency_id', 'competency_name', 
            'competency_category_id', 'competency_category_name',
            'proficiency_level_id', 'proficiency_level_name'
        ]


class JobQualificationReadSerializer(serializers.ModelSerializer):
    """Read serializer for JobQualificationRequirement"""
    qualification_type_id = serializers.IntegerField(source='qualification_type.id', read_only=True)
    qualification_type_name = serializers.CharField(source='qualification_type.name', read_only=True)
    qualification_title_id = serializers.IntegerField(source='qualification_title.id', read_only=True)
    qualification_title_name = serializers.CharField(source='qualification_title.name', read_only=True)

    class Meta:
        model = JobQualificationRequirement
        fields = [
            'qualification_type_id', 'qualification_type_name', 
            'qualification_title_id', 'qualification_title_name'
        ]


class JobReadSerializer(serializers.ModelSerializer):
    """Read serializer for Job model"""
    business_group_id = serializers.IntegerField(source='business_group.id', read_only=True)
    business_group_name = serializers.CharField(source='business_group.organization_name', read_only=True)
    job_category_id = serializers.IntegerField(source='job_category.id', read_only=True)
    job_category_name = serializers.CharField(source='job_category.name', read_only=True)
    job_title_id = serializers.IntegerField(source='job_title.id', read_only=True)
    job_title_name = serializers.CharField(source='job_title.name', read_only=True)

    competency_requirements = JobCompetencyReadSerializer(many=True, read_only=True)
    qualification_requirements = JobQualificationReadSerializer(many=True, read_only=True)
    grade_details = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'code', 'business_group_id', 'business_group_name',
            'job_category_id', 'job_category_name', 'job_title_id', 'job_title_name',
            'job_description', 'responsibilities',
            'competency_requirements', 'qualification_requirements',
            'grades', 'grade_details',
            'effective_start_date', 'effective_end_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'business_group_name', 'job_category_name',
            'job_title_name',
            'competency_requirements', 'qualification_requirements', 'grade_details',
            'created_at', 'updated_at'
        ]

    def get_grade_details(self, obj):
        return [
            {'id': g.id, 'name': g.grade_name.name, 'sequence': g.sequence}
            for g in obj.grades.all()
        ]


class CompetencyRequirementSerializer(serializers.Serializer):
    """Serializer for competency requirement DTO"""
    competency_id = serializers.IntegerField()
    proficiency_level_id = serializers.IntegerField()

    def to_dto(self) -> CompetencyRequirementDTO:
        return CompetencyRequirementDTO(**self.validated_data)


class QualificationRequirementSerializer(serializers.Serializer):
    """Serializer for qualification requirement DTO"""
    qualification_type_id = serializers.IntegerField()
    qualification_title_id = serializers.IntegerField()

    def to_dto(self) -> QualificationRequirementDTO:
        return QualificationRequirementDTO(**self.validated_data)


class JobCreateSerializer(serializers.Serializer):
    """Write serializer for creating a job"""
    code = serializers.CharField(max_length=50)
    business_group_id = serializers.IntegerField()
    job_category_id = serializers.IntegerField()
    job_title_id = serializers.IntegerField()
    job_description = serializers.CharField()
    responsibilities = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    competency_requirements = CompetencyRequirementSerializer(many=True, required=False)
    qualification_requirements = QualificationRequirementSerializer(many=True, required=False)
    grade_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    effective_start_date = serializers.DateField()  # REQUIRED
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self) -> JobCreateDTO:
        data = self.validated_data.copy()
        
        # Convert nested serializers to DTOs
        if 'competency_requirements' in data:
            data['competency_requirements'] = [
                CompetencyRequirementDTO(**item) for item in data['competency_requirements']
            ]
        
        if 'qualification_requirements' in data:
            data['qualification_requirements'] = [
                QualificationRequirementDTO(**item) for item in data['qualification_requirements']
            ]
            
        return JobCreateDTO(**data)


class JobUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a job"""
    job_id = serializers.IntegerField()  # Primary Key
    job_category_id = serializers.IntegerField(required=False)
    job_title_id = serializers.IntegerField(required=False)
    job_description = serializers.CharField(required=False)
    responsibilities = serializers.ListField(child=serializers.CharField(), required=False)
    competency_requirements = CompetencyRequirementSerializer(many=True, required=False)
    qualification_requirements = QualificationRequirementSerializer(many=True, required=False)
    grade_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    effective_end_date = serializers.DateField(required=False, allow_null=True)
    new_start_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self) -> JobUpdateDTO:
        data = self.validated_data.copy()
        
        if 'competency_requirements' in data:
            data['competency_requirements'] = [
                CompetencyRequirementDTO(**item) for item in data['competency_requirements']
            ]
        
        if 'qualification_requirements' in data:
            data['qualification_requirements'] = [
                QualificationRequirementDTO(**item) for item in data['qualification_requirements']
            ]
            
        return JobUpdateDTO(**data)
