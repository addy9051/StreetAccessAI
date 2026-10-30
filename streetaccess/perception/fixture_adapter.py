"""Deterministic fixture perception adapter.

Provides stable, reproducible observations for test and development scenarios.
All outputs are explicitly marked as mock data.
"""

from streetaccess.perception.adapter import PerceptionAdapter
from streetaccess.perception.models import (
    CoarsePassability,
    FrameObservation,
    NormalizedBoundingBox,
    ObstacleCategory,
    PerceptionBatchRequest,
    PerceptionOutput,
)


class FixturePerceptionAdapter(PerceptionAdapter):
    """Deterministic mock adapter backed by predefined test fixtures.
    
    No real-world perception is performed; this allows predictable testing
    of verification, storage, and routing pipelines without external model calls.
    """

    def __init__(self) -> None:
        self._fixtures: dict[str, list[FrameObservation]] = {
            "fixture_clear_sidewalk": [
                FrameObservation(
                    frame_index=0,
                    timestamp_ms=0,
                    category=ObstacleCategory.CLEAR_SIDEWALK,
                    passability=CoarsePassability.CLEAR,
                    bounding_box=None,
                    visual_evidence_text="Even concrete sidewalk with no visible obstructions in pathway.",
                    is_mock=True,
                    perception_source="fixture_mock",
                )
            ],
            "fixture_blocked_construction": [
                FrameObservation(
                    frame_index=15,
                    timestamp_ms=500,
                    category=ObstacleCategory.CONSTRUCTION,
                    passability=CoarsePassability.BLOCKED,
                    bounding_box=NormalizedBoundingBox(
                        ymin=0.25,
                        xmin=0.10,
                        ymax=0.85,
                        xmax=0.90,
                    ),
                    visual_evidence_text="Construction barricades and open ditch spanning entire walking width.",
                    is_mock=True,
                    perception_source="fixture_mock",
                )
            ],
            "fixture_narrowed_vegetation": [
                FrameObservation(
                    frame_index=30,
                    timestamp_ms=1000,
                    category=ObstacleCategory.VEGETATION_OVERGROWTH,
                    passability=CoarsePassability.NARROWED,
                    bounding_box=NormalizedBoundingBox(
                        ymin=0.10,
                        xmin=0.55,
                        ymax=0.90,
                        xmax=0.98,
                    ),
                    visual_evidence_text="Overgrown hedge encroaching roughly halfway into pedestrian path.",
                    is_mock=True,
                    perception_source="fixture_mock",
                )
            ],
            "fixture_broken_pavement": [
                FrameObservation(
                    frame_index=45,
                    timestamp_ms=1500,
                    category=ObstacleCategory.SURFACE_DAMAGE,
                    passability=CoarsePassability.NARROWED,
                    bounding_box=NormalizedBoundingBox(
                        ymin=0.60,
                        xmin=0.20,
                        ymax=0.95,
                        xmax=0.80,
                    ),
                    visual_evidence_text="Deep potholes and missing sidewalk slabs leaving narrow passable edge.",
                    is_mock=True,
                    perception_source="fixture_mock",
                )
            ],
            "fixture_empty": [],
        }

    @property
    def name(self) -> str:
        return "deterministic_fixture_adapter_v1"

    @property
    def is_mock(self) -> bool:
        return True

    def analyze(self, request: PerceptionBatchRequest) -> PerceptionOutput:
        """Return stable fixture observations.
        
        If input_identifier is unknown or empty, returns empty observation list
        with diagnostic metadata rather than crashing.
        """
        identifier = request.input_identifier.strip()
        
        if not identifier:
            return PerceptionOutput(
                adapter_name=self.name,
                is_mock=True,
                observations=[],
                metadata={"status": "error", "message": "Empty input identifier provided"},
            )

        observations = self._fixtures.get(identifier)
        if observations is None:
            return PerceptionOutput(
                adapter_name=self.name,
                is_mock=True,
                observations=[],
                metadata={
                    "status": "not_found",
                    "message": f"Fixture '{identifier}' not found in registered fixtures",
                    "available_fixtures": ",".join(self._fixtures.keys()),
                },
            )

        return PerceptionOutput(
            adapter_name=self.name,
            is_mock=True,
            observations=observations,
            metadata={"status": "success", "fixture_id": identifier},
        )

