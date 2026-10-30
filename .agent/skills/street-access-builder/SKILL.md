---
name: street-access-builder
description: Builds StreetAccess with a swappable perception adapter, human-reviewed reports, uncertainty-aware route comparisons, and evaluation gates. Use when planning, implementing, or reviewing StreetAccess.
---

# StreetAccess Builder

Use this skill for StreetAccess work. Keep the existing ReturnsShield application unchanged; create StreetAccess in its own `streetaccess/` directory unless the user explicitly directs otherwise.

## Product boundary

StreetAccess compares walking-route options using community reports about pedestrian conditions. It does not certify that a route is safe, accessible, or obstacle-free. A missing report means `UNKNOWN` unless that segment has a recent, recorded survey.

Model output is an unverified observation. It must never enter the active route evidence set until the report passes the verification workflow. Route explanations must be generated from persisted, verified records and deterministic application logic, not from free-form model output.

## Runtime model boundary

- Antigravity's coding-agent model is an IDE setting. Do not configure or change it from application code.
- Do not assume a product perception provider has been selected. The initial implementation must use a `PerceptionAdapter` interface and a deterministic/mock adapter backed by fixtures.
- Do not add Gemini runtime calls, API keys, `GEMINI_API_MODEL`, cloud model configuration, or provider-specific dependencies in the MVP.
- Keep observation DTOs and validation provider-neutral. A future provider adapter may be added only after the user selects a runtime model and approves that implementation scope.
- The mock adapter must return stable outputs for the same fixture and support malformed/empty input cases. It must be clearly marked as mock data in the API and UI.

## Architecture and data rules

Keep modules separate for `perception`, `verification`, `routing`, `evals`, and `api`. Use typed request/response models and explicit interfaces between modules.

Represent perception as frame-level observations. Each observation must include a valid frame index or timestamp, category, coarse passability (`clear`, `narrowed`, `blocked`, `unknown`), normalized bounding box when applicable, and visual evidence text. Validate box order and bounds server-side. Do not request metric widths, calibrated severity, GPS confidence, or cross-frame track IDs from a VLM.

Treat GPS, bearing, visual location, and route-segment match confidence as separate evidence fields. Preserve reported GPS accuracy. A matching algorithm must be able to return `CONFIDENT`, `AMBIGUOUS`, or `UNMATCHED`; never silently snap an ambiguous report to one of multiple nearby sidewalks or parallel roads. Do not hard-code buffer sizes, bearing thresholds, decay half-lives, or coverage thresholds as validated facts. Keep provisional values configurable and document them as hypotheses.

Use a documented dataset manifest and group-level split strategy. Avoid near-duplicate leakage across train/validation/test. Verify the actual labels, annotation availability, and license of every dataset before relying on it. Treat SANPO as a baseline for the labels it actually contains; do not claim it validates India-specific obstacle classes unless those classes are annotated.

## Verification workflow

Use explicit states and a declarative transition table. At minimum support uploader confirmation, pending independent review, needs-more-evidence, verified, rejected, disputed, and expired states.

- Enforce role checks on the server; client-provided role names are not authorization.
- An uploader cannot verify their own report.
- A report can affect route comparisons only in `VERIFIED` state.
- Dispute resolution must be performed by an authorized moderator who is distinct from the uploader, prior verifier(s), and disputers.
- TTL expiry must apply only to eligible states and must record a valid transition.
- Reject invalid transitions without mutating the report or appending a misleading audit event.
- Persist transitions transactionally. Make the audit trail append-only at the storage layer where practical; do not describe a mutable in-memory list as immutable.

## Route comparison

Start with a synthetic pedestrian graph and deterministic evidence fixtures. Make route trade-offs explicit (for example, estimated time, recent verified barriers, stale reports, and surveyed coverage). Do not combine arbitrary units into an unexplained score. Do not describe a route as clear because no reports exist.

Define coverage from route-segment length and survey state. Distinguish `UNSURVEYED`, `STALE_ONLY`, and recently surveyed conditions. If only one candidate route is returned, do not show comparative badges. Show the Google walking-route beta warning whenever Google walking routes are displayed, and follow the current Maps API attribution, display, and caching policies before enabling that adapter.

## Evaluation and delivery

Keep perception evaluation separate from report verification and route ranking. Match metrics to available labels: use box metrics only when box annotations exist, mask metrics for masks, and tracking metrics only when per-frame object identity ground truth exists. Do not claim a dataset supports a metric it cannot support.

For route evaluation, use synthetic scenarios with explicit expected trade-offs and report unknown coverage. For local data, document consent, PII blurring, retention, and deletion behavior before collection or upload. Never silently upload video.

Work incrementally. First inspect the repository and report the proposed file plan. Implement only the next stage, keep the application runnable, and explain assumptions or blockers. Do not change unrelated ReturnsShield files. Do not add production model integration or live navigation until the user requests it.
