from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date, datetime, timedelta
from typing import List, Optional
from HR.person.dtos import AssignmentCreateDTO, AssignmentUpdateDTO
from HR.person.models import Assignment, Person, Contract
from HR.work_structures.models import Organization, Job, Position, Grade
from core.lookups.models import LookupValue
from dateutil.relativedelta import relativedelta
from HR.lookup_config import CoreLookups

class AssignmentService:
    """Service layer for Assignment business logic"""

    @staticmethod
    def calculate_probation_end(start_date: date, period_lookup: LookupValue) -> Optional[date]:
        """
        Calculate probation end date based on start date and period lookup record.
        Expected names: '2 Weeks', '1 Month', '2 Months', '3 Months', '6 Months'
        """
        if not start_date or not period_lookup:
            return None
        
        name = period_lookup.name.lower()
        
        if 'week' in name:
            try:
                # Extract number from string like "2 Weeks"
                weeks = int(name.split()[0])
                return start_date + timedelta(weeks=weeks)
            except (ValueError, IndexError):
                pass
        elif 'month' in name:
            try:
                # Extract number from string like "3 Months"
                months = int(name.split()[0])
                return start_date + relativedelta(months=months)
            except (ValueError, IndexError):
                pass
                
        return None

    @staticmethod
    @transaction.atomic
    def create(user, dto: AssignmentCreateDTO) -> Assignment:
        """Create a new assignment record"""
        # Validate Person
        try:
            person = Person.objects.get(pk=dto.person_id)
        except Person.DoesNotExist:
            raise ValidationError({'person_id': 'Person not found'})

        # Validate Business Group
        try:
            bg = Organization.objects.get(pk=dto.business_group_id)
            if not bg.is_business_group:
                raise ValidationError({'business_group_id': 'Selected organization is not a root Business Group'})
        except Organization.DoesNotExist:
            raise ValidationError({'business_group_id': 'Business Group not found'})

        # Validate Department
        try:
            dept = Organization.objects.get(pk=dto.department_id)
        except Organization.DoesNotExist:
            raise ValidationError({'department_id': 'Department not found'})

        # Validate Job
        try:
            job = Job.objects.get(pk=dto.job_id)
        except Job.DoesNotExist:
            raise ValidationError({'job_id': 'Job not found'})

        # Validate Position
        try:
            pos = Position.objects.get(pk=dto.position_id)
        except Position.DoesNotExist:
            raise ValidationError({'position_id': 'Position not found'})

        # Validate Grade
        try:
            grade = Grade.objects.get(pk=dto.grade_id)
        except Grade.DoesNotExist:
            raise ValidationError({'grade_id': 'Grade not found'})

        # Validate Lookups
        lookups = {
            'assignment_action_reason': (dto.assignment_action_reason_id, CoreLookups.ASSIGNMENT_ACTION_REASON),
            'assignment_status': (dto.assignment_status_id, CoreLookups.ASSIGNMENT_STATUS),
            'payroll': (dto.payroll_id, CoreLookups.PAYROLL),
            'salary_basis': (dto.salary_basis_id, CoreLookups.SALARY_BASIS),
            'probation_period': (dto.probation_period_id, CoreLookups.PROBATION_PERIOD),
            'termination_notice_period': (dto.termination_notice_period_id, CoreLookups.TERMINATION_NOTICE_PERIOD),
        }

        lookup_objs = {}

        for key, (lookup_id, expected_type) in lookups.items():
            if lookup_id:
                try:
                    lookup = LookupValue.objects.get(pk=lookup_id)
                    if lookup.lookup_type.name != expected_type:
                        # expected_type is a SimpleLazyObject, so we can access .name if needed for error msg, 
                        # but direct comparison works. For error msg, we might want the string name.
                        # Since expected_type is the object, we can get its name.
                        # Or we can just use a generic message.
                        raise ValidationError({f'{key}_id': f'Invalid lookup type for {key}'})
                    
                    if not lookup.is_active:
                        raise ValidationError({f'{key}_id': f'Selected {key} is inactive'})
                        
                    lookup_objs[key] = lookup
                except LookupValue.DoesNotExist:
                    raise ValidationError({f'{key}_id': f'{key} lookup not found'})
            else:
                lookup_objs[key] = None

        # Handle Primary Assignment Logic
        if dto.primary_assignment:
            Assignment.objects.filter(person=person, primary_assignment=True).update(primary_assignment=False)

        # Calculate Probation End Date
        probation_end = None
        if dto.probation_period_start and 'probation_period' in lookup_objs:
            probation_end = AssignmentService.calculate_probation_end(
                dto.probation_period_start, 
                lookup_objs['probation_period']
            )

        assignment = Assignment(
            person=person,
            business_group=bg,
            assignment_no=dto.assignment_no,
            department=dept,
            job=job,
            position=pos,
            grade=grade,
            payroll=lookup_objs.get('payroll'),
            salary_basis=lookup_objs.get('salary_basis'),
            line_manager_id=dto.line_manager_id,
            assignment_action_reason=lookup_objs.get('assignment_action_reason'),
            primary_assignment=dto.primary_assignment,
            contract_id=dto.contract_id,
            assignment_status=lookup_objs.get('assignment_status'),
            project_manager_id=dto.project_manager_id,
            probation_period_start=dto.probation_period_start,
            probation_period=lookup_objs.get('probation_period'),
            probation_period_end=probation_end,
            termination_notice_period=lookup_objs.get('termination_notice_period'),
            hourly_salaried=dto.hourly_salaried,
            working_frequency=dto.working_frequency,
            work_start_time=dto.work_start_time,
            work_end_time=dto.work_end_time,
            work_from_home=dto.work_from_home,
            is_manager=dto.is_manager,
            title=dto.title,
            employment_confirmation_date=dto.employment_confirmation_date,
            effective_start_date=dto.effective_start_date or date.today(),
            effective_end_date=dto.effective_end_date,
            created_by=user,
            updated_by=user
        )
        assignment.full_clean()
        assignment.save()
        return assignment

    @staticmethod
    @transaction.atomic
    def update(user, dto: AssignmentUpdateDTO) -> Assignment:
        """Update an assignment record (correction or new version)"""
        assignment = Assignment.objects.latest_version('assignment_no', dto.assignment_no)
        
        if not assignment:
             raise ValidationError(f"Assignment with no {dto.assignment_no} not found")

        field_updates = {}
        # ... map DTO fields to field_updates ...
        # (similar to contract_service but more fields)
        
        dto_fields = [
            'department_id', 'job_id', 'position_id', 'grade_id', 
            'assignment_action_reason_id', 'assignment_status_id', 
            'payroll_id', 'salary_basis_id', 'line_manager_id', 
            'primary_assignment', 'contract_id', 'project_manager_id', 
            'probation_period_start', 'probation_period_id', 
            'termination_notice_period_id', 'hourly_salaried', 
            'working_frequency', 'work_start_time', 'work_end_time', 
            'work_from_home', 'is_manager', 'title', 
            'employment_confirmation_date'
        ]
        
        for field in dto_fields:
            val = getattr(dto, field, None)
            if val is not None:
                field_updates[field] = val

        # Special handling for primary_assignment in update
        if dto.primary_assignment is True:
            Assignment.objects.filter(person=assignment.person, primary_assignment=True).exclude(pk=assignment.pk).update(primary_assignment=False)

        # Re-calculate probation end if either start or period changed
        prob_start = field_updates.get('probation_period_start', assignment.probation_period_start)
        prob_period_id = field_updates.get('probation_period', assignment.probation_period_id)
        
        if prob_start and prob_period_id:
            prob_period_lv = LookupValue.objects.get(pk=prob_period_id)
            field_updates['probation_period_end'] = AssignmentService.calculate_probation_end(prob_start, prob_period_lv)

        updated_assignment = assignment.update_version(
            field_updates=field_updates,
            new_start_date=dto.effective_start_date,
            new_end_date=dto.effective_end_date
        )
        updated_assignment.updated_by = user
        updated_assignment.save(update_fields=['updated_by'])
        return updated_assignment

    @staticmethod
    @transaction.atomic
    def deactivate(user, assignment_no: str, end_date: Optional[date] = None) -> Assignment:
        """Deactivate an assignment by end-dating it"""
        assignment = Assignment.objects.latest_version('assignment_no', assignment_no)
        if not assignment:
            raise ValidationError(f"Assignment with no {assignment_no} not found")
        
        assignment.deactivate(end_date=end_date)
        assignment.updated_by = user
        assignment.save(update_fields=['updated_by'])
        return assignment

    @staticmethod
    def get_assignments_by_person(person_id: int) -> List[Assignment]:
        """Get all assignments for a person"""
        return Assignment.objects.filter(person_id=person_id).order_by('-effective_start_date')

    @staticmethod
    def get_primary_assignment(person_id: int, reference_date: Optional[date] = None) -> Optional[Assignment]:
        """Get the primary assignment for a person on a specific date"""
        if reference_date is None:
            reference_date = date.today()
        return Assignment.objects.active_on(reference_date).filter(person_id=person_id, primary_assignment=True).first()

    @staticmethod
    def get_active_assignment(person_id: int, reference_date: Optional[date] = None) -> Optional[Assignment]:
        """Get the active assignment for a person on a specific date (any assignment)"""
        if reference_date is None:
            reference_date = date.today()
        return Assignment.objects.active_on(reference_date).filter(person_id=person_id).first()

    @staticmethod
    def get_assignments_by_department(department_id: int) -> List[Assignment]:
        """Get all active assignments in a department"""
        return Assignment.objects.active_on(date.today()).filter(department_id=department_id)

    @staticmethod
    def get_assignments_by_job(job_id: int) -> List[Assignment]:
        """Get all active assignments for a job"""
        return Assignment.objects.active_on(date.today()).filter(job_id=job_id)
