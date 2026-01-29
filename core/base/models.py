import re
from datetime import date, timedelta
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.conf import settings


class StatusChoices(models.TextChoices):
    """
    Standard status choices for entities across the system.

    Use this instead of defining custom status choices in each model.
    For more specific statuses, create custom TextChoices or use lookups (Task 3).
    """
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'


class AuditMixin(models.Model):
    """
    Adds audit fields to track creation and modification metadata.

    Fields:
        - created_at: Timestamp when record was created
        - updated_at: Timestamp when record was last modified
        - created_by: User who created the record (optional)
        - updated_by: User who last modified the record (optional)

    Usage:
        class MyModel(AuditMixin):
            name = models.CharField(max_length=100)

    Note: created_by and updated_by should be set manually in views/serializers.
    Django signals can be used to auto-populate from request context.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when record was last modified"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_created',
        help_text="User who created this record"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_updated',
        help_text="User who last updated this record"
    )


    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Mixin for models that support soft deletion.

    Instead of permanently deleting records, they are marked as inactive.
    This preserves referential integrity and audit history.

    Fields:
        - status: StatusChoices (ACTIVE/INACTIVE)

    Methods:
        - deactivate(): Marks record as inactive (soft delete)
        - hard_delete(): Permanently deletes the record from database
    """
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
        help_text="Record status. Set to INACTIVE instead of deleting."
    )

    class Meta:
        abstract = True

    def deactivate(self):
        """
        Soft delete: mark as inactive instead of removing from DB.
        """
        self.status = StatusChoices.INACTIVE
        self.save(update_fields=['status'])

    def reactivate(self):
        """
        Reactivate a soft-deleted record by setting status to ACTIVE.

        Example:
            location = Location.objects.get(code='LOC1')
            location.reactivate()  # Sets status back to ACTIVE
        """
        self.status = StatusChoices.ACTIVE
        self.save(update_fields=['status'])

    def update_fields(self, field_updates: dict):
        """
        Generic method to update multiple fields on a SoftDeleteMixin model.

        Provides a consistent pattern for updates similar to VersionedMixin.update_version()
        but simpler since there's no versioning.

        Args:
            field_updates: Dict of field_name -> new_value for fields to update

        Returns:
            self (for chaining)

        Example:
            location.update_fields({
                'name': 'New Name',
                'description': 'New Description',
                'city': city_obj
            })
        """
        for field_name, value in field_updates.items():
            setattr(self, field_name, value)
        self.full_clean()
        self.save()
        return self

    def hard_delete(self):
        """
        Permanently delete the record.
        """
        super().delete()

