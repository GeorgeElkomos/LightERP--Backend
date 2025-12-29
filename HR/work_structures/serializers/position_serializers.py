import re
from rest_framework import serializers
from HR.work_structures.models import Position, Grade, GradeRateType, GradeRate, BusinessGroup, Department, Location
from HR.work_structures.dtos import PositionCreateDTO, PositionUpdateDTO, GradeCreateDTO, GradeUpdateDTO, GradeRateCreateDTO


class PositionSerializer(serializers.ModelSerializer):
    """
    Serializer for Position model (list/retrieve).
    Code is auto-generated from name if not provided.
    Code cannot be changed after creation.
    """
    department_name = serializers.CharField(source='department.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    grade_name = serializers.CharField(source='grade.name', read_only=True)
    reports_to_code = serializers.CharField(source='reports_to.code', read_only=True, allow_null=True)
    reports_to_name = serializers.CharField(source='reports_to.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Position
        fields = [
            'id',
            'code',
            'name',
            'department',
            'department_name',
            'location',
            'location_name',
            'grade',
            'grade_name',
            'reports_to',
            'reports_to_code',
            'reports_to_name',
            'status',
            'effective_start_date',
            'effective_end_date'
        ]
        read_only_fields = [
            'id',
            'code',
            'status',
            'department_name',
            'location_name',
            'grade_name',
            'reports_to_code',
            'reports_to_name'
        ]


class PositionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating positions.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    
    Supports flexible lookups for all FK fields:
    - department (ID) or department_code (string)
    - location (ID) or location_code (string)
    - grade (ID) or grade_code (string)
    - reports_to (ID) or reports_to_code (string)
    """
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    name = serializers.CharField(max_length=128)
    
    # Department - ID or code lookup
    department = serializers.IntegerField(required=False, allow_null=True)
    department_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Location - ID or code lookup
    location = serializers.IntegerField(required=False, allow_null=True)
    location_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Grade - ID or code lookup
    grade = serializers.IntegerField(required=False, allow_null=True)
    grade_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Reports to - ID or code lookup
    reports_to = serializers.IntegerField(required=False, allow_null=True)
    reports_to_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
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
        
        # Department: code → ID
        department_code = data.pop('department_code', None)
        if department_code and not data.get('department'):
            try:
                dept = Department.objects.active().get(code=department_code)
                data['department'] = dept.id
            except Department.DoesNotExist:
                raise serializers.ValidationError({
                    'department_code': f"No active department found with code '{department_code}'"
                })
        
        if not data.get('department'):
            raise serializers.ValidationError({'department': 'Either department or department_code is required.'})
        
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
        
        # Grade: code → ID
        grade_code = data.pop('grade_code', None)
        if grade_code and not data.get('grade'):
            try:
                grade = Grade.objects.active().get(code=grade_code)
                data['grade'] = grade.id
            except Grade.DoesNotExist:
                raise serializers.ValidationError({
                    'grade_code': f"No active grade found with code '{grade_code}'"
                })
        
        if not data.get('grade'):
            raise serializers.ValidationError({'grade': 'Either grade or grade_code is required.'})
        
        # Reports to: code → ID (optional)
        reports_to_code = data.pop('reports_to_code', None)
        if reports_to_code and not data.get('reports_to'):
            try:
                position = Position.objects.active().get(code=reports_to_code)
                data['reports_to'] = position.id
            except Position.DoesNotExist:
                raise serializers.ValidationError({
                    'reports_to_code': f"No active position found with code '{reports_to_code}'"
                })
        
        return data

    def to_dto(self):
        # Convert model field names to DTO field names (with _id suffix)
        dto_data = {
            'code': self.validated_data.get('code', ''),
            'name': self.validated_data['name'],
            'department_id': self.validated_data['department'],
            'location_id': self.validated_data['location'],
            'grade_id': self.validated_data['grade'],
            'reports_to_id': self.validated_data.get('reports_to'),
            'effective_start_date': self.validated_data.get('effective_start_date'),
            'effective_end_date': self.validated_data.get('effective_end_date'),
        }
        return PositionCreateDTO(**dto_data)


class PositionUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating positions.
    Code cannot be changed after creation (identifies the position).
    Access control is handled by role-based permissions.
    
    Supports flexible lookups for all FK fields:
    - department (ID) or department_code (string)
    - location (ID) or location_code (string)
    - grade (ID) or grade_code (string)
    - reports_to (ID) or reports_to_code (string)
    
    Update modes:
    1. Version creation: Provide effective_start_date + field changes to create new version
    2. Direct update: Provide effective_end_date to modify existing record's end date
    """
    code = serializers.CharField(max_length=50, read_only=True)
    name = serializers.CharField(max_length=128, required=False)
    
    # Department - ID or code lookup
    department = serializers.IntegerField(required=False, allow_null=True)
    department_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Location - ID or code lookup
    location = serializers.IntegerField(required=False, allow_null=True)
    location_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Grade - ID or code lookup
    grade = serializers.IntegerField(required=False, allow_null=True)
    grade_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Reports to - ID or code lookup
    reports_to = serializers.IntegerField(required=False, allow_null=True)
    reports_to_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        """Convert code lookups to IDs for all FK fields"""        
        # Department: code → ID
        department_code = data.pop('department_code', None)
        if department_code and not data.get('department'):
            try:
                dept = Department.objects.active().get(code=department_code)
                data['department'] = dept.id
            except Department.DoesNotExist:
                raise serializers.ValidationError({
                    'department_code': f"No active department found with code '{department_code}'"
                })
        
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
        
        # Grade: code → ID
        grade_code = data.pop('grade_code', None)
        if grade_code and not data.get('grade'):
            try:
                grade = Grade.objects.active().get(code=grade_code)
                data['grade'] = grade.id
            except Grade.DoesNotExist:
                raise serializers.ValidationError({
                    'grade_code': f"No active grade found with code '{grade_code}'"
                })
        
        # Reports to: code → ID (optional)
        reports_to_code = data.pop('reports_to_code', None)
        if reports_to_code and not data.get('reports_to'):
            try:
                position = Position.objects.active().get(code=reports_to_code)
                data['reports_to'] = position.id
            except Position.DoesNotExist:
                raise serializers.ValidationError({
                    'reports_to_code': f"No active position found with code '{reports_to_code}'"
                })
        
        return data

    def to_dto(self, code=None):
        # Convert model field names to DTO field names (with _id suffix)
        dto_data = {'code': code} if code else {}
        
        # Track which fields were explicitly provided
        provided_fields = set()
        
        if 'name' in self.validated_data:
            dto_data['name'] = self.validated_data['name']
            provided_fields.add('name')
        if 'department' in self.validated_data:
            dto_data['department_id'] = self.validated_data['department']
            provided_fields.add('department_id')
        if 'location' in self.validated_data:
            dto_data['location_id'] = self.validated_data['location']
            provided_fields.add('location_id')
        if 'grade' in self.validated_data:
            dto_data['grade_id'] = self.validated_data['grade']
            provided_fields.add('grade_id')
        if 'reports_to' in self.validated_data:
            dto_data['reports_to_id'] = self.validated_data['reports_to']
            provided_fields.add('reports_to_id')
            
        if 'effective_start_date' in self.validated_data:
            dto_data['effective_start_date'] = self.validated_data['effective_start_date']
            provided_fields.add('effective_start_date')
        if 'effective_end_date' in self.validated_data:
            dto_data['effective_end_date'] = self.validated_data['effective_end_date']
            provided_fields.add('effective_end_date')
        
        dto = PositionUpdateDTO(**dto_data)
        # Add marker for provided fields
        dto._provided_fields = provided_fields
        return dto


class GradeSerializer(serializers.ModelSerializer):
    """
    Serializer for Grade model (list/retrieve).
    Code is auto-generated from name if not provided.
    Code cannot be changed after creation.
    """
    business_group_name = serializers.CharField(source='business_group.name', read_only=True)
    rates = serializers.SerializerMethodField()
    
    class Meta:
        model = Grade
        fields = [
            'id',
            'code',
            'name',
            'business_group',
            'business_group_name',
            'effective_start_date',
            'effective_end_date',
            'status',
            'rates'
        ]
        read_only_fields = ['id', 'business_group_name', 'rates', 'code', 'status']

    def get_rates(self, obj):
        rates = obj.rate_levels.all()
        return GradeRateSerializer(rates, many=True).data


class GradeCreateSerializer(serializers.Serializer):
    """
    Serializer for creating grades.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    
    Supports flexible lookups for FK fields:
    - business_group (ID) or business_group_code (string)
    """
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    name = serializers.CharField(max_length=128)
    
    # Business Group - ID or code lookup
    business_group = serializers.IntegerField(required=False, allow_null=True)
    business_group_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
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
        
        return data

    def to_dto(self):
        # Convert model field names to DTO field names (with _id suffix)
        dto_data = {
            'code': self.validated_data.get('code', ''),
            'name': self.validated_data['name'],
            'business_group_id': self.validated_data['business_group'],
            'effective_start_date': self.validated_data.get('effective_start_date'),
            'effective_end_date': self.validated_data.get('effective_end_date'),
        }
        return GradeCreateDTO(**dto_data)


class GradeUpdateSerializer(serializers.Serializer):
    """Serializer for updating Grade (creating new version)"""
    name = serializers.CharField(max_length=128, required=False)
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self, code):
        provided_fields = set()
        for field in ['name', 'effective_start_date', 'effective_end_date']:
            if field in self.validated_data:
                provided_fields.add(field)
        
        dto = GradeUpdateDTO(
            code=code,
            name=self.validated_data.get('name'),
            effective_start_date=self.validated_data.get('effective_start_date'),
            effective_end_date=self.validated_data.get('effective_end_date')
        )
        dto._provided_fields = provided_fields
        return dto


class GradeRateTypeSerializer(serializers.ModelSerializer):
    """Serializer for Grade Rate Types"""
    
    class Meta:
        model = GradeRateType
        fields = [
            'id',
            'code',
            'name',
            'has_range',
            'description'
        ]
        read_only_fields = ['id']


class GradeRateSerializer(serializers.ModelSerializer):
    """Serializer for Grade Rate Levels with version history"""
    rate_type_name = serializers.CharField(source='rate_type.name', read_only=True)
    rate_type_code = serializers.CharField(source='rate_type.code', read_only=True)
    rate_type_has_range = serializers.BooleanField(source='rate_type.has_range', read_only=True)
    
    class Meta:
        model = GradeRate
        fields = [
            'id',
            'grade',
            'rate_type',
            'rate_type_name',
            'rate_type_code',
            'rate_type_has_range',
            'min_amount',
            'max_amount',
            'fixed_amount',
            'currency',
            'effective_start_date',
            'effective_end_date',
            'status'
        ]
        read_only_fields = ['id', 'status', 'rate_type_name', 'rate_type_code', 'rate_type_has_range']


class GradeRateCreateSerializer(serializers.Serializer):
    """
    Serializer for creating grade rate levels.
    
    Supports flexible lookups for FK fields:
    - grade (ID) or grade_code (string)
    - rate_type (ID) or rate_type_code (string)
    
    Validates data based on whether rate_type.has_range is True or False:
    - If has_range=True: requires min_amount and max_amount
    - If has_range=False: requires fixed_amount
    """
    # Grade - ID or code lookup
    grade = serializers.IntegerField(required=False, allow_null=True)
    grade_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Rate Type - ID or code lookup
    rate_type = serializers.IntegerField(required=False, allow_null=True)
    rate_type_code = serializers.CharField(max_length=50, required=False, allow_null=True, write_only=True)
    
    # Range-based fields
    min_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    max_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    
    # Fixed-value field
    fixed_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    
    currency = serializers.CharField(max_length=3, default='EGP')
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """Convert code lookups to IDs and validate based on rate type"""
        # Grade: code → ID
        grade_code = data.pop('grade_code', None)
        if grade_code and not data.get('grade'):
            try:
                grade = Grade.objects.active().get(code=grade_code)
                data['grade'] = grade.id
            except Grade.DoesNotExist:
                raise serializers.ValidationError({
                    'grade_code': f"No active grade found with code '{grade_code}'"
                })
        
        if not data.get('grade'):
            raise serializers.ValidationError({'grade': 'Either grade or grade_code is required.'})
        
        # Rate Type: code → ID
        rate_type_code = data.pop('rate_type_code', None)
        if rate_type_code and not data.get('rate_type'):
            try:
                rate_type = GradeRateType.objects.get(code=rate_type_code)
                data['rate_type'] = rate_type.id
            except GradeRateType.DoesNotExist:
                raise serializers.ValidationError({
                    'rate_type_code': f"No rate type found with code '{rate_type_code}'"
                })
        
        if not data.get('rate_type'):
            raise serializers.ValidationError({'rate_type': 'Either rate_type or rate_type_code is required.'})
        
        # Validate amounts based on rate type
        rate_type = GradeRateType.objects.get(id=data['rate_type'])
        
        if rate_type.has_range:
            # Range-based: require min and max
            if data.get('min_amount') is None or data.get('max_amount') is None:
                raise serializers.ValidationError({
                    'rate_type': f"Rate type '{rate_type.name}' requires both min_amount and max_amount"
                })
            if data.get('fixed_amount') is not None:
                raise serializers.ValidationError({
                    'fixed_amount': "Range-based rates should not have fixed_amount"
                })
        else:
            # Fixed-value: require fixed amount
            if data.get('fixed_amount') is None:
                raise serializers.ValidationError({
                    'rate_type': f"Rate type '{rate_type.name}' requires fixed_amount"
                })
            if data.get('min_amount') is not None or data.get('max_amount') is not None:
                raise serializers.ValidationError({
                    'min_amount': "Fixed-value rates should not have min_amount or max_amount"
                })
        
        return data

    def to_dto(self):
        # Convert model field names to DTO field names (with _id suffix)
        dto_data = {
            'grade_id': self.validated_data['grade'],
            'rate_type_id': self.validated_data['rate_type'],
            'min_amount': self.validated_data.get('min_amount'),
            'max_amount': self.validated_data.get('max_amount'),
            'fixed_amount': self.validated_data.get('fixed_amount'),
            'currency': self.validated_data.get('currency', 'EGP'),
            'effective_start_date': self.validated_data.get('effective_start_date'),
            'effective_end_date': self.validated_data.get('effective_end_date'),
        }
        return GradeRateCreateDTO(**dto_data)
