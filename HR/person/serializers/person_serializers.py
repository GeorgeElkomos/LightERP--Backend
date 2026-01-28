"""
Serializers for Person model (managed parent)
"""
from rest_framework import serializers
from HR.person.models import Person


class PersonSerializer(serializers.ModelSerializer):
    """Read serializer for Person model"""

    class Meta:
        model = Person
        fields = [
            'id', 
            'first_name', 'middle_name', 'last_name', 'full_name',
            'first_name_arabic', 'middle_name_arabic', 'last_name_arabic', 'title',
            'date_of_birth', 'gender',
            'marital_status',
            'nationality',
            'national_id',
            'religion', 'blood_type',
            'email_address',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'full_name', 
            'created_at', 'updated_at'
        ]


class PersonUpdateSerializer(PersonSerializer):
    """Update serializer for Person model with all fields optional"""
    class Meta(PersonSerializer.Meta):
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'email_address': {'required': False},
            'date_of_birth': {'required': False},
            'gender': {'required': False},
            'nationality': {'required': False},
            'marital_status': {'required': False},
        }