# !!! DEPRECATED !!!
# class CodeGenerationMixin:
#     """
#     Automatically generates unique codes from name field.
#
#     Pattern:
#         - Multi-word names: Use initials (Backend Development → BD)
#         - Single word: Truncate (Marketing → MARKET)
#         - Ensure uniqueness: Add numeric suffix if needed (BD1, BD2, etc.)
#
#     Usage:
#         1. Add 'code' and 'name' fields to your model
#         2. Inherit this mixin
#         3. Override get_code_generation_config() to customize
#         4. Call super().save() in your model's save() method
#
#     Configuration Options (override get_code_generation_config):
#         - skip_words: Words to ignore when generating acronyms
#         - scope_filter: Dict for scoped uniqueness (e.g., {'business_group': self.bg})
#         - min_length: Minimum code length (default: 2)
#         - use_acronym: Whether to use initials vs truncation (default: True)
#
#     Example:
#         class Department(CodeGenerationMixin, models.Model):
#             code = models.CharField(max_length=50, blank=True)
#             name = models.CharField(max_length=128)
#             business_group = models.ForeignKey(BusinessGroup, ...)
#
#             def get_code_generation_config(self):
#                 return {
#                     'skip_words': {'and', 'of', 'department'},
#                     'scope_filter': {'business_group': self.business_group},
#                     'min_length': 2,
#                     'use_acronym': True
#                 }
#     """
#
#     def get_code_generation_config(self):
#         """
#         Override this method to customize code generation behavior.
#
#         Returns:
#             dict with keys:
#                 - skip_words: set of words to ignore (default: common connectors)
#                 - scope_filter: dict for uniqueness check (default: {} = globally unique)
#                 - min_length: minimum code length (default: 2)
#                 - use_acronym: use initials vs truncation (default: True)
#         """
#         return {
#             'skip_words': {'and', 'of', 'the', 'for', 'in', 'on', 'at', 'to'},
#             'scope_filter': {},  # Empty = globally unique
#             'min_length': 2,
#             'use_acronym': True
#         }
#
#     def _generate_unique_code(self):
#         """
#         Generate readable acronym-based code from name field.
#
#         Returns:
#             str: Unique code for this instance
#         """
#         if not hasattr(self, 'name') or not self.name:
#             raise ValueError(f"{self.__class__.__name__} must have a 'name' field to generate code")
#
#         config = self.get_code_generation_config()
#
#         # Remove special chars and split into words
#         clean_name = re.sub(r'[^\w\s]', '', self.name)
#         words = clean_name.split()
#
#         # Filter out skip words
#         skip_words = config.get('skip_words', set())
#         significant_words = [w for w in words if w.lower() not in skip_words]
#
#         # Generate base code
#         if config.get('use_acronym', True) and len(significant_words) >= 2:
#             # Use initials: "Backend Development" -> "BD"
#             base_code = ''.join(w[0].upper() for w in significant_words[:4])
#         else:
#             # Single word or truncation: use first 4-6 chars
#             base_code = clean_name[:6].upper().replace(' ', '')
#
#         # Ensure minimum length
#         min_length = config.get('min_length', 2)
#         if len(base_code) < min_length:
#             base_code = clean_name[:max(min_length, 4)].upper().replace(' ', '')
#
#         return self._ensure_unique_code(base_code, config.get('scope_filter', {}))
#
#     def _ensure_unique_code(self, base_code, scope_filter):
#         """
#         Add numeric suffix if code exists within scope.
#
#         Args:
#             base_code: Generated base code
#             scope_filter: Dict of field filters for uniqueness scope
#
#         Returns:
#             str: Unique code with suffix if needed
#         """
#         code = base_code
#         suffix = 1
#
#         # Build filter query
#         filter_kwargs = {'code': code}
#         filter_kwargs.update(scope_filter)
#
#         # Check uniqueness and add suffix if needed
#         while self.__class__.objects.filter(**filter_kwargs).exclude(pk=self.pk).exists():
#             code = f"{base_code}{suffix}"
#             filter_kwargs['code'] = code
#             suffix += 1
#
#         return code
#
#     def save(self, *args, **kwargs):
#         """Auto-generate code from name if not provided"""
#         if not self.code and hasattr(self, 'name') and self.name:
#             self.code = self._generate_unique_code()
#         super().save(*args, **kwargs)


