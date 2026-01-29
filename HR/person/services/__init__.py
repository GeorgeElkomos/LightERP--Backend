"""
Person Domain Services

Business logic for person lifecycle management.
All state transitions and workflows should go through these services.

Services:
- EmployeeService: Hire, terminate, rehire, type conversions
- ApplicantService: Application lifecycle, hiring transitions
- ContingentWorkerService: Placement management
- ContactService: Contact relationship management
"""

from .employee_service import EmployeeService
from .applicant_service import ApplicantService
from .contingent_worker_service import ContingentWorkerService
from .contact_service import ContactService

__all__ = [
    'EmployeeService',
    'ApplicantService',
    'ContingentWorkerService',
    'ContactService',
]
