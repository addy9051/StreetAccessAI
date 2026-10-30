"""Verification workflow service.

Coordinates declarative state evaluations, role authorization checks,
and transactional persistence with append-only audit trails.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from streetaccess.storage.repository import StorageRepository
from streetaccess.verification.models import (
    AuditEvent,
    CommunityReport,
    GeoPoint,
    ReportState,
    UserRole,
)
from streetaccess.verification.transition_table import evaluate_transition


class InvalidTransitionError(Exception):
    """Raised when a proposed transition violates declarative rules or authorization."""
    pass


class ReportNotFoundError(Exception):
    """Raised when a referenced report ID does not exist."""
    pass


class VerificationService:
    """Service governing report lifecycle and human verification workflow."""

    def __init__(self, repository: StorageRepository):
        self.repository = repository

    def submit_report(
        self,
        uploader_id: str,
        location: GeoPoint,
        observations: list,
        report_id: Optional[str] = None,
    ) -> CommunityReport:
        """Create and persist a new community report in SUBMITTED state."""
        new_id = report_id or str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc).isoformat()
        
        report = CommunityReport(
            report_id=new_id,
            uploader_id=uploader_id,
            location=location,
            state=ReportState.SUBMITTED,
            created_at_utc=now_utc,
            updated_at_utc=now_utc,
            observations=observations,
        )
        self.repository.save_report(report)
        return report

    def transition_report(
        self,
        report_id: str,
        target_state: ReportState,
        actor_id: str,
        actor_role: UserRole,
        reason: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> CommunityReport:
        """Apply a declarative state transition to a report.
        
        CRITICAL RULES:
        1. Evaluates declarative rules and role permissions before making any change.
        2. If invalid, raises InvalidTransitionError. No report mutation occurs,
           and NO audit event is written.
        3. If valid, atomically writes the updated state and append-only audit event.
        """
        report = self.repository.get_report(report_id)
        if not report:
            raise ReportNotFoundError(f"Report '{report_id}' does not exist.")

        # Declarative check
        eval_result = evaluate_transition(
            report=report,
            target_state=target_state,
            actor_id=actor_id,
            actor_role=actor_role,
        )

        if not eval_result.is_valid:
            # Reject immediately: do not mutate, do not write audit log
            raise InvalidTransitionError(eval_result.error_message)

        # Prepare state mutation
        prev_state = report.state
        now_utc = datetime.now(timezone.utc).isoformat()
        report.state = target_state
        report.updated_at_utc = now_utc

        # Track verifier / disputer provenance
        if target_state == ReportState.VERIFIED and actor_role == UserRole.REVIEWER:
            report.last_verifier_id = actor_id
        elif target_state == ReportState.DISPUTED:
            report.disputed_by_actor_id = actor_id

        # Create immutable audit record
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            report_id=report.report_id,
            from_state=prev_state,
            to_state=target_state,
            actor_id=actor_id,
            actor_role=actor_role,
            timestamp_utc=now_utc,
            reason=reason,
            metadata=metadata or {},
        )

        # Atomically commit both
        self.repository.record_transition_transactional(report, event)
        return report

    def get_report(self, report_id: str) -> Optional[CommunityReport]:
        return self.repository.get_report(report_id)

    def get_audit_trail(self, report_id: str) -> List[AuditEvent]:
        return self.repository.get_audit_trail(report_id)

