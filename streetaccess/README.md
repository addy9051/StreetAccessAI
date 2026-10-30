# StreetAccess — Deterministic Pedestrian Condition & Route Trade-Off Engine

StreetAccess compares candidate walking route options using human-verified community reports about pedestrian conditions.

> **CRITICAL PRODUCT BOUNDARIES:**
> 1. StreetAccess **never** claims that a route is safe, accessible, or obstacle-free.
> 2. Absence of a report means **`UNKNOWN`**, unless the segment has a recent recorded survey.
> 3. Only **`VERIFIED`** reports may affect route barrier evaluations.
> 4. We do not estimate real-world metric widths or calibrated severity from uncalibrated 2D images.
> 5. Explanations shown to users are deterministically generated from verified records and survey recency; no combined opaque safety scores are used.

---

## Model Boundary Notice

- **Gemini 3.8 Flash** is an IDE coding assistant only. It is **not** used as a runtime perception system.
- No model API keys, `GEMINI_API_MODEL`, or hosted model dependencies are configured.
- The perception layer uses a provider-neutral `PerceptionAdapter` interface, implemented in this MVP via `FixturePerceptionAdapter`.
- All mock observations are explicitly stamped with `is_mock=True` and `perception_source="fixture_mock"`.

---

## Architecture Layout

All files are strictly isolated under `./streetaccess/`:

```
streetaccess/
├── config.py                 # Provisional hypothesis thresholds (clearly documented)
├── main.py                   # Server & CLI runner
├── perception/               # Provider-neutral perception interface & fixtures
│   ├── adapter.py            # PerceptionAdapter (abstract base class)
│   ├── fixture_adapter.py    # Deterministic mock adapter backed by test fixtures
│   └── models.py             # Server-validated FrameObservation & BoundingBox
├── verification/             # Human verification state machine
│   ├── models.py             # CommunityReport, GeoPoint, AuditEvent, Roles
│   ├── transition_table.py   # Declarative state transition rules & role authorization
│   └── service.py            # VerificationService coordinating transactions
├── storage/                  # SQLite append-only audit trail & entity persistence
│   ├── db.py                 # SQLite connection and schema
│   └── repository.py         # Transactional report & append-only audit repository
├── routing/                  # Pedestrian graph, spatial matcher & trade-off comparator
│   ├── graph.py              # Synthetic pedestrian graph (segments, survey status)
│   ├── matcher.py            # Spatial matcher (CONFIDENT, AMBIGUOUS, UNMATCHED)
│   └── comparator.py         # Route trade-off comparator (with explicit UNKNOWN coverage)
├── api/                      # FastAPI HTTP endpoints
│   └── app.py                # REST API endpoints
└── tests/                    # Deterministic test suite (pytest)
    ├── test_api.py
    ├── test_matcher.py
    ├── test_perception.py
    ├── test_routing.py
    └── test_verification.py
```

---

## Provisional Thresholds (Hypotheses)

Thresholds defined in `streetaccess/config.py` are explicitly treated as **provisional hypotheses**, not evidence-backed constants:

- `SPATIAL_MATCH_DISTANCE_THRESHOLD_METERS = 15.0`: Candidate radius for associating reports with pedestrian segments.
- `SPATIAL_AMBIGUITY_DELTA_THRESHOLD_METERS = 5.0`: When distance difference between nearest candidate segments is under 5m, matcher returns `AMBIGUOUS` rather than silently snapping.
- `SURVEY_RECENCY_HORIZON_DAYS = 30`: Surveys older than 30 days are classified as `STALE_ONLY`.
- `REPORT_RECENCY_HORIZON_DAYS = 60`: Verified reports older than 60 days are flagged as stale.
- `REPORT_TTL_DAYS = 90`: Unverified pending reports expire after 90 days.

---

## How to Run

### 1. Run Unit & Integration Tests
```bash
python -m pytest streetaccess/tests -v
```

### 2. Run API Server
```bash
python streetaccess/main.py --host 127.0.0.1 --port 8000
```
Interactive API documentation: `http://127.0.0.1:8000/docs`

