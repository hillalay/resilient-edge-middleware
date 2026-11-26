from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from edge_middleware.models.input_availability import InputAvailabilityObservation
from edge_middleware.models.task_definition import InputRequirementRef


OBSERVED_AT = datetime(2026, 11, 26, 9, tzinfo=UTC)


@pytest.fixture
def observation():
    return InputAvailabilityObservation("node-a", "task-1", "events", 25, 0, OBSERVED_AT)


def test_unknown_total_and_hash_can_be_represented_with_available_bytes(observation):
    assert observation.available_verified_bytes == 25
    assert observation.expected_size_bytes is None
    assert observation.expected_content_hash is None


def test_count_may_equal_known_expected_size_including_zero(observation):
    full = replace(observation, expected_size_bytes=25)
    empty = replace(observation, expected_size_bytes=0, available_verified_bytes=0)

    assert full.available_verified_bytes == full.expected_size_bytes == 25
    assert empty.available_verified_bytes == empty.expected_size_bytes == 0


def test_different_content_versions_and_nodes_are_reported_separately(observation):
    first = replace(observation, expected_content_hash="A" * 64, expected_size_bytes=50)
    second = replace(first, expected_content_hash="B" * 64, available_verified_bytes=10)
    other_node = replace(first, node_id="node-b", available_verified_bytes=40)

    assert first.task_id == second.task_id == other_node.task_id
    assert first.input_id == second.input_id == other_node.input_id
    assert first.expected_content_hash == other_node.expected_content_hash == "a" * 64
    assert second.expected_content_hash == "b" * 64
    assert first.available_verified_bytes == 25
    assert second.available_verified_bytes == 10
    assert other_node.available_verified_bytes == 40


def test_hash_normalization_matches_the_input_definition(observation):
    digest = "AB12" * 16
    definition_ref = InputRequirementRef("events", content_hash=digest)
    report = replace(observation, expected_content_hash=digest)

    assert report.expected_content_hash == definition_ref.content_hash == digest.lower()


def test_time_normalization_is_deterministic_and_observations_are_immutable(observation):
    local_time = OBSERVED_AT.astimezone(timezone(timedelta(hours=-4)))
    normalized = replace(observation, observed_at=local_time)

    assert normalized == observation
    assert normalized.observed_at.tzinfo is UTC
    with pytest.raises(FrozenInstanceError):
        normalized.available_verified_bytes = 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("node_id", 1),
        ("task_id", None),
        ("input_id", b"events"),
        ("expected_content_hash", b"a" * 64),
        ("expected_size_bytes", True),
        ("expected_size_bytes", 50.5),
        ("available_verified_bytes", False),
        ("available_verified_bytes", None),
        ("source_revision", True),
        ("observed_at", "2026-11-26T09:00:00Z"),
    ],
)
def test_rejects_wrong_types(observation, field, value):
    with pytest.raises(TypeError, match=field):
        replace(observation, **{field: value})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("node_id", "", "node_id"),
        ("task_id", " \t", "task_id"),
        ("input_id", "", "input_id"),
        ("expected_content_hash", "a" * 63, "64 SHA-256 hex digits"),
        ("expected_content_hash", "g" * 64, "64 SHA-256 hex digits"),
        ("expected_content_hash", "sha256:" + "a" * 64, "64 SHA-256 hex digits"),
        ("expected_size_bytes", -1, "expected_size_bytes must be non-negative"),
        ("expected_size_bytes", 24, "available_verified_bytes must not exceed"),
        ("available_verified_bytes", -1, "available_verified_bytes"),
        ("source_revision", -1, "source_revision"),
        ("observed_at", OBSERVED_AT.replace(tzinfo=None), "timezone-aware"),
    ],
)
def test_rejects_invalid_values(observation, field, value, message):
    with pytest.raises(ValueError, match=message):
        replace(observation, **{field: value})


def test_rejects_wall_time_outside_representable_utc_range(observation):
    boundary = datetime.min.replace(tzinfo=timezone(timedelta(hours=1)))

    with pytest.raises(ValueError, match="outside the supported UTC range"):
        replace(observation, observed_at=boundary)
