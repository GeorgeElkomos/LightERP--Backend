from django.db import models
from django.core.exceptions import ValidationError
from Finance.core.models import Currency

class XX_SegmentType(models.Model):
    """
    Defines segment types for this client installation.
    Examples: Entity (Cost Center), Account, Project, Line Item, etc.
    Configured during client setup.
    """
    segment_name = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Display name (e.g., 'Entity', 'Account', 'Project')"
    )
    is_required = models.BooleanField(
        default=True,
        help_text="Whether this segment is required in transactions"
    )
    has_hierarchy = models.BooleanField(
        default=False,
        help_text="Whether this segment supports parent-child relationships"
    )
    length = models.IntegerField(
        default=50,
        help_text="Fixed code length for this segment (all codes must be this length)"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying in UI (lower = first)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of what this segment represents"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this segment is currently active"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "XX_SEGMENT_TYPE_XX"
        verbose_name = "Segment Type"
        verbose_name_plural = "Segment Types"
        ordering = ['display_order', 'segment_name']
    
    def __str__(self):
        return f"{self.segment_name}"
    
    def is_used_in_transactions(self):
        """
        Check if this segment type is used in any transactions.
        Returns tuple: (is_used: bool, usage_details: list)
        """
        usage = []
        
        try:
            # Check if any segment values of this type are used in combinations
            segment_values = self.values.all()
            if segment_values.exists():
                # Get all combinations using any segment of this type
                combinations_using_type = segment_combination_detials.objects.filter(
                    segment_type=self
                ).values_list('segment_combination_id', flat=True).distinct()
                
                if combinations_using_type:
                    # Check if these combinations are used in journal lines
                    journal_line_count = JournalLine.objects.filter(
                        segment_combination_id__in=combinations_using_type
                    ).count()
                    
                    if journal_line_count > 0:
                        usage.append(
                            f"Segment type used in {len(combinations_using_type)} combination(s) "
                            f"referenced by {journal_line_count} journal line(s)"
                        )
        except Exception:
            # Tables might not exist yet during migrations
            pass
        
        return (len(usage) > 0, usage)
    
    @property
    def can_delete(self):
        """
        Check if this segment type can be safely deleted.
        Returns False if used in transactions or has segment values.
        """
        # Check if used in transactions
        is_used, _ = self.is_used_in_transactions()
        if is_used:
            return False
        
        # Check if has any segment values
        if self.values.exists():
            return False
        
        return True
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion if segment type is used in transactions.
        Suggest marking as inactive instead.
        """
        is_used, usage_details = self.is_used_in_transactions()
        
        if is_used:
            error_msg = (
                f"Cannot delete segment type '{self.segment_name}' because it is used in transactions:\n"
                + "\n".join(f"  - {detail}" for detail in usage_details)
                + "\n\nInstead of deleting, consider marking it as inactive by setting is_active=False."
            )
            raise ValidationError(error_msg)
        
        # Check if it has any segment values (even if not used in transactions)
        segment_count = self.values.count()
        if segment_count > 0:
            error_msg = (
                f"Cannot delete segment type '{self.segment_name}' because it has {segment_count} segment value(s).\n"
                "Please delete or reassign all segment values first, or mark this segment type as inactive."
            )
            raise ValidationError(error_msg)
        
        super().delete(*args, **kwargs)

class XX_Segment(models.Model):
    """
    Generic segment value model that replaces XX_Entity, XX_Account, XX_Project.
    All segment values (regardless of type) are stored here.
    """
    segment_type = models.ForeignKey(
        XX_SegmentType,
        on_delete=models.CASCADE,
        related_name='values',
        help_text="Which segment type this value belongs to"
    )
    code = models.CharField(
        max_length=50,
        help_text="The actual segment code/value"
    )
    parent_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Parent segment code for hierarchical segments"
    )
    alias = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Display name / description"
    )
    node_type = models.CharField(
        max_length=20,
        choices=[
            ('parent', 'Parent'),
            ('sub_parent', 'Sub-Parent'),
            ('child', 'Child')
        ],
        null=False,
        help_text="Node type in hierarchy: parent (root), sub_parent (intermediate), or child (leaf)"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this segment value is active"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "XX_SEGMENT_XX"
        verbose_name = "Segment Value"
        verbose_name_plural = "Segment Values"
        unique_together = ("segment_type", "code")
        indexes = [
            models.Index(fields=["segment_type", "code"]),
            models.Index(fields=["segment_type", "parent_code"]),
            models.Index(fields=["code"]),
        ]
    
    def __str__(self):
        return f"{self.segment_type.segment_name}: {self.code} ({self.alias or 'No alias'})"
    
    @property
    def name(self):
        """Compatibility property for old Account model"""
        return self.alias or self.code
    
    @property
    def type(self):
        """Compatibility property for old Account model"""
        return self.segment_type.segment_type if self.segment_type else None
    
    @property
    def parent(self):
        """Get parent segment object if exists"""
        if self.parent_code:
            try:
                return XX_Segment.objects.get(
                    segment_type=self.segment_type,
                    code=self.parent_code
                )
            except XX_Segment.DoesNotExist:
                return None
        return None
    
    @property
    def full_path(self):
        """Get full hierarchical path"""
        path = [self.code]
        current = self
        while current.parent_code:
            try:
                current = XX_Segment.objects.get(
                    segment_type=current.segment_type,
                    code=current.parent_code
                )
                path.insert(0, current.code)
            except XX_Segment.DoesNotExist:
                break
        return " > ".join(path)
    
    @property
    def hierarchy_level(self):
        """Get numeric hierarchy level"""
        return self.level
    
    def get_all_children(self):
        """Get all descendant codes recursively"""
        children = list(XX_Segment.objects.filter(
            segment_type=self.segment_type,
            parent_code=self.code
        ).values_list('code', flat=True))
        
        descendants = []
        for child_code in children:
            descendants.append(child_code)
            try:
                child = XX_Segment.objects.get(
                    segment_type=self.segment_type,
                    code=child_code
                )
                descendants.extend(child.get_all_children())
            except XX_Segment.DoesNotExist:
                continue
        
        return descendants
    
    def is_used_in_transactions(self):
        """
        Check if this segment is used in any transactions.
        Returns tuple: (is_used: bool, usage_details: list)
        """
        usage = []
        
        try:
            # Check if this segment is used in any segment combinations
            combinations_using_segment = segment_combination_detials.objects.filter(
                segment=self
            ).values_list('segment_combination_id', flat=True)
            
            if combinations_using_segment:
                # Check if these combinations are used in journal lines
                journal_line_count = JournalLine.objects.filter(
                    segment_combination_id__in=combinations_using_segment
                ).count()
                
                if journal_line_count > 0:
                    usage.append(
                        f"Used in {len(combinations_using_segment)} segment combination(s) "
                        f"referenced by {journal_line_count} journal line(s)"
                    )
        except Exception:
            # Tables might not exist yet during migrations
            pass
        
        return (len(usage) > 0, usage)
    
    @property
    def can_delete(self):
        """
        Check if this segment can be safely deleted.
        Returns False if used in transactions or has children.
        """
        # Check if used in transactions
        is_used, _ = self.is_used_in_transactions()
        if is_used:
            return False
        
        # Check if has children
        has_children = XX_Segment.objects.filter(
            segment_type=self.segment_type,
            parent_code=self.code
        ).exists()
        if has_children:
            return False
        
        return True
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion if segment is used in any transactions.
        Suggest marking as inactive instead.
        """
        is_used, usage_details = self.is_used_in_transactions()
        
        if is_used:
            error_msg = (
                f"Cannot delete segment '{self.code} - {self.alias}' because it is used in transactions:\n"
                + "\n".join(f"  - {detail}" for detail in usage_details)
                + "\n\nInstead of deleting, mark it as inactive by setting is_active=False."
            )
            raise ValidationError(error_msg)
        
        # Also check if this segment has children
        children_count = XX_Segment.objects.filter(
            segment_type=self.segment_type,
            parent_code=self.code
        ).count()
        
        if children_count > 0:
            error_msg = (
                f"Cannot delete segment '{self.code} - {self.alias}' because it has {children_count} child segment(s).\n"
                "Please delete or reassign all child segments first, or mark this segment as inactive."
            )
            raise ValidationError(error_msg)
        
        super().delete(*args, **kwargs)

class XX_Segment_combination(models.Model):
    """
    Dynamic envelope model that replaces Project_Envelope.
    Stores envelope amounts for ANY segment combination (not just projects).
   
    Example:
    - For 3 segments (Entity, Account, Project): stores envelope per project
    - For 5 segments: stores envelope per 5-segment combination
    - Flexible JSON storage for any number of segments
    
    IMPORTANT: Once created, segment combinations are IMMUTABLE.
    They cannot be modified or deleted to maintain accounting integrity.
    
    Usage:
        # Search for a combination
        combo = XX_Segment_combination.find_combination([
            (entity_type, entity_segment),
            (account_type, account_segment),
            (project_type, project_segment)
        ])
        
        # Get or create a combination
        combo_id = XX_Segment_combination.get_combination_id([
            (entity_type, entity_segment),
            (account_type, account_segment),
            (project_type, project_segment)
        ])
    """
    id = models.AutoField(primary_key=True)
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Optional description of this envelope"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this envelope is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
   
    class Meta:
        db_table = "XX_SEGMENT_combination_XX"
        verbose_name = "Segment Combination"
        verbose_name_plural = "Segment Combinations"
        indexes = [
            models.Index(fields=["is_active"]),
        ]
   
    def __str__(self):
        """String representation showing all segment types and values"""
        details = self.details.select_related('segment_type', 'segment').all()
        if not details:
            return f"Combination {self.id} (empty)"
        segments_str = ", ".join([
            f"{detail.segment_type.segment_name}:{detail.segment.code}" 
            for detail in details
        ])
        return f"Combination {self.id}: {segments_str}"
    
    def save(self, *args, **kwargs):
        """
        Prevent modification of existing segment combinations.
        Once created, combinations are immutable for accounting integrity.
        """
        # Check if this is an update (not a new record)
        if self.pk is not None:
            raise ValidationError(
                f"Cannot modify Segment Combination #{self.pk}. "
                "Segment combinations are immutable after creation for accounting integrity. "
                "Create a new combination instead."
            )
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion of segment combinations.
        Combinations are immutable once created.
        """
        raise ValidationError(
            f"Cannot delete Segment Combination #{self.pk}. "
            "Segment combinations are immutable for accounting integrity. "
            "Consider marking it as inactive (is_active=False) instead."
        )
    
    def get_combination_dict(self):
        """
        Returns a dictionary representation of the combination using segment codes.
        Format: {segment_type_id: segment_code, ...}
        """
        return {
            detail.segment_type_id: detail.segment.code
            for detail in self.details.select_related('segment').all()
        }
    
    def get_combination_display(self):
        """
        Returns a human-readable dictionary of the combination.
        Format: {segment_type_name: segment_code, ...}
        """
        return {
            detail.segment_type.segment_name: detail.segment.code
            for detail in self.details.select_related('segment_type', 'segment').all()
        }
    
    @classmethod
    def find_combination(cls, combination_list):
        """
        Search for an existing combination using segment codes.
        
        Args:
            combination_list: List of tuples [(segment_type_id, segment_code), ...]
                             segment_type_id: int - The ID of the segment type
                             segment_code: str - The code of the segment value
        
        Returns:
            XX_Segment_combination object if found, None otherwise
        
        Example:
            combo = XX_Segment_combination.find_combination([
                (1, "100"),    # segment_type_id=1, segment_code="100"
                (2, "5000"),   # segment_type_id=2, segment_code="5000"
                (3, "PROJ1"),  # segment_type_id=3, segment_code="PROJ1"
            ])
        """
        from django.db.models import Count, Q
        
        if not combination_list:
            return None
        
        # Normalize to segment type ID and segment code
        normalized_combo = []
        for item in combination_list:
            seg_type_id = item[0]
            seg_code = str(item[1])  # Ensure it's a string
            normalized_combo.append((seg_type_id, seg_code))
        
        # Build query to find combinations with exact matches
        # Start with all combinations that have the right number of details
        candidates = cls.objects.annotate(
            detail_count=Count('details')
        ).filter(detail_count=len(normalized_combo))
        
        # Filter by each segment type and segment code pair
        for seg_type_id, seg_code in normalized_combo:
            candidates = candidates.filter(
                details__segment_type_id=seg_type_id,
                details__segment__code=seg_code
            )
        
        # Get the first match (should be unique due to validation)
        return candidates.first()
    
    @classmethod
    def create_combination(cls, combination_list, description=None):
        """
        Create a new segment combination using segment codes.
        
        Args:
            combination_list: List of tuples [(segment_type_id, segment_code), ...]
                             segment_type_id: int - The ID of the segment type
                             segment_code: str - The code of the segment value
            description: Optional description for the combination
        
        Returns:
            XX_Segment_combination object (newly created)
        
        Raises:
            ValidationError: If segment types are not unique, segments don't exist, 
                           or segments don't match their types
        
        Example:
            combo = XX_Segment_combination.create_combination([
                (1, "100"),    # Entity type ID=1, code="100"
                (2, "5000"),   # Account type ID=2, code="5000"
                (3, "PROJ1"),  # Project type ID=3, code="PROJ1"
            ], description="Entity 100 - Account 5000 - Project PROJ1")
        """
        from django.core.exceptions import ValidationError
        from django.db import transaction
        
        if not combination_list:
            raise ValidationError("Combination list cannot be empty")
        
        # Normalize and validate
        normalized_combo = []
        segment_type_ids = set()
        
        for item in combination_list:
            seg_type_id = item[0]
            seg_code = str(item[1])  # Ensure it's a string
            
            # Get segment_type object
            try:
                seg_type = XX_SegmentType.objects.get(id=seg_type_id)
            except XX_SegmentType.DoesNotExist:
                raise ValidationError(f"Segment type with ID {seg_type_id} does not exist")
            
            # Get segment object by code and type
            try:
                seg = XX_Segment.objects.get(
                    segment_type_id=seg_type_id,
                    code=seg_code
                )
            except XX_Segment.DoesNotExist:
                raise ValidationError(
                    f"Segment with code '{seg_code}' does not exist for segment type '{seg_type.segment_name}' (ID: {seg_type_id})"
                )
            
            # Check for duplicate segment types
            if seg_type.id in segment_type_ids:
                raise ValidationError(
                    f"Duplicate segment type '{seg_type.segment_name}' in combination. "
                    "Each segment type must appear only once."
                )
            segment_type_ids.add(seg_type.id)
            
            normalized_combo.append((seg_type, seg))
        
        # Create the combination with all details in a transaction
        with transaction.atomic():
            combination = cls.objects.create(description=description)
            
            for seg_type, seg in normalized_combo:
                segment_combination_detials.objects.create(
                    segment_combination=combination,
                    segment_type=seg_type,
                    segment=seg
                )
        
        return combination
    
    @classmethod
    def get_combination_id(cls, combination_list, description=None):
        """
        Get the ID of an existing combination, or create a new one if it doesn't exist.
        This is the main method you'll use throughout the application.
        
        Args:
            combination_list: List of tuples [(segment_type_id, segment_code), ...]
                             segment_type_id: int - The ID of the segment type
                             segment_code: str - The code of the segment value
            description: Optional description (only used if creating new combination)
        
        Returns:
            int: The ID of the combination (existing or newly created)
        
        Example:
            # Using segment type IDs and segment codes
            combo_id = XX_Segment_combination.get_combination_id([
                (1, "100"),    # Entity type ID=1, code="100"
                (2, "5000"),   # Account type ID=2, code="5000"
                (3, "PROJ1"),  # Project type ID=3, code="PROJ1"
            ])
            
            # With description
            combo_id = XX_Segment_combination.get_combination_id([
                (1, "100"),
                (2, "5000"),
                (3, "PROJ1"),
            ], description="My combination")
        """
        # Try to find existing combination
        existing = cls.find_combination(combination_list)
        
        if existing:
            return existing.id
        
        # Create new combination
        new_combo = cls.create_combination(combination_list, description)
        return new_combo.id

class segment_combination_detials(models.Model):
    """
    Details of a segment combination - links segment types and values to a combination.
    Each combination must have unique segment types (enforced by unique_together and validation).
    
    IMPORTANT: Once created, segment combination details are IMMUTABLE.
    They cannot be modified or deleted to maintain accounting integrity.
    """
    segment_combination = models.ForeignKey(
        XX_Segment_combination,
        on_delete=models.CASCADE,
        related_name='details',
        help_text="Parent segment combination"
    )
    segment_type = models.ForeignKey(
        XX_SegmentType,
        on_delete=models.CASCADE,
        help_text="Which segment type this value belongs to"
    )
    segment = models.ForeignKey(
        XX_Segment,
        on_delete=models.CASCADE,
        help_text="The actual segment code/value"
    )
    
    class Meta:
        db_table = "segment_combination_detials_XX"
        verbose_name = "Segment Combination Detail"
        verbose_name_plural = "Segment Combination Details"
        unique_together = ("segment_combination", "segment_type")
        indexes = [
            models.Index(fields=["segment_combination", "segment_type"]),
            models.Index(fields=["segment_type", "segment"]),
        ]

    def __str__(self):  
        return f"Combination {self.segment_combination.id}: {self.segment_type.segment_name}={self.segment.code}"
    
    def clean(self):
        """Validate that segment belongs to the correct segment_type"""
        from django.core.exceptions import ValidationError
        
        if self.segment and self.segment_type:
            if self.segment.segment_type_id != self.segment_type_id:
                raise ValidationError(
                    f"Segment '{self.segment.code}' does not belong to segment type '{self.segment_type.segment_name}'"
                )
    
    def save(self, *args, **kwargs):
        """
        Prevent modification of existing segment combination details.
        Once created, details are immutable for accounting integrity.
        """
        # Check if this is an update (not a new record)
        if self.pk is not None:
            raise ValidationError(
                f"Cannot modify Segment Combination Detail #{self.pk}. "
                "Segment combination details are immutable after creation for accounting integrity. "
                "Create a new combination instead."
            )
        
        # Validate before saving
        self.full_clean()
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion of segment combination details.
        Details are immutable once created.
        """
        raise ValidationError(
            f"Cannot delete Segment Combination Detail #{self.pk}. "
            "Segment combination details are immutable for accounting integrity."
        )

class JournalEntry(models.Model):
    date = models.DateField()
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    memo = models.CharField(max_length=255, blank=True)
    posted = models.BooleanField(default=False)

    def __str__(self):
        return f"JE#{self.id} - {self.date} - {self.memo or 'No memo'}"
    
    def save(self, *args, **kwargs):
        """
        Prevent modification of posted journal entries.
        Once posted, a journal entry becomes immutable.
        """
        # Check if this is an update (not a new record)
        if self.pk is not None:
            # Get the original record from database
            try:
                original = JournalEntry.objects.get(pk=self.pk)
                
                # If original was posted, prevent any changes
                if original.posted:
                    raise ValidationError(
                        f"Cannot modify Journal Entry #{self.pk} because it is already posted. "
                        "Posted entries are immutable for accounting integrity."
                    )
            except JournalEntry.DoesNotExist:
                # New record, allow save
                pass
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion of posted journal entries.
        """
        if self.posted:
            raise ValidationError(
                f"Cannot delete Journal Entry #{self.pk} because it is posted. "
                "Posted entries cannot be deleted for accounting integrity. "
                "Consider creating a reversing entry instead."
            )
        
        super().delete(*args, **kwargs)
    
    @classmethod
    def filter_by_segment(cls, segment_type_id, segment_code):
        """
        Filter journal entries that use a specific segment.
        
        Args:
            segment_type_id: int - The ID of the segment type
            segment_code: str - The code of the segment value
        
        Returns:
            QuerySet of JournalEntry objects
        
        Example:
            # Find all journal entries using Entity "100"
            entries = JournalEntry.filter_by_segment(1, "100")
        """
        # Find all combinations that include this segment
        combinations = XX_Segment_combination.objects.filter(
            details__segment_type_id=segment_type_id,
            details__segment__code=segment_code
        ).values_list('id', flat=True)
        
        # Find journal entries with lines using these combinations
        return cls.objects.filter(
            lines__segment_combination_id__in=combinations
        ).distinct()
    
    @classmethod
    def filter_by_segments(cls, segment_list):
        """
        Filter journal entries that use ALL of the specified segments.
        
        Args:
            segment_list: List of tuples [(segment_type_id, segment_code), ...]
        
        Returns:
            QuerySet of JournalEntry objects
        
        Example:
            # Find all journal entries using Entity "100" AND Account "5000"
            entries = JournalEntry.filter_by_segments([
                (1, "100"),    # Entity
                (2, "5000"),   # Account
            ])
        """
        if not segment_list:
            return cls.objects.none()
        
        # Start with all journal entries
        queryset = cls.objects.all()
        
        # Filter by each segment
        for segment_type_id, segment_code in segment_list:
            # Find combinations with this segment
            combinations = XX_Segment_combination.objects.filter(
                details__segment_type_id=segment_type_id,
                details__segment__code=segment_code
            ).values_list('id', flat=True)
            
            # Filter entries that have lines with these combinations
            queryset = queryset.filter(
                lines__segment_combination_id__in=combinations
            )
        
        return queryset.distinct()
    
    @classmethod
    def filter_by_any_segment(cls, segment_list):
        """
        Filter journal entries that use ANY of the specified segments.
        
        Args:
            segment_list: List of tuples [(segment_type_id, segment_code), ...]
        
        Returns:
            QuerySet of JournalEntry objects
        
        Example:
            # Find all journal entries using Entity "100" OR Entity "200"
            entries = JournalEntry.filter_by_any_segment([
                (1, "100"),    # Entity 100
                (1, "200"),    # Entity 200
            ])
        """
        from django.db.models import Q
        
        if not segment_list:
            return cls.objects.none()
        
        # Build Q objects for each segment
        q_objects = Q()
        for segment_type_id, segment_code in segment_list:
            # Find combinations with this segment
            combinations = XX_Segment_combination.objects.filter(
                details__segment_type_id=segment_type_id,
                details__segment__code=segment_code
            ).values_list('id', flat=True)
            
            # Add to Q objects
            q_objects |= Q(lines__segment_combination_id__in=combinations)
        
        return cls.objects.filter(q_objects).distinct()
    
    def get_total_debit(self):
        """
        Calculate the total debit amount for this journal entry.
        
        Returns:
            Decimal: Total debit amount
        
        Example:
            entry = JournalEntry.objects.get(id=1)
            total_debit = entry.get_total_debit()
        """
        from decimal import Decimal
        from django.db.models import Sum
        
        result = self.lines.filter(type='DEBIT').aggregate(
            total=Sum('amount')
        )
        return result['total'] or Decimal('0.00')
    
    def get_total_credit(self):
        """
        Calculate the total credit amount for this journal entry.
        
        Returns:
            Decimal: Total credit amount
        
        Example:
            entry = JournalEntry.objects.get(id=1)
            total_credit = entry.get_total_credit()
        """
        from decimal import Decimal
        from django.db.models import Sum
        
        result = self.lines.filter(type='CREDIT').aggregate(
            total=Sum('amount')
        )
        return result['total'] or Decimal('0.00')
    
    def is_balanced(self):
        """
        Check if the journal entry is balanced (debits = credits).
        
        Returns:
            bool: True if balanced, False otherwise
        
        Example:
            entry = JournalEntry.objects.get(id=1)
            if entry.is_balanced():
                print("Entry is balanced")
        """
        return self.get_total_debit() == self.get_total_credit()
    
    def get_balance_difference(self):
        """
        Get the difference between debits and credits.
        
        Returns:
            Decimal: Debit - Credit (positive if debits > credits)
        
        Example:
            entry = JournalEntry.objects.get(id=1)
            diff = entry.get_balance_difference()
            if diff != 0:
                print(f"Out of balance by: {diff}")
        """
        return self.get_total_debit() - self.get_total_credit()
    
    def post(self):
        """
        Post this journal entry to the General Ledger.
        
        This method:
        1. Validates that the entry is balanced (debits = credits)
        2. Sets the posted flag to True
        3. Creates a GeneralLedger entry with today's date
        
        Once posted, the journal entry becomes immutable.
        
        Returns:
            GeneralLedger: The created general ledger entry
        
        Raises:
            ValidationError: If entry is already posted or not balanced
        
        Example:
            entry = JournalEntry.objects.get(id=1)
            gl_entry = entry.post()
            print(f"Posted to GL#{gl_entry.id}")
        """
        from django.utils import timezone
        from django.db import transaction
        
        # Check if already posted
        if self.posted:
            raise ValidationError(
                f"Journal Entry #{self.pk} is already posted. "
                "Cannot post the same entry twice."
            )
        
        # Validate that entry is balanced
        if not self.is_balanced():
            diff = self.get_balance_difference()
            raise ValidationError(
                f"Cannot post Journal Entry #{self.pk} because it is not balanced. "
                f"Difference: {diff} (Debits: {self.get_total_debit()}, Credits: {self.get_total_credit()})"
            )
        
        # Post the entry in a transaction
        with transaction.atomic():
            # Set posted flag to True
            self.posted = True
            # Temporarily bypass the save validation for posting
            super(JournalEntry, self).save(update_fields=['posted'])
            
            # Create GeneralLedger entry with today's date
            gl_entry = GeneralLedger.objects.create(
                submitted_date=timezone.now().date(),
                JournalEntry=self
            )
        
        return gl_entry

class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, related_name="lines", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=14, decimal_places=5)
    type = models.CharField(max_length=16, choices=[
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ])
    segment_combination = models.ForeignKey('XX_Segment_combination', on_delete=models.PROTECT)
    
    def __str__(self):
        return f"JL#{self.id} - JE#{self.entry.id} - {self.type} {self.amount}"
    
    def save(self, *args, **kwargs):
        """
        Prevent modification of journal lines belonging to posted entries.
        """
        # Check if the parent journal entry is posted
        if self.entry and self.entry.posted:
            raise ValidationError(
                f"Cannot modify Journal Line #{self.pk} because its Journal Entry #{self.entry.id} is posted. "
                "Posted entries and their lines are immutable for accounting integrity."
            )
        
        # If updating an existing line, check if it was previously attached to a posted entry
        if self.pk is not None:
            try:
                original = JournalLine.objects.get(pk=self.pk)
                if original.entry and original.entry.posted:
                    raise ValidationError(
                        f"Cannot modify Journal Line #{self.pk} because its Journal Entry #{original.entry.id} is posted. "
                        "Posted entries and their lines are immutable for accounting integrity."
                    )
            except JournalLine.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion of journal lines belonging to posted entries.
        """
        if self.entry and self.entry.posted:
            raise ValidationError(
                f"Cannot delete Journal Line #{self.pk} because its Journal Entry #{self.entry.id} is posted. "
                "Posted entries and their lines cannot be deleted for accounting integrity."
            )
        
        super().delete(*args, **kwargs)

class GeneralLedger(models.Model):
    submitted_date = models.DateField()
    JournalEntry = models.ForeignKey(JournalEntry, related_name="GeneralLedger", on_delete=models.CASCADE)    
    def __str__(self):
        return f"GL#{self.id} - {self.submitted_date} - JE#{self.JournalEntry.id}"
    
    @classmethod
    def filter_by_segment(cls, segment_type_id, segment_code):
        """
        Filter general ledgers that use a specific segment.
        
        Args:
            segment_type_id: int - The ID of the segment type
            segment_code: str - The code of the segment value
        
        Returns:
            QuerySet of GeneralLedger objects
        
        Example:
            # Find all general ledgers using Entity "100"
            ledgers = GeneralLedger.filter_by_segment(1, "100")
        """
        # Find all combinations that include this segment
        combinations = XX_Segment_combination.objects.filter(
            details__segment_type_id=segment_type_id,
            details__segment__code=segment_code
        ).values_list('id', flat=True)
        
        # Find general ledgers whose journal entries have lines using these combinations
        return cls.objects.filter(
            JournalEntry__lines__segment_combination_id__in=combinations
        ).distinct()
    
    @classmethod
    def filter_by_segments(cls, segment_list):
        """
        Filter general ledgers that use ALL of the specified segments.
        
        Args:
            segment_list: List of tuples [(segment_type_id, segment_code), ...]
        
        Returns:
            QuerySet of GeneralLedger objects
        
        Example:
            # Find all general ledgers using Entity "100" AND Account "5000"
            ledgers = GeneralLedger.filter_by_segments([
                (1, "100"),    # Entity
                (2, "5000"),   # Account
            ])
        """
        if not segment_list:
            return cls.objects.none()
        
        # Start with all general ledgers
        queryset = cls.objects.all()
        
        # Filter by each segment
        for segment_type_id, segment_code in segment_list:
            # Find combinations with this segment
            combinations = XX_Segment_combination.objects.filter(
                details__segment_type_id=segment_type_id,
                details__segment__code=segment_code
            ).values_list('id', flat=True)
            
            # Filter ledgers whose journal entries have lines with these combinations
            queryset = queryset.filter(
                JournalEntry__lines__segment_combination_id__in=combinations
            )
        
        return queryset.distinct()
    
    @classmethod
    def filter_by_any_segment(cls, segment_list):
        """
        Filter general ledgers that use ANY of the specified segments.
        
        Args:
            segment_list: List of tuples [(segment_type_id, segment_code), ...]
        
        Returns:
            QuerySet of GeneralLedger objects
        
        Example:
            # Find all general ledgers using Entity "100" OR Entity "200"
            ledgers = GeneralLedger.filter_by_any_segment([
                (1, "100"),    # Entity 100
                (1, "200"),    # Entity 200
            ])
        """
        from django.db.models import Q
        
        if not segment_list:
            return cls.objects.none()
        
        # Build Q objects for each segment
        q_objects = Q()
        for segment_type_id, segment_code in segment_list:
            # Find combinations with this segment
            combinations = XX_Segment_combination.objects.filter(
                details__segment_type_id=segment_type_id,
                details__segment__code=segment_code
            ).values_list('id', flat=True)
            
            # Add to Q objects
            q_objects |= Q(JournalEntry__lines__segment_combination_id__in=combinations)
        
        return cls.objects.filter(q_objects).distinct()


