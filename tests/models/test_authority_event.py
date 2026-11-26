import json
import time
import uuid
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from edge_middleware.models.authority_event import (
    AuthorityEvent,
    AuthorityEventType,
    CancellationConfirmation,
    CancellationRequest,
    ResultAcceptance,
)
from edge_middleware.models.execution_state import ExecutionState, ExecutionStatus
from edge_middleware.models.lease import Lease
from edge_middleware.models.ownership import (
    CriticalAuthorizationRef,
    CriticalOwnershipEvidence,
    CriticalOwnershipScope,
    QuorumDecisionRef,
    RoutineClaimRef,
    RoutineOwnershipClaim,
)
from edge_middleware.models.task_policy import TaskSecurityClass


ISSUED_AT = datetime(2026, 11, 26, 9, tzinfo=UTC)


def make_event(event_type, security_class, payload):
    return AuthorityEvent(
        event_id="event-1",
        task_id="task-1",
        security_class=security_class,
        event_type=event_type,
        issuer_node_id="reporter-a",
        issued_at=ISSUED_AT,
        payload=payload,
    )


def test_authority_event_type_values_and_json_serialization():
    expected = {
        "OWNERSHIP_GRANTED": "ownership_granted",
        "OWNERSHIP_TRANSFERRED": "ownership_transferred",
        "LEASE_RENEWED": "lease_renewed",
        "OWNERSHIP_RELEASED": "ownership_released",
        "OWNERSHIP_REVOKED": "ownership_revoked",
        "RESULT_ACCEPTED": "result_accepted",
        "CANCELLATION_CONFIRMED": "cancellation_confirmed",
    }
    actual = {name: member.value for name, member in AuthorityEventType.__members__.items()}
    assert actual == expected
    assert json.loads(json.dumps(list(AuthorityEventType))) == list(expected.values())


@pytest.fixture(params=list(TaskSecurityClass))
def ownership(request):
    security_class = request.param
    if security_class is TaskSecurityClass.ROUTINE:
        initial = RoutineOwnershipClaim("claim-1", "task-1", "worker-a")
        prior = RoutineClaimRef("task-1", "worker-a", "claim-1")
        transfer = RoutineOwnershipClaim(
            "claim-2", "task-1", "worker-b", predecessor_claim=prior
        )
        reference = RoutineClaimRef("task-1", "worker-b", "claim-2")
    else:
        initial = CriticalOwnershipEvidence(
            "auth-1", "task-1", "worker-a", "members-1", 4,
            CriticalOwnershipScope.GRANT, QuorumDecisionRef("decision-1"),
        )
        transfer = CriticalOwnershipEvidence(
            "auth-2", "task-1", "worker-b", "members-1", 5,
            CriticalOwnershipScope.TRANSFER, QuorumDecisionRef("decision-2"),
            CriticalAuthorizationRef("task-1", "auth-1"),
        )
        reference = CriticalAuthorizationRef("task-1", "auth-2")

    return security_class, {
        AuthorityEventType.OWNERSHIP_GRANTED: initial,
        AuthorityEventType.OWNERSHIP_TRANSFERRED: transfer,
        AuthorityEventType.LEASE_RENEWED: Lease(
            "lease-2", reference, "lease-grantor", ISSUED_AT, 2000, "lease-1"
        ),
        AuthorityEventType.OWNERSHIP_RELEASED: reference,
        AuthorityEventType.OWNERSHIP_REVOKED: reference,
        AuthorityEventType.RESULT_ACCEPTED: ResultAcceptance("attempt-2", "manifest-1", reference),
        AuthorityEventType.CANCELLATION_CONFIRMED: CancellationConfirmation(
            "request-1", reference
        ),
    }


@pytest.mark.parametrize("event_type", list(AuthorityEventType))
def test_each_event_accepts_its_payload_for_both_security_classes(ownership, event_type):
    security_class, payloads = ownership
    event = make_event(event_type, security_class, payloads[event_type])

    assert event.event_type is event_type
    assert event.security_class is security_class
    assert event.payload is payloads[event_type]


def test_structural_validation_uses_supplied_identity_and_time(ownership, monkeypatch):
    security_class, payloads = ownership
    expected = [make_event(kind, security_class, payload) for kind, payload in payloads.items()]

    def unexpected_call(*args, **kwargs):
        pytest.fail("Structural validation must use supplied time and identifiers")

    with monkeypatch.context() as patch:
        patch.setattr(time, "time", unexpected_call)
        patch.setattr(time, "monotonic", unexpected_call)
        patch.setattr(uuid, "uuid4", unexpected_call)
        actual = [make_event(kind, security_class, payload) for kind, payload in payloads.items()]

    assert actual == expected


@pytest.mark.parametrize("event_type", list(AuthorityEventType))
def test_rejects_ownership_context_from_another_security_class(ownership, event_type):
    security_class, payloads = ownership
    other_class, = [value for value in TaskSecurityClass if value is not security_class]

    with pytest.raises(ValueError, match="security_class"):
        make_event(event_type, other_class, payloads[event_type])


@pytest.mark.parametrize("event_type", list(AuthorityEventType))
def test_rejects_payloads_for_a_different_task(ownership, event_type):
    security_class, payloads = ownership
    event = make_event(event_type, security_class, payloads[event_type])

    with pytest.raises(ValueError, match="task_id"):
        replace(event, task_id="another-task")


