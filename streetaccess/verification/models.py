"""Verification models, roles, and community report structures.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from streetaccess.perception.models import FrameObservation


class ReportState(str, Enum):
    """Explicit states for pedestrian condition community reports."""
    SUBMITTED = "submitted"
    PENDING_INDEPENDENT_REVIEW = "pending_independent_review"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    VERIFIED = "verified"
    REJECTED = "rejected"
    DISPUTED = "disputed"
    EXPIRED = "expired"


class UserRole(str, Enum):
    """Authorized roles for report workflows."""
    UPLOADER = "uploader"
    REVIEWER = "reviewer"       # Independent community verifier
    MODERATOR = "moderator"     # Trusted administrator for disputes
    SYSTEM = "system"           # Automated background worker (TTL expiry)


class GeoPoint(BaseModel):
    """Geographic point with explicit GPS accuracy."""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    gps_accuracy_meters: float = Field(..., ge=0.0, description="Reported GPS accuracy radius in meters")
    bearing_degrees: Optional[float] = Field(None, ge=0.0, le=360.0, description="Compass bearing if recorded")


class AuditEvent(BaseModel):
    """Immutable audit record for state transitions.
    
    Persisted to append-only audit storage.
    """
    event_id: str = Field(..., description="Unique event UUID")
    report_id: str = Field(..., description="Target report ID")
    from_state: ReportState = Field(..., description="Previous report state")
    to_state: ReportState = Field(..., description="New report state")
    actor_id: str = Field(..., description="Unique actor user ID")
    actor_role: UserRole = Field(..., description="Role exercised during transition")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason / notes for the transition")
    metadata: dict[str, str] = Field(default_factory=dict)


class CommunityReport(BaseModel):
    """Pedestrian condition report submitted by a community member."""
    report_id: str
    uploader_id: str
    location: GeoPoint
    state: ReportState = Field(default=ReportState.SUBMITTED)
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Visual observations attached to report
    observations: list[FrameObservation] = Field(default_factory=list)
    
    # Associated segment (determined through spatial matching)
    matched_segment_id: Optional[str] = None
    spatial_match_status: Optional[str] = None  # CONFIDENT, AMBIGUOUS, UNMATCHED

    # Provenance tracking for dispute resolution
    last_verifier_id: Optional[str] = None
    disputed_by_actor_id: Optional[str] = None