class VersionedMixin(models.Model):
    """
    Mixin for models that track versions over time.

    Models with versions do NOT have status field - status is computed
    from effective_start_date and effective_end_date only.

    Fields:
        - effective_start_date: When this version becomes active
        - effective_end_date: When this version ends (NULL = currently active)

    Properties:
        - status: Computed property based on dates (ACTIVE if active today)

    Methods:
        - active_on(reference_date): Check if active on a specific date
        - deactivate(end_date): End-date the record
        - update_version(field_updates, new_start_date, new_end_date): Generic correction/versioning
        - get_version_group_field(): Override to enable overlap validation
        - get_version_scope_filters(): Override for scoped uniqueness

    Usage:
        class Department(CodeGenerationMixin, VersionedMixin):
            code = models.CharField(max_length=50, blank=True)
            name = models.CharField(max_length=128)
            objects = VersionedManager()

        # Status is computed from dates:
        dept.status  # StatusChoices.ACTIVE or StatusChoices.INACTIVE
        dept.active_on(date(2024, 1, 1))  # Check specific date

        # Update versioned record (correction or new version):
        dept.update_version({'name': 'New Name'})  # Correction
        dept.update_version({'name': 'New Name'}, new_start_date=date(2026, 2, 1))  # New version
    """
    effective_start_date = models.DateField(
        help_text="Date this version becomes active"
    )
    effective_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date this version ends. NULL = currently active"
    )

    class Meta:
        abstract = True
        ordering = ['-effective_start_date']

    @property
    def status(self):
        """
        Computed property: status based on effective dates.

        Returns:
            StatusChoices: ACTIVE if active today, INACTIVE otherwise
        """
        if self.active_on(date.today()):
            return StatusChoices.ACTIVE
        return StatusChoices.INACTIVE

    def active_on(self, reference_date):
        """
        Check if this version is active on a specific date.

        Args:
            reference_date: Date to check against

        Returns:
            bool: True if active on that date, False otherwise
        """
        # Not yet started
        if self.effective_start_date > reference_date:
            return False

        # Already ended (end_date is exclusive)
        if self.effective_end_date and self.effective_end_date <= reference_date:
            return False

        return True

    def deactivate(self, end_date=None):
        """
        End-date this record (preferred way to "delete" versioned data).

        Args:
            end_date: Date to end this record. Defaults to yesterday so it's
                     inactive today.

        Example:
            dept = Department.objects.get(code='IT', effective_end_date=None)
            dept.deactivate()  # Ends yesterday, inactive today
        """
        if end_date is None:
            end_date = date.today() - timedelta(days=1)

        # Prevent start > end error
        if end_date < self.effective_start_date:
            end_date = self.effective_start_date

        self.effective_end_date = end_date
        self.save(update_fields=['effective_end_date'])


    def update_version(self, field_updates, new_start_date=None, new_end_date=None):
        """
        Generic method to update a versioned record.
        Handles two modes:
        1. Correction mode: new_start_date == current start_date (or None)
           - Updates fields in-place on the current record
        2. New version mode: new_start_date != current start_date
           - End-dates current record
           - Creates new version with updated fields
        Args:
            field_updates: Dict of field_name -> new_value for fields to update
            new_start_date: New effective_start_date (None = keep current, use correction mode)
            new_end_date: New effective_end_date
        Returns:
            The updated or newly created instance
        Example:
            # Correction (update in place)
            dept.update_version({'name': 'New Name', 'location_id': 5})
            # New version (end-date current, create new)
            dept.update_version(
                {'name': 'New Name'}, 
                new_start_date=date(2026, 2, 1)
            )
        """
        # Determine if this is correction or new version
        if new_start_date is None:
            new_start_date = self.effective_start_date
        is_correction = (new_start_date == self.effective_start_date)
        if is_correction:
            # Correction mode: Update current record
            for field_name, value in field_updates.items():
                setattr(self, field_name, value)
            # Allow updating end date in correction mode
            if new_end_date is not None:
                self.effective_end_date = new_end_date
            self.full_clean()
            self.save()
            return self
        else:
            # New version mode: End current, create new
            original_end_date = self.effective_end_date
            # End-date current version
            self.effective_end_date = new_start_date - timedelta(days=1)
            self.save()
            # Prepare fields for new version
            new_version_fields = {}
            # Copy all fields from current instance
            for field in self._meta.fields:
                if field.name in ['id', 'pk']:
                    continue
                field_value = getattr(self, field.name)
                new_version_fields[field.name] = field_value
            # Apply updates
            for field_name, value in field_updates.items():
                new_version_fields[field_name] = value
            # Set new dates
            new_version_fields['effective_start_date'] = new_start_date
            # ? Should we set effective_end_date to None by default for new versions if it's not provided?
            new_version_fields['effective_end_date'] = new_end_date if new_end_date is not None else original_end_date
            # Create new version
            new_version = self.__class__(**new_version_fields)
            new_version.full_clean()
            new_version.save()

            # Copy Many-to-Many relationships
            for field in self._meta.many_to_many:
                if field.name in field_updates:
                    continue

                if field.remote_field.through._meta.auto_created:
                    # Simple M2M: use set() to copy relations
                    getattr(new_version, field.name).set(getattr(self, field.name).all())
                else:
                    # M2M with custom through model: manually copy rows
                    through_model = field.remote_field.through
                    fk_name = field.m2m_field_name()
                    
                    # Filter for rows related to the current (old) instance
                    filter_kwargs = {fk_name: self.pk}
                    old_rows = through_model.objects.filter(**filter_kwargs)
                    
                    for row in old_rows:
                        # Clone the row
                        row.pk = None
                        setattr(row, fk_name, new_version)
                        row.save()

            return new_version

    def get_version_group_field(self):
        """
        Override to specify which field groups versions together.

        Returns:
            str: Field name (e.g., 'code')

        Raises:
            NotImplementedError: Must be implemented by child class
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_version_group_field()"
        )

    def get_version_scope_filters(self):
        """
        Override for scoped uniqueness (e.g., code unique per business_group).

        Returns:
            dict: Additional filters for uniqueness checks
        """
        return {}

    def clean(self):
        """Validate date ranges and prevent overlaps."""
        # Check date order
        if self.effective_end_date and self.effective_start_date > self.effective_end_date:
            raise ValidationError({
                'effective_end_date': 'Start date must be before end date'
            })

        # Check for overlaps
        try:
            group_field = self.get_version_group_field()
        except NotImplementedError:
            return

        group_value = getattr(self, group_field, None)
        if group_value is None:
            return

        filter_kwargs = {group_field: group_value}
        filter_kwargs.update(self.get_version_scope_filters())

        overlapping = self.__class__.objects.filter(
            **filter_kwargs,
            effective_start_date__lt=(self.effective_end_date or date.max),
        ).exclude(pk=self.pk)

        overlapping = overlapping.filter(
            Q(effective_end_date__isnull=True) |
            Q(effective_end_date__gt=self.effective_start_date)
        )

        if overlapping.exists():
            raise ValidationError({
                'effective_start_date': f"Date range overlaps with existing {group_field}={group_value}"
            })



