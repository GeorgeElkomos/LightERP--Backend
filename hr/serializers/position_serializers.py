import re
from rest_framework import serializers
from hr.models import Position, Grade, GradeRate
from hr.dtos import PositionCreateDTO, PositionUpdateDTO, GradeCreateDTO, GradeRateCreateDTO


class PositionSerializer(serializers.ModelSerializer):
    """
    Serializer for Position model.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    """
    department_name = serializers.CharField(source='department.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    grade_name = serializers.CharField(source='grade.name', read_only=True)
    reports_to_code = serializers.CharField(source='reports_to.code', read_only=True, allow_null=True)
    reports_to_name = serializers.CharField(source='reports_to.name', read_only=True, allow_null=True)
    code = serializers.CharField(required=False, allow_blank=True)
    
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
            'department_name',
            'location_name',
            'grade_name',
            'reports_to_code',
            'reports_to_name'
        ]

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value


class PositionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating positions.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    """
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    name = serializers.CharField(max_length=128)
    department_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    grade_id = serializers.IntegerField()
    reports_to_id = serializers.IntegerField(required=False, allow_null=True)
    effective_start_date = serializers.DateField(required=False, allow_null=True)

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value

    def to_dto(self):
        return PositionCreateDTO(**self.validated_data)


class PositionUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating positions.
    Code cannot be changed after creation (identifies the position).
    Access control is handled by role-based permissions.
    """
    code = serializers.CharField(max_length=50, read_only=True)
    name = serializers.CharField(max_length=128, required=False)
    department_id = serializers.IntegerField(required=False)
    location_id = serializers.IntegerField(required=False)
    grade_id = serializers.IntegerField(required=False)
    reports_to_id = serializers.IntegerField(required=False, allow_null=True)
    effective_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self, code=None):
        data = self.validated_data.copy()
        if code:
            data['code'] = code
        return PositionUpdateDTO(**data)


class GradeSerializer(serializers.ModelSerializer):
    """
    Serializer for Grade model.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    """
    business_group_name = serializers.CharField(source='business_group.name', read_only=True)
    rates = serializers.SerializerMethodField()
    code = serializers.CharField(required=False, allow_blank=True)
    
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
            'rates'
        ]
        read_only_fields = ['id', 'business_group_name', 'rates']

    def get_rates(self, obj):
        rates = obj.rates.all()
        return GradeRateSerializer(rates, many=True).data

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value


class GradeCreateSerializer(serializers.Serializer):
    """
    Serializer for creating grades.
    Code is auto-generated from name if not provided.
    Access control for code editing is handled by role-based permissions.
    """
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    name = serializers.CharField(max_length=128)
    business_group_id = serializers.IntegerField()
    effective_start_date = serializers.DateField(required=False, allow_null=True)

    def validate_code(self, value):
        """Validate code format when manually provided"""
        if value and not re.match(r'^[A-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Invalid code format. Use uppercase letters, numbers, and underscores only."
            )
        return value

    def to_dto(self):
        return GradeCreateDTO(**self.validated_data)


class GradeRateSerializer(serializers.ModelSerializer):
    """Serializer for Grade Rates"""
    
    class Meta:
        model = GradeRate
        fields = [
            'id',
            'grade',
            'rate_type',
            'amount',
            'currency',
            'effective_start_date',
            'effective_end_date'
        ]
        read_only_fields = ['id']


class GradeRateCreateSerializer(serializers.Serializer):
    """Serializer for creating grade rates"""
    grade_id = serializers.IntegerField()
    rate_type = serializers.CharField(max_length=50)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField(max_length=3, default='EGP')
    effective_start_date = serializers.DateField(required=False, allow_null=True)
    effective_end_date = serializers.DateField(required=False, allow_null=True)

    def to_dto(self):
        return GradeRateCreateDTO(**self.validated_data)
