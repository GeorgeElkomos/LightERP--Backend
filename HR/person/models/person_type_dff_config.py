"""
PersonType DFF Configuration Model

Maps logical custom fields to physical DFF columns per person type.
Extends DFFConfigBase from core/dff with PersonType-specific relationship.

Example:
- person_type='SECONDED_EMP', field_name='home_organization', column_name='dff_char1'
- person_type='TEMP_WORKER', field_name='agency_name', column_name='dff_char1'

Note: Same physical column stores different logical fields per context!
"""

from django.db import models
from core.dff import DFFConfigBase


class PersonTypeDFFConfig(DFFConfigBase):
    """
    DFF configuration for PersonType.

    Extends core DFF infrastructure with PersonType-specific FK relationship.
    All validation and logic inherited from DFFConfigBase.
    """

    person_type = models.ForeignKey(
        'PersonType',
        on_delete=models.CASCADE,
        related_name='dff_fields',
        help_text="Which person type this field applies to"
    )

    class Meta(DFFConfigBase.Meta):
        db_table = 'person_type_dff_config'
        unique_together = [
            ('person_type', 'field_name'),  # One field name per type
            ('person_type', 'column_name'),  # One column per type (can't reuse)
        ]
        indexes = [
            models.Index(fields=['person_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.person_type.code}: {self.field_label}"


    @classmethod
    def get_active_fields_for_type(cls, person_type_code):
        """Get all active DFF fields for a person type"""
        return cls.objects.filter(
            person_type__code=person_type_code,
            is_active=True
        ).order_by('sequence', 'field_name')

    @classmethod
    def get_field_config(cls, person_type_code, field_name):
        """Get configuration for a specific field"""
        try:
            return cls.objects.get(
                person_type__code=person_type_code,
                field_name=field_name,
                is_active=True
            )
        except cls.DoesNotExist:
            return None

