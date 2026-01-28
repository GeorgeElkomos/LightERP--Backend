"""
Person Domain Models

Core models for person management with versioned child pattern.

Models:
- PersonType: Lookup table for person type classification
- PersonTypeDFFConfig: DFF configuration for custom fields per person type
- Person: Core identity (managed parent - never created directly)
- Employee: Employment periods (base_type='EMP')
- Applicant: Application periods (base_type='APL')
- ContingentWorker: Contingent worker placements (base_type='CWK')
- Contact: Contact relationships (base_type='CON')
- Address: Person addresses with lookup-based country/city
- Competency: System-wide competency definitions
- CompetencyProficiency: Person competency proficiency tracking with date ranges
- Qualification: Educational qualifications and certifications with status-based validation
- Contract: Employee contract management with temporal versioning
- Assignment: Employee job assignments with temporal versioning
"""

from .person_type import PersonType
from .person_type_dff_config import PersonTypeDFFConfig
from .person import Person
from .employee import Employee
from .applicant import Applicant
from .contingent_worker import ContingentWorker
from .address import Address
from .contact import Contact
from .competency import Competency
from .competency_proficiency import CompetencyProficiency
from .competency_requirements import JobCompetencyRequirement, PositionCompetencyRequirement
from .qualification import Qualification
from .contract import Contract
from .assignment import Assignment

__all__ = [
    'PersonType',
    'Person',
    'Employee',
    'Applicant',
    'ContingentWorker',
    'Contact',
    'PersonTypeDFFConfig',
    'Address',
    'Competency',
    'CompetencyProficiency',
    'JobCompetencyRequirement',
    'PositionCompetencyRequirement',
    'Qualification',
    'Contract',
    'Assignment',
]
