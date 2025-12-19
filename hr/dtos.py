from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class DepartmentCreateDTO:
    business_group_id: int
    code: str
    name: str
    location_id: int
    parent_id: Optional[int] = None
    effective_start_date: Optional[date] = None

@dataclass
class DepartmentUpdateDTO:
    code: str
    name: Optional[str] = None
    location_id: Optional[int] = None
    parent_id: Optional[int] = None
    effective_date: Optional[date] = None

@dataclass
class PositionCreateDTO:
    code: str
    name: str
    department_id: int
    location_id: int
    grade_id: int
    reports_to_id: Optional[int] = None
    effective_start_date: Optional[date] = None

@dataclass
class PositionUpdateDTO:
    code: str
    name: Optional[str] = None
    department_id: Optional[int] = None
    location_id: Optional[int] = None
    grade_id: Optional[int] = None
    reports_to_id: Optional[int] = None
    effective_date: Optional[date] = None

@dataclass
class GradeCreateDTO:
    code: str
    name: str
    business_group_id: int
    effective_start_date: Optional[date] = None

@dataclass
class GradeRateCreateDTO:
    grade_id: int
    rate_type: str
    amount: float
    currency: str = 'EGP'
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None
