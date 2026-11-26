"""A node's local observations of logical task status."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from edge_middleware.models._observation_validation import (
    as_utc,
    validate_identifier,
    validate_nonnegative_int,
)
from edge_middleware.models.task_lifecycle import TaskStatus


@dataclass(frozen=True, slots=True)
class TaskStateObservation:
    """Status seen by one observer, with a revision scoped to its task stream."""

    task_id: str
    observer_node_id: str
    observed_status: TaskStatus
    source_revision: int
    observed_at: datetime
    known_execution_ids: Sequence[str] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.observer_node_id, "observer_node_id")
        if type(self.observed_status) is not TaskStatus:
            raise TypeError("observed_status must be a TaskStatus member")
        validate_nonnegative_int(self.source_revision, "source_revision")
        object.__setattr__(self, "observed_at", as_utc(self.observed_at, "observed_at"))

        if not isinstance(self.known_execution_ids, Sequence) or isinstance(
            self.known_execution_ids, (str, bytes, bytearray)
        ):
            raise TypeError("known_execution_ids must be a sequence of execution IDs")
        execution_ids = tuple(self.known_execution_ids)
        for execution_id in execution_ids:
            validate_identifier(execution_id, "known execution ID")
        if len(set(execution_ids)) != len(execution_ids):
            raise ValueError("known_execution_ids must not contain duplicate execution IDs")
        object.__setattr__(self, "known_execution_ids", execution_ids)
