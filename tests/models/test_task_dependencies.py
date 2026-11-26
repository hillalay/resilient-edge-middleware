from datetime import UTC, datetime

import pytest

from edge_middleware.models.resource_requirements import ResourceRequirements
from edge_middleware.models.task_definition import TaskDefinition
from edge_middleware.models.task_dependencies import (
    TaskDependencyError,
    validate_task_dependencies,
)
from edge_middleware.models.task_policy import TaskSecurityClass, TaskTransferability


def make_task(task_id, *dependency_ids):
    return TaskDefinition(
        task_id=task_id,
        task_type="test-task",
        security_class=TaskSecurityClass.ROUTINE,
        transferability=TaskTransferability.RESTART,
        resource_requirements=ResourceRequirements(1, 1, 1),
        priority=0,
        created_at=datetime(2026, 11, 26, tzinfo=UTC),
        dependency_task_ids=dependency_ids,
    )


def test_accepts_a_dag_with_disconnected_components_and_an_independent_task():
    snapshot = [
        make_task("join", "left", "right"),
        make_task("left", "root"),
        make_task("right", "root"),
        make_task("root"),
        make_task("report", "collect"),
        make_task("collect"),
        make_task("independent"),
    ]

    assert validate_task_dependencies(snapshot) is None
    assert validate_task_dependencies(reversed(snapshot)) is None
    assert validate_task_dependencies([]) is None


def test_accepts_a_deep_dag():
    snapshot = [make_task("0")]
    snapshot.extend(make_task(str(i), str(i - 1)) for i in range(1, 1500))

    assert validate_task_dependencies(reversed(snapshot)) is None


def test_rejects_items_that_are_not_task_definitions():
    with pytest.raises(TypeError, match="TaskDefinition"):
        validate_task_dependencies([make_task("a"), "b"])


def test_rejects_duplicate_task_ids_even_for_identical_definitions():
    task = make_task("a")

    with pytest.raises(TaskDependencyError, match="duplicate task ID 'a'") as exc:
        validate_task_dependencies([task, task])

    assert exc.value.reason == "duplicate_task_id"


def test_reports_missing_dependency_before_searching_for_cycles():
    snapshot = [make_task("a", "b"), make_task("b", "a"), make_task("c", "absent")]

    with pytest.raises(TaskDependencyError, match="'c' depends on missing task 'absent'") as exc:
        validate_task_dependencies(snapshot)

    assert exc.value.reason == "missing_dependency"


def test_snapshot_defensively_rejects_self_dependencies():
    task = make_task("a")
    object.__setattr__(task, "dependency_task_ids", ("a",))

    with pytest.raises(TaskDependencyError, match="'a' depends on itself") as exc:
        validate_task_dependencies([task])

    assert exc.value.reason == "self_dependency"


@pytest.mark.parametrize(
    "edges",
    [
        [("a", "b"), ("b", "a")],
        [("a", "b"), ("b", "c"), ("c", "a")],
    ],
)
def test_reports_cycles_deterministically_in_dependency_direction(edges):
    snapshot = [make_task("independent"), *(make_task(*edge) for edge in edges)]
    messages = []

    for _ in range(2):
        with pytest.raises(TaskDependencyError, match="task dependency cycle") as exc:
            validate_task_dependencies(snapshot)
        assert exc.value.reason == "cycle"
        messages.append(str(exc.value))

    assert messages[0] == messages[1]
    path = messages[0].removeprefix("task dependency cycle: ").split(" -> ")
    ids = [node.strip("'") for node in path]
    assert ids[0] == ids[-1]
    assert set(zip(ids, ids[1:])) == set(edges)
