"""
Contact Service - Business Logic Layer

Handles all contact lifecycle workflows:
- Creating contact relationships
- Managing emergency contacts
- Deactivating contacts

All contact state transitions MUST go through this service.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date
from HR.person.models import Contact, Employee, PersonType
from HR.person.dtos import ContactUpdateDTO


class ContactService:
    """Service layer for contact lifecycle management"""

    @staticmethod
    @transaction.atomic
    def update(user, dto: ContactUpdateDTO) -> Contact:
        """
        Update contact details.
        
        Args:
            user: User performing the action
            dto: ContactUpdateDTO
            
        Returns:
            Contact: Updated contact
        """
        contact = Contact.objects.get(pk=dto.contact_id)
        
        field_updates = {}
        
        # Update contact type if provided
        if dto.contact_type_id:
            try:
                contact_type = PersonType.objects.get(
                    pk=dto.contact_type_id,
                    base_type='CON',
                    is_active=True
                )
                field_updates['contact_type'] = contact_type
            except PersonType.DoesNotExist:
                raise ValidationError({'contact_type_id': 'Invalid or inactive contact type'})
                
        # Update other fields
        if dto.organization_name is not None:
            field_updates['organization_name'] = dto.organization_name
        if dto.job_title is not None:
            field_updates['job_title'] = dto.job_title
        if dto.relationship_to_company is not None:
            field_updates['relationship_to_company'] = dto.relationship_to_company
        if dto.preferred_contact_method is not None:
            field_updates['preferred_contact_method'] = dto.preferred_contact_method
        if dto.emergency_relationship is not None:
            field_updates['emergency_relationship'] = dto.emergency_relationship
        if dto.is_primary_contact is not None:
            field_updates['is_primary_contact'] = dto.is_primary_contact
            
            # Handle primary flag logic
            if dto.is_primary_contact and contact.emergency_for_employee:
                ContactService._unset_primary_emergency_contacts(contact.emergency_for_employee)

        # Use VersionedMixin's update_version
        # Since Contact is versioned, we should use update_version to handle effective dates
        updated_contact = contact.update_version(
            field_updates=field_updates,
            new_start_date=dto.effective_start_date, # If provided, might trigger new version
            new_end_date=dto.effective_end_date
        )
        
        updated_contact.updated_by = user
        updated_contact.save(update_fields=['updated_by'])
        return updated_contact

    @staticmethod
    @transaction.atomic
    def create_contact(person_data, contact_data, effective_start_date=None):
        """
        Create new contact relationship.
        
        Args:
            person_data: Dict with person fields (first_name, email_address, etc.)
            contact_data: Dict with contact_type, contact_number, etc.
                {
                    'contact_type': PersonType,
                    'contact_number': str,
                    'organization_name': str (optional),
                    'job_title': str (optional),
                    'relationship_to_company': str (optional),
                    'preferred_contact_method': str (optional)
                }
            effective_start_date: Date contact relationship started (default: today)
        
        Returns:
            Contact: Newly created contact record
        """
        if effective_start_date is None:
            effective_start_date = date.today()

        # Merge data for ChildModelMixin
        combined_data = {
            **person_data,
            'contact_type': contact_data['contact_type'],
            'contact_number': contact_data['contact_number'],
            'effective_start_date': effective_start_date,
            'organization_name': contact_data.get('organization_name', ''),
            'job_title': contact_data.get('job_title', ''),
            'relationship_to_company': contact_data.get('relationship_to_company', ''),
            'preferred_contact_method': contact_data.get('preferred_contact_method', ''),
            'is_primary_contact': False  # Default
        }

        contact = Contact.objects.create(**combined_data)
        return contact

    @staticmethod
    @transaction.atomic
    def add_emergency_contact(employee_id, person_data, contact_data, relationship, is_primary=False):
        """
        Add emergency contact for an employee.
        
        Args:
            employee_id: Employee record ID
            person_data: Dict with person fields (first_name, phone, etc.)
            contact_data: Dict with contact_type, contact_number
            relationship: Relationship to employee (spouse, parent, sibling, etc.)
            is_primary: Is this the primary emergency contact?
        
        Returns:
            Contact: Newly created emergency contact record
        """
        employee = Employee.objects.get(pk=employee_id)

        # If setting as primary, unset other primary contacts
        if is_primary:
            ContactService._unset_primary_emergency_contacts(employee)

        # Create emergency contact
        combined_data = {
            **person_data,
            'contact_type': contact_data['contact_type'],
            'contact_number': contact_data['contact_number'],
            'effective_start_date': date.today(),
            'emergency_for_employee': employee,
            'emergency_relationship': relationship,
            'is_primary_contact': is_primary
        }

        contact = Contact.objects.create(**combined_data)
        return contact

    @staticmethod
    @transaction.atomic
    def set_primary_emergency_contact(contact_id):
        """
        Set a contact as the primary emergency contact.
        Unsets any other primary contacts for the same employee.
        
        Args:
            contact_id: Contact record ID
        
        Returns:
            Contact: Updated contact record
        """
        contact = Contact.objects.get(pk=contact_id)

        if not contact.emergency_for_employee:
            raise ValidationError("Contact is not an emergency contact")

        # Unset other primary contacts
        ContactService._unset_primary_emergency_contacts(contact.emergency_for_employee)

        # Set this as primary
        contact.is_primary_contact = True
        contact.save()

        return contact

    @staticmethod
    def _unset_primary_emergency_contacts(employee):
        """
        Helper: Unset all primary emergency contacts for an employee.
        
        Args:
            employee: Employee instance
        """
        Contact.objects.filter(
            emergency_for_employee=employee,
            is_primary_contact=True
        ).update(is_primary_contact=False)

    @staticmethod
    @transaction.atomic
    def deactivate_contact(contact_id, end_date=None):
        """
        End contact relationship.
        
        Args:
            contact_id: Contact record ID
            end_date: Date to end relationship (default: today)
        
        Returns:
            Contact: Updated contact record
        """
        contact = Contact.objects.get(pk=contact_id)

        if end_date is None:
            end_date = date.today()

        # Use VersionedMixin's deactivate method
        contact.deactivate(end_date=end_date)

        return contact

    @staticmethod
    def get_emergency_contacts_for_employee(employee_id, active_only=True):
        """
        Get all emergency contacts for an employee.
        
        Args:
            employee_id: Employee ID
            active_only: Only return active contacts (default: True)
        
        Returns:
            QuerySet of Contact objects (primary contact first)
        """
        contacts = Contact.objects.filter(emergency_for_employee_id=employee_id)

        if active_only:
            today = date.today()
            contacts = contacts.filter(pk__in=Contact.objects.active_on(today).values_list('pk', flat=True))

        return contacts.order_by('-is_primary_contact', 'person__first_name')

    @staticmethod
    def get_active_contacts(as_of_date=None):
        """
        Get all active contacts on a specific date.
        
        Args:
            as_of_date: Reference date (default: today)
        
        Returns:
            QuerySet of Contact objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        return Contact.objects.active_on(as_of_date)

    @staticmethod
    def get_contacts_by_organization(organization_name, as_of_date=None):
        """
        Get all active contacts from a specific organization.
        
        Args:
            organization_name: Organization name
            as_of_date: Reference date (default: today)
        
        Returns:
            QuerySet of Contact objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        return Contact.objects.active_on(as_of_date).filter(
            organization_name__icontains=organization_name
        )
