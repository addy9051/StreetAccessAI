"""SQLite database initialization and transaction management.

Provides local transactional persistence with an append-only audit trail.
"""

import os
import sqlite3
from typing import Generator
from contextlib import contextmanager

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "streetaccess.db")


def initialize_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite tables for reports and immutable audit events."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            
            # Reports table: stores current entity state
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                uploader_id TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                gps_accuracy_meters REAL NOT NULL,
                bearing_degrees REAL,
                state TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                matched_segment_id TEXT,
                spatial_match_status TEXT,
                last_verifier_id TEXT,
                disputed_by_actor_id TEXT,
                raw_json TEXT NOT NULL
            );
            """)

            # Audit events table: strictly append-only
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                reason TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                FOREIGN KEY (report_id) REFERENCES reports (report_id)
            );
            """)

            # Index for fast audit lookup by report_id
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_report_id ON audit_events(report_id);
            """)

    finally:
        conn.close()


@contextmanager
def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()

