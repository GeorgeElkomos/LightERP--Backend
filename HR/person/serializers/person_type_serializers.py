from rest_framework import serializers
from HR.person.models import PersonType
from HR.person.dtos import PersonTypeCreateDTO

class PersonTypeSerializer(serializers.ModelSerializer):
    """Serializer for PersonType model"""
    class Meta:
        model = PersonType
        fields = ['id', 'code', 'name', 'description', 'base_type', 'is_active']

class PersonTypeCreateSerializer(serializers.Serializer):
    """Serializer for creating PersonType"""
    code = serializers.CharField(max_length=50, required=True)
    name = serializers.CharField(max_length=128, required=True)
    base_type = serializers.ChoiceField(choices=PersonType.BASE_TYPE_CHOICES, required=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    is_active = serializers.BooleanField(required=False, default=True)

    def to_dto(self) -> PersonTypeCreateDTO:
        return PersonTypeCreateDTO(
            code=self.validated_data['code'],
            name=self.validated_data['name'],
            base_type=self.validated_data['base_type'],
            description=self.validated_data.get('description', ''),
            is_active=self.validated_data.get('is_active', True)
        )
