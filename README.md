# StreetAccess

**Transparent pedestrian condition comparison powered by human-verified community reports and survey recency.**

StreetAccess compares candidate walking routes using human-verified community reports about sidewalk conditions, surface disruptions, and physical barriers. It is designed to provide transparent, uncertainty-aware pedestrian information without creating a false sense of safety.

---

## Non-Negotiable Product Truth Boundaries

1. **No Guarantees of Safety or Accessibility**: StreetAccess **never** claims that a route is safe, accessible, or obstacle-free.
2. **Explicit UNKNOWN Handling**: The absence of a report means **`UNKNOWN`**, unless that segment has a recent, recorded survey.
3. **Verified Evidence Only**: Only **`VERIFIED`** community reports may affect active route comparisons. Draft, submitted, rejected, disputed, or expired reports are excluded from barrier counts.
4. **No Uncalibrated Physical Claims**: StreetAccess does not estimate real-world metric widths or calibrated severity from uncalibrated 2D smartphone images. Only coarse categorical passability (`clear`, `narrowed`, `blocked`, `unknown`) is recorded.
5. **Transparent Explanations**: Route trade-offs are presented deterministically (distance, walking time, survey coverage, itemized barriers, stale data). Arbitrary scalar "safety scores" that obscure underlying uncertainties are prohibited.

---

## Runtime Model Boundary

* **IDE Assistant Only**: Gemini 3.8 Flash serves strictly as the developer's Antigravity coding assistant. It is **not** used as a runtime perception model for StreetAccess in this MVP.
* **Provider-Neutral Interface**: All visual observation logic is abstracted behind the `PerceptionAdapter` interface.
* **Deterministic Fixtures**: The runtime uses `FixturePerceptionAdapter`, returning predictable, reproducible outputs backed by local fixtures. All mock observations are explicitly stamped with `is_mock=True` and `perception_source="fixture_mock"`.
* **Zero Model Credentials**: The codebase contains no cloud model SDKs, API keys, or `GEMINI_API_MODEL` runtime dependencies.

---

## Architecture Layout

StreetAccess is cleanly organized into separated, single-responsibility modules under `./streetaccess/`:

```
streetaccess/
├── config.py                 # Provisional thresholds (clearly documented hypotheses)
├── main.py                   # Server & CLI runner
├── perception/               # Provider-neutral vision abstraction
│   ├── adapter.py            # PerceptionAdapter abstract base class
│   ├── fixture_adapter.py    # Deterministic mock adapter backed by test fixtures
│   └── models.py             # Server-validated FrameObservation & NormalizedBoundingBox
├── verification/             # Human verification state machine & roles
│   ├── models.py             # CommunityReport, GeoPoint, AuditEvent, UserRole
│   ├── transition_table.py   # Declarative state transition rules & role authorization
│   └── service.py            # VerificationService coordinating transactions & audit
├── storage/                  # SQLite append-only audit persistence & entity storage
│   ├── db.py                 # SQLite connection & schema initialization
│   └── repository.py         # Transactional report & append-only audit repository
├── routing/                  # Pedestrian graph, spatial matcher & route comparator
│   ├── graph.py              # Synthetic pedestrian graph (segments & survey status)
│   ├── matcher.py            # Spatial matcher (CONFIDENT, AMBIGUOUS, UNMATCHED)
│   └── comparator.py         # Route trade-off comparator (with explicit UNKNOWN coverage)
├── api/                      # Minimal FastAPI HTTP server
│   └── app.py                # REST API endpoints for perception, reports, and routing
└── tests/                    # Deterministic test suite (pytest)
    ├── test_api.py           # End-to-end API client integration tests
    ├── test_matcher.py       # Spatial ambiguity & proximity tests
    ├── test_perception.py    # Bounding box & timing validation tests
    ├── test_routing.py       # Route trade-offs, coverage, & single-route badge tests
    └── test_verification.py  # Lifecycle, role checks, & append-only audit tests
```

---

## Core Systems

### 1. Perception & Server-Side Validation
* Validates normalized bounding boxes ($ymin, xmin, ymax, xmax \in [0.0, 1.0]$, ensuring $ymin \le ymax$ and $xmin \le xmax$).
* Enforces non-negative frame indices or timestamps.
* Controlled categories: `construction`, `surface_damage`, `temporary_obstruction`, `stairs_without_ramp`, `narrow_pathway`, `vegetation_overgrowth`, `parked_vehicle`, `debris_or_garbage`, `clear_sidewalk`, `other`.

