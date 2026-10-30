"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from streetaccess.api.app import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["is_mock_perception"] is True
    assert data["perception_adapter"] == "deterministic_fixture_adapter_v1"


def test_fixture_perception_endpoint():
    res = client.post(
        "/perception/analyze",
        json={"input_identifier": "fixture_clear_sidewalk"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_mock"] is True
    assert len(data["observations"]) == 1
    assert data["observations"][0]["category"] == "clear_sidewalk"


def test_submit_and_transition_report_api():
    # 1. Submit report
    submit_res = client.post(
        "/reports",
        json={
            "uploader_id": "api_user_1",
            "location": {
                "latitude": 37.7755,
                "longitude": -122.41925,
                "gps_accuracy_meters": 3.0,
            },
            "observations": [
                {
                    "frame_index": 0,
                    "category": "construction",
                    "passability": "blocked",
                    "visual_evidence_text": "Barrier across path",
                    "is_mock": True,
                    "perception_source": "fixture_mock",
                }
            ],
        },
    )
    assert submit_res.status_code == 201
    rep = submit_res.json()
    report_id = rep["report_id"]
    assert rep["state"] == "submitted"
    assert rep["spatial_match_status"] == "confident"
    assert rep["matched_segment_id"] == "SEG_EAST_1"

    # 2. Transition: submitted -> pending_independent_review
    trans_res1 = client.post(
        f"/reports/{report_id}/transition",
        json={
            "target_state": "pending_independent_review",
            "actor_id": "api_user_1",
            "actor_role": "uploader",
            "reason": "Submitter confirmed details",
        },
    )
    assert trans_res1.status_code == 200
    assert trans_res1.json()["state"] == "pending_independent_review"

    # 3. Uploader cannot self-verify (must return 400)
    invalid_verify_res = client.post(
        f"/reports/{report_id}/transition",
        json={
            "target_state": "verified",
            "actor_id": "api_user_1",  # Same as uploader!
            "actor_role": "reviewer",
            "reason": "Trying to self-verify",
        },
    )
    assert invalid_verify_res.status_code == 400
    assert "Uploader separation violation" in invalid_verify_res.json()["detail"]

    # 4. Independent reviewer verifies
    valid_verify_res = client.post(
        f"/reports/{report_id}/transition",
        json={
            "target_state": "verified",
            "actor_id": "independent_reviewer_99",
            "actor_role": "reviewer",
            "reason": "Independent community verification passed",
        },
    )
    assert valid_verify_res.status_code == 200
    assert valid_verify_res.json()["state"] == "verified"

    # 5. Check audit trail
    audit_res = client.get(f"/reports/{report_id}/audit")
    assert audit_res.status_code == 200
    audit = audit_res.json()
    assert len(audit) == 2


def test_compare_routes_api():
    res = client.post(
        "/routes/compare",
        json={
            "routes": [
                {
                    "route_id": "east_route",
                    "route_name": "East Sidewalk Path",
                    "segment_ids": ["SEG_EAST_1", "SEG_EAST_2"],
                },
                {
                    "route_id": "west_route",
                    "route_name": "West Sidewalk Path",
                    "segment_ids": ["SEG_WEST_1", "SEG_WEST_2"],
                },
            ]
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_multi_route_comparison"] is True
    assert "DISCLAIMER" in data["disclaimer"]
    assert len(data["candidate_routes"]) == 2

