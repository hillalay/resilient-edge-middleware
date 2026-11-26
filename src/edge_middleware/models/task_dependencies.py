"""Validate dependencies in a complete task definition snapshot."""

from collections.abc import Iterable
from graphlib import CycleError, TopologicalSorter
from typing import Literal

from edge_middleware.models.task_definition import TaskDefinition


class TaskDependencyError(ValueError):
    """A dependency validation failure with a machine-readable reason."""

    def __init__(
        self,
        reason: Literal[
            "duplicate_task_id", "missing_dependency", "self_dependency", "cycle"
        ],
        message: str,
    ) -> None:
        super().__init__(message)
        self.reason = reason


def validate_task_dependencies(task_definitions: Iterable[TaskDefinition]) -> None:
    """Raise TaskDependencyError for a broken complete snapshot of task definitions."""
    dependencies: dict[str, tuple[str, ...]] = {}
    for task in task_definitions:
        if type(task) is not TaskDefinition:
            raise TypeError("task_definitions must contain TaskDefinition instances")
        if task.task_id in dependencies:
            raise TaskDependencyError(
                "duplicate_task_id", f"duplicate task ID {task.task_id!r}"
            )
        dependencies[task.task_id] = tuple(task.dependency_task_ids)

    for task_id, dependency_ids in dependencies.items():
        for dependency_id in dependency_ids:
            if dependency_id == task_id:
                raise TaskDependencyError(
                    "self_dependency", f"task {task_id!r} depends on itself"
                )
            if dependency_id not in dependencies:
                raise TaskDependencyError(
                    "missing_dependency",
                    f"task {task_id!r} depends on missing task {dependency_id!r}",
                )

    try:
        TopologicalSorter(dependencies).prepare()
    except CycleError as error:
        # graphlib reports the cycle in predecessor-to-dependent order.
        path = " -> ".join(repr(task_id) for task_id in reversed(error.args[1]))
        raise TaskDependencyError("cycle", f"task dependency cycle: {path}") from error
