"""
Person Domain Serializers
"""
from .address_serializers import (
    AddressSerializer,
    AddressCreateSerializer,
    AddressUpdateSerializer
)
from .competency_serializers import (
    CompetencySerializer,
    CompetencyCreateSerializer,
    CompetencyUpdateSerializer,
    CompetencyProficiencySerializer,
    CompetencyProficiencyCreateSerializer,
    CompetencyProficiencyUpdateSerializer
)
from .qualification_serializers import (
    QualificationSerializer,
    QualificationCreateSerializer,
    QualificationUpdateSerializer
)
from .contract_serializers import (
    ContractSerializer,
    ContractCreateSerializer,
    ContractUpdateSerializer
)
from .assignment_serializers import (
    AssignmentSerializer,
    AssignmentCreateSerializer,
    AssignmentUpdateSerializer
)

__all__ = [
    'AddressSerializer',
    'AddressCreateSerializer',
    'AddressUpdateSerializer',
    'CompetencySerializer',
    'CompetencyCreateSerializer',
    'CompetencyUpdateSerializer',
    'CompetencyProficiencySerializer',
    'CompetencyProficiencyCreateSerializer',
    'CompetencyProficiencyUpdateSerializer',
    'QualificationSerializer',
    'QualificationCreateSerializer',
    'QualificationUpdateSerializer',
    'ContractSerializer',
    'ContractCreateSerializer',
    'ContractUpdateSerializer',
    'AssignmentSerializer',
    'AssignmentCreateSerializer',
    'AssignmentUpdateSerializer',
]
