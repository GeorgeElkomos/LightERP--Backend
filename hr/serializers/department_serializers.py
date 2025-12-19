import re
from rest_framework import serializers
from hr.models import Department, DepartmentManager
from hr.dtos import DepartmentCreateDTO, DepartmentUpdateDTO


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Department model.
    Code is auto-generated from name if not provided (scoped to business group).
    Access control for code editing is handled by role-based permissions.
    """
    business_group_name = serializers.CharField(source='business_group.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    parent_code = serializers.CharField(source='parent.code', read_only=True, allow_null=True)
    code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Department
        fields = [
            'id',
            'code',
            'name',
            'business_group',
            'business_group_name',
            'location',
            'location_name',
            'parent',
            'parent_code',
            'status',
            'effective_start_date',
            'effective_end_date'
        ]
        read_only_fields = ['id', 'business_group_name', 'location_name', 'parent_code']

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value


class DepartmentCreateSerializer(serializers.Serializer):
    """
    Serializer for creating departments.
    Code is auto-generated from name if not provided (scoped to business group).
    Access control for code editing is handled by role-based permissions.
    """
    business_group_id = serializers.IntegerField()
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    name = serializers.CharField(max_length=128)
    location_id = serializers.IntegerField()
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    effective_start_date = serializers.DateField(required=False, allow_null=True)

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value

    def to_dto(self):
        return DepartmentCreateDTO(**self.validated_data)


class DepartmentUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating departments.
    Code cannot be changed after creation (identifies the department).
    Access control is handled by role-based permissions.
    """
    code = serializers.CharField(max_length=50, read_only=True)
    name = serializers.CharField(max_length=128, required=False)
    location_id = serializers.IntegerField(required=False)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    effective_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self, code=None):
        data = self.validated_data.copy()
        if code:
            data['code'] = code
        return DepartmentUpdateDTO(**data)


class DepartmentManagerSerializer(serializers.ModelSerializer):
    """Serializer for Department Manager assignments"""
    code = serializers.CharField(source='department.code', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    manager_name = serializers.CharField(source='manager.name', read_only=True)
    
    class Meta:
        model = DepartmentManager
        fields = [
            'id',
            'department',
            'code',
            'department_name',
            'manager',
            'manager_name',
            'effective_start_date',
            'effective_end_date'
        ]
        read_only_fields = ['id', 'code', 'department_name', 'manager_name']

    def validate(self, attrs):
        """Validate manager has an Employee record and is active on assignment date, if Employee model exists."""
        try:
            effective_start = attrs.get('effective_start_date')
            manager = attrs.get('manager')
            temp = DepartmentManager(
                department=attrs.get('department') or None,
                manager=manager,
                effective_start_date=effective_start
            )
            temp.clean()
        except Exception as e:
            raise serializers.ValidationError({'manager': str(e)})
        return attrs
