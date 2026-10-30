"""Perception data models and server-side validation.

Models represent provider-neutral frame-level visual observations.
Bounding boxes, categories, frame indices, and timestamps are validated server-side.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CoarsePassability(str, Enum):
    """Pedestrian passability assessment.
    
    IMPORTANT: We do not estimate real-world metric widths or uncalibrated severity.
    Only categorical coarse passability is permitted.
    """
    CLEAR = "clear"
    NARROWED = "narrowed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ObstacleCategory(str, Enum):
    """Controlled obstacle/condition categories."""
    CONSTRUCTION = "construction"
    SURFACE_DAMAGE = "surface_damage"
    TEMPORARY_OBSTRUCTION = "temporary_obstruction"
    STAIRS_WITHOUT_RAMP = "stairs_without_ramp"
    NARROW_PATHWAY = "narrow_pathway"
    VEGETATION_OVERGROWTH = "vegetation_overgrowth"
    PARKED_VEHICLE = "parked_vehicle"
    DEBRIS_OR_GARBAGE = "debris_or_garbage"
    CLEAR_SIDEWALK = "clear_sidewalk"
    OTHER = "other"


class NormalizedBoundingBox(BaseModel):
    """Normalized bounding box coordinates in [0.0, 1.0].
    
    Order is ymin, xmin, ymax, xmax.
    """
    ymin: float = Field(..., ge=0.0, le=1.0, description="Top edge normalized coordinate [0, 1]")
    xmin: float = Field(..., ge=0.0, le=1.0, description="Left edge normalized coordinate [0, 1]")
    ymax: float = Field(..., ge=0.0, le=1.0, description="Bottom edge normalized coordinate [0, 1]")
    xmax: float = Field(..., ge=0.0, le=1.0, description="Right edge normalized coordinate [0, 1]")

    @model_validator(mode="after")
    def validate_coordinate_order(self) -> "NormalizedBoundingBox":
        if self.ymin > self.ymax:
            raise ValueError(f"Invalid bounding box: ymin ({self.ymin}) cannot be greater than ymax ({self.ymax})")
        if self.xmin > self.xmax:
            raise ValueError(f"Invalid bounding box: xmin ({self.xmin}) cannot be greater than xmax ({self.xmax})")
        return self


class FrameObservation(BaseModel):
    """Single frame-level pedestrian observation.
    
    Provider-neutral representation of what was visually observed in a frame.
    Must clearly mark whether it originates from a mock fixture.
    """
    frame_index: Optional[int] = Field(None, ge=0, description="Non-negative frame index if extracted from video")
    timestamp_ms: Optional[int] = Field(None, ge=0, description="Non-negative timestamp in milliseconds")
    category: ObstacleCategory = Field(..., description="Standardized obstacle or condition category")
    passability: CoarsePassability = Field(..., description="Coarse passability status")
    bounding_box: Optional[NormalizedBoundingBox] = Field(None, description="Normalized bounding box if obstacle is localized")
    visual_evidence_text: str = Field(..., min_length=1, max_length=1000, description="Descriptive text of observed visual evidence")
    
    # Provider metadata tracking
    is_mock: bool = Field(True, description="Always True for fixture/mock perception output")
    perception_source: str = Field("fixture_mock", description="Identifier of the perception provider")

    @model_validator(mode="after")
    def validate_timing_reference(self) -> "FrameObservation":
        if self.frame_index is None and self.timestamp_ms is None:
            raise ValueError("Observation must provide at least one of frame_index or timestamp_ms")
        return self


class PerceptionBatchRequest(BaseModel):
    """Input request for perception adapter analysis."""
    input_identifier: str = Field(..., description="Fixture key, video clip ID, or image sequence ID")
    frame_count: Optional[int] = Field(None, ge=1, description="Number of frames in the sequence")


class PerceptionOutput(BaseModel):
    """Output envelope returned by a PerceptionAdapter."""
    adapter_name: str
    is_mock: bool
    observations: list[FrameObservation] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

