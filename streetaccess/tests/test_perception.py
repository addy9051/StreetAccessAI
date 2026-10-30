"""Tests for perception models, server-side validation, and fixture adapter."""

import pytest
from pydantic import ValidationError
from streetaccess.perception.fixture_adapter import FixturePerceptionAdapter
from streetaccess.perception.models import (
    CoarsePassability,
    FrameObservation,
    NormalizedBoundingBox,
    ObstacleCategory,
    PerceptionBatchRequest,
)


def test_normalized_bounding_box_valid():
    box = NormalizedBoundingBox(ymin=0.1, xmin=0.2, ymax=0.8, xmax=0.9)
    assert box.ymin == 0.1
    assert box.xmax == 0.9


def test_bounding_box_invalid_coordinate_order():
    # ymin > ymax must be rejected
    with pytest.raises(ValidationError) as exc:
        NormalizedBoundingBox(ymin=0.8, xmin=0.2, ymax=0.1, xmax=0.9)
    assert "ymin" in str(exc.value)

    # xmin > xmax must be rejected
    with pytest.raises(ValidationError) as exc:
        NormalizedBoundingBox(ymin=0.1, xmin=0.9, ymax=0.8, xmax=0.2)
    assert "xmin" in str(exc.value)


def test_bounding_box_out_of_bounds():
    # Value > 1.0
    with pytest.raises(ValidationError):
        NormalizedBoundingBox(ymin=-0.1, xmin=0.0, ymax=0.5, xmax=0.5)

    with pytest.raises(ValidationError):
        NormalizedBoundingBox(ymin=0.0, xmin=0.0, ymax=1.1, xmax=0.5)


def test_observation_timing_reference_validation():
    # Neither frame_index nor timestamp_ms provided
    with pytest.raises(ValidationError) as exc:
        FrameObservation(
            category=ObstacleCategory.CONSTRUCTION,
            passability=CoarsePassability.BLOCKED,
            visual_evidence_text="Barricade",
        )
    assert "at least one of frame_index or timestamp_ms" in str(exc.value)


def test_fixture_adapter_deterministic_output():
    adapter = FixturePerceptionAdapter()
    assert adapter.is_mock is True
    assert adapter.name == "deterministic_fixture_adapter_v1"

    req = PerceptionBatchRequest(input_identifier="fixture_blocked_construction")
    output = adapter.analyze(req)
    
    assert output.is_mock is True
    assert len(output.observations) == 1
    obs = output.observations[0]
    assert obs.is_mock is True
    assert obs.perception_source == "fixture_mock"
    assert obs.category == ObstacleCategory.CONSTRUCTION
    assert obs.passability == CoarsePassability.BLOCKED
    assert obs.bounding_box is not None
    assert obs.bounding_box.ymin == 0.25


def test_fixture_adapter_missing_and_empty_inputs():
    adapter = FixturePerceptionAdapter()

    # Empty string input
    out_empty = adapter.analyze(PerceptionBatchRequest(input_identifier="  "))
    assert out_empty.is_mock is True
    assert len(out_empty.observations) == 0
    assert out_empty.metadata.get("status") == "error"

    # Unknown fixture
    out_unknown = adapter.analyze(PerceptionBatchRequest(input_identifier="non_existent_fixture"))
    assert out_unknown.is_mock is True
    assert len(out_unknown.observations) == 0
    assert out_unknown.metadata.get("status") == "not_found"

