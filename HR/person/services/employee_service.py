"""
Employee Service - Business Logic Layer

Handles all employee lifecycle workflows:
- Hiring (from applicant or direct)
- Termination
- Rehiring
- Type conversions (temp → permanent)
- Status updates

All employee state transitions MUST go through this service.
"""

from django.db import transaction, models
from django.db.models import Q, Prefetch
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from HR.person.models import Employee, Applicant, Person, PersonType, Assignment
from HR.work_structures.models import Organization, Position
from core.lookups.models import LookupValue
from HR.person.dtos import EmployeeUpdateDTO


class EmployeeService:
    """Service layer for employee lifecycle management"""

    @staticmethod
    @transaction.atomic
    def update(user, dto: EmployeeUpdateDTO) -> Employee:
        """
        Comprehensive update for employee and personal details.
        
        Args:
            user: User performing update
            dto: EmployeeUpdateDTO
        
        Returns:
            Employee: Updated employee instance
        """
        employee = Employee.objects.get(pk=dto.employee_id)
        person = employee.person

        # 1. Update Person fields
        person_fields = [
            'first_name', 'middle_name', 'last_name', 'first_name_arabic',
            'middle_name_arabic', 'last_name_arabic', 'title', 'date_of_birth',
            'gender', 'marital_status', 'nationality', 'national_id',
            'religion', 'blood_type', 'email_address'
        ]
        
        person_updated = False
        for field in person_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(person, field, value)
                person_updated = True
        
        if person_updated:
            person._allow_direct_save = True
            person.save()

        # 2. Update Employee fields
        if dto.employee_type_id:
            employee.employee_type_id = dto.employee_type_id
        
        if dto.hire_date:
            employee.hire_date = dto.hire_date
            
        if dto.effective_end_date is not None:
            employee.effective_end_date = dto.effective_end_date

        if dto.effective_start_date:
            employee.effective_start_date = dto.effective_start_date

        employee.updated_by = user
        employee.save()
        
        return employee

    @staticmethod
    @transaction.atomic
    def hire_from_applicant(applicant_id, employee_data, effective_start_date, hire_date=None):
        """
        Transition: Applicant → Employee
        
        Steps:
        1. End-date applicant period
        2. Create employee period
        3. Person type now inferred as EMP
        
        Args:
            applicant_id: Applicant record ID
            effective_start_date: Effective start date of employment record
            employee_data: Dict with employee_type, employee_number, etc.
            hire_date: Actual hire date (if different from effective start)
        
        Returns:
            Employee: Newly created employee record
        
        Raises:
            ValidationError: If applicant already hired or invalid data
        """
        if hire_date is None:
            hire_date = effective_start_date

        applicant = Applicant.objects.get(pk=applicant_id)
        person = applicant.person

        # Validate
        if applicant.application_status == 'hired':
            raise ValidationError("Applicant already hired")

        # End-date applicant period  
        # Set manually to avoid deactivate() adjusting dates
        if effective_start_date > applicant.effective_start_date:
            applicant.effective_end_date = effective_start_date - timedelta(days=1)
        else:
            # If hire date is same as or before app start, just end it at start date
            applicant.effective_end_date = applicant.effective_start_date
            
        applicant.application_status = 'hired'
        applicant.save()

        # Create employee period
        employee = Employee(
            person=person,
            employee_type=employee_data['employee_type'],
            effective_start_date=effective_start_date,
            effective_end_date=None,
            employee_number=employee_data['employee_number'],
            hire_date=hire_date
        )
        employee.full_clean()
        employee.save()

        return employee

    @staticmethod
    @transaction.atomic
    def hire_direct(person_data, employee_data, effective_start_date=None, hire_date=None, person=None):
        """
        Hire someone directly (not from applicant pool).
        
        Creates both Person and Employee records, or uses existing Person.
        
        Args:
            person_data: Dict with person fields (first_name, email_address, etc.)
            employee_data: Dict with employee_type, employee_number, etc.
            effective_start_date: Effective start date (default: today)
            hire_date: Actual hire date (default: effective_start_date)
            person: Optional existing Person instance. If provided, person_data is ignored for Person creation.
        
        Returns:
            Employee: Newly created employee record
        """
        if effective_start_date is None:
            effective_start_date = date.today()
            
        if hire_date is None:
            hire_date = effective_start_date

        if person:
            # Use existing person
            employee = Employee(
                person=person,
                employee_type=employee_data['employee_type'],
                employee_number=employee_data['employee_number'],
                hire_date=hire_date,
                effective_start_date=hire_date,
                effective_end_date=None
            )
            employee.full_clean()
            employee.save()
            
            return employee

        # Merge data for ChildModelMixin
        combined_data = {
            **person_data,
            'employee_type': employee_data['employee_type'],
            'employee_number': employee_data['employee_number'],
            'hire_date': hire_date,
            'effective_start_date': hire_date
        }

        employee = Employee.objects.create(**combined_data)
        
        return employee

    @staticmethod
    @transaction.atomic
    def terminate(employee_id, termination_date=None, reason=''):
        """
        Terminate employment period.
        
        After termination, person.current_type returns None
        (unless they have other active roles).
        
        Args:
            employee_id: Employee record ID
            termination_date: Last day of employment (default: today)
            reason: Termination reason (for audit/reporting)
        
        Returns:
            Employee: Updated employee record
        """
        employee = Employee.objects.get(pk=employee_id)

        if termination_date is None:
            termination_date = date.today()

        # Use VersionedMixin's deactivate method
        employee.deactivate(end_date=termination_date)

        return employee

    @staticmethod
    @transaction.atomic
    def rehire(person_id, effective_start_date, employee_data, hire_date=None):
        """
        Re-hire a previously terminated employee.
        Creates NEW employee period with NEW employee number.
        
        Args:
            person_id: Person ID
            effective_start_date: New hire date
            employee_data: Dict with employee_type, employee_number (NEW number), etc.
            hire_date: Actual hire date (if different from effective start)
        
        Returns:
            Employee: Newly created employee record
        
        Raises:
            ValidationError: If person already has active employment on effective_start_date
        """
        if hire_date is None:
            hire_date = effective_start_date

        person = Person.objects.get(pk=person_id)

        # Check for existing active employment on the effective_start_date
        existing = Employee.objects.active_on(effective_start_date).filter(person=person).first()

        if existing:
            raise ValidationError(
                f"Person already has active employment (employee_number={existing.employee_number}) "
                f"on {effective_start_date}. Terminate existing employment before rehiring."
            )

        # Create new employment period with NEW employee number
        employee = Employee(
            person=person,
            employee_type=employee_data['employee_type'],
            effective_start_date=effective_start_date,
            effective_end_date=None,
            employee_number=employee_data['employee_number'],  # Must be NEW number
            hire_date=hire_date
        )
        employee.full_clean()
        employee.save()

        return employee

    @staticmethod
    @transaction.atomic
    def convert_employee_type(employee_id, new_type, effective_date=None):
        """
        Convert employee subtype (e.g., Temp → Permanent).
        
        Updates the employee record IN-PLACE.
        - Same employee_number (E001 stays E001)
        - Same hire_date  
        - Same employment period
        - Only employee_type changes
        
        Args:
            employee_id: Current employee record
            new_type: New PersonType (must be base_type='EMP')
            effective_date: When conversion takes effect (for audit trail, optional)
        
        Returns:
            Employee: Updated employee record (same instance)
        
        Raises:
            ValidationError: If new_type is not base_type='EMP'
        """
        employee = Employee.objects.get(pk=employee_id)

        if new_type.base_type != 'EMP':
            raise ValidationError("New type must be base_type='EMP'")

        # Update type in-place (keeps everything else the same)
        employee.employee_type = new_type
        employee.save()

        # Note: effective_date could be stored in a separate EmployeeTypeHistory table
        # to track when the conversion happened, but that's optional

        return employee

    @staticmethod
    def list_employees(filters: dict = None) -> models.QuerySet:
        """
        List employees with flexible filtering.

        Args:
            filters: Dictionary of filters
                - as_of_date: Date (default 'ALL')
                - status: 'ALL' (default), 'ACTIVE', or 'INACTIVE'
                - search: Search query (name, number)
                - organization_id: Filter by organization
                - position_id: Filter by position
                - employee_type_id: Filter by employee type
                - person_id: Filter by person

        Returns:
            QuerySet of Employee objects
        """
        filters = filters or {}
        
        # Base queryset - optimization
        # Use Prefetch for primary assignment to avoid N+1 and allow access in serializers
        # We need to filter the prefetched assignments based on as_of_date if possible
        # But Prefetch filtering is for "what gets loaded into cache", not "what gets filtered from main queryset"
        
        as_of_date = filters.get('as_of_date')
        
        # Prepare assignment queryset for prefetch
        assignment_qs = Assignment.objects.filter(primary_assignment=True)
        if as_of_date and as_of_date != 'ALL':
             assignment_qs = assignment_qs.active_on(as_of_date)
        
        queryset = Employee.objects.all().select_related(
            'person', 
            'employee_type'
        ).prefetch_related(
            Prefetch('person__assignments', queryset=assignment_qs, to_attr='primary_assignments_cache')
        ).order_by('person__last_name', 'person__first_name')

        # Date filter (default to ALL if not specified or 'ALL')
        if as_of_date and as_of_date != 'ALL':
             queryset = queryset.active_on(as_of_date)

        # Other filters
        org_id = filters.get('organization_id')
        if org_id:
            # Filter by assignments in that department
            assign_filter = Q(person__assignments__department_id=org_id)
            if as_of_date and as_of_date != 'ALL':
                assign_filter &= Q(person__assignments__effective_start_date__lte=as_of_date)
                assign_filter &= (Q(person__assignments__effective_end_date__gte=as_of_date) | Q(person__assignments__effective_end_date__isnull=True))
            
            queryset = queryset.filter(assign_filter).distinct()

        pos_id = filters.get('position_id')
        if pos_id:
            assign_filter = Q(person__assignments__position_id=pos_id)
            if as_of_date and as_of_date != 'ALL':
                assign_filter &= Q(person__assignments__effective_start_date__lte=as_of_date)
                assign_filter &= (Q(person__assignments__effective_end_date__gte=as_of_date) | Q(person__assignments__effective_end_date__isnull=True))
            
            queryset = queryset.filter(assign_filter).distinct()

        type_id = filters.get('employee_type_id')
        if type_id:
            queryset = queryset.filter(employee_type_id=type_id)
            
        person_id = filters.get('person_id')
        if person_id:
            queryset = queryset.filter(person_id=person_id)

        search = filters.get('search')
        if search:
            queryset = queryset.filter(
                Q(person__first_name__icontains=search) |
                Q(person__last_name__icontains=search) |
                Q(person__middle_name__icontains=search) |
                Q(employee_number__icontains=search)
            )

        return queryset

    @staticmethod
    def get_active_employees(as_of_date=None):
        """
        Get all active employees on a specific date.
        
        Args:
            as_of_date: Reference date (default: today)
        
        Returns:
            QuerySet of Employee objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        return Employee.objects.active_on(as_of_date)

    @staticmethod
    def get_employment_history(person_id):
        """
        Get complete employment history for a person.
        
        Args:
            person_id: Person ID
        
        Returns:
            QuerySet of Employee objects ordered by effective_start_date
        """
        return Employee.objects.filter(
            person_id=person_id
        ).order_by('effective_start_date')
