"""
Data Transfer Objects for Person Domain

DTOs for service layer operations with validation and data transfer.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import date, time
from decimal import Decimal


@dataclass
class PersonTypeCreateDTO:
    """DTO for creating a new person type"""
    code: str
    name: str
    base_type: str
    description: Optional[str] = ''
    is_active: bool = True


@dataclass
class EmployeeCreateDTO:
    """DTO for creating a new employee"""
    employee_type_id: int
    effective_start_date: date
    hire_date: date
    person_id: Optional[int] = None
    effective_end_date: Optional[date] = None
    employee_number: Optional[str] = None

    # Person fields (for new person creation)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email_address: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    marital_status: Optional[str] = None
    middle_name: Optional[str] = None
    national_id: Optional[str] = None
    title: Optional[str] = None
    
    # Additional Person fields
    first_name_arabic: Optional[str] = None
    middle_name_arabic: Optional[str] = None
    last_name_arabic: Optional[str] = None
    religion: Optional[str] = None
    blood_type: Optional[str] = None


@dataclass
class EmployeeUpdateDTO:
    """DTO for updating an existing employee"""
    employee_id: int
    employee_type_id: Optional[int] = None
    organization_id: Optional[int] = None
    position_id: Optional[int] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None
    hire_date: Optional[date] = None
    
    # Person fields
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    first_name_arabic: Optional[str] = None
    middle_name_arabic: Optional[str] = None
    last_name_arabic: Optional[str] = None
    title: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    nationality: Optional[str] = None
    national_id: Optional[str] = None
    religion: Optional[str] = None
    blood_type: Optional[str] = None
    email_address: Optional[str] = None


@dataclass
class ApplicantCreateDTO:
    """DTO for creating a new applicant"""
    person_id: int
    business_group_id: int
    effective_start_date: date
    vacancy_id: Optional[int] = None
    application_status_id: Optional[int] = None
    disqualification_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class ApplicantUpdateDTO:
    """DTO for updating an existing applicant"""
    applicant_id: int
    application_status_id: Optional[int] = None
    vacancy_id: Optional[int] = None
    disqualification_date: Optional[date] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class ContingentWorkerCreateDTO:
    """DTO for creating a new contingent worker"""
    person_id: int
    business_group_id: int
    placement_date: date
    effective_start_date: date
    agency_id: Optional[int] = None
    effective_end_date: Optional[date] = None


@dataclass
class ContingentWorkerUpdateDTO:
    """DTO for updating an existing contingent worker"""
    worker_id: int
    agency_id: Optional[int] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None
    placement_date: Optional[date] = None


@dataclass
class ContactCreateDTO:
    """DTO for creating a new contact"""
    person_id: int
    contact_type_id: int
    contact_person_id: int
    relationship_id: int
    effective_start_date: date
    is_emergency_contact: bool = False
    priority: Optional[int] = None
    effective_end_date: Optional[date] = None


@dataclass
class ContactUpdateDTO:
    """DTO for updating an existing contact"""
    contact_id: int
    contact_type_id: Optional[int] = None
    organization_name: Optional[str] = None
    job_title: Optional[str] = None
    relationship_to_company: Optional[str] = None
    preferred_contact_method: Optional[str] = None
    emergency_relationship: Optional[str] = None
    is_primary_contact: Optional[bool] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class AddressCreateDTO:
    """DTO for creating a new address"""
    person_id: int
    address_type_id: int
    country_id: int
    city_id: int
    street: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    building_number: Optional[str] = None
    apartment_number: Optional[str] = None
    is_primary: bool = False


@dataclass
class AddressUpdateDTO:
    """DTO for updating an existing address"""
    address_id: int
    address_type_id: Optional[int] = None
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    street: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    building_number: Optional[str] = None
    apartment_number: Optional[str] = None
    is_primary: Optional[bool] = None


@dataclass
class CompetencyCreateDTO:
    """DTO for creating a new competency"""
    code: str
    name: str
    competency_category_id: int  # FK to LookupValue (COMPETENCY_CATEGORY)
    description: Optional[str] = None


@dataclass
class CompetencyUpdateDTO:
    """DTO for updating an existing competency"""
    code: str  # Identifier for lookup
    name: Optional[str] = None
    competency_category_id: Optional[int] = None
    description: Optional[str] = None


@dataclass
class CompetencyProficiencyCreateDTO:
    """DTO for creating a new competency proficiency record"""
    person_id: int
    competency_id: int
    proficiency_level_id: int  # FK to LookupValue (PROFICIENCY_LEVEL)
    proficiency_source_id: int  # FK to LookupValue (PROFICIENCY_SOURCE)
    effective_start_date: date
    effective_end_date: Optional[date] = None


@dataclass
class CompetencyProficiencyUpdateDTO:
    """DTO for updating an existing competency proficiency record"""
    proficiency_id: int  # ID of the CompetencyProficiency record
    proficiency_level_id: Optional[int] = None
    proficiency_source_id: Optional[int] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class QualificationCreateDTO:
    """DTO for creating a new qualification"""
    person_id: int
    qualification_type_id: int  # FK to LookupValue (QUALIFICATION_TYPE)
    qualification_title_id: int  # FK to LookupValue (QUALIFICATION_TITLE)
    qualification_status_id: int  # FK to LookupValue (QUALIFICATION_STATUS)
    awarding_entity_id: int  # FK to LookupValue (AWARDING_ENTITY)
    title_if_others: Optional[str] = None
    grade: Optional[str] = None
    awarded_date: Optional[date] = None
    projected_completion_date: Optional[date] = None
    completed_percentage: Optional[int] = None
    study_start_date: Optional[date] = None
    study_end_date: Optional[date] = None
    competency_achieved_ids: Optional[list[int]] = None  # List of Competency IDs
    tuition_method_id: Optional[int] = None
    tuition_fees: Optional[float] = None
    tuition_fees_currency_id: Optional[int] = None
    remarks: Optional[str] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class QualificationUpdateDTO:
    """DTO for updating an existing qualification"""
    qualification_id: int  # ID of the Qualification record
    qualification_type_id: Optional[int] = None
    qualification_title_id: Optional[int] = None
    qualification_status_id: Optional[int] = None
    awarding_entity_id: Optional[int] = None
    title_if_others: Optional[str] = None
    grade: Optional[str] = None
    awarded_date: Optional[date] = None
    projected_completion_date: Optional[date] = None
    completed_percentage: Optional[int] = None
    study_start_date: Optional[date] = None
    study_end_date: Optional[date] = None
    competency_achieved_ids: Optional[list[int]] = None
    tuition_method_id: Optional[int] = None
    tuition_fees: Optional[float] = None
    tuition_fees_currency_id: Optional[int] = None
    remarks: Optional[str] = None
    effective_end_date: Optional[date] = None
    effective_start_date: Optional[date] = None


@dataclass
class ContractCreateDTO:
    """DTO for creating a new contract"""
    contract_reference: str
    person_id: int
    contract_status_id: int
    contract_duration: Decimal
    contract_period: str
    contract_start_date: date
    contract_end_date: date
    contractual_job_position: str
    basic_salary: Decimal
    effective_start_date: date
    contract_end_reason_id: Optional[int] = None
    description: Optional[str] = None
    extension_duration: Optional[Decimal] = None
    extension_period: Optional[str] = None
    extension_start_date: Optional[date] = None
    extension_end_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class ContractUpdateDTO:
    """DTO for updating an existing contract version or creating a new version"""
    contract_reference: str
    effective_start_date: date
    contract_status_id: Optional[int] = None
    contract_duration: Optional[Decimal] = None
    contract_period: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    contractual_job_position: Optional[str] = None
    basic_salary: Optional[Decimal] = None
    contract_end_reason_id: Optional[int] = None
    description: Optional[str] = None
    extension_duration: Optional[Decimal] = None
    extension_period: Optional[str] = None
    extension_start_date: Optional[date] = None
    extension_end_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class AssignmentCreateDTO:
    """DTO for creating a new assignment"""
    person_id: int
    business_group_id: int
    assignment_no: str
    department_id: int
    job_id: int
    position_id: int
    grade_id: int
    assignment_action_reason_id: int
    assignment_status_id: int
    effective_start_date: date
    payroll_id: Optional[int] = None
    salary_basis_id: Optional[int] = None
    line_manager_id: Optional[int] = None
    primary_assignment: bool = True
    contract_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    probation_period_start: Optional[date] = None
    probation_period_id: Optional[int] = None
    termination_notice_period_id: Optional[int] = None
    hourly_salaried: str = 'Salaried'
    working_frequency: str = 'Month'
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    work_from_home: bool = False
    is_manager: bool = False
    title: Optional[str] = None
    employment_confirmation_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class AssignmentUpdateDTO:
    """DTO for updating an existing assignment version or creating a new version"""
    assignment_no: str
    effective_start_date: date
    person_id: Optional[int] = None
    business_group_id: Optional[int] = None
    department_id: Optional[int] = None
    job_id: Optional[int] = None
    position_id: Optional[int] = None
    grade_id: Optional[int] = None
    assignment_action_reason_id: Optional[int] = None
    assignment_status_id: Optional[int] = None
    payroll_id: Optional[int] = None
    salary_basis_id: Optional[int] = None
    line_manager_id: Optional[int] = None
    primary_assignment: Optional[bool] = None
    contract_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    probation_period_start: Optional[date] = None
    probation_period_id: Optional[int] = None
    termination_notice_period_id: Optional[int] = None
    hourly_salaried: Optional[str] = None
    working_frequency: Optional[str] = None
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    work_from_home: Optional[bool] = None
    is_manager: Optional[bool] = None
    title: Optional[str] = None
    employment_confirmation_date: Optional[date] = None
    effective_end_date: Optional[date] = None
