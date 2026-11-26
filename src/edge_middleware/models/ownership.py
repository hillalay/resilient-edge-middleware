"""Routine claims and records referring to critical ownership decisions."""

from dataclasses import dataclass
from enum import StrEnum

from edge_middleware.models._observation_validation import (
    validate_identifier,
    validate_nonnegative_int,
)


@dataclass(frozen=True, slots=True)
class RoutineClaimRef:
    """Identify a routine claim in the scope of a task and claiming node."""

    task_id: str
    owner_node_id: str
    claim_id: str

    def __post_init__(self) -> None:
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.owner_node_id, "owner_node_id")
        validate_identifier(self.claim_id, "claim_id")


@dataclass(frozen=True, slots=True)
class RoutineOwnershipClaim:
    """A node's ownership claim, which can coexist with other nodes' claims."""

    claim_id: str
    task_id: str
    owner_node_id: str
    execution_id: str | None = None
    predecessor_claim: RoutineClaimRef | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.claim_id, "claim_id")
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.owner_node_id, "owner_node_id")
        if self.execution_id is not None:
            validate_identifier(self.execution_id, "execution_id")
        if self.predecessor_claim is not None:
            if type(self.predecessor_claim) is not RoutineClaimRef:
                raise TypeError("predecessor_claim must be a RoutineClaimRef")
            if self.predecessor_claim.task_id != self.task_id:
                raise ValueError("predecessor_claim must refer to the same task")
            if (
                self.predecessor_claim.claim_id == self.claim_id
                and self.predecessor_claim.owner_node_id == self.owner_node_id
            ):
                raise ValueError("predecessor_claim must refer to a different claim")


@dataclass(frozen=True, slots=True)
class CriticalAuthorizationRef:
    """Refer to a critical ownership evidence record by its task and record ID."""

    task_id: str
    authorization_id: str

    def __post_init__(self) -> None:
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.authorization_id, "authorization_id")


OwnershipReference = RoutineClaimRef | CriticalAuthorizationRef


def validate_ownership_reference(value: OwnershipReference) -> None:
    """Check the reference type without resolving the referenced record."""
    if type(value) not in (RoutineClaimRef, CriticalAuthorizationRef):
        raise TypeError("ownership_ref must be a RoutineClaimRef or CriticalAuthorizationRef")


@dataclass(frozen=True, slots=True)
class QuorumDecisionRef:
    """Identifier for an external quorum decision, resolved by coordination."""

    decision_id: str

    def __post_init__(self) -> None:
        validate_identifier(self.decision_id, "decision_id")


class CriticalOwnershipScope(StrEnum):
    """Ownership operation that the referenced quorum decision must cover."""

    GRANT = "grant_ownership"
    TRANSFER = "transfer_ownership"


@dataclass(frozen=True, slots=True)
class CriticalOwnershipEvidence:
    """Expected binding for a referenced quorum decision and its ownership operation."""

    authorization_id: str
    task_id: str
    owner_node_id: str
    membership_configuration_id: str
    fencing_token: int
    scope: CriticalOwnershipScope
    quorum_decision_ref: QuorumDecisionRef
    predecessor_authorization: CriticalAuthorizationRef | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.authorization_id, "authorization_id")
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.owner_node_id, "owner_node_id")
        validate_identifier(self.membership_configuration_id, "membership_configuration_id")
        validate_nonnegative_int(self.fencing_token, "fencing_token")
        if self.fencing_token == 0:
            raise ValueError("fencing_token must be positive")
        if type(self.scope) is not CriticalOwnershipScope:
            raise TypeError("scope must be a CriticalOwnershipScope member")
        if type(self.quorum_decision_ref) is not QuorumDecisionRef:
            raise TypeError("quorum_decision_ref must be a QuorumDecisionRef")
        predecessor = self.predecessor_authorization
        if predecessor is not None:
            if type(predecessor) is not CriticalAuthorizationRef:
                raise TypeError("predecessor_authorization must be a CriticalAuthorizationRef")
            if predecessor.task_id != self.task_id:
                raise ValueError("predecessor_authorization must refer to the same task")
            if predecessor.authorization_id == self.authorization_id:
                raise ValueError("predecessor_authorization must refer to a different record")
        if self.scope is CriticalOwnershipScope.TRANSFER and predecessor is None:
            raise ValueError("a transfer requires predecessor_authorization")
        if self.scope is CriticalOwnershipScope.GRANT and predecessor is not None:
            raise ValueError("an initial grant must not carry predecessor_authorization")
