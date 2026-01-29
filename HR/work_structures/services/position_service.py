from django.db import transaction, models
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import date
from typing import List, Optional
from decimal import Decimal
from HR.work_structures.dtos import PositionCreateDTO, PositionUpdateDTO
from HR.work_structures.models import Position, Organization, Job, Grade, Location
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class PositionService:
    """Service for Position business logic"""

    @staticmethod
    def list_positions(filters: dict = None) -> models.QuerySet:
        """List positions with flexible filtering."""
        filters = filters or {}
        queryset = Position.objects.all()
        
        # Date filter (default to ALL if not specified or 'ALL')
        as_of_date = filters.get('as_of_date')
        if as_of_date and as_of_date != 'ALL':
             queryset = queryset.active_on(as_of_date)

        # Basic filters
        if filters.get('organization_id'):
            queryset = queryset.filter(organization_id=filters.get('organization_id'))
            
        if filters.get('job_id'):
            queryset = queryset.filter(job_id=filters.get('job_id'))
            
        if filters.get('location_id'):
            queryset = queryset.filter(location_id=filters.get('location_id'))
            
        # Search filter
        search_query = filters.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(code__icontains=search_query) |
                Q(position_title__name__icontains=search_query)
            )
            
        return queryset.select_related(
            'organization',
            'job',
            'location',
            'position_title',
            'position_type',
            'position_status'
        ).order_by('organization__organization_name', 'code')

    @staticmethod
    @transaction.atomic
    def create(user, dto: PositionCreateDTO) -> Position:
        """
        Create new position with validation.

        Validates:
        - Business group exists and is root
        - Organization belongs to business group
        - Job belongs to business group
        - Grade belongs to business group
        - Location belongs to business group
        - All lookup values are valid and active
        - FTE is in valid range (0.1-1.5)
        - Head count > 0
        """
        today = date.today()
        # Validate organization exists and belongs to a business group
        try:
            organization = Organization.objects.active_on(today).get(pk=dto.organization_id)
            business_group = organization.get_root_business_group()
            
            if not business_group or not business_group.is_business_group:
                raise ValidationError({
                    'organization_id': 'Position must belong to an organization within a valid Business Group'
                })
                
            # Check if business group is active today
            if hasattr(business_group, 'effective_end_date'):
                if not business_group.active_on(today):
                     raise ValidationError({'organization_id': f'Business group "{business_group.organization_name}" is inactive'})

        except Organization.DoesNotExist:
            raise ValidationError({'organization_id': 'Organization not found or inactive'})

        # Validate job belongs to business group
        try:
            job = Job.objects.active_on(today).get(pk=dto.job_id)
            if job.business_group_id != business_group.id:
                raise ValidationError({
                    'job_id': f'Job must belong to business group "{business_group.organization_name}"'
                })
        except Job.DoesNotExist:
            raise ValidationError({'job_id': 'Job not found or inactive'})

        # Validate grade belongs to business group
        try:
            grade = Grade.objects.active().get(pk=dto.grade_id)
            if grade.organization_id != business_group.id:
                raise ValidationError({
                    'grade_id': f'Grade must belong to business group "{business_group.organization_name}"'
                })
        except Grade.DoesNotExist:
            raise ValidationError({'grade_id': 'Grade not found or inactive'})

        # Validate location belongs to business group (if provided)
        if dto.location_id:
            try:
                location = Location.objects.active().get(pk=dto.location_id)
                if location.business_group_id != business_group.id:
                    raise ValidationError({
                        'location_id': f'Location must belong to business group "{business_group.organization_name}"'
                    })
            except Location.DoesNotExist:
                raise ValidationError({'location_id': 'Location not found or inactive'})

        # Validate position title
        try:
            position_title = LookupValue.objects.get(pk=dto.position_title_id)
            if position_title.lookup_type.name != CoreLookups.POSITION_TITLE:
                raise ValidationError({'position_title_id': 'Must be a POSITION_TITLE lookup value'})
            if not position_title.is_active:
                raise ValidationError({'position_title_id': f'Position title "{position_title.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'position_title_id': 'Position title not found'})

        # Validate position type
        try:
            position_type = LookupValue.objects.get(pk=dto.position_type_id)
            if position_type.lookup_type.name != CoreLookups.POSITION_TYPE:
                raise ValidationError({'position_type_id': 'Must be a POSITION_TYPE lookup value'})
            if not position_type.is_active:
                raise ValidationError({'position_type_id': f'Position type "{position_type.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'position_type_id': 'Position type not found'})

        # Validate position status
        try:
            position_status = LookupValue.objects.get(pk=dto.position_status_id)
            if position_status.lookup_type.name != CoreLookups.POSITION_STATUS:
                raise ValidationError({'position_status_id': 'Must be a POSITION_STATUS lookup value'})
            if not position_status.is_active:
                raise ValidationError({'position_status_id': f'Position status "{position_status.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'position_status_id': 'Position status not found'})


        # Validate FTE range
        fte = Decimal(str(dto.full_time_equivalent))
        if fte < Decimal('0.1') or fte > Decimal('1.5'):
            raise ValidationError({'full_time_equivalent': 'FTE must be between 0.1 and 1.5'})

        # Validate head count
        if dto.head_count <= 0:
            raise ValidationError({'head_count': 'Head count must be greater than 0'})

        # Validate reporting position
        reports_to = None
        if dto.reports_to_id:
            try:
                reports_to = Position.objects.active_on(today).get(pk=dto.reports_to_id)
            except Position.DoesNotExist:
                raise ValidationError({'reports_to_id': 'Reporting position not found or inactive'})

        # Validate competency requirements
        competency_requirements = []
        if dto.competency_requirements:
            from HR.person.models import Competency
            for req in dto.competency_requirements:
                try:
                    comp = Competency.objects.active().get(pk=req.competency_id)
                    prof = LookupValue.objects.get(pk=req.proficiency_level_id)
                    competency_requirements.append((comp, prof))
                except (Competency.DoesNotExist, LookupValue.DoesNotExist):
                    raise ValidationError({'competency_requirements': 'Competency or Proficiency level not found'})

        # Validate qualification requirements
        qualification_requirements = []
        if dto.qualification_requirements:
            for req in dto.qualification_requirements:
                try:
                    qual_type = LookupValue.objects.get(pk=req.qualification_type_id)
                    qual_title = LookupValue.objects.get(pk=req.qualification_title_id)
                    qualification_requirements.append((qual_type, qual_title))
                except LookupValue.DoesNotExist:
                    raise ValidationError({'qualification_requirements': 'Qualification type or title not found'})
        # Create position
        position = Position(
            code=dto.code,
            organization=organization,
            job=job,
            position_title=position_title,
            position_type=position_type,
            position_status=position_status,
            location=location,
            grade=grade,
            full_time_equivalent=fte,
            head_count=dto.head_count,
            position_sync=dto.position_sync or False,
            payroll_id=dto.payroll_id,
            salary_basis_id=dto.salary_basis_id,
            reports_to=reports_to,
            effective_start_date=dto.effective_start_date or date.today(),
            effective_end_date=dto.effective_end_date,
            created_by=user,
            updated_by=user
        )
        position.full_clean()
        position.save()

        # Create requirements
        if competency_requirements:
            from HR.person.models import PositionCompetencyRequirement
            for comp, prof_level in competency_requirements:
                PositionCompetencyRequirement.objects.create(
                    position=position,
                    competency=comp,
                    proficiency_level=prof_level,
                    created_by=user,
                    updated_by=user
                )

        # Create qualification requirements
        if qualification_requirements:
            from HR.work_structures.models import PositionQualificationRequirement
            for qual_type, qual_title in qualification_requirements:
                PositionQualificationRequirement.objects.create(
                    position=position,
                    qualification_type=qual_type,
                    qualification_title=qual_title,
                    created_by=user,
                    updated_by=user
                )

        return position

    @staticmethod
    @transaction.atomic
    def update(user, dto: PositionUpdateDTO) -> Position:
        """
        Update existing position using VersionedMixin.update_version().

        Supports both correction mode (same effective_start_date) and
        new version mode (different effective_start_date).
        """
        today = date.today()
        try:
            position = Position.objects.active_on(today).get(pk=dto.position_id)
        except Position.DoesNotExist:
            raise ValidationError(f"No active position found with ID '{dto.position_id}'")

        # Build field updates dictionary
        field_updates = {}

        # Validate and prepare FK updates
        if dto.organization_id is not None:
            try:
                organization = Organization.objects.active_on(today).get(pk=dto.organization_id)
                # Must belong to same business group
                if organization.id != position.business_group.id:
                    if not hasattr(organization, 'business_group') or organization.business_group_id != position.business_group.id:
                        raise ValidationError({
                            'organization_id': 'Organization must belong to position\'s business group'
                        })
                field_updates['organization'] = organization
            except Organization.DoesNotExist:
                raise ValidationError({'organization_id': 'Organization not found or inactive'})

        if dto.job_id is not None:
            try:
                job = Job.objects.active_on(today).get(pk=dto.job_id)
                if job.business_group_id != position.business_group.id:
                    raise ValidationError({
                        'job_id': 'Job must belong to position\'s business group'
                    })
                field_updates['job'] = job
            except Job.DoesNotExist:
                raise ValidationError({'job_id': 'Job not found or inactive'})

        if dto.grade_id is not None:
            try:
                grade = Grade.objects.active().get(pk=dto.grade_id)
                if grade.organization_id != position.business_group.id:
                    raise ValidationError({
                        'grade_id': 'Grade must belong to position\'s business group'
                    })
                field_updates['grade'] = grade
            except Grade.DoesNotExist:
                raise ValidationError({'grade_id': 'Grade not found or inactive'})

        if dto.location_id is not None:
            try:
                location = Location.objects.active().get(pk=dto.location_id)
                if location.business_group_id != position.business_group.id:
                    raise ValidationError({
                        'location_id': 'Location must belong to position\'s business group'
                    })
                field_updates['location'] = location
            except Location.DoesNotExist:
                raise ValidationError({'location_id': 'Location not found or inactive'})

        # Validate and prepare lookup updates
        if dto.position_title_id is not None:
            try:
                position_title = LookupValue.objects.get(pk=dto.position_title_id)
                if position_title.lookup_type.name != CoreLookups.POSITION_TITLE:
                    raise ValidationError({'position_title_id': 'Must be a POSITION_TITLE lookup value'})
                if not position_title.is_active:
                    raise ValidationError({'position_title_id': f'Position title "{position_title.name}" is inactive'})
                field_updates['position_title'] = position_title
            except LookupValue.DoesNotExist:
                raise ValidationError({'position_title_id': 'Position title not found'})

        if dto.position_type_id is not None:
            try:
                position_type = LookupValue.objects.get(pk=dto.position_type_id)
                if position_type.lookup_type.name != CoreLookups.POSITION_TYPE:
                    raise ValidationError({'position_type_id': 'Must be a POSITION_TYPE lookup value'})
                if not position_type.is_active:
                    raise ValidationError({'position_type_id': f'Position type "{position_type.name}" is inactive'})
                field_updates['position_type'] = position_type
            except LookupValue.DoesNotExist:
                raise ValidationError({'position_type_id': 'Position type not found'})

        if dto.position_status_id is not None:
            try:
                position_status = LookupValue.objects.get(pk=dto.position_status_id)
                if position_status.lookup_type.name != CoreLookups.POSITION_STATUS:
                    raise ValidationError({'position_status_id': 'Must be a POSITION_STATUS lookup value'})
                if not position_status.is_active:
                    raise ValidationError({'position_status_id': f'Position status "{position_status.name}" is inactive'})
                field_updates['position_status'] = position_status
            except LookupValue.DoesNotExist:
                raise ValidationError({'position_status_id': 'Position status not found'})

        # Optional fields - reports_to
        if dto.reports_to_id is not None:
            if dto.reports_to_id == -1: # -1 indicates clearing the field
                field_updates['reports_to'] = None
            else:
                try:
                    reports_to = Position.objects.active_on(today).get(pk=dto.reports_to_id)
                    field_updates['reports_to'] = reports_to
                except Position.DoesNotExist:
                    raise ValidationError({'reports_to_id': 'Reporting position not found or inactive'})

        # Simple field updates
        if dto.full_time_equivalent is not None:
            fte = Decimal(str(dto.full_time_equivalent))
            if fte < Decimal('0.1') or fte > Decimal('1.5'):
                raise ValidationError({'full_time_equivalent': 'FTE must be between 0.1 and 1.5'})
            field_updates['full_time_equivalent'] = fte

        if dto.head_count is not None:
            if dto.head_count <= 0:
                raise ValidationError({'head_count': 'Head count must be greater than 0'})
            field_updates['head_count'] = dto.head_count
 
        # Handle other optional direct fields
        if dto.position_sync is not None:
                field_updates['position_sync'] = dto.position_sync
        if dto.payroll_id is not None:
                field_updates['payroll_id'] = dto.payroll_id
        if dto.salary_basis_id is not None:
                field_updates['salary_basis_id'] = dto.salary_basis_id

        # Use VersionedMixin.update_version()
        updated = position.update_version(
            field_updates=field_updates,
            new_start_date=dto.new_start_date,
            new_end_date=dto.effective_end_date
        )
        
        # Update requirements
        if dto.competency_requirements is not None:
            updated.competency_requirements.all().delete()
            
            # Handle list of requirements
            if dto.competency_requirements:
                from HR.person.models import PositionCompetencyRequirement
                from HR.person.models import Competency
                for req in dto.competency_requirements:
                    try:
                        comp = Competency.objects.active().get(pk=req.competency_id)
                        prof = LookupValue.objects.get(pk=req.proficiency_level_id)
                        PositionCompetencyRequirement.objects.create(
                            position=updated, competency=comp, proficiency_level=prof,
                            created_by=user, updated_by=user
                        )
                    except (Competency.DoesNotExist, LookupValue.DoesNotExist):
                        raise ValidationError("Competency or Proficiency level not found")

        if dto.qualification_requirements is not None:
            updated.qualification_requirements.all().delete()
            from HR.work_structures.models import PositionQualificationRequirement
            for req in dto.qualification_requirements:
                try:
                    qual_type = LookupValue.objects.get(pk=req.qualification_type_id)
                    qual_title = LookupValue.objects.get(pk=req.qualification_title_id)
                    PositionQualificationRequirement.objects.create(
                    position=updated,
                    qualification_type=qual_type,
                    qualification_title=qual_title,
                    created_by=user,
                    updated_by=user
                )
                except LookupValue.DoesNotExist:
                    raise ValidationError("Qualification type or title not found")

        updated.updated_by = user
        updated.save(update_fields=['updated_by'])
        return updated

    @staticmethod
    @transaction.atomic
    def deactivate(user, position_id: int, effective_end_date: Optional[date] = None) -> Position:
        """
        Deactivate position by setting effective_end_date.

        Uses VersionedMixin.deactivate() method.
        """
        today = date.today()
        try:
            position = Position.objects.active_on(today).get(pk=position_id)
        except Position.DoesNotExist:
            raise ValidationError(f"No active position found with ID '{position_id}'")

        # Dependency Checks
        check_date = effective_end_date or today

        # Check for active assignments using this position
        from HR.person.models import Assignment
        assign_count = Assignment.objects.active_on(check_date).filter(
            position_id=position.id
        ).count()
        if assign_count > 0:
            raise ValidationError(
                f"Cannot deactivate Position '{position.code}' because it is used by {assign_count} active employee assignments."
            )

        position.deactivate(end_date=effective_end_date)
        position.updated_by = user
        position.save(update_fields=['updated_by'])
        return position

    @staticmethod
    def get_positions_by_organization(organization_id: int, as_of_date: Optional[date] = None) -> List[Position]:
        """
        Get all active positions in an organization as of a specific date.

        Args:
            organization_id: ID of the organization
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of Position instances
        """
        check_date = as_of_date or date.today()

        return Position.objects.active_on(check_date).filter(
            organization_id=organization_id
        ).select_related(
            'organization',
            'job',
            'location',
            'grade',
            'position_title',
            'position_type',
            'position_status'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title'
        ).order_by('code')

    @staticmethod
    def get_positions_by_job(job_id: int, as_of_date: Optional[date] = None) -> List[Position]:
        """
        Get all active positions for a specific job as of a date.

        Args:
            job_id: ID of the job
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of Position instances
        """
        check_date = as_of_date or date.today()

        return Position.objects.active_on(check_date).filter(
            job_id=job_id
        ).select_related(
            'organization',
            'job',
            'location',
            'grade',
            'position_title',
            'position_type',
            'position_status'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title'
        ).order_by('organization__organization_name', 'code')

    @staticmethod
    def get_positions_by_business_group(business_group_id: int, as_of_date: Optional[date] = None) -> List[Position]:
        """
        Get all active positions in a business group as of a date.

        Args:
            business_group_id: ID of the business group
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of Position instances
        """
        check_date = as_of_date or date.today()

        from django.db.models import Q
        return Position.objects.active_on(check_date).filter(
            Q(organization_id=business_group_id) | Q(organization__business_group_id=business_group_id)
        ).select_related(
            'organization',
            'job',
            'location',
            'grade',
            'position_title',
            'position_type',
            'position_status'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title'
        ).order_by('organization__organization_name', 'code')

    @staticmethod
    def get_position_by_code(code: str, as_of_date: Optional[date] = None) -> Optional[Position]:
        """
        Get a position by code as of a specific date.

        Args:
            code: Position code
            as_of_date: Date to check (defaults to today)

        Returns:
            Position instance or None if not found
        """
        check_date = as_of_date or date.today()

        return Position.objects.active_on(check_date).filter(code=code).select_related(
            'organization',
            'job',
            'location',
            'grade',
            'position_title',
            'position_type',
            'position_status',
            'reports_to'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title'
        ).first()

    @staticmethod
    def get_position_versions(position_id: int) -> List[Position]:
        """
        Get all versions of a position (historical and current).

        Args:
            position_id: ID of any version of the position

        Returns:
            QuerySet of all Position versions ordered by effective_start_date (newest first)
        """
        try:
            position = Position.objects.get(pk=position_id)
        except Position.DoesNotExist:
             raise ValidationError(f"No position found with ID '{position_id}'")

        return Position.objects.filter(code=position.code).select_related(
            'organization',
            'job',
            'location',
            'grade',
            'position_title',
            'position_type',
            'position_status'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title'
        ).order_by('-effective_start_date')

