"""Worker observations about individual execution attempts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from edge_middleware.models._observation_validation import (
    as_utc,
    validate_identifier,
    validate_nonnegative_int,
)


class ExecutionStatus(StrEnum):
    """Reported status of an attempt, independent of logical task status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ExecutionState:
    """Observation scoped to a task, execution attempt, and reporting worker.

    The worker supplies source_revision for this observation stream within
    its current source incarnation. Timestamps record reported wall time.
    """

    task_id: str
    execution_id: str
    worker_node_id: str
    status: ExecutionStatus
    source_revision: int
    observed_at: datetime
    progress_bps: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.task_id, "task_id")
        validate_identifier(self.execution_id, "execution_id")
        validate_identifier(self.worker_node_id, "worker_node_id")
        if type(self.status) is not ExecutionStatus:
            raise TypeError("status must be an ExecutionStatus member")
        validate_nonnegative_int(self.source_revision, "source_revision")
        if self.progress_bps is not None:
            validate_nonnegative_int(self.progress_bps, "progress_bps")
            if self.progress_bps > 10_000:
                raise ValueError("progress_bps must be between 0 and 10000")
        if self.failure_code is not None:
            validate_identifier(self.failure_code, "failure_code")

        object.__setattr__(self, "observed_at", as_utc(self.observed_at, "observed_at"))
        if self.started_at is not None:
            object.__setattr__(self, "started_at", as_utc(self.started_at, "started_at"))
        if self.finished_at is not None:
            object.__setattr__(self, "finished_at", as_utc(self.finished_at, "finished_at"))
