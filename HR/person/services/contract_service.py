from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date
from typing import List, Optional
from HR.person.dtos import ContractCreateDTO, ContractUpdateDTO
from HR.person.models import Contract, Person
from core.lookups.models import LookupValue
from HR.lookup_config import CoreLookups

class ContractService:
    """Service layer for Contract business logic"""

    @staticmethod
    @transaction.atomic
    def create(user, dto: ContractCreateDTO) -> Contract:
        """Create a new contract record"""
        # Validate person
        try:
            person = Person.objects.get(pk=dto.person_id)
        except Person.DoesNotExist:
            raise ValidationError({'person_id': 'Person not found'})

        # Validate contract status
        try:
            status = LookupValue.objects.get(pk=dto.contract_status_id)
            if status.lookup_type.name != CoreLookups.CONTRACT_STATUS:
                raise ValidationError({'contract_status_id': 'Must be a CONTRACT_STATUS lookup value'})
        except LookupValue.DoesNotExist:
            raise ValidationError({'contract_status_id': 'Contract status not found'})

        # Validate end reason if provided
        end_reason = None
        if dto.contract_end_reason_id:
            try:
                end_reason = LookupValue.objects.get(pk=dto.contract_end_reason_id)
                if end_reason.lookup_type.name != CoreLookups.CONTRACT_END_REASON:
                    raise ValidationError({'contract_end_reason_id': 'Must be a CONTRACT_END_REASON lookup value'})
            except LookupValue.DoesNotExist:
                raise ValidationError({'contract_end_reason_id': 'Contract end reason not found'})

        contract = Contract(
            contract_reference=dto.contract_reference,
            person=person,
            contract_status=status,
            contract_end_reason=end_reason,
            description=dto.description,
            contract_duration=dto.contract_duration,
            contract_period=dto.contract_period,
            contract_start_date=dto.contract_start_date,
            contract_end_date=dto.contract_end_date,
            contractual_job_position=dto.contractual_job_position,
            extension_duration=dto.extension_duration,
            extension_period=dto.extension_period,
            extension_start_date=dto.extension_start_date,
            extension_end_date=dto.extension_end_date,
            basic_salary=dto.basic_salary,
            effective_start_date=dto.effective_start_date or date.today(),
            effective_end_date=dto.effective_end_date,
            created_by=user,
            updated_by=user
        )
        contract.full_clean()
        contract.save()
        return contract

    @staticmethod
    @transaction.atomic
    def update(user, dto: ContractUpdateDTO) -> Contract:
        """Update a contract record (correction or new version)"""
        # Find the latest version of this contract
        contract = Contract.objects.latest_version('contract_reference', dto.contract_reference)
        if not contract:
            raise ValidationError(f"Contract with reference {dto.contract_reference} not found")

        field_updates = {}
        # ... (rest of the fields) ...
        if dto.contract_status_id is not None:
            field_updates['contract_status_id'] = dto.contract_status_id
        if dto.contract_end_reason_id is not None:
            field_updates['contract_end_reason_id'] = dto.contract_end_reason_id
        if dto.description is not None:
            field_updates['description'] = dto.description
        if dto.contract_duration is not None:
            field_updates['contract_duration'] = dto.contract_duration
        if dto.contract_period is not None:
            field_updates['contract_period'] = dto.contract_period
        if dto.contract_start_date is not None:
            field_updates['contract_start_date'] = dto.contract_start_date
        if dto.contract_end_date is not None:
            field_updates['contract_end_date'] = dto.contract_end_date
        if dto.contractual_job_position is not None:
            field_updates['contractual_job_position'] = dto.contractual_job_position
        if dto.extension_duration is not None:
            field_updates['extension_duration'] = dto.extension_duration
        if dto.extension_period is not None:
            field_updates['extension_period'] = dto.extension_period
        if dto.extension_start_date is not None:
            field_updates['extension_start_date'] = dto.extension_start_date
        if dto.extension_end_date is not None:
            field_updates['extension_end_date'] = dto.extension_end_date
        if dto.basic_salary is not None:
            field_updates['basic_salary'] = dto.basic_salary

        # Use VersionedMixin's update_version
        # Note: update_version expects new_start_date if creating a new version.
        # If new_start_date is same as current, it's a correction.
        # Here we'll assume correction if new_start_date is not provided or matches.
        # Actually, let's just use update_version directly with field_updates.
        
        updated_contract = contract.update_version(
            field_updates=field_updates,
            new_start_date=dto.effective_start_date, # This makes it a correction if it matches
            new_end_date=dto.effective_end_date
        )
        updated_contract.updated_by = user
        updated_contract.save(update_fields=['updated_by'])
        return updated_contract

    @staticmethod
    @transaction.atomic
    def deactivate(user, contract_reference: str, end_date: Optional[date] = None) -> Contract:
        """Deactivate a contract by end-dating it"""
        contract = Contract.objects.latest_version('contract_reference', contract_reference)
        if not contract:
            raise ValidationError(f"Contract with reference {contract_reference} not found")
        
        contract.deactivate(end_date=end_date)
        contract.updated_by = user
        contract.save(update_fields=['updated_by'])
        return contract

    @staticmethod
    def get_contracts_by_person(person_id: int) -> List[Contract]:
        """Get all contracts for a person"""
        return Contract.objects.filter(person_id=person_id).order_by('-effective_start_date')

    @staticmethod
    def get_active_contract(person_id: int, reference_date: Optional[date] = None) -> Optional[Contract]:
        """Get the active contract for a person on a specific date"""
        if reference_date is None:
            reference_date = date.today()
        return Contract.objects.active_on(reference_date).filter(person_id=person_id).first()

    @staticmethod
    def get_contract_by_reference(contract_reference: str) -> List[Contract]:
        """Get all versions of a contract by reference"""
        return Contract.objects.filter(contract_reference=contract_reference).order_by('-effective_start_date')
