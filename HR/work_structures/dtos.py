from dataclasses import dataclass
from datetime import date, time, datetime
from typing import Optional, List

@dataclass
class OrganizationCreateDTO:
    """DTO for creating a new organization"""
    organization_name: str
    organization_type_id: int  # FK to LookupValue (ORGANIZATION_TYPE)
    location_id: Optional[int] = None  # Optional to avoid circular dependency in tests
    business_group_id: Optional[int] = None  # None for root business groups
    work_start_time: time = time(9, 0)
    work_end_time: time = time(17, 0)
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None

@dataclass
class OrganizationUpdateDTO:
    """DTO for updating an existing organization"""
    organization_id: int  # Primary Key
    organization_name: Optional[str] = None
    organization_type_id: Optional[int] = None
    location_id: Optional[int] = None
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None

@dataclass
class OrganizationManagerCreateDTO:
    """DTO for creating a new organization manager assignment"""
    organization_id: int
    person_id: int
    effective_start_date: date
    effective_end_date: Optional[date] = None

@dataclass
class OrganizationManagerUpdateDTO:
    """DTO for updating an existing organization manager assignment"""
    assignment_id: int  # ID of the OrganizationManager record
    effective_end_date: Optional[date] = None
    # Note: Cannot change organization or person - create new assignment instead

@dataclass
class CompetencyRequirementDTO:
    """DTO for competency requirement with proficiency level"""
    competency_id: int
    proficiency_level_id: int

@dataclass
class QualificationRequirementDTO:
    """DTO for qualification requirement"""
    qualification_type_id: int
    qualification_title_id: int

@dataclass
class PositionCreateDTO:
    """DTO for creating a new position"""
    code: str
    organization_id: int  # Organization (department/unit)
    job_id: int
    position_title_id: int  # FK to LookupValue (POSITION_TITLE)
    position_type_id: int  # FK to LookupValue (POSITION_TYPE)
    position_status_id: int  # FK to LookupValue (POSITION_STATUS)
    location_id: Optional[int] = None
    grade_id: Optional[int] = None
    full_time_equivalent: float = 1.0
    head_count: int = 1
    position_sync: Optional[bool] = None
    payroll_id: Optional[int] = None
    salary_basis_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    competency_requirements: Optional[list[CompetencyRequirementDTO]] = None  # Full requirements with proficiency
    qualification_requirements: Optional[list[QualificationRequirementDTO]] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class PositionUpdateDTO:
    """DTO for updating an existing position"""
    position_id: int  # Primary Key
    position_title_id: Optional[int] = None
    position_type_id: Optional[int] = None
    position_status_id: Optional[int] = None
    organization_id: Optional[int] = None
    job_id: Optional[int] = None
    location_id: Optional[int] = None
    grade_id: Optional[int] = None
    full_time_equivalent: Optional[float] = None
    head_count: Optional[int] = None
    position_sync: Optional[bool] = None
    payroll_id: Optional[int] = None
    salary_basis_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    competency_requirements: Optional[list[CompetencyRequirementDTO]] = None
    qualification_requirements: Optional[list[QualificationRequirementDTO]] = None
    effective_end_date: Optional[date] = None
    new_start_date: Optional[date] = None  # For creating new version

@dataclass
class GradeCreateDTO:
    """DTO for creating a new grade"""
    business_group_id: int  # Root organization (business group)
    grade_name_id: int  # FK to LookupValue (GRADE_NAME)
    sequence: int  # Numeric order within business group
    effective_from: date

@dataclass
class GradeUpdateDTO:
    """DTO for updating an existing grade"""
    grade_id: int  # Primary Key
    grade_name_id: Optional[int] = None
    sequence: Optional[int] = None

@dataclass
class JobCreateDTO:
    """DTO for creating a new job"""
    code: str
    business_group_id: int  # Root organization (business group)
    job_category_id: int  # FK to LookupValue (JOB_CATEGORY)
    job_title_id: int  # FK to LookupValue (JOB_TITLE)
    job_description: str
    responsibilities: list[str]  # List of responsibility strings
    competency_requirements: Optional[list[CompetencyRequirementDTO]] = None  # Full requirements with proficiency
    qualification_requirements: Optional[list[QualificationRequirementDTO]] = None
    grade_ids: Optional[list[int]] = None  
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None


@dataclass
class JobUpdateDTO:
    """DTO for updating an existing job"""
    job_id: int  # Primary Key
    job_category_id: Optional[int] = None
    job_title_id: Optional[int] = None
    job_description: Optional[str] = None
    responsibilities: Optional[list[str]] = None
    competency_requirements: Optional[list[CompetencyRequirementDTO]] = None
    qualification_requirements: Optional[list[QualificationRequirementDTO]] = None
    grade_ids: Optional[list[int]] = None
    effective_end_date: Optional[date] = None
    new_start_date: Optional[date] = None  # For creating new version
    qualification_requirements: Optional[list[QualificationRequirementDTO]] = None
    grade_ids: Optional[list[int]] = None
    effective_end_date: Optional[date] = None
    new_start_date: Optional[date] = None  # For creating new version


@dataclass
class LocationCreateDTO:
    location_name: str
    country_id: int
    city_id: int
    effective_from: date
    business_group_id: Optional[int] = None  # Root organization (business group)
    description: Optional[str] = None
    zone: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    office: Optional[str] = None
    po_box: Optional[str] = None

@dataclass
class LocationUpdateDTO:
    location_id: int  # Primary Key
    location_name: Optional[str] = None
    description: Optional[str] = None
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    business_group_id: Optional[int] = None
    zone: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    office: Optional[str] = None
    po_box: Optional[str] = None

@dataclass
class DepartmentManagerAssignDTO:
    department_id: int
    manager_id: int
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None

@dataclass
class GradeRateCreateDTO:
    """DTO for creating a new grade rate"""
    grade_id: int
    rate_type_id: int
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    fixed_amount: Optional[float] = None
    currency_id: Optional[int] = None
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None

@dataclass
class GradeRateUpdateDTO:
    """DTO for updating an existing grade rate (creates new version)"""
    grade_id: int  # Identifier for lookup (with rate_type)
    rate_type_id: int  # Identifier for lookup (with grade)
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    fixed_amount: Optional[float] = None
    currency_id: Optional[int] = None
    effective_end_date: Optional[date] = None  # For closing current version
    new_start_date: Optional[date] = None  # For creating new version

@dataclass
class GradeRateTypeCreateDTO:
    """DTO for creating a new grade rate type"""
    code: str
    description: Optional[str] = None

@dataclass
class GradeRateTypeUpdateDTO:
    """DTO for updating an existing grade rate type"""
    rate_type_id: int
    code: Optional[str] = None
    description: Optional[str] = None
