"""Tests for verification workflow, state transitions, role checks, and append-only audit persistence."""

import os
import pytest
from streetaccess.storage.db import initialize_database
from streetaccess.storage.repository import StorageRepository
from streetaccess.verification.models import GeoPoint, ReportState, UserRole
from streetaccess.verification.service import InvalidTransitionError, VerificationService


@pytest.fixture
def clean_service(tmp_path):
    db_file = str(tmp_path / "test_verification.db")
    initialize_database(db_file)
    repo = StorageRepository(db_file)
    service = VerificationService(repo)
    return service, repo


def test_valid_verification_lifecycle(clean_service):
    service, repo = clean_service
    location = GeoPoint(latitude=37.775, longitude=-122.419, gps_accuracy_meters=4.0)

    # 1. Submit
    report = service.submit_report(
        uploader_id="user_alice",
        location=location,
        observations=[],
    )
    assert report.state == ReportState.SUBMITTED

    # 2. Uploader confirms -> PENDING_INDEPENDENT_REVIEW
    report = service.transition_report(
        report_id=report.report_id,
        target_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        actor_id="user_alice",
        actor_role=UserRole.UPLOADER,
        reason="Confirmed report details and uploaded photos.",
    )
    assert report.state == ReportState.PENDING_INDEPENDENT_REVIEW

    # 3. Independent reviewer verifies -> VERIFIED
    report = service.transition_report(
        report_id=report.report_id,
        target_state=ReportState.VERIFIED,
        actor_id="user_bob_reviewer",
        actor_role=UserRole.REVIEWER,
        reason="Visual evidence clearly shows clear sidewalk with curb ramp.",
    )
    assert report.state == ReportState.VERIFIED
    assert report.last_verifier_id == "user_bob_reviewer"

    # Verify audit trail contains exactly 2 events
    audit = repo.get_audit_trail(report.report_id)
    assert len(audit) == 2
    assert audit[0].from_state == ReportState.SUBMITTED
    assert audit[0].to_state == ReportState.PENDING_INDEPENDENT_REVIEW
    assert audit[0].actor_id == "user_alice"

    assert audit[1].from_state == ReportState.PENDING_INDEPENDENT_REVIEW
    assert audit[1].to_state == ReportState.VERIFIED
    assert audit[1].actor_id == "user_bob_reviewer"


def test_uploader_cannot_verify_own_report(clean_service):
    service, repo = clean_service
    location = GeoPoint(latitude=37.775, longitude=-122.419, gps_accuracy_meters=4.0)

    report = service.submit_report(
        uploader_id="user_charlie",
        location=location,
        observations=[],
    )
    service.transition_report(
        report_id=report.report_id,
        target_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        actor_id="user_charlie",
        actor_role=UserRole.UPLOADER,
        reason="Ready for review",
    )

    # Attempt self-verification by charlie
    with pytest.raises(InvalidTransitionError) as exc:
        service.transition_report(
            report_id=report.report_id,
            target_state=ReportState.VERIFIED,
            actor_id="user_charlie",  # same as uploader!
            actor_role=UserRole.REVIEWER,
            reason="I am verifying my own report.",
        )
    assert "Uploader separation violation" in str(exc.value)

    # Verify report state is UNCHANGED and NO audit event was appended
    fresh_report = repo.get_report(report.report_id)
    assert fresh_report.state == ReportState.PENDING_INDEPENDENT_REVIEW

    audit = repo.get_audit_trail(report.report_id)
    assert len(audit) == 1  # Only the initial transition, no rejected event logged
    assert audit[0].to_state == ReportState.PENDING_INDEPENDENT_REVIEW


def test_dispute_resolution_moderator_conflict_checks(clean_service):
    service, repo = clean_service
    location = GeoPoint(latitude=37.775, longitude=-122.419, gps_accuracy_meters=4.0)

    report = service.submit_report(
        uploader_id="user_alice",
        location=location,
        observations=[],
    )
    service.transition_report(
        report_id=report.report_id,
        target_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        actor_id="user_alice",
        actor_role=UserRole.UPLOADER,
        reason="Ready",
    )
    service.transition_report(
        report_id=report.report_id,
        target_state=ReportState.VERIFIED,
        actor_id="user_bob",
        actor_role=UserRole.REVIEWER,
        reason="Verified",
    )
    # Charlie disputes
    service.transition_report(
        report_id=report.report_id,
        target_state=ReportState.DISPUTED,
        actor_id="user_charlie",
        actor_role=UserRole.REVIEWER,
        reason="Sidewalk is blocked by ongoing construction now.",
    )

    # 1. Prior verifier bob cannot resolve dispute as moderator
    with pytest.raises(InvalidTransitionError) as exc:
        service.transition_report(
            report_id=report.report_id,
            target_state=ReportState.VERIFIED,
            actor_id="user_bob",
            actor_role=UserRole.MODERATOR,
            reason="I verified it originally, keeping it.",
        )
    assert "conflict of interest: actor is the prior verifier" in str(exc.value)

    # 2. Disputer charlie cannot resolve dispute
    with pytest.raises(InvalidTransitionError) as exc:
        service.transition_report(
            report_id=report.report_id,
            target_state=ReportState.REJECTED,
            actor_id="user_charlie",
            actor_role=UserRole.MODERATOR,
            reason="I disputed it, so I reject it.",
        )
    assert "conflict of interest: actor is the disputer" in str(exc.value)

    # 3. Independent moderator diana can resolve
    report = service.transition_report(
        report_id=report.report_id,
        target_state=ReportState.REJECTED,
        actor_id="user_diana_mod",
        actor_role=UserRole.MODERATOR,
        reason="Independent on-site review confirmed ongoing construction blockage.",
    )
    assert report.state == ReportState.REJECTED

