"""
DFF Service for Person Child Models (Employee, Applicant, ContingentWorker, Contact)

Thin wrapper around core DFFService for person-type-specific convenience.
DFF data is stored on the child model instances (each employee/applicant/worker/contact),
configured based on their type (employee_type, applicant_type, worker_type, contact_type).
"""

from core.dff import DFFService
from HR.person.models import PersonTypeDFFConfig


class PersonTypeDFFService:
    """
    Convenience wrapper for Person child model DFF operations.

    Works with Employee, Applicant, ContingentWorker, Contact instances.
    Each instance stores its own DFF data based on its type.

    Example:
        employee = Employee.objects.get(employee_number='E001')
        # Get DFF data for this specific employee based on their employee_type
        data = PersonTypeDFFService.get_dff_data(employee, 'employee_type')
    """

    @staticmethod
    def get_dff_data(instance, type_field_name):
        """
        Get all DFF field values for a child model instance.

        Args:
            instance: Employee/Applicant/ContingentWorker/Contact instance
            type_field_name: Name of the type field ('employee_type', 'applicant_type', etc.)

        Returns:
            dict: {field_name: value} for all configured DFF fields

        Example:
            >>> employee = Employee.objects.get(employee_number='E001')
            >>> data = PersonTypeDFFService.get_dff_data(employee, 'employee_type')
            >>> print(data)
            {'home_organization': 'Cairo Office', 'secondment_end_date': date(2026, 12, 31)}
        """
        person_type = getattr(instance, type_field_name)
        return DFFService.get_dff_data(
            instance=instance,
            config_model=PersonTypeDFFConfig,
            context_field='person_type__code',
            context_value=person_type.code
        )

    @staticmethod
    def set_dff_data(instance, type_field_name, dff_data):
        """
        Set DFF field values for a child model instance.

        Args:
            instance: Employee/Applicant/ContingentWorker/Contact instance
            type_field_name: Name of the type field ('employee_type', 'applicant_type', etc.)
            dff_data: dict of {field_name: value}

        Raises:
            ValidationError: If validation fails

        Example:
            >>> employee = Employee.objects.get(employee_number='E001')
            >>> PersonTypeDFFService.set_dff_data(employee, 'employee_type', {
            ...     'home_organization': 'Cairo Office',
            ...     'secondment_end_date': date(2026, 12, 31)
            ... })
            >>> employee.save()
        """
        person_type = getattr(instance, type_field_name)
        DFFService.set_dff_data(
            instance=instance,
            config_model=PersonTypeDFFConfig,
            dff_data=dff_data,
            context_field='person_type__code',
            context_value=person_type.code
        )

    @staticmethod
    def clear_dff_data(instance, type_field_name):
        """
        Clear all DFF field values for a child model instance.

        Args:
            instance: Employee/Applicant/ContingentWorker/Contact instance
            type_field_name: Name of the type field ('employee_type', 'applicant_type', etc.)
        """
        person_type = getattr(instance, type_field_name)
        DFFService.clear_dff_data(
            instance=instance,
            config_model=PersonTypeDFFConfig,
            context_field='person_type__code',
            context_value=person_type.code
        )

    @staticmethod
    def get_field_configs(person_type_code):
        """
        Get all DFF field configurations for a person type.

        Args:
            person_type_code: PersonType code

        Returns:
            QuerySet of PersonTypeDFFConfig
        """
        return DFFService.get_field_configs(
            config_model=PersonTypeDFFConfig,
            context_field='person_type__code',
            context_value=person_type_code
        )

