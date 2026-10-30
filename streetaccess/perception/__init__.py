"""Perception package: provider-neutral interfaces and deterministic mock adapter."""

from streetaccess.perception.adapter import PerceptionAdapter
from streetaccess.perception.fixture_adapter import FixturePerceptionAdapter
from streetaccess.perception.models import (
    CoarsePassability,
    FrameObservation,
    NormalizedBoundingBox,
    ObstacleCategory,
    PerceptionBatchRequest,
    PerceptionOutput,
)

__all__ = [
    "CoarsePassability",
    "ObstacleCategory",
    "NormalizedBoundingBox",
    "FrameObservation",
    "PerceptionBatchRequest",
    "PerceptionOutput",
    "PerceptionAdapter",
    "FixturePerceptionAdapter",
]

