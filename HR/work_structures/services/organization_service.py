from django.db import transaction, models
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import date
from typing import List, Dict, Any
from HR.work_structures.dtos import OrganizationCreateDTO, OrganizationUpdateDTO
from HR.work_structures.models import Organization, Location
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class OrganizationService:
    """Service for Organization business logic"""

    @staticmethod
    def list_organizations(filters: dict = None) -> models.QuerySet:
        """
        List organizations with flexible filtering.

        Args:
            filters: Dictionary of filters
                - business_group: ID
                - location_id: ID
                - search: Search query string
                - as_of_date: Date to check active status (default: today)

        Returns:
            QuerySet of Organization objects
        """
        filters = filters or {}
        
        # Base Queryset
        queryset = Organization.objects.all().select_related(
            'organization_type', 'location', 'business_group', 'business_group__organization_type'
        ).order_by('organization_name')

        # Date filter (default to ALL if not specified or 'ALL')
        as_of_date = filters.get('as_of_date')
        if as_of_date and as_of_date != 'ALL':
             queryset = queryset.active_on(as_of_date)

        # Apply filters
        bg_filter = filters.get('business_group')
        if bg_filter:
            queryset = queryset.filter(business_group_id=bg_filter)

        is_business_group = filters.get('is_business_group')
        if is_business_group is not None:
            # Handle boolean conversion from string if necessary
            if isinstance(is_business_group, str):
                is_business_group = is_business_group.lower() == 'true'
            
            if is_business_group:
                queryset = queryset.filter(business_group__isnull=True)
            else:
                queryset = queryset.filter(business_group__isnull=False)

        location_id = filters.get('location_id')
        if location_id:
            queryset = queryset.filter(location_id=location_id)

        search_query = filters.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(organization_name__icontains=search_query) |
                Q(organization_type__name__icontains=search_query)
            )

        return queryset

    @staticmethod
    @transaction.atomic
    def create(user, dto: OrganizationCreateDTO) -> Organization:
        """
        Create new organization with validation.

        Validates:
        - Organization type lookup is valid and active
        - Location exists
        - If business_group provided, it must be a root organization and active
        - Classification lookups are valid
        - Work times are valid
        - No circular references
        """
        # Validate organization type lookup
        try:
            organization_type = LookupValue.objects.get(pk=dto.organization_type_id)
            if organization_type.lookup_type.name != CoreLookups.ORGANIZATION_TYPE:
                raise ValidationError({'organization_type_id': 'Must be an ORGANIZATION_TYPE lookup value'})
            if not organization_type.is_active:
                raise ValidationError({'organization_type_id': 'Selected organization type is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'organization_type_id': 'Organization type lookup not found'})

        # Validate location
        location = None
        if dto.location_id:
            try:
                location = Location.objects.active().get(pk=dto.location_id)
            except Location.DoesNotExist:
                raise ValidationError({'location_id': 'Location not found or inactive'})

        # Validate business group (if provided)
        business_group = None
        if dto.business_group_id:
            try:
                # Get active version of business group
                today = date.today()
                business_group = Organization.objects.active_on(today).get(pk=dto.business_group_id)

                # Must be a root organization
                if not business_group.is_business_group:
                    raise ValidationError({
                        'business_group_id': 'Business group must be a root organization'
                    })
            except Organization.DoesNotExist:
                raise ValidationError({'business_group_id': 'Business group not found or inactive'})

        # Validate work times
        if dto.work_end_time <= dto.work_start_time:
            raise ValidationError({
                'work_end_time': 'Work end time must be after work start time'
            })

        # Set effective_start_date to today if not provided
        effective_start = dto.effective_start_date or date.today()

        # Create organization
        organization = Organization(
            organization_name=dto.organization_name,
            business_group=business_group,
            organization_type=organization_type,
            location=location,
            work_start_time=dto.work_start_time,
            work_end_time=dto.work_end_time,
            effective_start_date=effective_start,
            effective_end_date=dto.effective_end_date,
            created_by=user,
            updated_by=user
        )
        organization.full_clean()
        organization.save()


        return organization

    @staticmethod
    @transaction.atomic
    def update(user, dto: OrganizationUpdateDTO) -> Organization:
        """
        Update existing organization using VersionedMixin.update_version().

        This method updates the current active version in-place (correction mode).
        To create a new version with a different start date, use update_version directly.

        Validates:
        - Organization exists and is active
        - If lookups updated, validates them
        - Work times are valid
        """
        today = date.today()
        try:
            # Get current active version
            organization = Organization.objects.active_on(today).get(pk=dto.organization_id)
        except Organization.DoesNotExist:
            raise ValidationError(f"No active organization found with ID '{dto.organization_id}'")

        # Build field updates dictionary
        field_updates = {}

        # Validate and prepare name update
        if dto.organization_name is not None:
            # Check for uniqueness if name is changing
            if dto.organization_name != organization.organization_name:
                if Organization.objects.filter(organization_name=dto.organization_name).exists():
                    raise ValidationError({'organization_name': 'Organization name already exists'})
                field_updates['organization_name'] = dto.organization_name

        # Validate and prepare organization_type update
        if dto.organization_type_id is not None:
            try:
                org_type = LookupValue.objects.get(pk=dto.organization_type_id)
                if org_type.lookup_type.name != CoreLookups.ORGANIZATION_TYPE:
                    raise ValidationError({'organization_type_id': 'Must be an ORGANIZATION_TYPE lookup value'})
                if not org_type.is_active:
                    raise ValidationError({'organization_type_id': 'Selected organization type is inactive'})
                field_updates['organization_type'] = org_type
            except LookupValue.DoesNotExist:
                raise ValidationError({'organization_type_id': 'Organization type lookup not found'})

        # Validate and prepare location update
        if dto.location_id is not None:
            try:
                location = Location.objects.active().get(pk=dto.location_id)
                field_updates['location'] = location
            except Location.DoesNotExist:
                raise ValidationError({'location_id': 'Location not found or inactive'})

        # Prepare work times updates
        if dto.work_start_time is not None:
            field_updates['work_start_time'] = dto.work_start_time
        if dto.work_end_time is not None:
            field_updates['work_end_time'] = dto.work_end_time

        # Validate work times if both are being updated or if updating one when other exists
        work_start = field_updates.get('work_start_time', organization.work_start_time)
        work_end = field_updates.get('work_end_time', organization.work_end_time)
        if work_end <= work_start:
            raise ValidationError({
                'work_end_time': 'Work end time must be after work start time'
            })

        # Use VersionedMixin.update_version() in correction mode (no new_start_date)
        # This updates the current record in-place
        updated = organization.update_version(
            field_updates=field_updates,
            new_end_date=dto.effective_end_date
        )


        updated.updated_by = user
        updated.save(update_fields=['updated_by'])
        return updated

    @staticmethod
    @transaction.atomic
    def deactivate(user, organization_id: int, effective_end_date: date = None) -> Organization:
        """
        Deactivate organization by setting effective_end_date.

        Uses VersionedMixin.deactivate() pattern:
        - If no end_date provided: defaults to yesterday (inactive today)
        - If end_date provided: uses that date

        Args:
            user: User performing deactivation
            organization_id: Organization ID
            effective_end_date: Date to end effectiveness (defaults to yesterday per VersionedMixin)

        Returns:
            Deactivated organization
        """
        today = date.today()
        try:
            organization = Organization.objects.active_on(today).get(pk=organization_id)
        except Organization.DoesNotExist:
            raise ValidationError(f"No active organization found with ID '{organization_id}'")

        # Dependency Checks
        check_date = effective_end_date or today

        # 1. Check for active child organizations (if business group)
        if organization.is_business_group:
            child_count = Organization.objects.active_on(check_date).filter(
                business_group_id=organization.id
            ).count()
            if child_count > 0:
                raise ValidationError(
                    f"Cannot deactivate Business Group '{organization.organization_name}' because it has {child_count} active child organizations."
                )

        # 2. Check for active Jobs (if business group)
        from HR.work_structures.models import Job, Position
        if organization.is_business_group:
            job_count = Job.objects.active_on(check_date).filter(
                business_group_id=organization.id
            ).count()
            if job_count > 0:
                raise ValidationError(
                    f"Cannot deactivate Business Group '{organization.organization_name}' because it has {job_count} active jobs."
                )

        # 3. Check for active Positions (using this organization)
        # Position links to organization (department)
        position_count = Position.objects.active_on(check_date).filter(
            organization_id=organization.id
        ).count()
        if position_count > 0:
             raise ValidationError(
                f"Cannot deactivate Organization '{organization.organization_name}' because it has {position_count} active positions."
            )

        # 4. Check for active Assignments (using this organization or business group)
        from HR.person.models import Assignment
        
        # Check as department
        dept_assign_count = Assignment.objects.active_on(check_date).filter(
            department_id=organization.id
        ).count()
        if dept_assign_count > 0:
            raise ValidationError(
                f"Cannot deactivate Organization '{organization.organization_name}' because it is used by {dept_assign_count} active employee assignments (as department)."
            )

        # Check as business group
        if organization.is_business_group:
            bg_assign_count = Assignment.objects.active_on(check_date).filter(
                business_group_id=organization.id
            ).count()
            if bg_assign_count > 0:
                raise ValidationError(
                    f"Cannot deactivate Business Group '{organization.organization_name}' because it is used by {bg_assign_count} active employee assignments."
                )

        # Use VersionedMixin.deactivate() method
        organization.deactivate(end_date=effective_end_date)
        organization.updated_by = user
        organization.save(update_fields=['updated_by'])
        return organization

    @staticmethod
    def get_business_groups() -> List[Organization]:
        """Get all active root business groups"""
        today = date.today()
        return Organization.objects.active_on(today).filter(
            business_group__isnull=True
        ).select_related('location').order_by('organization_name')

    @staticmethod
    def get_children(business_group_id: int) -> List[Organization]:
        """Get all active child organizations for a business group"""
        today = date.today()
        return Organization.objects.active_on(today).filter(
            business_group_id=business_group_id
        ).select_related('location', 'business_group').order_by('organization_name')

    @staticmethod
    def get_organization_hierarchy(business_group_id: int) -> Dict[str, Any]:
        """
        Get organization hierarchy as nested dictionary structure.

        Returns:
        {
            'id': int,
            'organization_name': str,
            'organization_type': str,
            'is_business_group': bool,
            'hierarchy_level': int,
            'children': [...]  # Recursive list of child organizations
        }
        """
        today = date.today()

        # Get the business group
        try:
            bg = Organization.objects.active_on(today).get(pk=business_group_id)
            if not bg.is_business_group:
                raise ValidationError('Provided organization is not a business group')
        except Organization.DoesNotExist:
            raise ValidationError('Business group not found or inactive')

        # Get all child organizations for this business group
        children = Organization.objects.active_on(today).filter(
            business_group_id=business_group_id
        ).select_related('organization_type', 'location').order_by('organization_name')  # Explicit ordering to avoid FK loop

        # Build hierarchy recursively
        def build_tree(org):
            """Build tree structure for an organization"""
            node = {
                'id': org.id,
                'organization_name': org.organization_name,
                'organization_type': org.organization_type.name,
                'is_business_group': org.is_business_group,
                'hierarchy_level': org.hierarchy_level,
                'location': {
                    'id': org.location.id,
                    'name': org.location.location_name
                } if org.location else None,
                'working_hours': org.working_hours,
                'children': []
            }

            # Find direct children (organizations that have this org as business_group)
            # Note: This is simplified - for true hierarchy, would need parent field
            # For now, all children under BG are at same level

            return node

        # Build tree starting from business group
        root = build_tree(bg)

        # Add all child organizations (flat structure for now)
        for child in children:
            root['children'].append(build_tree(child))

        return root

    @staticmethod
    def validate_no_circular_reference(org_id: int, business_group_id: int) -> bool:
        """
        Validate that setting business_group_id doesn't create circular reference.

        Returns True if valid, raises ValidationError if circular reference detected.
        """
        if org_id == business_group_id:
            raise ValidationError('Organization cannot be its own business group')

        # Check if business_group_id is a descendant of org_id
        # For now, with flat hierarchy (BG -> children), this is simple
        # Just ensure business_group is a root org
        try:
            bg = Organization.objects.get(pk=business_group_id)
            if not bg.is_business_group:
                raise ValidationError('Business group must be a root organization')
        except Organization.DoesNotExist:
            raise ValidationError('Business group not found')

        return True

    @staticmethod
    def get_by_organization_name(organization_name: str, as_of_date: date = None) -> Organization:
        """Get organization by organization_name as of a specific date"""
        as_of = as_of_date or date.today()
        try:
            return Organization.objects.active_on(as_of).get(organization_name=organization_name)
        except Organization.DoesNotExist:
            raise ValidationError(f"No organization found with organization_name '{organization_name}' as of {as_of}")

