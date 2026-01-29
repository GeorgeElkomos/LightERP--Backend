"""
DFF (Descriptive Flexfield) Service - Core Infrastructure

Generic service for managing DFF data on any model that uses DFFMixin.
Provides validation, type conversion, and CRUD operations for custom fields.

Usage:
    from core.dff.services import DFFService

    # Get DFF data
    data = DFFService.get_dff_data(
        instance=my_person_type,
        config_model=PersonTypeDFFConfig,
        context_field='code'
    )

    # Set DFF data
    DFFService.set_dff_data(
        instance=my_person_type,
        config_model=PersonTypeDFFConfig,
        context_field='code',
        dff_data={'field1': 'value1'}
    )
"""

from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from datetime import date, datetime


class DFFService:
    """Generic service for managing DFF fields on any model with DFFMixin"""

    @staticmethod
    def get_dff_data(instance, config_model, context_field='code', context_value=None):
        """
        Get all DFF field values as a dictionary with logical field names.

        Args:
            instance: Model instance with DFFMixin
            config_model: DFF config model class (e.g., PersonTypeDFFConfig)
            context_field: Field to filter on (can include __ for FK traversal)
            context_value: Value to match (if None, extracted from instance using context_field)

        Returns:
            dict: {field_name: value} for all configured DFF fields

        Example:
            >>> from HR.person.models import PersonType, PersonTypeDFFConfig
            >>> pt = PersonType.objects.get(code='SECONDED_EMP')
            >>> data = DFFService.get_dff_data(pt, PersonTypeDFFConfig, 'person_type__code', pt.code)
            >>> print(data)
            {'home_organization': 'Head Office', 'secondment_end_date': date(2026, 12, 31)}
        """
        if context_value is None:
            context_value = getattr(instance, context_field)

        dff_configs = DFFService._get_active_configs(config_model, context_field, context_value)

        result = {}
        for config in dff_configs:
            # Get value from physical column
            physical_value = getattr(instance, config.column_name, None)

            # Convert to appropriate type if needed
            if physical_value is not None:
                if config.data_type == 'date' and isinstance(physical_value, str):
                    try:
                        physical_value = datetime.strptime(physical_value, '%Y-%m-%d').date()
                    except ValueError:
                        physical_value = None
                elif config.data_type == 'number' and isinstance(physical_value, str):
                    try:
                        physical_value = Decimal(physical_value)
                    except InvalidOperation:
                        physical_value = None

            result[config.field_name] = physical_value

        return result

    @staticmethod
    def set_dff_data(instance, config_model, dff_data, context_field='code', context_value=None):
        """
        Set DFF field values from a dictionary with logical field names.

        Args:
            instance: Model instance with DFFMixin
            config_model: DFF config model class (e.g., PersonTypeDFFConfig)
            dff_data: dict of {field_name: value}
            context_field: Field to filter on (can include __ for FK traversal)
            context_value: Value to match (if None, extracted from instance using context_field)

        Raises:
            ValidationError: If validation fails

        Example:
            >>> from HR.person.models import PersonType, PersonTypeDFFConfig
            >>> pt = PersonType.objects.get(code='SECONDED_EMP')
            >>> DFFService.set_dff_data(pt, PersonTypeDFFConfig, {
            ...     'home_organization': 'Head Office',
            ...     'secondment_end_date': date(2026, 12, 31)
            ... }, 'person_type__code', pt.code)
            >>> pt.save()
        """
        errors = {}
        if context_value is None:
            context_value = getattr(instance, context_field)

        # Get all configured fields for validation
        all_configs = DFFService._get_active_configs(config_model, context_field, context_value)

        # Check required fields
        for config in all_configs:
            if config.required and config.field_name not in dff_data:
                errors[config.field_name] = f"{config.field_label} is required"

        # Validate and set provided fields
        for field_name, value in dff_data.items():
            # Get configuration for this field
            config = DFFService._get_field_config(config_model, context_field, context_value, field_name)

            if not config:
                errors[field_name] = f"Unknown DFF field: {field_name}"
                continue

            # Validate and set value
            try:
                validated_value = DFFService._validate_and_convert(value, config)
                setattr(instance, config.column_name, validated_value)
            except ValidationError as e:
                errors[field_name] = str(e)

        if errors:
            raise ValidationError(errors)

    @staticmethod
    def clear_dff_data(instance, config_model, context_field='code', context_value=None):
        """
        Clear all DFF field values for an instance.

        Args:
            instance: Model instance with DFFMixin
            config_model: DFF config model class
            context_field: Field to filter on (can include __ for FK traversal)
            context_value: Value to match (if None, extracted from instance using context_field)
        """
        if context_value is None:
            context_value = getattr(instance, context_field)

        dff_configs = DFFService._get_active_configs(config_model, context_field, context_value)

        for config in dff_configs:
            if config.data_type == 'char':
                setattr(instance, config.column_name, '')
            else:
                setattr(instance, config.column_name, None)

    @staticmethod
    def get_field_configs(config_model, context_field, context_value):
        """
        Get all DFF field configurations for a context.

        Args:
            config_model: DFF config model class
            context_field: Field name that identifies the context
            context_value: Value of the context field

        Returns:
            QuerySet of DFF config records
        """
        return DFFService._get_active_configs(config_model, context_field, context_value)

    # ===== Private helper methods =====

    @staticmethod
    def _get_active_configs(config_model, context_field, context_value):
        """
        Get all active DFF configs for a context.

        Args:
            context_field: Field to filter on (can include __ for FK traversal)
            context_value: Value to match
        """
        filter_kwargs = {
            context_field: context_value,
            'is_active': True
        }
        return config_model.objects.filter(**filter_kwargs).order_by('sequence', 'field_name')

    @staticmethod
    def _get_field_config(config_model, context_field, context_value, field_name):
        """Get configuration for a specific field"""
        filter_kwargs = {
            context_field: context_value,
            'field_name': field_name,
            'is_active': True
        }
        try:
            return config_model.objects.get(**filter_kwargs)
        except config_model.DoesNotExist:
            return None

    @staticmethod
    def _validate_and_convert(value, config):
        """
        Validate and convert value based on DFF configuration.

        Args:
            value: The value to validate
            config: DFF config instance

        Returns:
            Validated and converted value

        Raises:
            ValidationError: If validation fails
        """
        # Handle None/empty values
        if value is None or value == '':
            if config.required:
                raise ValidationError(f"{config.field_label} is required")
            return None if config.data_type in ['date', 'number'] else ''

        # Type-specific validation
        if config.data_type == 'char':
            return DFFService._validate_char(value, config)
        elif config.data_type == 'date':
            return DFFService._validate_date(value, config)
        elif config.data_type == 'number':
            return DFFService._validate_number(value, config)

        return value

    @staticmethod
    def _validate_char(value, config):
        """Validate text field"""
        if not isinstance(value, str):
            value = str(value)

        if config.max_length and len(value) > config.max_length:
            raise ValidationError(
                f"{config.field_label} cannot exceed {config.max_length} characters"
            )

        return value

    @staticmethod
    def _validate_date(value, config):
        """Validate date field"""
        if isinstance(value, date):
            return value

        if isinstance(value, str):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError(
                    f"{config.field_label} must be a valid date (YYYY-MM-DD)"
                )

        raise ValidationError(f"{config.field_label} must be a date")

    @staticmethod
    def _validate_number(value, config):
        """Validate number field"""
        try:
            if isinstance(value, str):
                value = Decimal(value)
            elif isinstance(value, (int, float)):
                value = Decimal(str(value))
            elif not isinstance(value, Decimal):
                raise ValidationError(f"{config.field_label} must be a number")

            # Check min/max
            if config.min_value is not None and value < config.min_value:
                raise ValidationError(
                    f"{config.field_label} must be at least {config.min_value}"
                )

            if config.max_value is not None and value > config.max_value:
                raise ValidationError(
                    f"{config.field_label} must be at most {config.max_value}"
                )

            return value
        except (InvalidOperation, ValueError):
            raise ValidationError(f"{config.field_label} must be a valid number")

