import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from edge_middleware.models.execution_state import ExecutionState, ExecutionStatus
from edge_middleware.models.task_lifecycle import TaskStatus
from edge_middleware.models.task_state import TaskStateObservation


OBSERVED_AT = datetime(2026, 11, 26, 9, tzinfo=UTC)
OFFSET = timezone(timedelta(hours=3))


@pytest.fixture
def execution():
    return ExecutionState(
        "task-1", "attempt-1", "worker-a", ExecutionStatus.RUNNING, 0, OBSERVED_AT
    )


def test_execution_status_values_and_json_serialization():
    expected = {
        "PENDING": "pending",
        "RUNNING": "running",
        "SUCCEEDED": "succeeded",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
    }
    assert {name: member.value for name, member in ExecutionStatus.__members__.items()} == expected
    serialized = json.loads(json.dumps(list(ExecutionStatus)))
    assert serialized == list(expected.values())
    assert all(
        ExecutionStatus(value) is member for value, member in zip(serialized, ExecutionStatus)
    )


def test_reassignment_keeps_progress_in_each_attempt(execution):
    original = replace(execution, progress_bps=8500)
    retry = replace(
        original, execution_id="attempt-2", worker_node_id="worker-b", progress_bps=1500
    )

    assert original.task_id == retry.task_id
    assert original.execution_id != retry.execution_id
    assert (original.progress_bps, retry.progress_bps) == (8500, 1500)


def test_failed_and_succeeded_attempts_do_not_change_logical_task_observation(execution):
    task = TaskStateObservation(
        "task-1", "observer-a", TaskStatus.RUNNING, 0, OBSERVED_AT, ["attempt-1"]
    )

    failed = replace(execution, status=ExecutionStatus.FAILED, failure_code="compute_error")
    succeeded = replace(execution, execution_id="attempt-2", status=ExecutionStatus.SUCCEEDED)

    assert failed.task_id == succeeded.task_id == task.task_id
    assert failed.failure_code == "compute_error"
    assert succeeded.progress_bps is None
    assert task.observed_status is TaskStatus.RUNNING
    assert task.known_execution_ids == ("attempt-1",)


@pytest.mark.parametrize("status", ExecutionStatus)
def test_progress_and_attempt_timestamps_may_be_unknown(execution, status):
    record = replace(execution, status=status)

    assert record.progress_bps is None
    assert record.started_at is None
    assert record.finished_at is None
    assert record.failure_code is None


@pytest.mark.parametrize("progress_bps", [0, 1500, 10_000])
def test_progress_accepts_bounds_and_partial_success_observations(execution, progress_bps):
    succeeded = replace(execution, status=ExecutionStatus.SUCCEEDED, progress_bps=progress_bps)

    assert succeeded.progress_bps == progress_bps


def test_wall_times_are_normalized_independently_without_ordering(execution):
    start = datetime(2026, 11, 26, 12, 1, tzinfo=OFFSET)
    finish = datetime(2026, 11, 26, 12, 0, tzinfo=OFFSET)
    observed = datetime(2026, 11, 26, 11, 59, tzinfo=OFFSET)
    record = replace(execution, started_at=start, finished_at=finish, observed_at=observed)

    assert (record.started_at, record.finished_at, record.observed_at) == (
        OBSERVED_AT + timedelta(minutes=1),
        OBSERVED_AT,
        OBSERVED_AT - timedelta(minutes=1),
    )
    assert record.started_at.tzinfo is UTC
    assert record.finished_at.tzinfo is UTC
    assert record.observed_at.tzinfo is UTC
    assert record == replace(execution, started_at=start, finished_at=finish, observed_at=observed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", None),
        ("execution_id", 1),
        ("worker_node_id", b"worker-a"),
        ("status", "running"),
        ("status", TaskStatus.RUNNING),
        ("source_revision", True),
        ("source_revision", 1.5),
        ("progress_bps", False),
        ("progress_bps", 1000.0),
        ("failure_code", 500),
        ("observed_at", None),
        ("started_at", "2026-11-26T09:00:00Z"),
        ("finished_at", 1),
    ],
)
def test_rejects_wrong_types(execution, field, value):
    with pytest.raises(TypeError, match=field):
        replace(execution, **{field: value})


@pytest.mark.parametrize("field", ["task_id", "execution_id", "worker_node_id", "failure_code"])
def test_rejects_blank_identifiers_and_codes(execution, field):
    with pytest.raises(ValueError, match=field):
        replace(execution, **{field: " \t"})


@pytest.mark.parametrize("field", ["observed_at", "started_at", "finished_at"])
def test_rejects_naive_wall_times(execution, field):
    with pytest.raises(ValueError, match=field):
        replace(execution, **{field: OBSERVED_AT.replace(tzinfo=None)})


@pytest.mark.parametrize(
    ("field", "value"), [("source_revision", -1), ("progress_bps", -1), ("progress_bps", 10_001)]
)
def test_rejects_out_of_range_values(execution, field, value):
    with pytest.raises(ValueError, match=field):
        replace(execution, **{field: value})


def test_execution_observation_is_immutable(execution):
    with pytest.raises(FrozenInstanceError):
        execution.progress_bps = 1000
