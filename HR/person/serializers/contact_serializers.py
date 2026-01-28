"""
Serializers for Contact model
"""
from rest_framework import serializers
from HR.person.models import Contact, Person, PersonType
from HR.person.dtos import ContactUpdateDTO
from datetime import date

class ContactSerializer(serializers.ModelSerializer):
    """Read serializer for Contact model"""
    person_name = serializers.CharField(source='person.full_name', read_only=True)
    contact_type_name = serializers.CharField(source='contact_type.name', read_only=True)
    
    # Person details (since Contact is a child, we want to see person details)
    first_name = serializers.CharField(source='person.first_name', read_only=True)
    last_name = serializers.CharField(source='person.last_name', read_only=True)
    email_address = serializers.CharField(source='person.email_address', read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            'id', 'person', 'person_name',
            'first_name', 'last_name', 'email_address',
            'contact_type', 'contact_type_name',
            'contact_number',
            'organization_name', 'job_title',
            'relationship_to_company',
            'preferred_contact_method',
            'emergency_for_employee', 'emergency_relationship',
            'is_primary_contact',
            'effective_start_date', 'effective_end_date',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'person_name', 'contact_type_name', 
            'first_name', 'last_name', 'email_address',
            'created_at', 'updated_at'
        ]

class ContactCreateSerializer(serializers.Serializer):
    """Write serializer for creating a new contact (and person)"""
    # Person fields
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email_address = serializers.EmailField()
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')])
    nationality = serializers.CharField(max_length=100)
    marital_status = serializers.ChoiceField(choices=[('Single', 'Single'), ('Married', 'Married'), ('Divorced', 'Divorced'), ('Widowed', 'Widowed')])
    
    # Contact fields
    contact_type_id = serializers.IntegerField()
    contact_number = serializers.CharField(max_length=50)
    organization_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=100, required=False, allow_blank=True)
    relationship_to_company = serializers.CharField(max_length=100, required=False, allow_blank=True)
    preferred_contact_method = serializers.ChoiceField(choices=['email', 'phone', 'sms', 'mail'], required=False)
    
    effective_start_date = serializers.DateField(required=False)

    def validate_contact_type_id(self, value):
        try:
            PersonType.objects.get(pk=value, base_type='CON', is_active=True)
        except PersonType.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive contact type")
        return value

    def to_data(self):
        """Convert validated data to (person_data, contact_data) tuple for service"""
        data = self.validated_data
        person_data = {
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'email_address': data['email_address'],
            'date_of_birth': data['date_of_birth'],
            'gender': data['gender'],
            'nationality': data['nationality'],
            'marital_status': data['marital_status']
        }
        contact_data = {
            'contact_type': PersonType.objects.get(pk=data['contact_type_id']),
            'contact_number': data['contact_number'],
            'organization_name': data.get('organization_name'),
            'job_title': data.get('job_title'),
            'relationship_to_company': data.get('relationship_to_company'),
            'preferred_contact_method': data.get('preferred_contact_method')
        }
        start_date = data.get('effective_start_date')
        return person_data, contact_data, start_date

class ContactUpdateSerializer(serializers.Serializer):
    """Write serializer for updating a contact"""
    contact_id = serializers.IntegerField()
    contact_type_id = serializers.IntegerField(required=False)
    organization_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=100, required=False, allow_blank=True)
    relationship_to_company = serializers.CharField(max_length=100, required=False, allow_blank=True)
    preferred_contact_method = serializers.ChoiceField(choices=['email', 'phone', 'sms', 'mail'], required=False)
    emergency_relationship = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_primary_contact = serializers.BooleanField(required=False)
    
    effective_start_date = serializers.DateField(required=False)
    effective_end_date = serializers.DateField(required=False)

    def validate_contact_id(self, value):
        try:
            Contact.objects.get(pk=value)
        except Contact.DoesNotExist:
            raise serializers.ValidationError("Contact not found")
        return value

    def validate_contact_type_id(self, value):
        if value is None:
            return value
        try:
            PersonType.objects.get(pk=value, base_type='CON', is_active=True)
        except PersonType.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive contact type")
        return value

    def to_dto(self):
        return ContactUpdateDTO(**self.validated_data)
