import builtins
import io
import itertools
import json
import socket
import sqlite3
import time
from dataclasses import FrozenInstanceError, asdict
from enum import StrEnum

import pytest

from edge_middleware.models.task_policy import (
    TaskPolicyRequirements,
    TaskSecurityClass,
    TaskTransferability,
    resolve_task_policy,
)


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    [
        (TaskSecurityClass, {"ROUTINE": "routine", "CRITICAL": "critical"}),
        (
            TaskTransferability,
            {
                "RESTART": "restart",
                "CHECKPOINT": "checkpoint",
                "NON_TRANSFERABLE": "non_transferable",
            },
        ),
    ],
)
def test_enum_values_and_json_serialization(enum_type, expected):
    members = {name: member.value for name, member in enum_type.__members__.items()}
    assert members == expected
    values = json.loads(json.dumps(list(enum_type)))
    assert values == list(expected.values())
    assert all(enum_type(value) is member for value, member in zip(values, enum_type))


POLICY_FIELDS = (
    "duplicate_execution_tolerated",
    "result_deduplication_required",
    "quorum_required_for_new_ownership",
    "result_fencing_required",
    "resource_fencing_required",
    "inter_node_transfer_supported",
    "checkpoint_required_for_transfer",
    "safe_restart_required_for_transfer",
)


@pytest.mark.parametrize(
    ("security_class", "transferability", "expected"),
    [
        (
            TaskSecurityClass.ROUTINE,
            TaskTransferability.RESTART,
            (True, True, False, False, False, True, False, False),
        ),
        (
            TaskSecurityClass.ROUTINE,
            TaskTransferability.CHECKPOINT,
            (True, True, False, False, False, True, True, False),
        ),
        (
            TaskSecurityClass.ROUTINE,
            TaskTransferability.NON_TRANSFERABLE,
            (True, True, False, False, False, False, False, False),
        ),
        (
            TaskSecurityClass.CRITICAL,
            TaskTransferability.RESTART,
            (False, True, True, True, True, True, False, True),
        ),
        (
            TaskSecurityClass.CRITICAL,
            TaskTransferability.CHECKPOINT,
            (False, True, True, True, True, True, True, False),
        ),
        (
            TaskSecurityClass.CRITICAL,
            TaskTransferability.NON_TRANSFERABLE,
            (False, True, True, True, True, False, False, False),
        ),
    ],
)
def test_resolves_every_policy_combination(security_class, transferability, expected):
    policy = resolve_task_policy(security_class, transferability)

    assert isinstance(policy, TaskPolicyRequirements)
    assert asdict(policy) == dict(zip(POLICY_FIELDS, expected, strict=True))


class OtherEnum(StrEnum):
    ROUTINE = "routine"
    RESTART = "restart"


@pytest.mark.parametrize(
    "invalid", ["routine", None, TaskTransferability.RESTART, OtherEnum.ROUTINE]
)
def test_rejects_invalid_security_class(invalid):
    with pytest.raises(TypeError, match="security_class"):
        resolve_task_policy(invalid, TaskTransferability.RESTART)


@pytest.mark.parametrize(
    "invalid", ["restart", None, TaskSecurityClass.ROUTINE, OtherEnum.RESTART]
)
def test_rejects_invalid_transferability(invalid):
    with pytest.raises(TypeError, match="transferability"):
        resolve_task_policy(TaskSecurityClass.ROUTINE, invalid)


def test_policy_is_immutable_and_slotted():
    policy = resolve_task_policy(TaskSecurityClass.CRITICAL, TaskTransferability.RESTART)

    with pytest.raises(FrozenInstanceError):
        policy.result_deduplication_required = False
    assert not hasattr(policy, "__dict__")


def test_resolution_is_deterministic_without_external_access(monkeypatch):
    inputs = tuple(itertools.product(TaskSecurityClass, TaskTransferability))

    def forbidden(*args, **kwargs):
        pytest.fail("Policy resolution must not perform I/O or read the clock")

    with monkeypatch.context() as patch:
        for module, name in (
            (builtins, "open"),
            (io, "open"),
            (socket, "socket"),
            (socket, "create_connection"),
            (sqlite3, "connect"),
            (time, "time"),
            (time, "monotonic"),
        ):
            patch.setattr(module, name, forbidden)

        first = tuple(resolve_task_policy(*pair) for pair in inputs)
        second = tuple(resolve_task_policy(*pair) for pair in reversed(inputs))
        assert first == second[::-1]
