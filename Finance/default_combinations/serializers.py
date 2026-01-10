"""
Default Combinations Serializers
API serializers for set_default_combinations model
"""
from rest_framework import serializers
from Finance.default_combinations.models import set_default_combinations
from Finance.GL.models import XX_Segment_combination


class DefaultCombinationsListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing default combinations (lightweight)
    """
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display',
        read_only=True
    )
    segment_combination_id = serializers.IntegerField(
        source='segment_combination.id',
        read_only=True
    )
    segment_combination_description = serializers.CharField(
        source='segment_combination.description',
        read_only=True,
        allow_null=True
    )
    created_by_username = serializers.CharField(
        source='created_by.email',
        read_only=True
    )
    updated_by_username = serializers.CharField(
        source='updated_by.email',
        read_only=True,
        allow_null=True
    )
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = set_default_combinations
        fields = [
            'id',
            'transaction_type',
            'transaction_type_display',
            'segment_combination_id',
            'segment_combination_description',
            'is_active',
            'is_valid',
            'created_by_username',
            'created_at',
            'updated_by_username',
            'updated_at'
        ]
    
    def get_is_valid(self, obj):
        """Check if the segment combination is valid"""
        is_valid, _ = obj.validate_segment_combination_completeness()
        return is_valid


class DefaultCombinationsDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for default combinations with full segment information
    """
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display',
        read_only=True
    )
    segment_combination_id = serializers.IntegerField(
        source='segment_combination.id',
        read_only=True
    )
    segment_details = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(
        source='created_by.email',
        read_only=True
    )
    created_by_id = serializers.IntegerField(
        source='created_by.id',
        read_only=True
    )
    updated_by_username = serializers.CharField(
        source='updated_by.email',
        read_only=True,
        allow_null=True
    )
    updated_by_id = serializers.IntegerField(
        source='updated_by.id',
        read_only=True,
        allow_null=True
    )
    validation_status = serializers.SerializerMethodField()
    
    class Meta:
        model = set_default_combinations
        fields = [
            'id',
            'transaction_type',
            'transaction_type_display',
            'segment_combination_id',
            'segment_details',
            'is_active',
            'validation_status',
            'created_by_id',
            'created_by_username',
            'created_at',
            'updated_by_id',
            'updated_by_username',
            'updated_at'
        ]
    
    def get_segment_details(self, obj):
        """Get detailed segment information"""
        return obj.get_segment_details()
    
    def get_validation_status(self, obj):
        """Get validation status with error message if invalid"""
        is_valid, error_msg = obj.validate_segment_combination_completeness()
        return {
            'is_valid': is_valid,
            'error_message': error_msg if not is_valid else None
        }


class SegmentInputSerializer(serializers.Serializer):
    """
    Nested serializer for segment input
    """
    segment_type_id = serializers.IntegerField(
        min_value=1,
        help_text="ID of the segment type"
    )
    segment_code = serializers.CharField(
        max_length=50,
        help_text="Code of the segment value"
    )


class DefaultCombinationsCreateSerializer(serializers.Serializer):
    """
    Serializer for creating new default combinations
    Accepts segments directly instead of segment_combination_id
    Uses create_or_update_default method to ensure uniqueness
    """
    transaction_type = serializers.ChoiceField(
        choices=set_default_combinations.TRANSACTION_TYPES,
        help_text="Type of transaction for the default combination"
    )
    segments = serializers.ListField(
        child=SegmentInputSerializer(),
        min_length=1,
        help_text="List of segments defining the GL account combination"
    )
    
    def validate_segments(self, value):
        """Validate that all segments exist and are unique by segment type"""
        from Finance.GL.models import XX_SegmentType, XX_Segment
        
        segment_type_ids = set()
        validated_segments = []
        
        for segment_data in value:
            segment_type_id = segment_data['segment_type_id']
            segment_code = segment_data['segment_code']
            
            # Check for duplicate segment types
            if segment_type_id in segment_type_ids:
                raise serializers.ValidationError(
                    f"Duplicate segment type ID {segment_type_id}. "
                    "Each segment type must appear only once."
                )
            segment_type_ids.add(segment_type_id)
            
            # Validate segment type exists
            try:
                segment_type = XX_SegmentType.objects.get(id=segment_type_id)
            except XX_SegmentType.DoesNotExist:
                raise serializers.ValidationError(
                    f"Segment type with ID {segment_type_id} does not exist"
                )
            
            # Validate segment exists and matches the segment type
            try:
                segment = XX_Segment.objects.get(
                    segment_type_id=segment_type_id,
                    code=segment_code
                )
                if not segment.is_active:
                    raise serializers.ValidationError(
                        f"Segment '{segment_code}' for segment type '{segment_type.segment_name}' is not active"
                    )
            except XX_Segment.DoesNotExist:
                raise serializers.ValidationError(
                    f"Segment with code '{segment_code}' does not exist for segment type '{segment_type.segment_name}' (ID: {segment_type_id})"
                )
            
            validated_segments.append((segment_type_id, segment_code))
        
        return validated_segments
    
    def validate(self, data):
        """Additional validation before create"""
        # Get or create the segment combination
        combination_list = data['segments']
        
        # Try to find or create the combination
        segment_combination = XX_Segment_combination.find_combination(combination_list)
        
        if not segment_combination:
            # Create new combination
            try:
                segment_combination = XX_Segment_combination.create_combination(
                    combination_list,
                    description=f"Auto-created for {data['transaction_type']}"
                )
            except Exception as e:
                raise serializers.ValidationError({
                    'segments': f"Failed to create segment combination: {str(e)}"
                })
        
        # Store the combination in validated data
        data['_segment_combination'] = segment_combination
        
        # Create temporary instance to validate completeness
        temp_instance = set_default_combinations(
            transaction_type=data['transaction_type'],
            segment_combination=segment_combination
        )
        
        is_valid, error_msg = temp_instance.validate_segment_combination_completeness()
        if not is_valid:
            raise serializers.ValidationError({
                'segments': error_msg
            })
        
        return data
    
    def create(self, validated_data):
        """Create or update default combination"""
        segment_combination = validated_data['_segment_combination']
        
        request = self.context.get('request')
        user = request.user if request else None
        
        instance, created = set_default_combinations.create_or_update_default(
            transaction_type=validated_data['transaction_type'],
            segment_combination=segment_combination,
            user=user
        )
        
        return instance


class DefaultCombinationsUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating existing default combinations
    Accepts segments directly instead of segment_combination_id
    """
    segments = serializers.ListField(
        child=SegmentInputSerializer(),
        min_length=1,
        help_text="List of segments defining the new GL account combination"
    )
    
    def validate_segments(self, value):
        """Validate that all segments exist and are unique by segment type"""
        from Finance.GL.models import XX_SegmentType, XX_Segment
        
        segment_type_ids = set()
        validated_segments = []
        
        for segment_data in value:
            segment_type_id = segment_data['segment_type_id']
            segment_code = segment_data['segment_code']
            
            # Check for duplicate segment types
            if segment_type_id in segment_type_ids:
                raise serializers.ValidationError(
                    f"Duplicate segment type ID {segment_type_id}. "
                    "Each segment type must appear only once."
                )
            segment_type_ids.add(segment_type_id)
            
            # Validate segment type exists
            try:
                segment_type = XX_SegmentType.objects.get(id=segment_type_id)
            except XX_SegmentType.DoesNotExist:
                raise serializers.ValidationError(
                    f"Segment type with ID {segment_type_id} does not exist"
                )
            
            # Validate segment exists and matches the segment type
            try:
                segment = XX_Segment.objects.get(
                    segment_type_id=segment_type_id,
                    code=segment_code
                )
                if not segment.is_active:
                    raise serializers.ValidationError(
                        f"Segment '{segment_code}' for segment type '{segment_type.segment_name}' is not active"
                    )
            except XX_Segment.DoesNotExist:
                raise serializers.ValidationError(
                    f"Segment with code '{segment_code}' does not exist for segment type '{segment_type.segment_name}' (ID: {segment_type_id})"
                )
            
            validated_segments.append((segment_type_id, segment_code))
        
        return validated_segments
    
    def validate(self, data):
        """Validate completeness of the new combination"""
        instance = self.instance
        combination_list = data['segments']
        
        # Get or create the segment combination
        segment_combination = XX_Segment_combination.find_combination(combination_list)
        
        if not segment_combination:
            # Create new combination
            try:
                segment_combination = XX_Segment_combination.create_combination(
                    combination_list,
                    description=f"Auto-created for {instance.transaction_type}"
                )
            except Exception as e:
                raise serializers.ValidationError({
                    'segments': f"Failed to create segment combination: {str(e)}"
                })
        
        # Store the combination in validated data
        data['_segment_combination'] = segment_combination
        
        # Create temporary instance to validate
        temp_instance = set_default_combinations(
            transaction_type=instance.transaction_type,
            segment_combination=segment_combination
        )
        
        is_valid, error_msg = temp_instance.validate_segment_combination_completeness()
        if not is_valid:
            raise serializers.ValidationError({
                'segments': error_msg
            })
        
        return data
    
    def update(self, instance, validated_data):
        """Update the default combination"""
        segment_combination = validated_data['_segment_combination']
        
        request = self.context.get('request')
        user = request.user if request else None
        
        instance.update_default(segment_combination, user)
        
        return instance


class DefaultCombinationsValidationSerializer(serializers.Serializer):
    """
    Serializer for validation check responses
    """
    transaction_type = serializers.CharField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    error_message = serializers.CharField(read_only=True, allow_null=True)
    
    def to_representation(self, instance):
        """Convert model instance to validation response"""
        is_valid, error_msg = instance.validate_segment_combination_completeness()
        
        return {
            'transaction_type': instance.transaction_type,
            'is_valid': is_valid,
            'is_active': instance.is_active,
            'error_message': error_msg if not is_valid else None
        }
