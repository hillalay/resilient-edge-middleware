from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from edge_middleware.models.execution_state import ExecutionStatus
from edge_middleware.models.task_lifecycle import TaskStatus
from edge_middleware.models.task_state import TaskStateObservation


OBSERVED_AT = datetime(2026, 11, 26, 9, tzinfo=UTC)


@pytest.fixture
def observation():
    return TaskStateObservation("task-1", "node-a", TaskStatus.RUNNING, 0, OBSERVED_AT)


def test_conflicting_terminal_observations_keep_local_status_and_references(observation):
    completed = replace(
        observation, observed_status=TaskStatus.COMPLETED, known_execution_ids=["attempt-1"]
    )
    cancelled = replace(
        observation, observer_node_id="node-b", observed_status=TaskStatus.CANCELLED
    )

    assert completed.task_id == cancelled.task_id
    assert completed.observer_node_id != cancelled.observer_node_id
    assert completed.source_revision == cancelled.source_revision
    assert completed.observed_status is TaskStatus.COMPLETED
    assert cancelled.observed_status is TaskStatus.CANCELLED
    assert completed.known_execution_ids == ("attempt-1",)
    assert cancelled.known_execution_ids == ()
    assert observation.observed_status is TaskStatus.RUNNING


def test_normalization_and_collection_snapshot_are_deterministic(observation):
    timeshift = OBSERVED_AT.astimezone(timezone(timedelta(hours=3)))
    execution_ids = ["attempt-1", "attempt-2"]
    first = replace(observation, observed_at=timeshift, known_execution_ids=execution_ids)
    second = replace(observation, known_execution_ids=tuple(execution_ids))
    execution_ids[0] = "unrelated"

    assert first == second
    assert first.observed_at.tzinfo is UTC
    assert first.known_execution_ids == ("attempt-1", "attempt-2")
    with pytest.raises(FrozenInstanceError):
        first.known_execution_ids = ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", 123),
        ("observer_node_id", None),
        ("observed_status", "running"),
        ("observed_status", ExecutionStatus.RUNNING),
        ("source_revision", False),
        ("source_revision", "0"),
        ("observed_at", "2026-11-26T09:00:00Z"),
        ("known_execution_ids", "attempt-1"),
        ("known_execution_ids", {"attempt-1"}),
        ("known_execution_ids", [1]),
        ("known_execution_ids", [["attempt-1"]]),
    ],
)
def test_rejects_wrong_types(observation, field, value):
    with pytest.raises(TypeError):
        replace(observation, **{field: value})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("task_id", "", "task_id"),
        ("observer_node_id", " \t", "observer_node_id"),
        ("source_revision", -1, "source_revision"),
        ("observed_at", OBSERVED_AT.replace(tzinfo=None), "timezone-aware"),
        ("known_execution_ids", [" \t"], "blank"),
        ("known_execution_ids", ["attempt-1", "attempt-1"], "duplicate"),
    ],
)
def test_rejects_invalid_values(observation, field, value, message):
    with pytest.raises(ValueError, match=message):
        replace(observation, **{field: value})
