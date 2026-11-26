from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from edge_middleware.models.lease import Lease
from edge_middleware.models.ownership import CriticalAuthorizationRef, RoutineClaimRef


ISSUED_AT = datetime(2026, 11, 26, 9, tzinfo=UTC)


@pytest.fixture
def lease():
    reference = RoutineClaimRef("task-1", "worker-a", "claim-1")
    return Lease("lease-1", reference, "node-a", ISSUED_AT, 1500)


@pytest.mark.parametrize(
    "ownership_ref",
    [
        RoutineClaimRef("task-1", "worker-a", "claim-1"),
        CriticalAuthorizationRef("task-1", "auth-1"),
    ],
)
def test_lease_preserves_duration_in_milliseconds_and_grantor_time(lease, ownership_ref):
    local_time = ISSUED_AT.astimezone(timezone(timedelta(hours=3)))
    record = replace(lease, ownership_ref=ownership_ref, issued_at=local_time)

    assert record.ownership_ref is ownership_ref
    assert record.duration_ms == 1500
    assert record.issuer_node_id == "node-a"
    assert record.issued_at == ISSUED_AT
    assert record.issued_at.tzinfo is UTC
    assert record.predecessor_lease_id is None
    assert replace(record) == record
    with pytest.raises(FrozenInstanceError):
        record.duration_ms = 900


def test_renewal_record_references_the_previous_lease(lease):
    next_record = replace(
        lease,
        lease_id="lease-2",
        predecessor_lease_id=lease.lease_id,
        issued_at=lease.issued_at - timedelta(seconds=1),
    )

    assert next_record.ownership_ref == lease.ownership_ref
    assert next_record.predecessor_lease_id == "lease-1"
    assert next_record.issued_at < lease.issued_at


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("lease_id", "", ValueError),
        ("issuer_node_id", " \t", ValueError),
        ("issuer_node_id", 10, TypeError),
        ("ownership_ref", "claim-1", TypeError),
        ("duration_ms", True, TypeError),
        ("duration_ms", 1.5, TypeError),
        ("duration_ms", 0, ValueError),
        ("duration_ms", -1, ValueError),
        ("issued_at", ISSUED_AT.replace(tzinfo=None), ValueError),
        ("issued_at", "2026-11-26T09:00:00Z", TypeError),
        ("predecessor_lease_id", " ", ValueError),
        ("predecessor_lease_id", "lease-1", ValueError),
    ],
)
def test_lease_rejects_invalid_fields(lease, field, value, error):
    with pytest.raises(error, match=field):
        replace(lease, **{field: value})
