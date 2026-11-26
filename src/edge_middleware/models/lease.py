"""Lease data reported by a grantor for a specific ownership reference."""

from dataclasses import dataclass
from datetime import datetime

from edge_middleware.models._observation_validation import (
    as_utc,
    validate_identifier,
    validate_nonnegative_int,
)
from edge_middleware.models.ownership import OwnershipReference, validate_ownership_reference


@dataclass(frozen=True, slots=True)
class Lease:
    """A grantor's issuance time and duration for the referenced ownership record."""

    lease_id: str
    ownership_ref: OwnershipReference
    issuer_node_id: str
    issued_at: datetime
    duration_ms: int
    predecessor_lease_id: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.lease_id, "lease_id")
        validate_ownership_reference(self.ownership_ref)
        validate_identifier(self.issuer_node_id, "issuer_node_id")
        object.__setattr__(self, "issued_at", as_utc(self.issued_at, "issued_at"))
        validate_nonnegative_int(self.duration_ms, "duration_ms")
        if self.duration_ms == 0:
            raise ValueError("duration_ms must be positive")
        if self.predecessor_lease_id is not None:
            validate_identifier(self.predecessor_lease_id, "predecessor_lease_id")
            if self.predecessor_lease_id == self.lease_id:
                raise ValueError("predecessor_lease_id must refer to a different lease")
