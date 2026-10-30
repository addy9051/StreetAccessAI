"""FastAPI application for StreetAccess core API."""

from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from streetaccess.config import CONFIG
from streetaccess.perception.fixture_adapter import FixturePerceptionAdapter
from streetaccess.perception.models import FrameObservation, PerceptionBatchRequest, PerceptionOutput
from streetaccess.routing.comparator import RouteComparator, RouteComparisonResponse
from streetaccess.routing.graph import SyntheticPedestrianGraph
from streetaccess.routing.matcher import SpatialMatcher, SpatialMatchResult
from streetaccess.storage.db import initialize_database, DEFAULT_DB_PATH
from streetaccess.storage.repository import StorageRepository
from streetaccess.verification.models import (
    AuditEvent,
    CommunityReport,
    GeoPoint,
    ReportState,
    UserRole,
)
from streetaccess.verification.service import (
    InvalidTransitionError,
    ReportNotFoundError,
    VerificationService,
)

# Initialize application
app = FastAPI(
    title="StreetAccess Deterministic Core API",
    description=(
        "StreetAccess compares candidate walking routes using human-verified community reports. "
        "It never claims that a route is safe, accessible, or obstacle-free."
    ),
    version="0.1.0",
)

# Initialize local database and repositories
initialize_database(DEFAULT_DB_PATH)
storage_repo = StorageRepository(DEFAULT_DB_PATH)
verification_service = VerificationService(storage_repo)
fixture_perception_adapter = FixturePerceptionAdapter()
pedestrian_graph = SyntheticPedestrianGraph.create_default_network()
spatial_matcher = SpatialMatcher(pedestrian_graph)
route_comparator = RouteComparator(pedestrian_graph)


# --- Request DTOs ---

class CreateReportRequest(BaseModel):
    uploader_id: str
    location: GeoPoint
    observations: List[FrameObservation] = Field(default_factory=list)


class TransitionReportRequest(BaseModel):
    target_state: ReportState
    actor_id: str
    actor_role: UserRole
    reason: str
    metadata: Optional[Dict[str, str]] = None


class RouteCandidateInput(BaseModel):
    route_id: str
    route_name: str
    segment_ids: List[str]


class CompareRoutesRequest(BaseModel):
    routes: List[RouteCandidateInput]


# --- Endpoints ---

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint clearly indicating mock perception provider."""
    return {
        "status": "healthy",
        "service": "StreetAccess",
        "perception_adapter": fixture_perception_adapter.name,
        "is_mock_perception": fixture_perception_adapter.is_mock,
        "active_graph_segments": len(pedestrian_graph.segments),
    }


@app.post("/perception/analyze", response_model=PerceptionOutput, tags=["Perception"])
def analyze_perception(request: PerceptionBatchRequest):
    """Run deterministic fixture perception analysis.
    
    All output is explicitly marked with is_mock=True.
    """
    return fixture_perception_adapter.analyze(request)


@app.post("/reports", response_model=CommunityReport, status_code=status.HTTP_201_CREATED, tags=["Reports"])
def submit_report(req: CreateReportRequest):
    """Submit a new pedestrian condition community report.
    
    Performs server-side spatial association against the synthetic pedestrian graph.
    """
    report = verification_service.submit_report(
        uploader_id=req.uploader_id,
        location=req.location,
        observations=req.observations,
    )
    # Perform spatial matching
    match_res = spatial_matcher.match_location(req.location)
    report.spatial_match_status = match_res.confidence.value
    report.matched_segment_id = match_res.matched_segment_id
    storage_repo.save_report(report)
    return report


@app.get("/reports/{report_id}", response_model=CommunityReport, tags=["Reports"])
def get_report(report_id: str):
    """Retrieve current state of a community report."""
    report = verification_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    return report


@app.post("/reports/{report_id}/match-spatial", response_model=SpatialMatchResult, tags=["Reports"])
def match_report_spatial(report_id: str):
    """Evaluate spatial association for a report without silent snapping."""
    report = verification_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    
    match_result = spatial_matcher.match_location(report.location)
    report.spatial_match_status = match_result.confidence.value
    report.matched_segment_id = match_result.matched_segment_id
    storage_repo.save_report(report)
    return match_result


@app.post("/reports/{report_id}/transition", response_model=CommunityReport, tags=["Verification"])
def transition_report(report_id: str, req: TransitionReportRequest):
    """Apply a declarative state transition to a report with role verification.
    
    Invalid transitions fail without modifying report or appending to audit log.
    """
    try:
        updated = verification_service.transition_report(
            report_id=report_id,
            target_state=req.target_state,
            actor_id=req.actor_id,
            actor_role=req.actor_role,
            reason=req.reason,
            metadata=req.metadata,
        )
        return updated
    except ReportNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/reports/{report_id}/audit", response_model=List[AuditEvent], tags=["Verification"])
def get_audit_trail(report_id: str):
    """Retrieve immutable chronological audit trail for a report."""
    report = verification_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    return verification_service.get_audit_trail(report_id)


@app.post("/routes/compare", response_model=RouteComparisonResponse, tags=["Routing"])
def compare_routes(req: CompareRoutesRequest):
    """Compare candidate pedestrian routes side-by-side.
    
    Only VERIFIED community reports affect active barrier counts.
    Never claims route is safe, accessible, or obstacle-free.
    """
    all_reports = storage_repo.list_reports()
    route_specs = [
        {
            "route_id": r.route_id,
            "route_name": r.route_name,
            "segment_ids": r.segment_ids,
        }
        for r in req.routes
    ]
    return route_comparator.compare_routes(route_specs, all_reports)

