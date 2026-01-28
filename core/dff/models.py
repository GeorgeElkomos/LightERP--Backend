"""
DFF (Descriptive Flexfield) Models - Core Infrastructure

Provides reusable DFF pattern for any model that needs business-configurable custom fields.
Similar to core/base/ mixins, this provides infrastructure that can be mixed into any model.

Usage:
    class MyModel(DFFMixin, models.Model):
        # Your regular fields
        name = models.CharField(max_length=100)
        # DFF columns are inherited from DFFMixin

    class MyModelDFFConfig(DFFConfigBase):
        # Inherits all DFF configuration logic
        parent_model = models.ForeignKey(MyModel, ...)
        dff_context_field = 'code'  # Which field identifies the context
"""

from django.db import models
from django.core.exceptions import ValidationError


class DFFMixin(models.Model):
    """
    Mixin that adds 30 DFF (Descriptive Flexfield) columns to any model.

    Provides 20 text, 5 date, and 5 number fields for business-configurable
    custom fields without requiring database migrations.

    Usage:
        class PersonType(DFFMixin, models.Model):
            code = models.CharField(max_length=50)
            name = models.CharField(max_length=128)
            # DFF columns are inherited

    Configure custom fields via DFFConfigBase subclass (e.g., PersonTypeDFFConfig).
    """

    # Text fields (20)
    dff_char1 = models.CharField(max_length=255, blank=True)
    dff_char2 = models.CharField(max_length=255, blank=True)
    dff_char3 = models.CharField(max_length=255, blank=True)
    dff_char4 = models.CharField(max_length=255, blank=True)
    dff_char5 = models.CharField(max_length=255, blank=True)
    dff_char6 = models.CharField(max_length=255, blank=True)
    dff_char7 = models.CharField(max_length=255, blank=True)
    dff_char8 = models.CharField(max_length=255, blank=True)
    dff_char9 = models.CharField(max_length=255, blank=True)
    dff_char10 = models.CharField(max_length=255, blank=True)
    dff_char11 = models.CharField(max_length=255, blank=True)
    dff_char12 = models.CharField(max_length=255, blank=True)
    dff_char13 = models.CharField(max_length=255, blank=True)
    dff_char14 = models.CharField(max_length=255, blank=True)
    dff_char15 = models.CharField(max_length=255, blank=True)
    dff_char16 = models.CharField(max_length=255, blank=True)
    dff_char17 = models.CharField(max_length=255, blank=True)
    dff_char18 = models.CharField(max_length=255, blank=True)
    dff_char19 = models.CharField(max_length=255, blank=True)
    dff_char20 = models.CharField(max_length=255, blank=True)

    # Date fields (5)
    dff_date1 = models.DateField(null=True, blank=True)
    dff_date2 = models.DateField(null=True, blank=True)
    dff_date3 = models.DateField(null=True, blank=True)
    dff_date4 = models.DateField(null=True, blank=True)
    dff_date5 = models.DateField(null=True, blank=True)

    # Number fields (5)
    dff_number1 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    dff_number2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    dff_number3 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    dff_number4 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    dff_number5 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        abstract = True


