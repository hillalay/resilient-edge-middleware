from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from edge_middleware.models.resource_requirements import ResourceRequirements
from edge_middleware.models.task_definition import InputRequirementRef, TaskDefinition
from edge_middleware.models.task_policy import (
    TaskSecurityClass,
    TaskTransferability,
    resolve_task_policy,
)


CREATED_AT = datetime(2026, 11, 26, 9, tzinfo=UTC)


def make_task(**overrides):
    values = {
        "task_id": "aggregate-1",
        "task_type": "aggregate",
        "security_class": TaskSecurityClass.ROUTINE,
        "transferability": TaskTransferability.RESTART,
        "resource_requirements": ResourceRequirements(250, 128 * 1024**2, 1500),
        "priority": 25,
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    return TaskDefinition(**values)


def test_independent_task_uses_caller_identity_and_time():
    task = make_task()

    assert task.task_id == "aggregate-1"
    assert task.task_type == "aggregate"
    assert task.created_at == CREATED_AT
    assert task.created_at.tzinfo is UTC
    assert task.deadline_at is None
    assert task.input_refs == ()
    assert task.dependency_task_ids == ()


@pytest.mark.parametrize("security_class", TaskSecurityClass)
@pytest.mark.parametrize("transferability", TaskTransferability)
def test_every_policy_combination_can_be_resolved_from_task(security_class, transferability):
    task = make_task(security_class=security_class, transferability=transferability)

    assert task.security_class is security_class
    assert task.transferability is transferability
    assert resolve_task_policy(task.security_class, task.transferability) == resolve_task_policy(
        security_class, transferability
    )


@pytest.mark.parametrize("priority", [0, 100])
def test_priority_accepts_both_bounds_independent_of_security_class(priority):
    for security_class in TaskSecurityClass:
        assert make_task(priority=priority, security_class=security_class).priority == priority


def test_timestamps_are_stored_in_utc_and_equal_deadline_is_allowed():
    local_zone = timezone(timedelta(hours=3))
    local_created_at = datetime(2026, 11, 26, 12, tzinfo=local_zone)
    task = make_task(created_at=local_created_at, deadline_at=CREATED_AT)

    assert task.created_at == task.deadline_at == CREATED_AT
    assert task.created_at.tzinfo is UTC
    assert task.deadline_at.tzinfo is UTC

    task = make_task(deadline_at=local_created_at + timedelta(minutes=1))
    assert task.deadline_at == CREATED_AT + timedelta(minutes=1)
    assert task.deadline_at.tzinfo is UTC


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("task_id", "", "task_id"),
        ("task_type", " \t", "task_type"),
        ("priority", -1, "priority"),
        ("priority", 101, "priority"),
        ("created_at", CREATED_AT.replace(tzinfo=None), "timezone-aware"),
        ("deadline_at", CREATED_AT.replace(tzinfo=None), "timezone-aware"),
        (
            "created_at",
            datetime.min.replace(tzinfo=timezone(timedelta(hours=1))),
            "outside the supported UTC range",
        ),
        (
            "deadline_at",
            datetime(2026, 11, 26, 12, tzinfo=timezone(timedelta(hours=4))),
            "must not precede",
        ),
        ("dependency_task_ids", [" \t"], "dependency task ID"),
        ("dependency_task_ids", ["aggregate-1"], "itself"),
        ("dependency_task_ids", ["collect-1", "collect-1"], "duplicate task IDs"),
        (
            "input_refs",
            [InputRequirementRef("events"), InputRequirementRef("events", size_bytes=32)],
            "duplicate input IDs",
        ),
    ],
)
def test_rejects_invalid_task_values(field, value, message):
    with pytest.raises(ValueError, match=message):
        make_task(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", 10),
        ("task_type", None),
        ("security_class", "routine"),
        ("security_class", TaskTransferability.RESTART),
        ("transferability", "restart"),
        ("transferability", TaskSecurityClass.ROUTINE),
        ("resource_requirements", {"min_cpu_millicores": 250}),
        ("priority", True),
        ("priority", 2.5),
        ("created_at", "2026-11-26T09:00:00Z"),
        ("deadline_at", 1),
        ("input_refs", "events"),
        ("input_refs", [{"input_id": "events"}]),
        ("dependency_task_ids", "collect-1"),
        ("dependency_task_ids", {"collect-1"}),
        ("dependency_task_ids", [1]),
    ],
)
def test_rejects_invalid_task_types(field, value):
    with pytest.raises(TypeError):
        make_task(**{field: value})


def test_task_freezes_input_and_dependency_sequences():
    ref = InputRequirementRef("events")
    inputs = [ref]
    dependencies = ["collect-1"]
    task = make_task(input_refs=inputs, dependency_task_ids=dependencies)

    inputs.clear()
    dependencies.append("collect-2")

    assert task.input_refs == (ref,)
    assert task.dependency_task_ids == ("collect-1",)
    with pytest.raises(FrozenInstanceError):
        task.priority = 10
    with pytest.raises(FrozenInstanceError):
        ref.size_bytes = 100


def test_input_metadata_can_be_unknown_or_supplied_independently():
    pending = InputRequirementRef("upstream-output")
    checksum = InputRequirementRef("events", content_hash="AB" * 32)
    empty = InputRequirementRef("empty-file", size_bytes=0)

    assert (pending.content_hash, pending.size_bytes) == (None, None)
    assert (checksum.content_hash, checksum.size_bytes) == ("ab" * 32, None)
    assert (empty.content_hash, empty.size_bytes) == (None, 0)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("input_id", "", ValueError),
        ("input_id", " \t", ValueError),
        ("input_id", None, TypeError),
        ("content_hash", "a" * 63, ValueError),
        ("content_hash", "g" * 64, ValueError),
        ("content_hash", b"a" * 64, TypeError),
        ("size_bytes", -1, ValueError),
        ("size_bytes", False, TypeError),
        ("size_bytes", 12.5, TypeError),
    ],
)
def test_rejects_invalid_input_references(field, value, error):
    fields = {"input_id": "events", field: value}
    with pytest.raises(error, match=field):
        InputRequirementRef(**fields)
