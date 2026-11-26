from dataclasses import FrozenInstanceError, replace

import pytest

from edge_middleware.models.ownership import (
    CriticalAuthorizationRef,
    CriticalOwnershipEvidence,
    CriticalOwnershipScope,
    QuorumDecisionRef,
    RoutineClaimRef,
    RoutineOwnershipClaim,
)


@pytest.fixture
def evidence():
    return CriticalOwnershipEvidence(
        authorization_id="auth-1",
        task_id="task-1",
        owner_node_id="node-a",
        membership_configuration_id="members-3",
        fencing_token=10,
        scope=CriticalOwnershipScope.GRANT,
        quorum_decision_ref=QuorumDecisionRef("decision-1"),
    )


def test_partitioned_nodes_can_report_separate_claims_for_the_same_task():
    left = RoutineOwnershipClaim("local-1", "task-1", "node-a", execution_id="attempt-a")
    right = RoutineOwnershipClaim("local-1", "task-1", "node-b", execution_id="attempt-b")

    assert left.task_id == right.task_id
    assert left != right
    assert RoutineClaimRef("task-1", "node-a", "local-1") != RoutineClaimRef(
        "task-1", "node-b", "local-1"
    )
    assert left.predecessor_claim is None


def test_claim_can_reference_another_node_using_the_same_local_claim_id():
    previous = RoutineClaimRef("task-1", "node-a", "local-1")
    claim = RoutineOwnershipClaim("local-1", "task-1", "node-b", predecessor_claim=previous)

    assert claim.predecessor_claim == previous
    assert claim.execution_id is None
    with pytest.raises(FrozenInstanceError):
        claim.owner_node_id = "node-a"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("claim_id", " ", ValueError),
        ("task_id", None, TypeError),
        ("owner_node_id", "", ValueError),
        ("execution_id", 1, TypeError),
        ("execution_id", " \t", ValueError),
        ("predecessor_claim", "local-0", TypeError),
        ("predecessor_claim", RoutineClaimRef("other", "node-a", "local-0"), ValueError),
        ("predecessor_claim", RoutineClaimRef("task-1", "node-a", "local-1"), ValueError),
    ],
)
def test_routine_claim_validates_identifiers_and_predecessor(field, value, error):
    claim = RoutineOwnershipClaim("local-1", "task-1", "node-a")

    with pytest.raises(error, match=field):
        replace(claim, **{field: value})


def test_critical_evidence_preserves_scope_and_expected_quorum_context(evidence):
    assert evidence.authorization_id == "auth-1"
    assert evidence.task_id == "task-1"
    assert evidence.owner_node_id == "node-a"
    assert evidence.membership_configuration_id == "members-3"
    assert evidence.fencing_token == 10
    assert evidence.scope is CriticalOwnershipScope.GRANT
    assert evidence.quorum_decision_ref == QuorumDecisionRef("decision-1")
    assert evidence.predecessor_authorization is None
    assert replace(evidence) == evidence
    with pytest.raises(FrozenInstanceError):
        evidence.fencing_token = 20
    with pytest.raises(FrozenInstanceError):
        evidence.quorum_decision_ref.decision_id = "decision-2"


def test_transfer_record_keeps_predecessor_reference_without_comparing_tokens(evidence):
    previous = CriticalAuthorizationRef(evidence.task_id, evidence.authorization_id)
    transfer = replace(
        evidence,
        authorization_id="auth-2",
        owner_node_id="node-b",
        scope=CriticalOwnershipScope.TRANSFER,
        quorum_decision_ref=QuorumDecisionRef("decision-2"),
        predecessor_authorization=previous,
        fencing_token=1,
    )

    assert transfer.predecessor_authorization == previous
    assert transfer.fencing_token == 1
    assert evidence.fencing_token == 10


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("authorization_id", b"auth-1", TypeError),
        ("task_id", "", ValueError),
        ("owner_node_id", " \t", ValueError),
        ("membership_configuration_id", None, TypeError),
        ("membership_configuration_id", "", ValueError),
        ("fencing_token", True, TypeError),
        ("fencing_token", 1.5, TypeError),
        ("fencing_token", 0, ValueError),
        ("fencing_token", -1, ValueError),
        ("scope", "grant_ownership", TypeError),
        ("quorum_decision_ref", "decision-1", TypeError),
        ("quorum_decision_ref", None, TypeError),
        ("quorum_decision_ref", True, TypeError),
        ("predecessor_authorization", CriticalAuthorizationRef("task-1", "auth-0"), ValueError),
    ],
)
def test_critical_evidence_rejects_invalid_shape(evidence, field, value, error):
    with pytest.raises(error, match=field):
        replace(evidence, **{field: value})


@pytest.mark.parametrize(
    ("predecessor", "error"),
    [
        (None, ValueError),
        (RoutineClaimRef("task-1", "node-a", "auth-0"), TypeError),
        (CriticalAuthorizationRef("another-task", "auth-0"), ValueError),
        (CriticalAuthorizationRef("task-1", "auth-1"), ValueError),
    ],
)
def test_transfer_requires_a_distinct_critical_reference_for_the_same_task(
    evidence, predecessor, error
):
    with pytest.raises(error, match="predecessor_authorization"):
        replace(
            evidence, scope=CriticalOwnershipScope.TRANSFER, predecessor_authorization=predecessor
        )


@pytest.mark.parametrize("decision_id", ["", " \t"])
def test_quorum_decision_reference_requires_a_nonblank_id(decision_id):
    with pytest.raises(ValueError, match="decision_id"):
        QuorumDecisionRef(decision_id)
