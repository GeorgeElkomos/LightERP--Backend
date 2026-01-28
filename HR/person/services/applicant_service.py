"""
Applicant Service - Business Logic Layer

Handles all applicant lifecycle workflows:
- Creating applications
- Status updates
- Hiring transitions
- Rejections/withdrawals

All applicant state transitions MUST go through this service.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date
from HR.person.models import Applicant, PersonType


class ApplicantService:
    """Service layer for applicant lifecycle management"""

    @staticmethod
    @transaction.atomic
    def create_application(person_data, applicant_data, effective_start_date=None):
        """
        Create new job application.
        
        Args:
            person_data: Dict with person fields (first_name, email_address, etc.)
            applicant_data: Dict with applicant_type, application_number, etc.
                {
                    'applicant_type': PersonType,
                    'application_number': str,
                    'application_source': str (optional),
                    'applied_position': Position (optional)
                }
            effective_start_date: Date application submitted (default: today)
        
        Returns:
            Applicant: Newly created applicant record (person auto-created)
        """
        if effective_start_date is None:
            effective_start_date = date.today()

        # Merge data for ChildModelMixin
        combined_data = {
            **person_data,
            'applicant_type': applicant_data['applicant_type'],
            'application_number': applicant_data['application_number'],
            'effective_start_date': effective_start_date,
            'application_source': applicant_data.get('application_source', ''),
            'applied_position': applicant_data.get('applied_position'),
            'application_status': 'applied'
        }

        applicant = Applicant.objects.create(**combined_data)
        return applicant

    @staticmethod
    @transaction.atomic
    def update_application_status(applicant_id, new_status):
        """
        Update application status.
        
        Valid statuses:
        - applied
        - screening
        - interview
        - assessment
        - offer
        - hired (use hire_from_applicant instead)
        - rejected
        - withdrawn
        
        Args:
            applicant_id: Applicant record ID
            new_status: New status code
        
        Returns:
            Applicant: Updated applicant record
        """
        applicant = Applicant.objects.get(pk=applicant_id)

        # Prevent changing status if already in terminal state
        if applicant.application_status in ['hired', 'rejected', 'withdrawn']:
            raise ValidationError(
                f"Cannot update status - application already {applicant.application_status}"
            )

        applicant.application_status = new_status
        applicant.save()

        return applicant

    @staticmethod
    @transaction.atomic
    def reject_application(applicant_id, rejection_date=None, reason=''):
        """
        Reject application and close applicant period.
        
        Args:
            applicant_id: Applicant record ID
            rejection_date: Date of rejection (default: today)
            reason: Rejection reason (for audit/reporting)
        
        Returns:
            Applicant: Updated applicant record
        """
        applicant = Applicant.objects.get(pk=applicant_id)

        if rejection_date is None:
            rejection_date = date.today()

        applicant.application_status = 'rejected'
        applicant.effective_end_date = rejection_date
        applicant.save()

        # Note: Could add RejectionRecord here if needed
        # RejectionRecord.objects.create(applicant=applicant, reason=reason, ...)

        return applicant

    @staticmethod
    @transaction.atomic
    def withdraw_application(applicant_id, withdrawal_date=None):
        """
        Withdraw application (candidate withdrew).
        
        Args:
            applicant_id: Applicant record ID
            withdrawal_date: Date of withdrawal (default: today)
        
        Returns:
            Applicant: Updated applicant record
        """
        applicant = Applicant.objects.get(pk=applicant_id)

        if withdrawal_date is None:
            withdrawal_date = date.today()

        applicant.application_status = 'withdrawn'
        applicant.effective_end_date = withdrawal_date
        applicant.save()

        return applicant

    @staticmethod
    def get_active_applicants(as_of_date=None):
        """
        Get all active applicants on a specific date.
        
        Args:
            as_of_date: Reference date (default: today)
        
        Returns:
            QuerySet of Applicant objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        return Applicant.objects.active_on(as_of_date).exclude(
            application_status__in=['hired', 'rejected', 'withdrawn']
        )

    @staticmethod
    def get_applicants_by_status(status, as_of_date=None):
        """
        Get all applicants with specific status.
        
        Args:
            status: Application status
            as_of_date: Reference date (default: today)
        
        Returns:
            QuerySet of Applicant objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        return Applicant.objects.active_on(as_of_date).filter(
            application_status=status
        )

    @staticmethod
    def get_application_history(person_id):
        """
        Get complete application history for a person.
        
        Args:
            person_id: Person ID
        
        Returns:
            QuerySet of Applicant objects ordered by effective_start_date
        """
        return Applicant.objects.filter(
            person_id=person_id
        ).order_by('-effective_start_date')
