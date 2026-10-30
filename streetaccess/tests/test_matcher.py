"""Tests for spatial matcher and ambiguity handling."""

import pytest
from streetaccess.routing.graph import SyntheticPedestrianGraph
from streetaccess.routing.matcher import MatchConfidence, SpatialMatcher
from streetaccess.verification.models import GeoPoint


@pytest.fixture
def graph():
    return SyntheticPedestrianGraph.create_default_network()


def test_confident_spatial_match(graph):
    matcher = SpatialMatcher(graph)
    # Coordinate placed right on East Sidewalk (SEG_EAST_1)
    loc = GeoPoint(
        latitude=37.7755,
        longitude=-122.41925,
        gps_accuracy_meters=3.0,
    )
    result = matcher.match_location(loc)
    assert result.confidence == MatchConfidence.CONFIDENT
    assert result.matched_segment_id == "SEG_EAST_1"
    assert "SEG_EAST_1" in result.candidate_segment_ids


def test_ambiguous_spatial_match_between_parallel_sidewalks(graph):
    matcher = SpatialMatcher(graph)
    # Point located at latitude 37.7755 midway between East and West sidewalks (e.g. middle of street, away from crosswalk)
    # Distance to SEG_EAST_1 and SEG_WEST_1 is virtually identical (~6.8m)
    loc = GeoPoint(
        latitude=37.7755,
        longitude=-122.419400,
        gps_accuracy_meters=5.0,
    )
    result = matcher.match_location(loc)
    
    # Must refuse to silently snap!
    assert result.confidence == MatchConfidence.AMBIGUOUS
    assert result.matched_segment_id is None
    assert len(result.candidate_segment_ids) >= 2
    assert "Refusing to silently snap" in result.reason


def test_unmatched_distant_location(graph):
    matcher = SpatialMatcher(graph)
    # Far away in downtown Oakland
    loc = GeoPoint(
        latitude=37.8044,
        longitude=-122.2712,
        gps_accuracy_meters=5.0,
    )
    result = matcher.match_location(loc)
    assert result.confidence == MatchConfidence.UNMATCHED
    assert result.matched_segment_id is None
    assert len(result.candidate_segment_ids) == 0
