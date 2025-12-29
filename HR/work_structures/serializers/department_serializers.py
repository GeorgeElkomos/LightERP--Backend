import re
from rest_framework import serializers
from HR.work_structures.models import Department, DepartmentManager, BusinessGroup, Location
from HR.work_structures.dtos import DepartmentCreateDTO, DepartmentUpdateDTO


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Department model (list/retrieve).
    Code is auto-generated from name if not provided (scoped to business group).
    Code cannot be changed after creation.
    """
    business_group_name = serializers.CharField(source='business_group.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    parent_code = serializers.CharField(source='parent.code', read_only=True, allow_null=True)
    
    class Meta:
        model = Department
        fields = [
            'id',
            'code',
            'name',
            'business_group',  # Changed from business_group_id
            'business_group_name',
            'location',  # Model field name
            'location_name',
            'parent',  # Model field name
            'parent_code',
            'status',
            'effective_start_date',
            'effective_end_date'
        ]
        read_only_fields = ['id', 'business_group_name', 'location_name', 'parent_code', 'code', 'status']


class DepartmentCreateSerializer(serializers.Serializer):
    """
    Serializer for creating departments.
    Code is auto-generated from name if not provided (scoped to business group).
    Access control for code editing is handled by role-based permissions.
    
    Supports flexible lookups for FK fields:
    - business_group (ID) or business_group_code (string)
    - location (ID) or location_code (string)
    - parent (ID) or parent_code (string)
    """
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    name = serializers.CharField(max_length=128)
    
    # Business Group - ID or code lookup
    business_group = serializers.IntegerField(required=False, allow_null=True)
    business_group_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Location - ID or code lookup
    location = serializers.IntegerField(required=False, allow_null=True)
    location_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Parent - ID or code lookup
    parent = serializers.IntegerField(required=False, allow_null=True)
    parent_code = serializers.CharField(max_length=50, required=False, allow_blank=True, write_only=True)
    
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value
    
    def validate(self, data):
        """Convert code lookups to IDs for all FK fields"""        
        # Business Group: code → ID
        business_group_code = data.pop('business_group_code', None)
        if business_group_code and not data.get('business_group'):
            try:
                bg = BusinessGroup.objects.filter(code=business_group_code).active().first()
                if not bg:
                    raise BusinessGroup.DoesNotExist
                data['business_group'] = bg.id
            except BusinessGroup.DoesNotExist:
                raise serializers.ValidationError({
                    'business_group_code': f"No active business group found with code '{business_group_code}'"
                })
        
        if not data.get('business_group'):
            raise serializers.ValidationError({'business_group': 'Either business_group or business_group_code is required.'})
        
        business_group_id = data['business_group']
        
        # Location: code → ID
        location_code = data.pop('location_code', None)
        if location_code and not data.get('location'):
            try:
                loc = Location.objects.filter(status='active').get(code=location_code)
                data['location'] = loc.id
            except Location.DoesNotExist:
                raise serializers.ValidationError({
                    'location_code': f"No active location found with code '{location_code}'"
                })
        
        if not data.get('location'):
            raise serializers.ValidationError({'location': 'Either location or location_code is required.'})
        
        # Parent: code → ID (optional)
        parent_code = data.pop('parent_code', None)
        if parent_code and not data.get('parent'):
            # Look up parent by code within the same business group
            parent_dept = Department.objects.filter(
                code=parent_code,
                business_group_id=business_group_id,
                effective_end_date__isnull=True
            ).first()
            
            if not parent_dept:
                raise serializers.ValidationError({
                    'parent_code': f"No active department with code '{parent_code}' found in this business group."
                })
            
            data['parent'] = parent_dept.id
        
        return data

    def to_dto(self):
        # Convert model field names to DTO field names (with _id suffix)
        dto_data = {
            'code': self.validated_data.get('code', ''),
            'name': self.validated_data['name'],
            'business_group_id': self.validated_data['business_group'],
            'location_id': self.validated_data['location'],
            'parent_id': self.validated_data.get('parent'),
            'effective_start_date': self.validated_data.get('effective_start_date'),
            'effective_end_date': self.validated_data.get('effective_end_date'),
        }
        return DepartmentCreateDTO(**dto_data)

class DepartmentUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating departments.
    Code cannot be changed after creation (identifies the department).
    Access control is handled by role-based permissions.
    
    Supports flexible lookups for FK fields:
    - location (ID) or location_code (string)
    - parent (ID) or parent_code (string)
    
    Update modes:
    1. Version creation: Provide effective_start_date + field changes to create new version
    2. Direct update: Provide effective_end_date to modify existing record's end date
    """
    code = serializers.CharField(max_length=50, read_only=True)
    name = serializers.CharField(max_length=128, required=False)
    
    # Location - ID or code lookup
    location = serializers.IntegerField(required=False, allow_null=True)
    location_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Parent - ID or code lookup
    parent = serializers.IntegerField(required=False, allow_null=True)
    parent_code = serializers.CharField(max_length=50, required=False, allow_blank=True, write_only=True)
    
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """Convert code lookups to IDs for all FK fields"""        
        # Location: code → ID
        location_code = data.pop('location_code', None)
        if location_code and not data.get('location'):
            try:
                loc = Location.objects.filter(status='active').get(code=location_code)
                data['location'] = loc.id
            except Location.DoesNotExist:
                raise serializers.ValidationError({
                    'location_code': f"No active location found with code '{location_code}'"
                })
        
        # Parent: code → ID (optional)
        parent_code = data.pop('parent_code', None)
        if parent_code and not data.get('parent'):
            # Look up parent by code (active departments only)
            parent_dept = Department.objects.filter(
                code=parent_code,
                effective_end_date__isnull=True
            ).first()
            
            if not parent_dept:
                raise serializers.ValidationError({
                    'parent_code': f"No active department with code '{parent_code}' found."
                })
            
            data['parent'] = parent_dept.id
        
        return data

    def to_dto(self, code=None):
        # Convert model field names to DTO field names (with _id suffix)
        dto_data = {'code': code} if code else {}
        
        # Track which fields were explicitly provided
        provided_fields = set()
        
        if 'name' in self.validated_data:
            dto_data['name'] = self.validated_data['name']
            provided_fields.add('name')
        if 'location' in self.validated_data:
            dto_data['location_id'] = self.validated_data['location']
            provided_fields.add('location_id')
        # Include parent_id even if None (to allow clearing parent)
        if 'parent' in self.validated_data:
            dto_data['parent_id'] = self.validated_data['parent']
            provided_fields.add('parent_id')
        
        if 'effective_start_date' in self.validated_data:
            dto_data['effective_start_date'] = self.validated_data['effective_start_date']
            provided_fields.add('effective_start_date')
        if 'effective_end_date' in self.validated_data:
            dto_data['effective_end_date'] = self.validated_data['effective_end_date']
            provided_fields.add('effective_end_date')
        
        dto = DepartmentUpdateDTO(**dto_data)
        # Add marker for provided fields
        dto._provided_fields = provided_fields
        return dto


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
            'effective_end_date',
            'status'
        ]
        read_only_fields = ['id', 'code', 'department_name', 'manager_name', 'status']

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
