"""
Contingent Worker Service - Business Logic Layer

Handles all contingent worker lifecycle workflows:
- Creating placements
- Ending placements
- Renewals
- Status updates

All contingent worker state transitions MUST go through this service.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from HR.person.models import ContingentWorker, PersonType


class ContingentWorkerService:
    """Service layer for contingent worker lifecycle management"""

    @staticmethod
    @transaction.atomic
    def create_placement(person_data, worker_data, effective_start_date=None, placement_date=None):
        """
        Create new contingent worker placement.
        
        Args:
            person_data: Dict with person fields (first_name, email_address, etc.)
            worker_data: Dict with worker_type, worker_number, etc.
                {
                    'worker_type': PersonType,
                    'worker_number': str,
                    'vendor_name': str (optional),
                    'po_number': str (optional),
                    'current_assignment': Organization (optional),
                    'assignment_role': Position (optional)
                }
            effective_start_date: Date placement started (default: today)
            placement_date: Actual placement date (default: effective_start_date)
        
        Returns:
            ContingentWorker: Newly created worker record (person auto-created)
        """
        if effective_start_date is None:
            effective_start_date = date.today()
            
        if placement_date is None:
            placement_date = effective_start_date

        # Merge data for ChildModelMixin
        combined_data = {
            **person_data,
            'worker_type': worker_data['worker_type'],
            'worker_number': worker_data['worker_number'],
            'placement_date': placement_date,
            'effective_start_date': effective_start_date,
            'vendor_name': worker_data.get('vendor_name', ''),
            'po_number': worker_data.get('po_number', ''),
            'current_assignment': worker_data.get('current_assignment'),
            'assignment_role': worker_data.get('assignment_role')
        }

        worker = ContingentWorker.objects.create(**combined_data)
        return worker

    @staticmethod
    @transaction.atomic
    def end_placement(worker_id, end_date=None, reason=''):
        """
        End contingent worker placement.
        
        Args:
            worker_id: ContingentWorker record ID
            end_date: Last day of placement (default: today)
            reason: Reason for ending (contract completion, early termination, etc.)
        
        Returns:
            ContingentWorker: Updated worker record
        """
        worker = ContingentWorker.objects.get(pk=worker_id)

        if end_date is None:
            end_date = date.today()

        # Use VersionedMixin's deactivate method
        worker.deactivate(end_date=end_date)

        # Note: Could add PlacementEndRecord here if needed
        # PlacementEndRecord.objects.create(worker=worker, reason=reason, ...)

        return worker

    @staticmethod
    @transaction.atomic
    def renew_placement(worker_id, renewal_date, new_end_date=None):
        """
        Renew contingent worker placement (creates new version).
        
        Args:
            worker_id: Current worker record ID
            renewal_date: Date renewal takes effect
            new_end_date: New expected end date (optional)
        
        Returns:
            ContingentWorker: Newly created worker record (renewal version)
        """
        worker = ContingentWorker.objects.get(pk=worker_id)

        # End current placement
        worker.deactivate(end_date=renewal_date - timedelta(days=1))

        # Create new placement (renewal)
        new_worker = ContingentWorker(
            person=worker.person,
            worker_type=worker.worker_type,
            worker_number=worker.worker_number,  # Keep same number
            placement_date=renewal_date,
            effective_start_date=renewal_date,
            effective_end_date=new_end_date,
            vendor_name=worker.vendor_name,
            po_number=worker.po_number,
            current_assignment=worker.current_assignment,
            assignment_role=worker.assignment_role
        )
        new_worker.full_clean()
        new_worker.save()

        return new_worker

    @staticmethod
    def get_active_workers(as_of_date=None):
        """
        Get all active contingent workers on a specific date.
        
        Args:
            as_of_date: Reference date (default: today)
        
        Returns:
            QuerySet of ContingentWorker objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        return ContingentWorker.objects.active_on(as_of_date)

    @staticmethod
    def get_workers_by_vendor(vendor_name, as_of_date=None):
        """
        Get all active workers from a specific vendor.
        
        Args:
            vendor_name: Vendor/agency name
            as_of_date: Reference date (default: today)
        
        Returns:
            QuerySet of ContingentWorker objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        return ContingentWorker.objects.active_on(as_of_date).filter(
            vendor_name__icontains=vendor_name
        )

    @staticmethod
    def get_placement_history(person_id):
        """
        Get complete placement history for a person.
        
        Args:
            person_id: Person ID
        
        Returns:
            QuerySet of ContingentWorker objects ordered by placement_date
        """
        return ContingentWorker.objects.filter(
            person_id=person_id
        ).order_by('-placement_date')
