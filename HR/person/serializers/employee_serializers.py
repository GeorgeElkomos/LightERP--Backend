"""
Serializers for Employee model (managed child pattern)
"""
from rest_framework import serializers
from HR.person.models import Employee, Person, PersonType
from HR.person.dtos import EmployeeCreateDTO, EmployeeUpdateDTO
from HR.person.services.assignment_service import AssignmentService
from HR.person.serializers.person_serializers import PersonSerializer, PersonUpdateSerializer


class EmployeeSerializer(serializers.ModelSerializer):
    """Read serializer for Employee model"""
    person = PersonSerializer(read_only=True)
    person_id = serializers.IntegerField(source='person.id', read_only=True)
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    
    current_organization = serializers.SerializerMethodField()
    current_organization_name = serializers.SerializerMethodField()
    current_position = serializers.SerializerMethodField()
    current_position_name = serializers.SerializerMethodField()
    employee_type = serializers.IntegerField(source='employee_type.id', read_only=True)
    employee_type_name = serializers.CharField(source='employee_type.name', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'person', 'person_id', 'person_name',
            'current_organization', 'current_organization_name',
            'current_position', 'current_position_name',
            'employee_type', 'employee_type_name',
            'employee_number', 'hire_date', 'effective_start_date', 'effective_end_date',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'person_id', 'person_name', 'current_organization', 'current_organization_name',
            'current_position', 'current_position_name', 'employee_type', 'employee_type_name', 
            'created_at', 'updated_at'
        ]

    def get_primary_assignment(self, obj):
        # Use cache from prefetch if available
        if hasattr(obj.person, 'primary_assignments_cache'):
            assignments = obj.person.primary_assignments_cache
            return assignments[0] if assignments else None
        
        # Fallback to query
        return AssignmentService.get_primary_assignment(obj.person_id)

    def get_current_organization(self, obj):
        assignment = self.get_primary_assignment(obj)
        return assignment.department.id if assignment and assignment.department else None

    def get_current_organization_name(self, obj):
        assignment = self.get_primary_assignment(obj)
        if assignment and assignment.department:
            return assignment.department.organization_name
        return None

    def get_current_position(self, obj):
        assignment = self.get_primary_assignment(obj)
        return assignment.position.id if assignment and assignment.position else None

    def get_current_position_name(self, obj):
        assignment = self.get_primary_assignment(obj)
        if assignment and assignment.position and assignment.position.position_title:
            return assignment.position.position_title.name
        return None


class EmployeeCreateSerializer(serializers.Serializer):
    """Write serializer for creating an employee using Person identity"""
    # Link to existing person
    person_id = serializers.IntegerField(required=False, allow_null=True)
    
    # Or create new person
    person_details = PersonSerializer(required=False)
    
    # Employee-specific fields
    employee_type_id = serializers.IntegerField()
    employee_number = serializers.CharField(required=False)
    effective_start_date = serializers.DateField()
    hire_date = serializers.DateField(required=False)

    def validate_person_id(self, value):
        if value:
            try:
                Person.objects.get(pk=value)
            except Person.DoesNotExist:
                raise serializers.ValidationError("Person not found")
        return value

    def validate_employee_type_id(self, value):
        try:
            PersonType.objects.get(pk=value, base_type='EMP', is_active=True)
        except PersonType.DoesNotExist:
            raise serializers.ValidationError("Invalid employee type")
        return value

    def validate(self, attrs):
        if not attrs.get('person_id') and not attrs.get('person_details'):
            raise serializers.ValidationError("Either person_id or person_details must be provided")
        return attrs

    def to_dto(self):
        data = self.validated_data.copy()
        person_details = data.pop('person_details', {})
        # Flatten person details into DTO fields
        for key, value in person_details.items():
            data[key] = value
            
        if 'hire_date' not in data or not data['hire_date']:
            data['hire_date'] = data['effective_start_date']
            
        # Default missing optional person fields to None for DTO
        return EmployeeCreateDTO(**data)


class EmployeeUpdateSerializer(serializers.Serializer):
    """Write serializer for updating an employee and their personal details"""
    employee_id = serializers.IntegerField()
    employee_type_id = serializers.IntegerField(required=False)
    hire_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)

    # Re-use PersonUpdateSerializer for personal details updates
    person_details = PersonUpdateSerializer(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bind the person instance to the nested serializer so uniqueness checks exclude it
        if self.instance:
            self.fields['person_details'].instance = self.instance.person

    def validate_employee_id(self, value):
        if not Employee.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Employee not found")
        return value

    def validate_employee_type_id(self, value):
        if value and not PersonType.objects.filter(pk=value, base_type='EMP', is_active=True).exists():
            raise serializers.ValidationError("Invalid employee type")
        return value

    def to_dto(self):
        data = self.validated_data.copy()
        person_details = data.pop('person_details', {})
        # Flatten person details into DTO fields
        for key, value in person_details.items():
            data[key] = value
            
        if 'end_date' in data:
            data['effective_end_date'] = data.pop('end_date')
            
        return EmployeeUpdateDTO(**data)
