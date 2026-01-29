from django.utils.functional import lazy
from core.lookups.models import LookupType
import logging

logger = logging.getLogger(__name__)

def _get_lookup_type(name):
    def _lazy_lookup():
        try:
            # We just need to ensure it exists, but return the name string
            # This allows limit_choices_to to work with the string
            # while ensuring the DB record exists.
            if LookupType.objects.filter(name=name).exists():
                return name
            logger.warning(f"LookupType '{name}' not found in DB.")
            return name
        except Exception as e:
            # Handle potential db errors during startup (e.g. migrations)
            # Just return the name so migrations can proceed
            return name
    return lazy(_lazy_lookup, str)()

class CoreLookups:
    """
    Central configuration for HR Lookup Types.
    Uses lazy loading to avoid DB access at module import time.
    Returns the name of the lookup type as a string, validated against the DB.
    """
    
    # Geography
    COUNTRY = _get_lookup_type("Country")
    CITY = _get_lookup_type("City")
    ADDRESS_TYPE = _get_lookup_type("Address Type")
    
    # Organization
    ORGANIZATION_TYPE = _get_lookup_type("Organization Type")
    ORGANIZATION_CLASSIFICATION = _get_lookup_type("Organization Classification")
    
    # Jobs
    JOB_CATEGORY = _get_lookup_type("Job Category")
    JOB_TITLE = _get_lookup_type("Job Title")
    JOB_FAMILY = _get_lookup_type("Job Family")
    FUNCTIONAL_AREA = _get_lookup_type("Functional Area")
    
    # Competencies & Skills
    PROFICIENCY_LEVEL = _get_lookup_type("Proficiency Level")
    COMPETENCY_CATEGORY = _get_lookup_type("Competency Category")
    PROFICIENCY_SOURCE = _get_lookup_type("Proficiency Source")
    
    # Positions
    POSITION_FAMILY = _get_lookup_type("Position Family")
    POSITION_CATEGORY = _get_lookup_type("Position Category")
    POSITION_TITLE = _get_lookup_type("Position Title")
    POSITION_TYPE = _get_lookup_type("Position Type")
    POSITION_STATUS = _get_lookup_type("Position Status")
    
    # Payroll & Grades
    PAYROLL = _get_lookup_type("Payroll")
    SALARY_BASIS = _get_lookup_type("Salary Basis")
    GRADE_NAME = _get_lookup_type("Grade Name")
    CURRENCY = _get_lookup_type("Currency")
    
    # Qualifications
    QUALIFICATION_TYPE = _get_lookup_type("Qualification Type")
    QUALIFICATION_TITLE = _get_lookup_type("Qualification Title")
    QUALIFICATION_STATUS = _get_lookup_type("Qualification Status")
    TUITION_METHOD = _get_lookup_type("Tuition Method")
    AWARDING_ENTITY = _get_lookup_type("Awarding Entity")
    
    # Employment & Assignments
    CONTRACT_STATUS = _get_lookup_type("Contract Status")
    CONTRACT_END_REASON = _get_lookup_type("Contract End Reason")
    ASSIGNMENT_STATUS = _get_lookup_type("Assignment Status")
    ASSIGNMENT_ACTION = _get_lookup_type("Assignment Action")
    ASSIGNMENT_ACTION_REASON = _get_lookup_type("Assignment Action Reason")
    PROBATION_PERIOD = _get_lookup_type("Probation Period")
    TERMINATION_NOTICE_PERIOD = _get_lookup_type("Termination Notice Period")
    EMPLOYMENT_CATEGORY = _get_lookup_type("Employment Category")
    WORKER_TYPE = _get_lookup_type("Worker Type")
