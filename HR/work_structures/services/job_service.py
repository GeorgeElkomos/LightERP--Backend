from django.db import transaction, models
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import date
from typing import List, Optional
from HR.work_structures.dtos import JobCreateDTO, JobUpdateDTO
from HR.work_structures.models import Job, Organization, Grade
from HR.person.models import Competency
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups


class JobService:
    """Service for Job business logic"""

    @staticmethod
    def list_jobs(filters: dict = None) -> models.QuerySet:
        """List jobs with flexible filtering."""
        filters = filters or {}
        queryset = Job.objects.all()
        
        # Date filter (default to ALL if not specified or 'ALL')
        as_of_date = filters.get('as_of_date')
        if as_of_date and as_of_date != 'ALL':
             queryset = queryset.active_on(as_of_date)
        
        # Basic filters
        bg_id = filters.get('business_group_id')
        if bg_id:
            queryset = queryset.filter(business_group_id=bg_id)
            
        bg_code = filters.get('business_group_code')
        if bg_code:
            queryset = queryset.filter(business_group__organization_name=bg_code)
            
        if filters.get('job_category_id'):
            queryset = queryset.filter(job_category_id=filters.get('job_category_id'))
            
        # Search filter
        search_query = filters.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(code__icontains=search_query) |
                Q(job_title__name__icontains=search_query)
            )
            
        return queryset.select_related(
            'business_group',
            'job_category',
            'job_title'
        ).order_by('business_group__organization_name', 'code')

    @staticmethod
    @transaction.atomic
    def create(user, dto: JobCreateDTO) -> Job:
        """
        Create new job with validation.

        Validates:
        - Business group exists and is root
        - All lookup values are valid and active
        - Grades belong to same business group
        - Competencies are active
        - Responsibilities is list of strings

        Note: Code uniqueness is enforced per version (code + business_group + effective_start_date)
        """
        # Validate business group exists and is root
        today = date.today()
        try:
            business_group = Organization.objects.active_on(today).get(pk=dto.business_group_id)
            if not business_group.is_business_group:
                raise ValidationError({
                    'business_group_id': 'Job must belong to a root organization (Business Group)'
                })
        except Organization.DoesNotExist:
            raise ValidationError({'business_group_id': 'Business group not found or inactive'})

        # Validate job category
        try:
            job_category = LookupValue.objects.get(pk=dto.job_category_id)
            if job_category.lookup_type.name != CoreLookups.JOB_CATEGORY:
                raise ValidationError({'job_category_id': 'Must be a JOB_CATEGORY lookup value'})
            if not job_category.is_active:
                raise ValidationError({'job_category_id': f'Job category "{job_category.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'job_category_id': 'Job category not found'})

        # Validate job title
        try:
            job_title = LookupValue.objects.get(pk=dto.job_title_id)
            if job_title.lookup_type.name != CoreLookups.JOB_TITLE:
                raise ValidationError({'job_title_id': 'Must be a JOB_TITLE lookup value'})
            if not job_title.is_active:
                raise ValidationError({'job_title_id': f'Job title "{job_title.name}" is inactive'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'job_title_id': 'Job title not found'})


        # Validate competency requirements
        competency_requirements = []
        if dto.competency_requirements:
            for req in dto.competency_requirements:
                try:
                    comp = Competency.objects.active().get(pk=req.competency_id)
                except Competency.DoesNotExist:
                    raise ValidationError({
                        'competency_requirements': f'Competency with ID {req.competency_id} not found or inactive'
                    })
                
                # Validate proficiency level
                try:
                    prof_level = LookupValue.objects.get(pk=req.proficiency_level_id)
                    if prof_level.lookup_type.name != CoreLookups.PROFICIENCY_LEVEL:
                        raise ValidationError({
                            'competency_requirements': 'Proficiency level must be a PROFICIENCY_LEVEL lookup value'
                        })
                    if not prof_level.is_active:
                        raise ValidationError({
                            'competency_requirements': f'Proficiency level "{prof_level.name}" is inactive'
                        })
                except LookupValue.DoesNotExist:
                    raise ValidationError({
                        'competency_requirements': f'Proficiency level with ID {req.proficiency_level_id} not found'
                    })
                
                competency_requirements.append((comp, prof_level))

        # Validate qualification requirements
        qualification_requirements = []
        if dto.qualification_requirements:
            from HR.work_structures.models import JobQualificationRequirement
            for req in dto.qualification_requirements:
                # Validate qualification type
                try:
                    qual_type = LookupValue.objects.get(pk=req.qualification_type_id)
                    if qual_type.lookup_type.name != CoreLookups.QUALIFICATION_TYPE:
                        raise ValidationError({
                            'qualification_requirements': 'Must be a QUALIFICATION_TYPE lookup value'
                        })
                    if not qual_type.is_active:
                        raise ValidationError({
                            'qualification_requirements': f'Qualification type "{qual_type.name}" is inactive'
                        })
                except LookupValue.DoesNotExist:
                    raise ValidationError({
                        'qualification_requirements': f'Qualification type with ID {req.qualification_type_id} not found'
                    })
                
                # Validate qualification title
                try:
                    qual_title = LookupValue.objects.get(pk=req.qualification_title_id)
                    if qual_title.lookup_type.name != CoreLookups.QUALIFICATION_TITLE:
                        raise ValidationError({
                            'qualification_requirements': 'Must be a QUALIFICATION_TITLE lookup value'
                        })
                    if not qual_title.is_active:
                        raise ValidationError({
                            'qualification_requirements': f'Qualification title "{qual_title.name}" is inactive'
                        })
                except LookupValue.DoesNotExist:
                    raise ValidationError({
                        'qualification_requirements': f'Qualification title with ID {req.qualification_title_id} not found'
                    })
                
                qualification_requirements.append((qual_type, qual_title))

        # Validate grades belong to same business group
        valid_grades = []
        grade_ids_to_check = dto.grade_ids or []
        if grade_ids_to_check:
            for grade_id in grade_ids_to_check:
                try:
                    grade = Grade.objects.active().get(pk=grade_id)
                    if grade.organization_id != dto.business_group_id:
                        raise ValidationError({
                            'grade_ids': f'Grade "{str(grade)}" does not belong to business group "{business_group.organization_name}"'
                        })
                    valid_grades.append(grade)
                except Grade.DoesNotExist:
                    raise ValidationError({'grade_ids': f'Grade with ID {grade_id} not found or inactive'})

        # Validate responsibilities is list of strings
        if dto.responsibilities:
            if not isinstance(dto.responsibilities, list):
                raise ValidationError({'responsibilities': 'Responsibilities must be a list'})
            for idx, item in enumerate(dto.responsibilities):
                if not isinstance(item, str):
                    raise ValidationError({
                        'responsibilities': f'Responsibility at index {idx} must be a string'
                    })

        # Create job
        job = Job(
            code=dto.code,
            business_group=business_group,
            job_category=job_category,
            job_title=job_title,
            job_description=dto.job_description,
            responsibilities=dto.responsibilities or [],
            effective_start_date=dto.effective_start_date or date.today(),
            effective_end_date=dto.effective_end_date,
            created_by=user,
            updated_by=user
        )
        job.full_clean()
        job.save()

        # Create competency requirements (through model)
        if competency_requirements:
            from HR.person.models import JobCompetencyRequirement
            for comp, prof_level in competency_requirements:
                JobCompetencyRequirement.objects.create(
                    job=job,
                    competency=comp,
                    proficiency_level=prof_level,
                    created_by=user,
                    updated_by=user
                )
        
        # Create qualification requirements (through model)
        if qualification_requirements:
            from HR.work_structures.models import JobQualificationRequirement
            for qual_type, qual_title in qualification_requirements:
                JobQualificationRequirement.objects.create(
                    job=job,
                    qualification_type=qual_type,
                    qualification_title=qual_title,
                    created_by=user,
                    updated_by=user
                )
        
        # Set grades (simple M2M)
        if valid_grades:
            job.grades.set(valid_grades)

        return job

    @staticmethod
    @transaction.atomic
    def update(user, dto: JobUpdateDTO) -> Job:
        """
        Update existing job using VersionedMixin.update_version().

        Supports both correction mode (same effective_start_date) and
        new version mode (different effective_start_date).
        """
        today = date.today()
        try:
            # Get current active version
            job = Job.objects.active_on(today).get(pk=dto.job_id)
        except Job.DoesNotExist:
            raise ValidationError(f"No active job found with ID '{dto.job_id}'")

        # Build field updates dictionary
        field_updates = {}

        # Validate and prepare job category update
        if dto.job_category_id is not None:
            try:
                job_category = LookupValue.objects.get(pk=dto.job_category_id)
                if job_category.lookup_type.name != CoreLookups.JOB_CATEGORY:
                    raise ValidationError({'job_category_id': 'Must be a JOB_CATEGORY lookup value'})
                if not job_category.is_active:
                    raise ValidationError({'job_category_id': f'Job category "{job_category.name}" is inactive'})
                field_updates['job_category'] = job_category
            except LookupValue.DoesNotExist:
                raise ValidationError({'job_category_id': 'Job category not found'})

        # Validate and prepare job title update
        if dto.job_title_id is not None:
            try:
                job_title = LookupValue.objects.get(pk=dto.job_title_id)
                if job_title.lookup_type.name != CoreLookups.JOB_TITLE:
                    raise ValidationError({'job_title_id': 'Must be a JOB_TITLE lookup value'})
                if not job_title.is_active:
                    raise ValidationError({'job_title_id': f'Job title "{job_title.name}" is inactive'})
                field_updates['job_title'] = job_title
            except LookupValue.DoesNotExist:
                raise ValidationError({'job_title_id': 'Job title not found'})


        # Simple field updates
        if dto.job_description is not None:
            field_updates['job_description'] = dto.job_description
        if dto.responsibilities is not None:
            # Validate responsibilities is list of strings
            if not isinstance(dto.responsibilities, list):
                raise ValidationError({'responsibilities': 'Responsibilities must be a list'})
            for idx, item in enumerate(dto.responsibilities):
                if not isinstance(item, str):
                    raise ValidationError({
                        'responsibilities': f'Responsibility at index {idx} must be a string'
                    })
            field_updates['responsibilities'] = dto.responsibilities

        # Use VersionedMixin.update_version()
        # If new_start_date provided, creates new version; otherwise correction mode
        updated = job.update_version(
            field_updates=field_updates,
            new_start_date=dto.new_start_date,
            new_end_date=dto.effective_end_date
        )

        # Handle requirements separately (after update_version)
        # Requirements use through models, so we need to clear and recreate
        
        # Update competency requirements
        if dto.competency_requirements is not None:
            from HR.person.models import JobCompetencyRequirement
            # Clear existing requirements
            updated.competency_requirements.all().delete()
            # Create new requirements
            for req in dto.competency_requirements:
                try:
                    comp = Competency.objects.active().get(pk=req.competency_id)
                except Competency.DoesNotExist:
                    raise ValidationError({
                        'competency_requirements': f'Competency with ID {req.competency_id} not found or inactive'
                    })
                
                # Validate proficiency level
                try:
                    prof_level = LookupValue.objects.get(pk=req.proficiency_level_id)
                    if prof_level.lookup_type.name != CoreLookups.PROFICIENCY_LEVEL:
                        raise ValidationError({
                            'competency_requirements': 'Proficiency level must be a PROFICIENCY_LEVEL lookup value'
                        })
                    if not prof_level.is_active:
                        raise ValidationError({
                            'competency_requirements': f'Proficiency level "{prof_level.name}" is inactive'
                        })
                except LookupValue.DoesNotExist:
                    raise ValidationError({
                        'competency_requirements': f'Proficiency level with ID {req.proficiency_level_id} not found'
                    })
                
                JobCompetencyRequirement.objects.create(
                    job=updated,
                    competency=comp,
                    proficiency_level=prof_level,
                    created_by=user,
                    updated_by=user
                )

        # Update qualification requirements
        if dto.qualification_requirements is not None:
            from HR.work_structures.models import JobQualificationRequirement
            # Clear existing requirements
            updated.qualification_requirements.all().delete()
            # Create new requirements
            for req in dto.qualification_requirements:
                # Validate qualification type
                try:
                    qual_type = LookupValue.objects.get(pk=req.qualification_type_id)
                    if qual_type.lookup_type.name != CoreLookups.QUALIFICATION_TYPE:
                        raise ValidationError({
                            'qualification_requirements': 'Must be a QUALIFICATION_TYPE lookup value'
                        })
                    if not qual_type.is_active:
                        raise ValidationError({
                            'qualification_requirements': f'Qualification type "{qual_type.name}" is inactive'
                        })
                except LookupValue.DoesNotExist:
                    raise ValidationError({
                        'qualification_requirements': f'Qualification type with ID {req.qualification_type_id} not found'
                    })
                
                # Validate qualification title
                try:
                    qual_title = LookupValue.objects.get(pk=req.qualification_title_id)
                    if qual_title.lookup_type.name != CoreLookups.QUALIFICATION_TITLE:
                        raise ValidationError({
                            'qualification_requirements': 'Must be a QUALIFICATION_TITLE lookup value'
                        })
                    if not qual_title.is_active:
                        raise ValidationError({
                            'qualification_requirements': f'Qualification title "{qual_title.name}" is inactive'
                        })
                except LookupValue.DoesNotExist:
                    raise ValidationError({
                        'qualification_requirements': f'Qualification title with ID {req.qualification_title_id} not found'
                    })
                
                JobQualificationRequirement.objects.create(
                    job=updated,
                    qualification_type=qual_type,
                    qualification_title=qual_title,
                    created_by=user,
                    updated_by=user
                )

        # Update grades (simple M2M)
        if dto.grade_ids is not None:
            valid_grades = []
            for grade_id in dto.grade_ids:
                try:
                    grade = Grade.objects.active().get(pk=grade_id)
                    if grade.organization_id != updated.business_group_id:
                        raise ValidationError({
                            'grade_ids': f'Grade "{str(grade)}" does not belong to job\'s business group'
                        })
                    valid_grades.append(grade)
                except Grade.DoesNotExist:
                    raise ValidationError({'grade_ids': f'Grade with ID {grade_id} not found or inactive'})
            updated.grades.set(valid_grades)

        updated.updated_by = user
        updated.save(update_fields=['updated_by'])
        return updated

    @staticmethod
    @transaction.atomic
    def deactivate(user, job_id: int, effective_end_date: Optional[date] = None) -> Job:
        """
        Deactivate job by setting effective_end_date.

        Uses VersionedMixin.deactivate() method.
        """
        today = date.today()
        try:
            job = Job.objects.active_on(today).get(pk=job_id)
        except Job.DoesNotExist:
            raise ValidationError(f"No active job found with ID '{job_id}'")

        # Dependency Checks
        check_date = effective_end_date or today

        # 1. Check for active positions using this job
        from HR.work_structures.models import Position
        position_count = Position.objects.active_on(check_date).filter(
            job_id=job.id
        ).count()
        if position_count > 0:
            raise ValidationError(
                f"Cannot deactivate Job '{job.code}' because it is used by {position_count} active positions."
            )

        # 2. Check for active assignments using this job
        from HR.person.models import Assignment
        assign_count = Assignment.objects.active_on(check_date).filter(
            job_id=job.id
        ).count()
        if assign_count > 0:
            raise ValidationError(
                f"Cannot deactivate Job '{job.code}' because it is used by {assign_count} active employee assignments."
            )

        # Use VersionedMixin.deactivate() method
        job.deactivate(end_date=effective_end_date)
        job.updated_by = user
        job.save(update_fields=['updated_by'])
        return job

    @staticmethod
    def get_jobs_by_business_group(business_group_id: int, as_of_date: Optional[date] = None) -> List[Job]:
        """
        Get all active jobs for a business group as of a specific date.

        Args:
            business_group_id: ID of the root organization
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of Job instances
        """
        check_date = as_of_date or date.today()

        return Job.objects.active_on(check_date).filter(
            business_group_id=business_group_id
        ).select_related(
            'business_group',
            'job_category',
            'job_title'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title',
            'grades'
        ).order_by('code')

    @staticmethod
    def get_jobs_by_category(category_name: str, as_of_date: Optional[date] = None) -> List[Job]:
        """
        Get all active jobs in a specific category.

        Args:
            category_name: Name of the JOB_CATEGORY lookup
            as_of_date: Date to check (defaults to today)

        Returns:
            QuerySet of Job instances
        """
        check_date = as_of_date or date.today()

        return Job.objects.active_on(check_date).filter(
            job_category__name=category_name
        ).select_related(
            'business_group',
            'job_category',
            'job_title'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title',
            'grades'
        ).order_by('business_group__organization_name', 'code')

    @staticmethod
    def get_job_by_code(code: str, as_of_date: Optional[date] = None) -> Optional[Job]:
        """
        Get a job by code as of a specific date.

        Args:
            code: Job code
            as_of_date: Date to check (defaults to today)

        Returns:
            Job instance or None if not found
        """
        check_date = as_of_date or date.today()

        return Job.objects.active_on(check_date).filter(code=code).select_related(
            'business_group',
            'job_category',
            'job_title'
        ).prefetch_related(
            'competency_requirements__competency',
            'competency_requirements__proficiency_level',
            'qualification_requirements__qualification_type',
            'qualification_requirements__qualification_title',
            'grades'
        ).first()

    @staticmethod
    def get_job_versions(job_id: int) -> List[Job]:
        """
        Get all versions of a job (historical and current).

        Args:
            job_id: ID of any version of the job

        Returns:
            QuerySet of all Job versions ordered by effective_start_date (newest first)
        """
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
             raise ValidationError(f"No job found with ID '{job_id}'")

        return Job.objects.filter(code=job.code).select_related(
            'business_group',
            'job_category',
            'job_title'
        ).order_by('-effective_start_date')

