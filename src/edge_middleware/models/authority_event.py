"""Reported authority events and their structural payload contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import get_args

from edge_middleware.models._observation_validation import as_utc, validate_identifier
from edge_middleware.models.lease import Lease
from edge_middleware.models.ownership import (
    CriticalAuthorizationRef,
    CriticalOwnershipEvidence,
    CriticalOwnershipScope,
    OwnershipReference,
    RoutineClaimRef,
    RoutineOwnershipClaim,
    validate_ownership_reference,
)
from edge_middleware.models.task_policy import TaskSecurityClass


class AuthorityEventType(StrEnum):
    """Operation reported as having occurred."""

    OWNERSHIP_GRANTED = "ownership_granted"
    OWNERSHIP_TRANSFERRED = "ownership_transferred"
    LEASE_RENEWED = "lease_renewed"
    OWNERSHIP_RELEASED = "ownership_released"
    OWNERSHIP_REVOKED = "ownership_revoked"
    RESULT_ACCEPTED = "result_accepted"
    CANCELLATION_CONFIRMED = "cancellation_confirmed"


@dataclass(frozen=True, slots=True)
class ResultAcceptance:
    """Attempt and output referenced by a reported result acceptance decision."""

    execution_id: str
    output_manifest_id: str
    ownership_ref: OwnershipReference

    def __post_init__(self) -> None:
        validate_identifier(self.execution_id, "execution_id")
        validate_identifier(self.output_manifest_id, "output_manifest_id")
        validate_ownership_reference(self.ownership_ref)


@dataclass(frozen=True, slots=True)
class CancellationRequest:
    """A caller's intent to cancel a task, separate from a reported confirmation."""

    request_id: str
    task_id: str
    requester_node_id: str
    requested_at: datetime

    def __post_init__(self) -> None:
        validate_identifier(self.request_id, "request_id")
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.requester_node_id, "requester_node_id")
        object.__setattr__(self, "requested_at", as_utc(self.requested_at, "requested_at"))


@dataclass(frozen=True, slots=True)
class CancellationConfirmation:
    """Reference to a cancellation request and any associated ownership context."""

    request_id: str
    ownership_ref: OwnershipReference | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.request_id, "request_id")
        if self.ownership_ref is not None:
            validate_ownership_reference(self.ownership_ref)


_OwnershipRecord = RoutineOwnershipClaim | CriticalOwnershipEvidence
AuthorityPayload = (
    _OwnershipRecord | OwnershipReference | Lease | ResultAcceptance | CancellationConfirmation
)

_PAYLOAD_TYPES = {
    AuthorityEventType.OWNERSHIP_GRANTED: get_args(_OwnershipRecord),
    AuthorityEventType.OWNERSHIP_TRANSFERRED: get_args(_OwnershipRecord),
    AuthorityEventType.LEASE_RENEWED: (Lease,),
    AuthorityEventType.OWNERSHIP_RELEASED: get_args(OwnershipReference),
    AuthorityEventType.OWNERSHIP_REVOKED: get_args(OwnershipReference),
    AuthorityEventType.RESULT_ACCEPTED: (ResultAcceptance,),
    AuthorityEventType.CANCELLATION_CONFIRMED: (CancellationConfirmation,),
}


@dataclass(frozen=True, slots=True)
class AuthorityEvent:
    """A reported decision with a structurally compatible payload."""

    event_id: str
    task_id: str
    security_class: TaskSecurityClass
    event_type: AuthorityEventType
    issuer_node_id: str
    issued_at: datetime
    payload: AuthorityPayload

    def __post_init__(self) -> None:
        validate_identifier(self.event_id, "event_id")
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.issuer_node_id, "issuer_node_id")
        if type(self.security_class) is not TaskSecurityClass:
            raise TypeError("security_class must be a TaskSecurityClass member")
        if type(self.event_type) is not AuthorityEventType:
            raise TypeError("event_type must be an AuthorityEventType member")
        object.__setattr__(self, "issued_at", as_utc(self.issued_at, "issued_at"))

        payload = self.payload
        if type(payload) not in get_args(AuthorityPayload):
            raise TypeError("payload must be an authority event payload model")
        if type(payload) not in _PAYLOAD_TYPES[self.event_type]:
            raise ValueError(f"payload does not match {self.event_type.value}")

        if isinstance(payload, _OwnershipRecord):
            self._validate_ownership_record(payload)
            return

        if isinstance(payload, Lease) and payload.predecessor_lease_id is None:
            raise ValueError("lease renewal requires predecessor_lease_id")
        reference = (
            payload if isinstance(payload, OwnershipReference) else payload.ownership_ref
        )
        if reference is not None:
            self._validate_reference(reference)

    def _validate_ownership_record(self, record: _OwnershipRecord) -> None:
        if record.task_id != self.task_id:
            raise ValueError("payload must refer to the event's task_id")

        transfer = self.event_type is AuthorityEventType.OWNERSHIP_TRANSFERRED
        if isinstance(record, RoutineOwnershipClaim):
            if self.security_class is not TaskSecurityClass.ROUTINE:
                raise ValueError("routine payload does not match security_class")
            if transfer != (record.predecessor_claim is not None):
                raise ValueError(
                    "predecessor_claim is required for transfer and forbidden for grant"
                )
        else:
            if self.security_class is not TaskSecurityClass.CRITICAL:
                raise ValueError("critical payload does not match security_class")
            expected_scope = (
                CriticalOwnershipScope.TRANSFER if transfer else CriticalOwnershipScope.GRANT
            )
            if record.scope is not expected_scope:
                raise ValueError("critical ownership scope does not match event_type")

    def _validate_reference(self, reference: OwnershipReference) -> None:
        if reference.task_id != self.task_id:
            raise ValueError("ownership_ref must refer to the event's task_id")
        expected_type = (
            RoutineClaimRef
            if self.security_class is TaskSecurityClass.ROUTINE
            else CriticalAuthorizationRef
        )
        if type(reference) is not expected_type:
            raise ValueError("ownership_ref does not match security_class")
