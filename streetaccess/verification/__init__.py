"""Verification package for StreetAccess."""

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
from streetaccess.verification.transition_table import (
    VALID_TRANSITIONS,
    TransitionRule,
    TransitionValidationResult,
    evaluate_transition,
)

__all__ = [
    "AuditEvent",
    "CommunityReport",
    "GeoPoint",
    "ReportState",
    "UserRole",
    "InvalidTransitionError",
    "ReportNotFoundError",
    "VerificationService",
    "VALID_TRANSITIONS",
    "TransitionRule",
    "TransitionValidationResult",
    "evaluate_transition",
]