class DFFConfigBase(models.Model):
    """
    Abstract base model for DFF configuration.

    Subclass this to create DFF configuration for your specific model.
    Maps logical field names to physical DFF columns.

    Usage:
        class PersonTypeDFFConfig(DFFConfigBase):
            person_type = models.ForeignKey(
                'PersonType',
                on_delete=models.CASCADE,
                related_name='dff_fields'
            )

            class Meta(DFFConfigBase.Meta):
                db_table = 'person_type_dff_config'
                unique_together = [
                    ('person_type', 'field_name'),
                    ('person_type', 'column_name'),
                ]

    Note: Subclasses must define the FK to their parent model and set unique_together.
    """

    # Column choices - available DFF columns
    COLUMN_CHOICES = (
        # Text fields (20)
        ('dff_char1', 'Text Field 1'),
        ('dff_char2', 'Text Field 2'),
        ('dff_char3', 'Text Field 3'),
        ('dff_char4', 'Text Field 4'),
        ('dff_char5', 'Text Field 5'),
        ('dff_char6', 'Text Field 6'),
        ('dff_char7', 'Text Field 7'),
        ('dff_char8', 'Text Field 8'),
        ('dff_char9', 'Text Field 9'),
        ('dff_char10', 'Text Field 10'),
        ('dff_char11', 'Text Field 11'),
        ('dff_char12', 'Text Field 12'),
        ('dff_char13', 'Text Field 13'),
        ('dff_char14', 'Text Field 14'),
        ('dff_char15', 'Text Field 15'),
        ('dff_char16', 'Text Field 16'),
        ('dff_char17', 'Text Field 17'),
        ('dff_char18', 'Text Field 18'),
        ('dff_char19', 'Text Field 19'),
        ('dff_char20', 'Text Field 20'),
        # Date fields (5)
        ('dff_date1', 'Date Field 1'),
        ('dff_date2', 'Date Field 2'),
        ('dff_date3', 'Date Field 3'),
        ('dff_date4', 'Date Field 4'),
        ('dff_date5', 'Date Field 5'),
        # Number fields (5)
        ('dff_number1', 'Number Field 1'),
        ('dff_number2', 'Number Field 2'),
        ('dff_number3', 'Number Field 3'),
        ('dff_number4', 'Number Field 4'),
        ('dff_number5', 'Number Field 5'),
    )

    DATA_TYPE_CHOICES = (
        ('char', 'Text'),
        ('date', 'Date'),
        ('number', 'Number'),
    )

    # Logical field definition
    field_name = models.CharField(
        max_length=100,
        help_text="Internal name (e.g., 'home_organization')"
    )
    field_label = models.CharField(
        max_length=200,
        help_text="Display label (e.g., 'Home Organization')"
    )
    help_text = models.TextField(
        blank=True,
        help_text="Help text shown to users"
    )

    # Physical column mapping
    column_name = models.CharField(
        max_length=20,
        choices=COLUMN_CHOICES,
        help_text="Physical column (e.g., 'dff_char1')"
    )
    data_type = models.CharField(
        max_length=20,
        choices=DATA_TYPE_CHOICES,
        help_text="Data type of the field"
    )

    # Display & validation
    sequence = models.IntegerField(
        default=0,
        help_text="Display order"
    )
    required = models.BooleanField(
        default=False,
        help_text="Is this field required?"
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Default value for new records"
    )

    # Optional validation rules
    max_length = models.IntegerField(
        null=True,
        blank=True,
        help_text="Max length for text fields"
    )
    min_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Min value for number fields"
    )
    max_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Max value for number fields"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive fields are hidden"
    )

    class Meta:
        abstract = True
        ordering = ['sequence', 'field_name']

    def clean(self):
        """Validate DFF configuration"""
        super().clean()

        # Validate data_type matches column_name prefix
        if self.data_type == 'char' and not self.column_name.startswith('dff_char'):
            raise ValidationError({
                'column_name': "Text fields must use dff_char columns"
            })
        if self.data_type == 'date' and not self.column_name.startswith('dff_date'):
            raise ValidationError({
                'column_name': "Date fields must use dff_date columns"
            })
        if self.data_type == 'number' and not self.column_name.startswith('dff_number'):
            raise ValidationError({
                'column_name': "Number fields must use dff_number columns"
            })

        # Validate field_name is valid Python identifier
        if not self.field_name.replace('_', '').isalnum():
            raise ValidationError({
                'field_name': "Field name must be alphanumeric with underscores only"
            })

        # Validate max_length only for char fields
        if self.max_length is not None and self.data_type != 'char':
            raise ValidationError({
                'max_length': "max_length only applies to text fields"
            })

        # Validate min/max only for number fields
        if (self.min_value is not None or self.max_value is not None) and self.data_type != 'number':
            raise ValidationError({
                'min_value': "min_value/max_value only apply to number fields"
            })

        # Validate min < max
        if self.min_value is not None and self.max_value is not None:
            if self.min_value >= self.max_value:
                raise ValidationError({
                    'min_value': "min_value must be less than max_value"
                })

