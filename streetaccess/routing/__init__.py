"""Routing and spatial matching package for StreetAccess."""

from streetaccess.routing.comparator import (
    MANDATORY_DISCLAIMER,
    RouteComparator,
    RouteComparisonResponse,
    RouteCoverageBreakdown,
    RouteTradeoffSummary,
    VerifiedBarrierSummary,
)
from streetaccess.routing.graph import (
    PedestrianNode,
    PedestrianSegment,
    SurveyStatus,
    SyntheticPedestrianGraph,
    haversine_distance_meters,
    point_to_segment_distance_meters,
)
from streetaccess.routing.matcher import (
    MatchConfidence,
    SpatialMatchResult,
    SpatialMatcher,
)

__all__ = [
    "MANDATORY_DISCLAIMER",
    "RouteComparator",
    "RouteComparisonResponse",
    "RouteCoverageBreakdown",
    "RouteTradeoffSummary",
    "VerifiedBarrierSummary",
    "PedestrianNode",
    "PedestrianSegment",
    "SurveyStatus",
    "SyntheticPedestrianGraph",
    "haversine_distance_meters",
    "point_to_segment_distance_meters",
    "MatchConfidence",
    "SpatialMatchResult",
    "SpatialMatcher",
]

