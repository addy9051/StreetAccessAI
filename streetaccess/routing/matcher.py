"""Spatial matching of community reports to pedestrian segments.

Enforces critical safety requirement:
- Never silently snap an ambiguous report to one of multiple nearby sidewalks or parallel roads.
- Returns CONFIDENT, AMBIGUOUS, or UNMATCHED with explicit reasons.
- Preserves reported GPS accuracy.
"""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from streetaccess.config import CONFIG
from streetaccess.routing.graph import (
    PedestrianSegment,
    SyntheticPedestrianGraph,
    point_to_segment_distance_meters,
)
from streetaccess.verification.models import GeoPoint


class MatchConfidence(str, Enum):
    """Categorical spatial association outcome."""
    CONFIDENT = "confident"      # Unambiguously matches a single candidate segment
    AMBIGUOUS = "ambiguous"      # Multiple nearby segments within ambiguity threshold
    UNMATCHED = "unmatched"      # No candidate segment within tolerance


class SpatialMatchResult(BaseModel):
    """Result of attempting to associate a report's GPS coordinate to graph segments."""
    confidence: MatchConfidence
    matched_segment_id: Optional[str] = None
    candidate_segment_ids: List[str] = Field(default_factory=list)
    shortest_distance_meters: Optional[float] = None
    reason: str


class SpatialMatcher:
    """Matches GPS coordinates to pedestrian graph segments with ambiguity awareness."""

    def __init__(self, graph: SyntheticPedestrianGraph):
        self.graph = graph

    def match_location(self, location: GeoPoint) -> SpatialMatchResult:
        """Evaluate spatial proximity of a GeoPoint to all graph segments.
        
        Uses provisional thresholds:
        - Candidate window = CONFIG.SPATIAL_MATCH_DISTANCE_THRESHOLD_METERS + location.gps_accuracy_meters
        - Ambiguity delta = CONFIG.SPATIAL_AMBIGUITY_DELTA_THRESHOLD_METERS
        """
        # Search radius accounts for device GPS accuracy
        effective_tolerance = (
            CONFIG.SPATIAL_MATCH_DISTANCE_THRESHOLD_METERS + location.gps_accuracy_meters
        )

        candidates: List[Tuple[str, float]] = []

        for seg_id, seg in self.graph.segments.items():
            from_node = self.graph.nodes[seg.from_node_id]
            to_node = self.graph.nodes[seg.to_node_id]

            dist = point_to_segment_distance_meters(
                plat=location.latitude,
                plon=location.longitude,
                lat1=from_node.latitude,
                lon1=from_node.longitude,
                lat2=to_node.latitude,
                lon2=to_node.longitude,
            )

            if dist <= effective_tolerance:
                candidates.append((seg_id, dist))

        # Sort by distance ascending
        candidates.sort(key=lambda x: x[1])

        if not candidates:
            return SpatialMatchResult(
                confidence=MatchConfidence.UNMATCHED,
                matched_segment_id=None,
                candidate_segment_ids=[],
                shortest_distance_meters=None,
                reason=(
                    f"No pedestrian segment found within {effective_tolerance:.1f}m tolerance "
                    f"(provisional threshold: {CONFIG.SPATIAL_MATCH_DISTANCE_THRESHOLD_METERS}m + "
                    f"reported GPS accuracy: {location.gps_accuracy_meters:.1f}m)."
                ),
            )

        # If exactly one candidate
        if len(candidates) == 1:
            best_seg, best_dist = candidates[0]
            return SpatialMatchResult(
                confidence=MatchConfidence.CONFIDENT,
                matched_segment_id=best_seg,
                candidate_segment_ids=[best_seg],
                shortest_distance_meters=round(best_dist, 2),
                reason=f"Single segment '{best_seg}' matched within {best_dist:.1f}m.",
            )

        # If multiple candidates, check ambiguity delta
        best_seg, best_dist = candidates[0]
        second_seg, second_dist = candidates[1]
        delta = second_dist - best_dist

        candidate_ids = [c[0] for c in candidates]

        if delta < CONFIG.SPATIAL_AMBIGUITY_DELTA_THRESHOLD_METERS:
            # Too close to call: parallel sidewalks or adjacent crosswalks
            return SpatialMatchResult(
                confidence=MatchConfidence.AMBIGUOUS,
                matched_segment_id=None,  # Refuse to silently assign
                candidate_segment_ids=candidate_ids,
                shortest_distance_meters=round(best_dist, 2),
                reason=(
                    f"Ambiguous spatial match: nearest candidate '{best_seg}' ({best_dist:.1f}m) "
                    f"and '{second_seg}' ({second_dist:.1f}m) differ by only {delta:.1f}m, which is "
                    f"below the {CONFIG.SPATIAL_AMBIGUITY_DELTA_THRESHOLD_METERS}m ambiguity threshold. "
                    "Refusing to silently snap to one sidewalk."
                ),
            )

        # Nearest candidate is distinct enough to be confident
        return SpatialMatchResult(
            confidence=MatchConfidence.CONFIDENT,
            matched_segment_id=best_seg,
            candidate_segment_ids=candidate_ids,
            shortest_distance_meters=round(best_dist, 2),
            reason=(
                f"Confident match to '{best_seg}' at {best_dist:.1f}m; next closest candidate "
                f"is {delta:.1f}m further away."
            ),
        )

