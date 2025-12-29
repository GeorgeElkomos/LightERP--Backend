from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from HR.work_structures.dtos import (
    EnterpriseCreateDTO, EnterpriseUpdateDTO,
    BusinessGroupCreateDTO, BusinessGroupUpdateDTO
)
from HR.work_structures.models import Enterprise, BusinessGroup, Department
from HR.work_structures.security import validate_location_scope

class StructureService:
    
    @staticmethod
    @transaction.atomic
    def create_enterprise(user, dto: EnterpriseCreateDTO):
        """Create enterprise with date tracking"""
        # Validate scope - Enterprise creation requires global access
        validate_location_scope(user, enterprise_id=None, business_group_id=None) # This will check global scope
        
        enterprise = Enterprise(
            code=dto.code,
            name=dto.name,
            effective_start_date=dto.effective_start_date or timezone.now().date(),
            effective_end_date=dto.effective_end_date
        )
        enterprise.full_clean()
        enterprise.save()
        return enterprise

    @staticmethod
    @transaction.atomic
    def update_enterprise(user, dto: EnterpriseUpdateDTO):
        """
        Update enterprise.
        - If new_start_date == current.effective_start_date: Correct current record.
        - Otherwise: End-date current record and create new version.
        """
        current = Enterprise.objects.active().filter(code=dto.code).first()
        if not current:
            raise ValidationError("No active enterprise found")
        
        # Validate scope - Enterprise update requires global access
        validate_location_scope(user) 
        
        # Determine effective dates
        # If effective_start_date not provided, keep original date (correction mode)
        if dto.effective_start_date is not None:
            new_start_date = dto.effective_start_date
        else:
            new_start_date = current.effective_start_date
        
        provided = getattr(dto, '_provided_fields', None)
        
        def is_provided(field_name):
            if provided is not None:
                return field_name in provided
            return getattr(dto, field_name) is not None

        # Same-day update = Correction
        # Correction mode: effective_start_date not provided OR equals current date
        if new_start_date == current.effective_start_date:
            if is_provided('name'):
                current.name = dto.name
            if is_provided('effective_end_date'):
                current.effective_end_date = dto.effective_end_date
                
            current.full_clean()
            current.save()
            return current
        
        # Different day = New Version
        # Capture original end date before modifying current
        original_end_date = current.effective_end_date
        
        # End current version
        current.effective_end_date = new_start_date - timedelta(days=1)
        current.full_clean()
        current.save()
        
        # Create new version
        new_version = Enterprise(
            code=current.code,
            name=dto.name if is_provided('name') else current.name,
            effective_start_date=new_start_date,
            effective_end_date=dto.effective_end_date if is_provided('effective_end_date') else original_end_date
        )
        new_version.full_clean()
        new_version.save()
        return new_version

    @staticmethod
    @transaction.atomic
    def create_business_group(user, dto: BusinessGroupCreateDTO):
        """Create business group with date tracking"""
        # Validate scope - creation requires access to parent Enterprise
        validate_location_scope(user, enterprise_id=dto.enterprise_id)
        
        bg = BusinessGroup(
            enterprise_id=dto.enterprise_id,
            code=dto.code,
            name=dto.name,
            effective_start_date=dto.effective_start_date or timezone.now().date(),
            effective_end_date=dto.effective_end_date
        )
        bg.full_clean()
        bg.save()
        return bg

    @staticmethod
    @transaction.atomic
    def update_business_group(user, dto: BusinessGroupUpdateDTO):
        """
        Update business group.
        - If new_start_date == current.effective_start_date: Correct current record.
        - Otherwise: End-date current record and create new version.
        """
        current = BusinessGroup.objects.active().filter(code=dto.code).first()
        if not current:
            raise ValidationError("No active business group found")
        
        # Validate scope - update requires access to the BG or its Enterprise
        validate_location_scope(user, enterprise_id=current.enterprise_id, business_group_id=current.id)
        
        # Determine effective dates
        # If effective_start_date not provided, keep original date (correction mode)
        if dto.effective_start_date is not None:
            new_start_date = dto.effective_start_date
        else:
            new_start_date = current.effective_start_date
        
        provided = getattr(dto, '_provided_fields', None)
        
        def is_provided(field_name):
            if provided is not None:
                return field_name in provided
            return getattr(dto, field_name) is not None

        # Same-day update = Correction
        # Correction mode: effective_start_date not provided OR equals current date
        if new_start_date == current.effective_start_date:
            if is_provided('name'):
                current.name = dto.name
            if is_provided('effective_end_date'):
                current.effective_end_date = dto.effective_end_date

            current.full_clean()
            current.save()
            return current
        
        # Different day = New Version
        # Capture original end date before modifying current
        original_end_date = current.effective_end_date
        
        # End current version
        current.effective_end_date = new_start_date - timedelta(days=1)
        current.full_clean()
        current.save()
        
        # Create new version
        new_version = BusinessGroup(
            enterprise_id=current.enterprise_id,
            code=current.code,
            name=dto.name if is_provided('name') else current.name,
            effective_start_date=new_start_date,
            effective_end_date=dto.effective_end_date if is_provided('effective_end_date') else original_end_date
        )
        new_version.full_clean()
        new_version.save()
        return new_version

    @staticmethod
    @transaction.atomic
    def deactivate_enterprise(user, pk, effective_end_date=None):
        enterprise = Enterprise.objects.get(pk=pk)
        
        # Validate scope - Enterprise deactivation requires global access
        validate_location_scope(user)
        
        # Validate no active business groups
        active_bgs = BusinessGroup.objects.filter(enterprise=enterprise).active()
        if active_bgs.exists():
            raise ValidationError(
                f'Cannot deactivate enterprise with {active_bgs.count()} active business group(s). '
                'Please deactivate all business groups first.'
            )
        
        enterprise.deactivate(end_date=effective_end_date)
        return enterprise

    @staticmethod
    @transaction.atomic
    def deactivate_business_group(user, pk, effective_end_date=None):
        bg = BusinessGroup.objects.get(pk=pk)
        
        # Validate scope - deactivation requires access to the BG or its Enterprise
        validate_location_scope(user, enterprise_id=bg.enterprise_id, business_group_id=bg.id)
        
        # Validate no active departments
        active_depts = Department.objects.filter(business_group=bg).active()
        if active_depts.exists():
            raise ValidationError(
                f'Cannot deactivate business group with {active_depts.count()} active department(s). '
                'Please deactivate all departments first.'
            )
        
        bg.deactivate(end_date=effective_end_date)
        return bg
