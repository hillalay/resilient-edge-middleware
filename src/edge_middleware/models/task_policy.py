"""Static task policy requirements for callers that authorize operations."""

from dataclasses import dataclass
from enum import StrEnum


class TaskSecurityClass(StrEnum):
    """Ownership and execution safety requirements, independent of priority and deadline."""

    ROUTINE = "routine"
    CRITICAL = "critical"


class TaskTransferability(StrEnum):
    """How a task structurally supports moving execution to another node."""

    RESTART = "restart"
    CHECKPOINT = "checkpoint"
    NON_TRANSFERABLE = "non_transferable"


@dataclass(frozen=True, slots=True)
class TaskPolicyRequirements:
    """Static requirements to consider when evaluating a runtime operation.

    duplicate_execution_tolerated: Concurrent or repeated attempts can be
        tolerated if they cause no unacceptable additional side effects.
    result_deduplication_required: Accept a logical task result only once.
    quorum_required_for_new_ownership: Require quorum approval for initial
        ownership and for granting ownership again, including transfers.
    result_fencing_required: Validate the fencing token at result acceptance.
    resource_fencing_required: Validate the fencing token at the resource
        performing the side effect.
    inter_node_transfer_supported: The task structurally supports moving to
        another node, subject to runtime authorization.
    checkpoint_required_for_transfer: Moving to another node requires a
        validated, compatible checkpoint.
    safe_restart_required_for_transfer: Before restarting on another node,
        ensure prior side effects are handled safely. False leaves the safety
        of other operations to runtime evaluation.
    """

    duplicate_execution_tolerated: bool
    result_deduplication_required: bool
    quorum_required_for_new_ownership: bool
    result_fencing_required: bool
    resource_fencing_required: bool
    inter_node_transfer_supported: bool
    checkpoint_required_for_transfer: bool
    safe_restart_required_for_transfer: bool


def resolve_task_policy(
    security_class: TaskSecurityClass,
    transferability: TaskTransferability,
) -> TaskPolicyRequirements:
    """Return the static policy for two domain enum members.

    Raise TypeError for invalid inputs because resolution constructs a policy
    from valid domain values. Phase 1's eligibility predicate answers a boolean
    question and returns False for invalid inputs. Deserialize at the caller
    boundary.
    """
    if type(security_class) is not TaskSecurityClass:
        raise TypeError("security_class must be a TaskSecurityClass member")
    if type(transferability) is not TaskTransferability:
        raise TypeError("transferability must be a TaskTransferability member")

    is_critical = security_class is TaskSecurityClass.CRITICAL
    return TaskPolicyRequirements(
        duplicate_execution_tolerated=not is_critical,
        result_deduplication_required=True,
        quorum_required_for_new_ownership=is_critical,
        result_fencing_required=is_critical,
        resource_fencing_required=is_critical,
        inter_node_transfer_supported=(
            transferability is not TaskTransferability.NON_TRANSFERABLE
        ),
        checkpoint_required_for_transfer=transferability is TaskTransferability.CHECKPOINT,
        safe_restart_required_for_transfer=(
            is_critical and transferability is TaskTransferability.RESTART
        ),
    )
