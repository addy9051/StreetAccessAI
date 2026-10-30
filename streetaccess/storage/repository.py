"""Transactional repository for reports and immutable audit events."""

import json
import sqlite3
from typing import Optional, List
from streetaccess.storage.db import DEFAULT_DB_PATH, get_db_connection
from streetaccess.verification.models import AuditEvent, CommunityReport, ReportState


class StorageRepository:
    """Manages transactional persistence for reports and append-only audit events."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def save_report(self, report: CommunityReport) -> None:
        """Create or update a community report record."""
        raw_json = report.model_dump_json()
        with get_db_connection(self.db_path) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO reports (
                        report_id, uploader_id, latitude, longitude,
                        gps_accuracy_meters, bearing_degrees, state,
                        created_at_utc, updated_at_utc, matched_segment_id,
                        spatial_match_status, last_verifier_id,
                        disputed_by_actor_id, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(report_id) DO UPDATE SET
                        state = excluded.state,
                        updated_at_utc = excluded.updated_at_utc,
                        matched_segment_id = excluded.matched_segment_id,
                        spatial_match_status = excluded.spatial_match_status,
                        last_verifier_id = excluded.last_verifier_id,
                        disputed_by_actor_id = excluded.disputed_by_actor_id,
                        raw_json = excluded.raw_json;
                    """,
                    (
                        report.report_id,
                        report.uploader_id,
                        report.location.latitude,
                        report.location.longitude,
                        report.location.gps_accuracy_meters,
                        report.location.bearing_degrees,
                        report.state.value,
                        report.created_at_utc,
                        report.updated_at_utc,
                        report.matched_segment_id,
                        report.spatial_match_status,
                        report.last_verifier_id,
                        report.disputed_by_actor_id,
                        raw_json,
                    ),
                )

    def get_report(self, report_id: str) -> Optional[CommunityReport]:
        """Fetch report by its unique ID."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json FROM reports WHERE report_id = ?", (report_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return CommunityReport.model_validate_json(row[0])

    def list_reports(self, state: Optional[ReportState] = None) -> List[CommunityReport]:
        """List reports, optionally filtered by state."""
        query = "SELECT raw_json FROM reports"
        params = ()
        if state:
            query += " WHERE state = ?"
            params = (state.value,)
        
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [CommunityReport.model_validate_json(row[0]) for row in rows]

    def record_transition_transactional(
        self,
        report: CommunityReport,
        audit_event: AuditEvent,
    ) -> None:
        """Atomically persist updated report state and append-only audit event in one transaction.
        
        If either fails, the entire transaction rolls back.
        """
        raw_json = report.model_dump_json()
        metadata_json = json.dumps(audit_event.metadata)

        with get_db_connection(self.db_path) as conn:
            with conn:  # Transaction begins
                cursor = conn.cursor()
                
                # 1. Update report state
                cursor.execute(
                    """
                    UPDATE reports SET
                        state = ?,
                        updated_at_utc = ?,
                        last_verifier_id = ?,
                        disputed_by_actor_id = ?,
                        raw_json = ?
                    WHERE report_id = ?
                    """,
                    (
                        report.state.value,
                        report.updated_at_utc,
                        report.last_verifier_id,
                        report.disputed_by_actor_id,
                        raw_json,
                        report.report_id,
                    ),
                )

                # 2. Append to immutable audit log
                cursor.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, report_id, from_state, to_state,
                        actor_id, actor_role, timestamp_utc, reason, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        audit_event.event_id,
                        audit_event.report_id,
                        audit_event.from_state.value,
                        audit_event.to_state.value,
                        audit_event.actor_id,
                        audit_event.actor_role.value,
                        audit_event.timestamp_utc,
                        audit_event.reason,
                        metadata_json,
                    ),
                )

    def get_audit_trail(self, report_id: str) -> List[AuditEvent]:
        """Retrieve audit events for a report in chronological order.
        
        Enforces read-only access to audit trail.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT event_id, report_id, from_state, to_state,
                       actor_id, actor_role, timestamp_utc, reason, metadata_json
                FROM audit_events
                WHERE report_id = ?
                ORDER BY timestamp_utc ASC
                """,
                (report_id,),
            )
            rows = cursor.fetchall()
            events = []
            for row in rows:
                events.append(
                    AuditEvent(
                        event_id=row[0],
                        report_id=row[1],
                        from_state=ReportState(row[2]),
                        to_state=ReportState(row[3]),
                        actor_id=row[4],
                        actor_role=row[5],
                        timestamp_utc=row[6],
                        reason=row[7],
                        metadata=json.loads(row[8]),
                    )
                )
            return events

