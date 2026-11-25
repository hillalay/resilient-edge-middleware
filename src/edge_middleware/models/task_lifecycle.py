"""Structural task transitions; validation never authorizes an operation."""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Logical task state, independent of ownership and execution attempts."""

    CREATED = "created"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TransitionIntent(StrEnum):
    """Requested operation, not a lifecycle state or proof of authorization."""

    NORMAL = "normal"
    CANCEL = "cancel"
    REASSIGN = "reassign"


_ALLOWED_TRANSITIONS = frozenset(
    {
        (TaskStatus.CREATED, TaskStatus.ASSIGNED, TransitionIntent.NORMAL),
        (TaskStatus.ASSIGNED, TaskStatus.RUNNING, TransitionIntent.NORMAL),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED, TransitionIntent.NORMAL),
        (TaskStatus.CREATED, TaskStatus.CANCELLED, TransitionIntent.CANCEL),
        (TaskStatus.ASSIGNED, TaskStatus.CANCELLED, TransitionIntent.CANCEL),
        (TaskStatus.RUNNING, TaskStatus.CANCELLED, TransitionIntent.CANCEL),
        (TaskStatus.ASSIGNED, TaskStatus.ASSIGNED, TransitionIntent.REASSIGN),
        (TaskStatus.RUNNING, TaskStatus.ASSIGNED, TransitionIntent.REASSIGN),
    }
)


def is_valid_transition(
    current: TaskStatus,
    target: TaskStatus,
    *,
    intent: TransitionIntent = TransitionIntent.NORMAL,
) -> bool:
    """Return structural eligibility only; do not mutate state or grant authority.

    Cancellation and reassignment require an explicit matching intent. A true
    result does not verify ownership, inputs, quorum, leases, fencing, result
    authority, or safe stopping. Those belong to later coordination layers.
    Inputs must be enum members; deserialize strings at the caller boundary.
    """
    if not (
        isinstance(current, TaskStatus)
        and isinstance(target, TaskStatus)
        and isinstance(intent, TransitionIntent)
    ):
        return False
    return (current, target, intent) in _ALLOWED_TRANSITIONS
