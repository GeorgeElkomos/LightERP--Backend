from django.db import models
from django.core.exceptions import ValidationError


class LookupType(models.Model):
    """
    Categories of lookup values.

    Examples:
    - RELATIONSHIP_TYPE (Spouse, Child, Parent)
    - DOCUMENT_TYPE (Passport, National ID)
    - ADDRESS_TYPE (Home, Work, Mailing)
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Display name"
    )
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'lookup_type'
        ordering = ['name']

    def __str__(self):
        return self.name


class LookupValue(models.Model):
    """
    Actual lookup values.

    Examples:
    - lookup_type='RELATIONSHIP_TYPE', name='Spouse'
    - lookup_type='RELATIONSHIP_TYPE', name='Child'
    """
    lookup_type = models.ForeignKey(
        LookupType,
        on_delete=models.CASCADE,
        related_name='values'
    )

    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g., 'Spouse')"
    )
    description = models.TextField(blank=True)

    # Ordering & status
    sequence = models.IntegerField(
        default=0,
        help_text="Display order"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive values hidden from dropdowns"
    )

    # Optional parent (for hierarchical lookups like City → Country)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="For hierarchical lookups (e.g., Cairo → Egypt)"
    )

    class Meta:
        db_table = 'lookup_value'
        unique_together = [('lookup_type', 'name')]
        ordering = ['lookup_type', 'sequence', 'name']

    def __str__(self):
        return f"{self.lookup_type.name}: {self.name}"

    @classmethod
    def get_active_for_type(cls, lookup_type_name):
        """Get all active lookup values for a lookup type"""
        return cls.objects.filter(
            lookup_type__name=lookup_type_name,
            is_active=True
        ).order_by('sequence', 'name')

    @classmethod
    def get_children_for_parent(cls, parent_id):
        """Get all active child lookup values for a parent (e.g., cities for a country)"""
        return cls.objects.filter(
            parent_id=parent_id,
            is_active=True
        ).order_by('sequence', 'name')

    def clean(self):
        """Validate lookup value data"""
        super().clean()

        # Prevent circular parent relationships
        if self.parent:
            if self.parent == self:
                raise ValidationError("A lookup value cannot be its own parent")

            # Check if parent has the same lookup_type
            if self.parent.lookup_type != self.lookup_type:
                raise ValidationError(
                    f"Parent lookup must have same type. Expected {self.lookup_type.name}, "
                    f"got {self.parent.lookup_type.name}"
                )