### 2. Declarative Verification State Machine
* **States**: `SUBMITTED`, `PENDING_INDEPENDENT_REVIEW`, `NEEDS_MORE_EVIDENCE`, `VERIFIED`, `REJECTED`, `DISPUTED`, `EXPIRED`.
* **Separation of Roles**:
  * An **uploader cannot verify, reject, or triage their own report**. Self-verification attempts fail with an `InvalidTransitionError`.
  * **Dispute resolution** must be conducted by an independent `MODERATOR` who is distinct from the uploader, the prior verifier, and the disputer.
  * **TTL expiry** applies only to eligible pending states and is executed solely by the `SYSTEM` role.
* **Transactional Append-Only Audit Trail**:
  * Valid transitions atomically update the report state and append an immutable event to the `audit_events` table in SQLite.
  * Invalid transitions fail immediately without modifying state or polluting the audit log.

### 3. Spatial Matcher with Ambiguity Detection
* Preserves reported device GPS accuracy.
* Evaluates proximity against pedestrian network segments using geodesic perpendicular distances.
* Returns explicit confidence:
  * **`CONFIDENT`**: Exactly one candidate segment matches within tolerance, or the nearest is sufficiently isolated from alternatives.
  * **`AMBIGUOUS`**: Multiple candidate segments (such as parallel sidewalks or crosswalks) are within the ambiguity threshold. **Refuses to silently snap to one segment.**
  * **`UNMATCHED`**: No segments exist within the tolerance radius.

### 4. Transparent Route Trade-Off Comparator
* Computes survey coverage breakdown:
  * **`RECENT_SURVEY`**: Surveyed within the recency horizon.
  * **`STALE_ONLY`**: Surveyed, but past the recency horizon.
  * **`UNSURVEYED`**: No recorded survey; pedestrian conditions are explicitly marked as **`UNKNOWN`**.
* Only active **`VERIFIED`** reports contribute to verified obstacle counts (`blocked`, `narrowed`).
* Single candidate route queries return transparent itemized trade-offs without comparative badges.
* Multi-route queries provide side-by-side trade-offs with descriptive badges (e.g. `High Survey Coverage`, `Known Blockage Reported`).

---

## Provisional Hypotheses (Configurable Thresholds)

All thresholds in [`streetaccess/config.py`](file:///d:/Downloads/projects/StreetAccessAI/streetaccess/config.py) are treated as **provisional hypotheses**, not evidence-backed constants:

| Parameter | Provisional Value | Description |
|---|---|---|
| `SPATIAL_MATCH_DISTANCE_THRESHOLD_METERS` | `15.0m` | Search radius hypothesis for matching GPS points to pedestrian segments |
| `SPATIAL_AMBIGUITY_DELTA_THRESHOLD_METERS` | `5.0m` | Minimum distance delta required between nearest segments before flagging `AMBIGUOUS` |
| `BEARING_TOLERANCE_DEGREES` | `45.0°` | Maximum orientation discrepancy when walking bearing is present |
| `SURVEY_RECENCY_HORIZON_DAYS` | `30 days` | Age after which segment surveys degrade to `STALE_ONLY` |
| `REPORT_RECENCY_HORIZON_DAYS` | `60 days` | Age after which verified reports are categorized as stale |
| `REPORT_TTL_DAYS` | `90 days` | Expiration window for unreviewed pending reports |
| `DEFAULT_WALKING_SPEED_MPS` | `1.2 m/s` | Standard walking velocity hypothesis for travel time estimation |

---

## Getting Started

### Prerequisites
* Python 3.11+
* FastAPI, Pydantic, Uvicorn, and Pytest

### Running the Test Suite
Run all 20 unit and integration tests:
```powershell
python -m pytest streetaccess/tests -v
```

### Running the Local API Server
Start the Uvicorn web server:
```powershell
python streetaccess/main.py --host 127.0.0.1 --port 8000
```

Once running:
* **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Alternative ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health and active perception provider identity (`is_mock=true`) |
| `POST` | `/perception/analyze` | Deterministic fixture perception analysis |
| `POST` | `/reports` | Submit a new pedestrian condition community report |
| `GET` | `/reports/{report_id}` | Retrieve report state and attached observations |
| `POST` | `/reports/{report_id}/match-spatial` | Evaluate spatial match status (`CONFIDENT`, `AMBIGUOUS`, `UNMATCHED`) |
| `POST` | `/reports/{report_id}/transition` | Execute a declarative state transition with role validation |
| `GET` | `/reports/{report_id}/audit` | View immutable chronological audit trail for a report |
| `POST` | `/routes/compare` | Compare candidate pedestrian routes and itemize condition trade-offs |

---

## License & Privacy Notice

Do not collect or upload real-world street imagery or personal identifying information until formal consent, face/license-plate blurring, data retention, and deletion protocols have been approved.