@pytest.mark.parametrize(
    ("event_type", "payload_for"),
    [
        (AuthorityEventType.OWNERSHIP_GRANTED, AuthorityEventType.OWNERSHIP_RELEASED),
        (AuthorityEventType.OWNERSHIP_TRANSFERRED, AuthorityEventType.OWNERSHIP_REVOKED),
        (AuthorityEventType.LEASE_RENEWED, AuthorityEventType.OWNERSHIP_GRANTED),
        (AuthorityEventType.OWNERSHIP_RELEASED, AuthorityEventType.OWNERSHIP_TRANSFERRED),
        (AuthorityEventType.OWNERSHIP_REVOKED, AuthorityEventType.RESULT_ACCEPTED),
        (AuthorityEventType.RESULT_ACCEPTED, AuthorityEventType.CANCELLATION_CONFIRMED),
        (AuthorityEventType.CANCELLATION_CONFIRMED, AuthorityEventType.RESULT_ACCEPTED),
    ],
)
def test_each_event_rejects_an_incompatible_payload_shape(ownership, event_type, payload_for):
    security_class, payloads = ownership

    with pytest.raises(ValueError, match="payload does not match"):
        make_event(event_type, security_class, payloads[payload_for])


@pytest.mark.parametrize(
    ("event_type", "opposite_type"),
    [
        (AuthorityEventType.OWNERSHIP_GRANTED, AuthorityEventType.OWNERSHIP_TRANSFERRED),
        (AuthorityEventType.OWNERSHIP_TRANSFERRED, AuthorityEventType.OWNERSHIP_GRANTED),
    ],
)
def test_initial_grant_and_transfer_require_different_lineage(ownership, event_type, opposite_type):
    security_class, payloads = ownership

    with pytest.raises(ValueError, match="predecessor_claim|scope"):
        make_event(event_type, security_class, payloads[opposite_type])


def test_lease_renewal_event_requires_predecessor(ownership):
    security_class, payloads = ownership
    lease = replace(payloads[AuthorityEventType.LEASE_RENEWED], predecessor_lease_id=None)

    with pytest.raises(ValueError, match="predecessor_lease_id"):
        make_event(AuthorityEventType.LEASE_RENEWED, security_class, lease)


@pytest.fixture
def event():
    return make_event(
        AuthorityEventType.OWNERSHIP_GRANTED,
        TaskSecurityClass.ROUTINE,
        RoutineOwnershipClaim("claim-1", "task-1", "worker-a"),
    )


def test_event_normalizes_time_and_keeps_distinct_payloads_with_same_event_id(event):
    local_time = ISSUED_AT.astimezone(timezone(timedelta(hours=3)))
    equivalent = replace(event, issued_at=local_time)
    conflicting = replace(event, payload=replace(event.payload, owner_node_id="worker-b"))

    assert equivalent == event
    assert equivalent.issued_at.tzinfo is UTC
    assert conflicting.event_id == event.event_id
    assert conflicting != event
    with pytest.raises(FrozenInstanceError):
        event.payload = conflicting.payload


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("event_id", "", ValueError),
        ("event_id", 10, TypeError),
        ("task_id", " \t", ValueError),
        ("issuer_node_id", "", ValueError),
        ("issuer_node_id", None, TypeError),
        ("security_class", "routine", TypeError),
        ("event_type", "ownership_granted", TypeError),
        ("event_type", ExecutionStatus.RUNNING, TypeError),
        ("issued_at", ISSUED_AT.replace(tzinfo=None), ValueError),
        ("issued_at", "2026-11-26T09:00:00Z", TypeError),
        ("payload", {"claim_id": "claim-1"}, TypeError),
    ],
)
def test_event_rejects_invalid_fields(event, field, value, error):
    with pytest.raises(error, match=field):
        replace(event, **{field: value})


def test_result_acceptance_refers_to_an_attempt_without_using_execution_status():
    succeeded = ExecutionState(
        "task-1", "attempt-1", "worker-a", ExecutionStatus.SUCCEEDED, 0, ISSUED_AT
    )
    reference = RoutineClaimRef("task-1", "worker-a", "claim-1")
    acceptance = ResultAcceptance(succeeded.execution_id, "manifest-1", reference)
    reported = make_event(AuthorityEventType.RESULT_ACCEPTED, TaskSecurityClass.ROUTINE, acceptance)

    assert reported.task_id == succeeded.task_id
    assert reported.payload.execution_id == succeeded.execution_id
    assert reported.payload.output_manifest_id == "manifest-1"
    with pytest.raises(TypeError, match="payload"):
        replace(reported, payload=succeeded)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("execution_id", "", ValueError),
        ("output_manifest_id", " ", ValueError),
        ("ownership_ref", None, TypeError),
    ],
)
def test_result_acceptance_requires_attempt_output_and_ownership(field, value, error):
    reference = CriticalAuthorizationRef("task-1", "auth-1")
    acceptance = ResultAcceptance("attempt-1", "manifest-1", reference)

    with pytest.raises(error, match=field):
        replace(acceptance, **{field: value})


@pytest.mark.parametrize("security_class", list(TaskSecurityClass))
def test_cancellation_request_is_separate_from_confirmation_without_an_owner(security_class):
    local_time = ISSUED_AT.astimezone(timezone(timedelta(hours=-2)))
    request = CancellationRequest("request-1", "task-1", "requester-a", local_time)
    confirmation = CancellationConfirmation(request.request_id)
    reported = make_event(AuthorityEventType.CANCELLATION_CONFIRMED, security_class, confirmation)

    assert reported.task_id == request.task_id
    assert reported.payload.request_id == request.request_id
    assert reported.payload.ownership_ref is None
    assert request.requested_at.tzinfo is UTC
    with pytest.raises(TypeError, match="payload"):
        replace(reported, payload=request)


def test_cancellation_confirmation_requires_a_request_reference():
    with pytest.raises(ValueError, match="request_id"):
        CancellationConfirmation(" ")
