"""
Default Combinations Models
Models for managing default segment combinations for different transaction types
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from Finance.core.models import ProtectedDeleteMixin
from Finance.GL.models import XX_Segment_combination, XX_SegmentType


class set_default_combinations(ProtectedDeleteMixin, models.Model):
    """
    Model to store default segment combinations for various transaction types
    """
    TRANSACTION_TYPES = [
        ('AP_INVOICE', 'Accounts Payable Invoice'),
        ('AR_INVOICE', 'Accounts Receivable Invoice'),
    ]

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        unique=True,
        help_text="Type of transaction for which the default combination is set"
    )
    segment_combination = models.ForeignKey(
        XX_Segment_combination, 
        on_delete=models.PROTECT
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this default is active. Auto-deactivated if segment types change."
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='default_combinations_created',
        help_text="User who created this default combination"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this default combination was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this default combination was last updated"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='default_combinations_updated',
        null=True,
        blank=True,
        help_text="User who last updated this default combination"
    )

    def clean(self):
        """Validate the model before saving"""
        super().clean()
        
        # Validate segment combination is not empty
        if not self.segment_combination:
            raise ValidationError("Segment combination cannot be empty.")
        
        # Validate only one record per transaction type
        if self.pk is None:  # New record
            if set_default_combinations.objects.filter(transaction_type=self.transaction_type).exists():
                raise ValidationError({
                    'transaction_type': f"A default combination for {self.get_transaction_type_display()} already exists. Use update instead."
                })
        
        # Validate segment combination has all required segments
        is_valid, error_msg = self.validate_segment_combination_completeness()
        if not is_valid:
            raise ValidationError({
                'segment_combination': error_msg
            })

    def __str__(self):
        return f"{self.get_transaction_type_display()} Default Combination"
    
    class Meta:
        verbose_name = "Default Segment Combination"
        verbose_name_plural = "Default Segment Combinations"
        ordering = ['transaction_type']
    
    # Helper Functions
    
    def validate_segment_combination_completeness(self):
        """
        Check if the segment combination has all required segment types.
        
        Returns:
            tuple: (is_valid: bool, error_message: str)
            
        Example:
            >>> config = set_default_combinations.objects.get(transaction_type='AP_INVOICE')
            >>> is_valid, error = config.validate_segment_combination_completeness()
            >>> if not is_valid:
            >>>     print(error)
        """
        if not self.segment_combination:
            return False, "Segment combination is not set."
        
        # Get all required segment types
        required_types = XX_SegmentType.objects.filter(is_required=True, is_active=True)
        
        # Get segment types in the combination
        combination_types = self.segment_combination.details.values_list('segment_type_id', flat=True)
        
        # Check for missing required types
        missing_types = []
        for seg_type in required_types:
            if seg_type.id not in combination_types:
                missing_types.append(seg_type.segment_name)
        
        if missing_types:
            return False, f"Segment combination is missing required segment types: {', '.join(missing_types)}"
        
        return True, ""
    
    def check_and_deactivate_if_invalid(self):
        """
        Check if the segment combination is still valid. If not, deactivate this default.
        
        This should be called when segment types are added or removed from the system.
        
        Returns:
            bool: True if was deactivated, False if still valid
            
        Example:
            >>> config = set_default_combinations.objects.get(transaction_type='AP_INVOICE')
            >>> if config.check_and_deactivate_if_invalid():
            >>>     print("Default was deactivated due to segment type changes")
        """
        is_valid, error_msg = self.validate_segment_combination_completeness()
        
        if not is_valid and self.is_active:
            self.is_active = False
            self.save(update_fields=['is_active', 'updated_at'])
            return True
        
        return False
    
    @classmethod
    def check_all_defaults_validity(cls):
        """
        Check all default combinations and deactivate those that are no longer valid.
        
        This should be called whenever segment types are added or removed.
        
        Returns:
            list: List of transaction types that were deactivated
            
        Example:
            >>> deactivated = set_default_combinations.check_all_defaults_validity()
            >>> if deactivated:
            >>>     print(f"Deactivated defaults for: {', '.join(deactivated)}")
        """
        deactivated = []
        
        for config in cls.objects.filter(is_active=True):
            if config.check_and_deactivate_if_invalid():
                deactivated.append(config.transaction_type)
        
        return deactivated
    
    def update_default(self, segment_combination, user):
        """
        Update the default segment combination for this transaction type.
        
        Args:
            segment_combination (XX_Segment_combination): New segment combination
            user (User): User performing the update
            
        Returns:
            set_default_combinations: The updated instance
            
        Raises:
            ValidationError: If the new combination is invalid
            
        Example:
            >>> config = set_default_combinations.objects.get(transaction_type='AP_INVOICE')
            >>> new_combo = XX_Segment_combination.objects.get(id=456)
            >>> config.update_default(new_combo, request.user)
        """
        self.segment_combination = segment_combination
        self.updated_by = user
        self.is_active = True  # Reactivate when updating
        
        # This will call clean() which validates the combination
        self.full_clean()
        self.save()
        
        return self
    
    @classmethod
    def create_or_update_default(cls, transaction_type, segment_combination, user):
        """
        Create a new default or update existing one for a transaction type.
        
        Ensures only one record exists per transaction type.
        
        Args:
            transaction_type (str): The transaction type ('AP_INVOICE', 'AR_INVOICE')
            segment_combination (XX_Segment_combination): The segment combination to set
            user (User): User creating/updating the default
            
        Returns:
            tuple: (instance, created: bool) - The instance and whether it was created (True) or updated (False)
            
        Example:
            >>> combo = XX_Segment_combination.objects.get(id=123)
            >>> config, created = set_default_combinations.create_or_update_default(
            >>>     'AP_INVOICE', combo, request.user
            >>> )
            >>> if created:
            >>>     print("New default created")
            >>> else:
            >>>     print("Existing default updated")
        """
        try:
            # Try to get existing record
            config = cls.objects.get(transaction_type=transaction_type)
            config.update_default(segment_combination, user)
            return config, False
        except cls.DoesNotExist:
            # Create new record
            config = cls.objects.create(
                transaction_type=transaction_type,
                segment_combination=segment_combination,
                created_by=user,
                is_active=True
            )
            return config, True
    
    @classmethod
    def get_default_for_transaction_type(cls, transaction_type):
        """
        Get the default segment combination for a specific transaction type.
        
        Args:
            transaction_type (str): The transaction type ('AP_INVOICE', 'AR_INVOICE', etc.)
            
        Returns:
            XX_Segment_combination: The default segment combination object, or None if not found
            
        Example:
            >>> default_combo = set_default_combinations.get_default_for_transaction_type('AP_INVOICE')
            >>> if default_combo:
            >>>     combo_id = default_combo.segment_combination_id
        """
        try:
            config = cls.objects.get(transaction_type=transaction_type)
            return config.segment_combination
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_default_for_ap_invoice(cls):
        """
        Get the default segment combination for AP invoices.
        
        Returns:
            XX_Segment_combination: The default segment combination for AP invoices, or None
            
        Example:
            >>> ap_combo = set_default_combinations.get_default_for_ap_invoice()
        """
        return cls.get_default_for_transaction_type('AP_INVOICE')
    
    @classmethod
    def get_default_for_ar_invoice(cls):
        """
        Get the default segment combination for AR invoices.
        
        Returns:
            XX_Segment_combination: The default segment combination for AR invoices, or None
            
        Example:
            >>> ar_combo = set_default_combinations.get_default_for_ar_invoice()
        """
        return cls.get_default_for_transaction_type('AR_INVOICE')
    
    @classmethod
    def set_default(cls, transaction_type, segment_combination, user):
        """
        Set or update the default segment combination for a transaction type.
        
        Args:
            transaction_type (str): The transaction type ('AP_INVOICE', 'AR_INVOICE', etc.)
            segment_combination (XX_Segment_combination): The segment combination to set as default
            user (User): The user creating/updating the default
            
        Returns:
            set_default_combinations: The created or updated default configuration
            
        Example:
            >>> from Finance.GL.models import XX_Segment_combination
            >>> combo = XX_Segment_combination.objects.get(id=123)
            >>> config = set_default_combinations.set_default('AP_INVOICE', combo, request.user)
        """
        obj, created = cls.objects.update_or_create(
            transaction_type=transaction_type,
            defaults={
                'segment_combination': segment_combination,
                'created_by': user
            }
        )
        return obj
    
    def get_segment_details(self):
        """
        Get detailed information about the segment combination.
        
        Returns:
            dict: Dictionary containing segment combination details
            
        Example:
            >>> config = set_default_combinations.objects.get(transaction_type='AP_INVOICE')
            >>> details = config.get_segment_details()
            >>> print(details['segments'])
        """
        if not self.segment_combination:
            return {}
        
        segments = []
        for detail in self.segment_combination.details.all():
            segments.append({
                'segment_type': detail.segment_type.segment_name,
                'segment_code': detail.segment.code,
                'segment_alias': detail.segment.alias,
            })
        
        return {
            'combination_id': self.segment_combination.id,
            'description': self.segment_combination.description,
            'is_active': self.segment_combination.is_active,
            'segments': segments
        }
    
    def is_valid_combination(self):
        """
        Check if the assigned segment combination is valid and active.
        
        Returns:
            bool: True if the combination is valid and active, False otherwise
            
        Example:
            >>> config = set_default_combinations.objects.get(transaction_type='AP_INVOICE')
            >>> if config.is_valid_combination():
            >>>     # Use the combination
        """
        if not self.segment_combination:
            return False
        return self.segment_combination.is_active
    
    @classmethod
    def get_all_defaults(cls):
        """
        Get all configured default segment combinations.
        
        Returns:
            dict: Dictionary with transaction types as keys and segment combinations as values
            
        Example:
            >>> defaults = set_default_combinations.get_all_defaults()
            >>> ap_combo = defaults.get('AP_INVOICE')
        """
        defaults = {}
        for config in cls.objects.select_related('segment_combination').all():
            defaults[config.transaction_type] = config.segment_combination
        return defaults
    
    def get_deletion_identifier(self):
        """
        Custom identifier for deletion error messages (from ProtectedDeleteMixin).
        
        Returns:
            str: A human-readable identifier for this configuration
        """
        return f"{self.get_transaction_type_display()} Default"
    


