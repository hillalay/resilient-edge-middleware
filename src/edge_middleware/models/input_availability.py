"""Node-local observations about task input availability."""

import re
from dataclasses import dataclass
from datetime import datetime

from edge_middleware.models._observation_validation import (
    as_utc,
    validate_identifier,
    validate_nonnegative_int,
)


@dataclass(frozen=True, slots=True)
class InputAvailabilityObservation:
    """Reported local verified bytes for a task input and expected content hash.

    source_revision belongs to the reporting node's stream for this task,
    input, and expected hash within a single source incarnation.
    """

    node_id: str
    task_id: str
    input_id: str
    available_verified_bytes: int
    source_revision: int
    observed_at: datetime
    expected_content_hash: str | None = None
    expected_size_bytes: int | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.node_id, "node_id")
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.input_id, "input_id")
        validate_nonnegative_int(self.available_verified_bytes, "available_verified_bytes")
        validate_nonnegative_int(self.source_revision, "source_revision")
        if self.expected_content_hash is not None:
            if type(self.expected_content_hash) is not str:
                raise TypeError("expected_content_hash must be a string or None")
            if re.fullmatch(r"[0-9a-fA-F]{64}", self.expected_content_hash) is None:
                raise ValueError("expected_content_hash must contain 64 SHA-256 hex digits")
            object.__setattr__(
                self, "expected_content_hash", self.expected_content_hash.lower()
            )
        if self.expected_size_bytes is not None:
            validate_nonnegative_int(self.expected_size_bytes, "expected_size_bytes")
            if self.available_verified_bytes > self.expected_size_bytes:
                raise ValueError("available_verified_bytes must not exceed expected_size_bytes")
        object.__setattr__(self, "observed_at", as_utc(self.observed_at, "observed_at"))
