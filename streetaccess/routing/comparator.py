"""Transparent route trade-off comparator.

Compares candidate pedestrian routes using verified community reports and survey recency.

NON-NEGOTIABLE PRODUCT BOUNDARIES:
1. Never claim a route is safe, accessible, or obstacle-free.
2. Absence of reports means UNKNOWN unless the segment has a recent recorded survey.
3. Only VERIFIED reports may affect route comparisons.
4. Do not combine heterogeneous metrics into an unexplained scalar safety score.
5. If only one candidate route is returned, do not show comparative badges.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from streetaccess.config import CONFIG
from streetaccess.perception.models import CoarsePassability
from streetaccess.routing.graph import SurveyStatus, SyntheticPedestrianGraph
from streetaccess.verification.models import CommunityReport, ReportState

MANDATORY_DISCLAIMER = (
    "DISCLAIMER: StreetAccess compares candidate routes based on human-verified community reports "
    "and survey records. It NEVER claims that a route is safe, accessible, or obstacle-free. "
    "Segments without recent surveys are UNKNOWN in condition, regardless of whether reports exist."
)


class RouteCoverageBreakdown(BaseModel):
    """Segment length percentages by survey status."""
    total_length_meters: float
    recent_survey_meters: float
    recent_survey_percentage: float
    stale_survey_meters: float
    stale_survey_percentage: float
    unsurveyed_meters: float
    unsurveyed_percentage: float


class VerifiedBarrierSummary(BaseModel):
    """Summary of verified obstacles along a route."""
    total_barriers_count: int
    blocked_count: int
    narrowed_count: int
    barrier_details: List[str]


class RouteTradeoffSummary(BaseModel):
    """Transparent metrics for a single candidate route.
    
    No opaque aggregate score is calculated; trade-offs are explicitly itemized.
    """
    route_id: str
    route_name: str
    segment_ids: List[str]
    total_distance_meters: float
    estimated_walking_time_seconds: float
    coverage: RouteCoverageBreakdown
    verified_barriers: VerifiedBarrierSummary
    stale_reports_count: int
    unverified_ignored_reports_count: int
    condition_explanation: str
    badge: Optional[str] = None  # Populated ONLY when comparing multiple routes


class RouteComparisonResponse(BaseModel):
    """Comparison response returned to pedestrian client."""
    is_multi_route_comparison: bool
    disclaimer: str = MANDATORY_DISCLAIMER
    candidate_routes: List[RouteTradeoffSummary]
    comparison_notes: List[str]


class RouteComparator:
    """Evaluates candidate pedestrian routes based on verified evidence and survey records."""

    def __init__(self, graph: SyntheticPedestrianGraph):
        self.graph = graph

    def compare_routes(
        self,
        routes: List[Dict[str, any]],  # list of {"route_id": str, "route_name": str, "segment_ids": list[str]}
        all_reports: List[CommunityReport],
    ) -> RouteComparisonResponse:
        """Compare one or more candidate routes side-by-side.
        
        Args:
            routes: List of candidate route specifications.
            all_reports: All community reports in the repository.
        """
        now = datetime.now(timezone.utc)
        summaries: List[RouteTradeoffSummary] = []

        # Filter reports: strictly only VERIFIED reports may affect route evaluation
        verified_reports = [r for r in all_reports if r.state == ReportState.VERIFIED]
        unverified_reports = [r for r in all_reports if r.state != ReportState.VERIFIED]

        # Group verified reports by matched segment id
        reports_by_segment: Dict[str, List[CommunityReport]] = {}
        for r in verified_reports:
            if r.matched_segment_id:
                reports_by_segment.setdefault(r.matched_segment_id, []).append(r)

        unverified_by_segment: Dict[str, List[CommunityReport]] = {}
        for r in unverified_reports:
            if r.matched_segment_id:
                unverified_by_segment.setdefault(r.matched_segment_id, []).append(r)

        for route_spec in routes:
            r_id = route_spec["route_id"]
            r_name = route_spec["route_name"]
            seg_ids = route_spec["segment_ids"]

            total_dist = 0.0
            total_time = 0.0
            recent_len = 0.0
            stale_len = 0.0
            unsurveyed_len = 0.0

            route_verified_barriers = 0
            blocked_barriers = 0
            narrowed_barriers = 0
            barrier_notes = []
            stale_reports_count = 0
            unverified_ignored = 0

            for sid in seg_ids:
                if sid not in self.graph.segments:
                    continue
                seg = self.graph.segments[sid]
                seg_len = seg.length_meters
                total_dist += seg_len
                total_time += seg_len / seg.typical_speed_mps

                # Survey status
                survey_st = seg.get_survey_status(now)
                if survey_st == SurveyStatus.RECENT_SURVEY:
                    recent_len += seg_len
                elif survey_st == SurveyStatus.STALE_ONLY:
                    stale_len += seg_len
                else:
                    unsurveyed_len += seg_len

                # Unverified reports on this segment are tracked for transparency but ignored for condition evaluation
                unverified_ignored += len(unverified_by_segment.get(sid, []))

                # Process verified reports
                seg_reports = reports_by_segment.get(sid, [])
                for rep in seg_reports:
                    # Check report freshness
                    rep_dt = datetime.fromisoformat(rep.updated_at_utc)
                    if rep_dt.tzinfo is None:
                        rep_dt = rep_dt.replace(tzinfo=timezone.utc)
                    rep_age_days = (now - rep_dt).total_seconds() / 86400.0

                    if rep_age_days > CONFIG.REPORT_RECENCY_HORIZON_DAYS:
                        stale_reports_count += 1

                    for obs in rep.observations:
                        if obs.passability == CoarsePassability.BLOCKED:
                            route_verified_barriers += 1
                            blocked_barriers += 1
                            barrier_notes.append(
                                f"Segment '{seg.name}': BLOCKED by {obs.category.value} ({obs.visual_evidence_text})"
                            )
                        elif obs.passability == CoarsePassability.NARROWED:
                            route_verified_barriers += 1
                            narrowed_barriers += 1
                            barrier_notes.append(
                                f"Segment '{seg.name}': NARROWED by {obs.category.value} ({obs.visual_evidence_text})"
                            )

            # Calculate percentages
            if total_dist > 0:
                recent_pct = round((recent_len / total_dist) * 100.0, 1)
                stale_pct = round((stale_len / total_dist) * 100.0, 1)
                unsurveyed_pct = round((unsurveyed_len / total_dist) * 100.0, 1)
            else:
                recent_pct = stale_pct = unsurveyed_pct = 0.0

            coverage = RouteCoverageBreakdown(
                total_length_meters=round(total_dist, 1),
                recent_survey_meters=round(recent_len, 1),
                recent_survey_percentage=recent_pct,
                stale_survey_meters=round(stale_len, 1),
                stale_survey_percentage=stale_pct,
                unsurveyed_meters=round(unsurveyed_len, 1),
                unsurveyed_percentage=unsurveyed_pct,
            )

            # Deterministic, transparent explanation
            explanation_parts = [
                f"Distance: {total_dist:.0f}m (approx. {total_time / 60.0:.1f} min walk).",
                f"Survey coverage: {recent_pct}% recent survey, {stale_pct}% stale survey, {unsurveyed_pct}% unsurveyed.",
            ]
            if unsurveyed_pct > 0:
                explanation_parts.append(
                    f"Notice: {unsurveyed_pct}% of path is unsurveyed; pedestrian conditions there are UNKNOWN."
                )
            if route_verified_barriers > 0:
                explanation_parts.append(
                    f"Verified barriers recorded: {blocked_barriers} blocked, {narrowed_barriers} narrowed."
                )
            else:
                explanation_parts.append("No active verified barriers recorded on surveyed portions.")

            if stale_reports_count > 0:
                explanation_parts.append(f"{stale_reports_count} verified reports are older than 60 days (stale).")

            if unverified_ignored > 0:
                explanation_parts.append(
                    f"{unverified_ignored} pending/unverified reports exist on this path and were excluded from active barrier evaluation."
                )

            summary = RouteTradeoffSummary(
                route_id=r_id,
                route_name=r_name,
                segment_ids=seg_ids,
                total_distance_meters=round(total_dist, 1),
                estimated_walking_time_seconds=round(total_time, 1),
                coverage=coverage,
                verified_barriers=VerifiedBarrierSummary(
                    total_barriers_count=route_verified_barriers,
                    blocked_count=blocked_barriers,
                    narrowed_count=narrowed_barriers,
                    barrier_details=barrier_notes,
                ),
                stale_reports_count=stale_reports_count,
                unverified_ignored_reports_count=unverified_ignored,
                condition_explanation=" ".join(explanation_parts),
                badge=None,  # Badges are assigned below only if multiple routes exist
            )
            summaries.append(summary)

        # Single-route rule:
        # "If only one candidate route is returned, do not show comparative badges."
        is_multi = len(summaries) > 1
        comparison_notes = []

        if is_multi:
            # Assign descriptive trade-off badges (e.g. Higher Coverage vs Fewer Recorded Obstacles)
            # Never label as "Best", "Safe", or "Accessible"
            for s in summaries:
                badges = []
                if s.coverage.recent_survey_percentage >= 80.0:
                    badges.append("High Survey Coverage")
                elif s.coverage.unsurveyed_percentage >= 50.0:
                    badges.append("High Uncertainty (Mostly Unsurveyed)")
                
                if s.verified_barriers.blocked_count > 0:
                    badges.append("Known Blockage Reported")
                elif s.verified_barriers.total_barriers_count == 0:
                    badges.append("No Barriers Recorded on Surveyed Segments")

                s.badge = " | ".join(badges) if badges else "Standard Path"

            comparison_notes.append(
                f"Evaluated {len(summaries)} candidate routes. Trade-offs reflect known verified barriers and survey coverage."
            )
        else:
            # Explicitly ensure badge is None for single-route responses
            if summaries:
                summaries[0].badge = None
            comparison_notes.append(
                "Single candidate route evaluated. Comparative badges are disabled for single-route responses."
            )

        return RouteComparisonResponse(
            is_multi_route_comparison=is_multi,
            disclaimer=MANDATORY_DISCLAIMER,
            candidate_routes=summaries,
            comparison_notes=comparison_notes,
        )

