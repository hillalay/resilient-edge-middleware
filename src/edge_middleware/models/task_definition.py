"""Immutable definition of a logical task and its input references."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from edge_middleware.models.resource_requirements import ResourceRequirements
from edge_middleware.models.task_policy import TaskSecurityClass, TaskTransferability


MIN_PRIORITY = 0
MAX_PRIORITY = 100


def _validate_identifier(value: str, name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


def _as_utc(value: datetime, name: str) -> datetime:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime")
    if value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    try:
        return value.astimezone(UTC)
    except OverflowError as error:
        raise ValueError(f"{name} is outside the supported UTC range") from error


@dataclass(frozen=True, slots=True)
class InputRequirementRef:
    """Required input with optional SHA-256 digest and expected length in bytes."""

    input_id: str
    content_hash: str | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.input_id, "input_id")
        if self.content_hash is not None:
            if type(self.content_hash) is not str:
                raise TypeError("content_hash must be a string or None")
            if re.fullmatch(r"[0-9a-fA-F]{64}", self.content_hash) is None:
                raise ValueError("content_hash must contain 64 SHA-256 hex digits")
            object.__setattr__(self, "content_hash", self.content_hash.lower())
        if self.size_bytes is not None:
            if type(self.size_bytes) is not int:
                raise TypeError("size_bytes must be an int or None")
            if self.size_bytes < 0:
                raise ValueError("size_bytes must be non-negative")


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """Caller-supplied task metadata, with timestamps stored in UTC."""

    task_id: str
    task_type: str
    security_class: TaskSecurityClass
    transferability: TaskTransferability
    resource_requirements: ResourceRequirements
    priority: int
    created_at: datetime
    input_refs: Sequence[InputRequirementRef] = ()
    dependency_task_ids: Sequence[str] = ()
    deadline_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.task_id, "task_id")
        _validate_identifier(self.task_type, "task_type")
        if type(self.security_class) is not TaskSecurityClass:
            raise TypeError("security_class must be a TaskSecurityClass member")
        if type(self.transferability) is not TaskTransferability:
            raise TypeError("transferability must be a TaskTransferability member")
        if type(self.resource_requirements) is not ResourceRequirements:
            raise TypeError("resource_requirements must be a ResourceRequirements instance")
        if type(self.priority) is not int:
            raise TypeError("priority must be an int")
        if not MIN_PRIORITY <= self.priority <= MAX_PRIORITY:
            raise ValueError(
                f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}"
            )

        created_at = _as_utc(self.created_at, "created_at")
        object.__setattr__(self, "created_at", created_at)
        if self.deadline_at is not None:
            deadline_at = _as_utc(self.deadline_at, "deadline_at")
            if deadline_at < created_at:
                raise ValueError("deadline_at must not precede created_at")
            object.__setattr__(self, "deadline_at", deadline_at)

        if not isinstance(self.input_refs, Sequence) or isinstance(
            self.input_refs, (str, bytes, bytearray)
        ):
            raise TypeError("input_refs must be a sequence of input requirement references")
        input_refs = tuple(self.input_refs)
        for ref in input_refs:
            if type(ref) is not InputRequirementRef:
                raise TypeError("input_refs must contain InputRequirementRef instances")
        if len({ref.input_id for ref in input_refs}) != len(input_refs):
            raise ValueError("input_refs must not contain duplicate input IDs")
        object.__setattr__(self, "input_refs", input_refs)

        if not isinstance(self.dependency_task_ids, Sequence) or isinstance(
            self.dependency_task_ids, (str, bytes, bytearray)
        ):
            raise TypeError("dependency_task_ids must be a sequence of identifiers")
        dependency_ids = tuple(self.dependency_task_ids)
        for dependency_id in dependency_ids:
            _validate_identifier(dependency_id, "dependency task ID")
        if self.task_id in dependency_ids:
            raise ValueError("a task cannot depend on itself")
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("dependency_task_ids must not contain duplicate task IDs")
        object.__setattr__(self, "dependency_task_ids", dependency_ids)
