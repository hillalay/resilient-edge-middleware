import builtins
import itertools
import json
import socket
import sqlite3
import time

import pytest

from edge_middleware.models.task_lifecycle import (
    TaskStatus,
    TransitionIntent,
    is_valid_transition,
)


# Each cell identifies the only eligible intent, or None for a forbidden edge.
# Rows and columns: CREATED, ASSIGNED, RUNNING, COMPLETED, CANCELLED.
N = TransitionIntent.NORMAL
C = TransitionIntent.CANCEL
R = TransitionIntent.REASSIGN
EXPECTED = (
    (None, N, None, None, C),
    (None, R, N, None, C),
    (None, R, None, N, C),
    (None, None, None, None, None),
    (None, None, None, None, None),
)
STATES = tuple(TaskStatus)


def test_status_values_and_string_serialization():
    expected = {
        "CREATED": "created",
        "ASSIGNED": "assigned",
        "RUNNING": "running",
        "COMPLETED": "completed",
        "CANCELLED": "cancelled",
    }
    assert {
        name: status.value for name, status in TaskStatus.__members__.items()
    } == expected
    assert all(isinstance(status, str) for status in TaskStatus)
    assert json.loads(json.dumps(list(TaskStatus))) == list(expected.values())
    assert [TaskStatus(value) for value in expected.values()] == list(TaskStatus)


@pytest.mark.parametrize("intent", TransitionIntent)
@pytest.mark.parametrize("current", TaskStatus)
@pytest.mark.parametrize("target", TaskStatus)
def test_every_state_pair_and_intent(current, target, intent):
    expected = EXPECTED[STATES.index(current)][STATES.index(target)]
    assert is_valid_transition(current, target, intent=intent) is (intent is expected)


@pytest.mark.parametrize("current", TaskStatus)
@pytest.mark.parametrize("target", TaskStatus)
def test_default_intent_only_allows_normal_progress(current, target):
    expected = EXPECTED[STATES.index(current)][STATES.index(target)]
    assert is_valid_transition(current, target) is (expected is N)


@pytest.mark.parametrize("status", TaskStatus)
def test_repeated_report_is_not_a_new_transition(status):
    assert not is_valid_transition(status, status)
    assert not is_valid_transition(status, status, intent=C)
    assert is_valid_transition(status, status, intent=R) is (
        status is TaskStatus.ASSIGNED
    )


@pytest.mark.parametrize("terminal", [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
def test_terminal_states_have_no_outgoing_transitions(terminal):
    assert not any(
        is_valid_transition(terminal, target, intent=intent)
        for target in TaskStatus
        for intent in TransitionIntent
    )


@pytest.mark.parametrize(
    ("current", "target", "intent"),
    [
        ("created", TaskStatus.ASSIGNED, N),
        (TaskStatus.CREATED, "assigned", N),
        (TaskStatus.CREATED, TaskStatus.ASSIGNED, "normal"),
        (None, TaskStatus.ASSIGNED, N),
        (TaskStatus.CREATED, [], N),
        (TaskStatus.CREATED, TaskStatus.ASSIGNED, None),
    ],
)
def test_non_enum_inputs_are_rejected(current, target, intent):
    assert not is_valid_transition(current, target, intent=intent)


def test_validation_is_deterministic_and_has_no_external_side_effects(monkeypatch):
    inputs = tuple(itertools.product(TaskStatus, TaskStatus, TransitionIntent))
    snapshot = tuple((a.value, b.value, c.value) for a, b, c in inputs)
    baseline = tuple(is_valid_transition(a, b, intent=c) for a, b, c in inputs)

    def forbidden(*args, **kwargs):
        pytest.fail("Lifecycle validation must not perform I/O or read the clock")

    with monkeypatch.context() as patch:
        for module, name in (
            (builtins, "open"),
            (socket, "socket"),
            (socket, "create_connection"),
            (sqlite3, "connect"),
            (time, "time"),
            (time, "monotonic"),
        ):
            patch.setattr(module, name, forbidden)
        for _ in range(3):
            assert tuple(
                is_valid_transition(a, b, intent=c) for a, b, c in inputs
            ) == baseline

    assert tuple((a.value, b.value, c.value) for a, b, c in inputs) == snapshot
