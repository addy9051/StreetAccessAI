"""Tests for route trade-off comparator, coverage calculation, and explicit UNKNOWN handling."""

from datetime import datetime, timezone
import pytest
from streetaccess.perception.models import (
    CoarsePassability,
    FrameObservation,
    ObstacleCategory,
)
from streetaccess.routing.comparator import MANDATORY_DISCLAIMER, RouteComparator
from streetaccess.routing.graph import SyntheticPedestrianGraph
from streetaccess.verification.models import CommunityReport, GeoPoint, ReportState


@pytest.fixture
def graph():
    return SyntheticPedestrianGraph.create_default_network()


def create_mock_report(
    report_id: str,
    segment_id: str,
    state: ReportState,
    passability: CoarsePassability,
    category: ObstacleCategory = ObstacleCategory.CONSTRUCTION,
    age_days: int = 0,
) -> CommunityReport:
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    created_dt = now - timedelta(days=age_days)
    created_iso = created_dt.isoformat()

    return CommunityReport(
        report_id=report_id,
        uploader_id="user_test",
        location=GeoPoint(latitude=37.775, longitude=-122.419, gps_accuracy_meters=5.0),
        state=state,
        created_at_utc=created_iso,
        updated_at_utc=created_iso,
        matched_segment_id=segment_id,
        spatial_match_status="confident",
        observations=[
            FrameObservation(
                frame_index=0,
                category=category,
                passability=passability,
                visual_evidence_text=f"Test evidence for {category.value}",
                is_mock=True,
                perception_source="fixture_mock",
            )
        ],
    )


def test_only_verified_reports_affect_route_barriers(graph):
    comparator = RouteComparator(graph)
    
    # Route A uses SEG_EAST_1 and SEG_EAST_2
    routes = [
        {"route_id": "route_east", "route_name": "East Corridor", "segment_ids": ["SEG_EAST_1", "SEG_EAST_2"]}
    ]

    # 1. Add unverified report (PENDING_INDEPENDENT_REVIEW)
    unverified_report = create_mock_report(
        "rep_pending", "SEG_EAST_1", ReportState.PENDING_INDEPENDENT_REVIEW, CoarsePassability.BLOCKED
    )
    res_unverified = comparator.compare_routes(routes, [unverified_report])
    
    # Must NOT count as a verified barrier!
    route_sum = res_unverified.candidate_routes[0]
    assert route_sum.verified_barriers.total_barriers_count == 0
    assert route_sum.unverified_ignored_reports_count == 1
    assert "No active verified barriers recorded" in route_sum.condition_explanation

    # 2. Add VERIFIED report
    verified_report = create_mock_report(
        "rep_verified", "SEG_EAST_1", ReportState.VERIFIED, CoarsePassability.BLOCKED
    )
    res_verified = comparator.compare_routes(routes, [verified_report])
    route_sum2 = res_verified.candidate_routes[0]
    assert route_sum2.verified_barriers.total_barriers_count == 1
    assert route_sum2.verified_barriers.blocked_count == 1
    assert "Verified barriers recorded: 1 blocked" in route_sum2.condition_explanation


def test_survey_coverage_and_unknown_handling(graph):
    comparator = RouteComparator(graph)

    # Route West uses SEG_WEST_1 (stale survey) and SEG_WEST_2 (unsurveyed)
    routes = [
        {"route_id": "route_west", "route_name": "West Corridor", "segment_ids": ["SEG_WEST_1", "SEG_WEST_2"]}
    ]

    res = comparator.compare_routes(routes, [])
    route = res.candidate_routes[0]

    # Check coverage calculation: total 370m, 185m stale (50%), 185m unsurveyed (50%)
    assert route.coverage.unsurveyed_percentage == 50.0
    assert route.coverage.stale_survey_percentage == 50.0
    assert route.coverage.recent_survey_percentage == 0.0

    # Must explicitly state UNKNOWN conditions
    assert "conditions there are UNKNOWN" in route.condition_explanation


def test_single_route_response_omits_comparative_badges(graph):
    comparator = RouteComparator(graph)
    routes = [
        {"route_id": "route_single", "route_name": "Single Route", "segment_ids": ["SEG_EAST_1"]}
    ]
    res = comparator.compare_routes(routes, [])
    assert res.is_multi_route_comparison is False
    assert res.candidate_routes[0].badge is None
    assert "Comparative badges are disabled for single-route responses" in res.comparison_notes[0]


def test_multi_route_comparison_provides_tradeoffs(graph):
    comparator = RouteComparator(graph)
    routes = [
        {"route_id": "route_east", "route_name": "East Corridor (Surveyed)", "segment_ids": ["SEG_EAST_1", "SEG_EAST_2"]},
        {"route_id": "route_west", "route_name": "West Corridor (Unsurveyed)", "segment_ids": ["SEG_WEST_1", "SEG_WEST_2"]},
    ]

    # Place a verified blockage on East corridor
    east_blockage = create_mock_report(
        "rep_east_block", "SEG_EAST_1", ReportState.VERIFIED, CoarsePassability.BLOCKED
    )

    res = comparator.compare_routes(routes, [east_blockage])
    assert res.is_multi_route_comparison is True
    assert len(res.candidate_routes) == 2

    east_summary = next(r for r in res.candidate_routes if r.route_id == "route_east")
    west_summary = next(r for r in res.candidate_routes if r.route_id == "route_west")

    # East has verified blockage and high survey coverage
    assert east_summary.verified_barriers.blocked_count == 1
    assert east_summary.coverage.recent_survey_percentage == 100.0
    assert "Known Blockage Reported" in east_summary.badge
    assert "High Survey Coverage" in east_summary.badge

    # West has 0 verified barriers but high uncertainty
    assert west_summary.verified_barriers.total_barriers_count == 0
    assert west_summary.coverage.unsurveyed_percentage == 50.0
    assert "High Uncertainty (Mostly Unsurveyed)" in west_summary.badge

    # Mandatory disclaimer present
    assert res.disclaimer == MANDATORY_DISCLAIMER

