---
name: street-access-builder
description: Builds StreetAccessAI as a standalone project with provider-neutral mock perception, human-reviewed reports, uncertainty-aware route comparisons, and staged evaluation. Use for planning, implementation, or review of StreetAccessAI.
---

# StreetAccessAI Builder

Use this skill only for the StreetAccessAI repository. First inspect its current files and repository instructions. Preserve existing work and conventions; do not assume a framework or scaffold until you inspect the repo.

## Product definition and safety boundary

StreetAccessAI compares available walking-route options using community reports about pedestrian conditions. It does not certify that a route is safe, accessible, or obstacle-free. No report means UNKNOWN unless the segment has a recent, recorded survey.

Perception output is an unverified observation. It must never affect route comparisons until a report passes the verification workflow. User-facing explanations must be derived from persisted verified records and deterministic application logic, not free-form model output.

## IDE model versus product runtime

- The model selected in Antigravity is the coding assistant only. Do not configure or change it from application code.
- For the initial product implementation, define a provider-neutral `PerceptionAdapter` and use a deterministic mock/fixture adapter.
- Do not add Gemini or another model API call, model API key, `GEMINI_API_MODEL`, cloud-model setting, or provider-specific runtime dependency in the MVP.
- Keep observation DTOs and validation independent of any model SDK. A future provider adapter requires the user to choose the model and explicitly request integration.
- Mark fixture-derived observations as mock data in API responses and UI. Never present a mock observation as real street evidence.

## Repository and architecture

- Keep all work in this repository. Do not refer to or modify ReturnsSheildAI/ReturnsShield files.
- Preserve the repository's established language, framework, and conventions where possible. If the repository is empty, propose a minimal stack and directory layout before scaffolding.
- Separate perception, verification, routing, evaluation, and API responsibilities. Use typed contracts and narrow interfaces.
- Make changes incrementally. Summarize the intended files and behavior before each stage; avoid unrelated refactors.

## Observation and data contracts

Represent findings as frame-level observations with a valid frame index or timestamp, category, coarse passability (`clear`, `narrowed`, `blocked`, `unknown`), normalized bounding box when applicable, and concise factual evidence text. Validate frame references, box ordering, and coordinate bounds server-side.

Do not infer metric width, calibrated severity, GPS confidence, or cross-frame identity from mock/VLM output. Keep sensor accuracy, visual observation confidence, and route-segment match confidence as distinct fields.

Use an explicit dataset manifest and documented group-level split strategy. Check each dataset's actual labels, annotation coverage, and license. Treat SANPO as a baseline only for classes and conditions it actually annotates; it does not establish accuracy for India-specific obstacle classes without corresponding labels.

## Verification invariants

Use explicit states and a declarative transition table. Support uploader confirmation, pending independent review, needs-more-evidence, verified, rejected, disputed, and expired states where these fit the MVP.

- Enforce authorization on the server; never trust a client-supplied role.
- An uploader cannot verify their own report.
- Only VERIFIED reports may enter route comparisons.
- Dispute resolution must use an authorized moderator distinct from the uploader, prior verifier(s), and disputers.
- TTL expiry is allowed only from explicitly eligible states.
- Invalid transitions must fail without mutating state or adding an audit event.
- Persist transitions transactionally. Use append-only audit persistence where practical; do not call a mutable in-memory list immutable.

## Spatial matching and route comparisons

Start with a synthetic pedestrian graph and deterministic fixtures. A spatial matcher must return `CONFIDENT`, `AMBIGUOUS`, or `UNMATCHED`; never silently attach a report to one of multiple plausible parallel sidewalks or roads. Preserve GPS accuracy and treat bearing as supporting evidence, not an unquestioned hard filter.

Define surveyed coverage by route-segment length and survey state. Distinguish `UNSURVEYED`, `STALE_ONLY`, and recently surveyed evidence. Do not treat lack of reports as evidence that a segment is clear.

Present transparent trade-offs such as estimated time, recent verified barriers, stale reports, and unknown coverage. Avoid arbitrary composite scores. When only one route is available, do not show comparative badges.

Do not enable live Google Routes integration until the synthetic comparator and spatial matching are reviewed. Before displaying Google walking routes, include the required walking-route beta warning and follow current Maps attribution, display, and caching policies.

## Evaluation, privacy, and completion

Keep perception evaluation separate from verification and route ranking. Match each metric to available ground truth: box metrics need box annotations, mask metrics need masks, and tracking metrics need per-frame identity annotations. Do not claim a benchmark validates classes or metrics it does not contain.

Evaluate routing first on synthetic cases with known expected trade-offs, including stale evidence, ambiguous matches, low coverage, and single-route responses. Clearly distinguish synthetic evaluation from field validation.

Before collecting or uploading real street imagery, define consent, face/license-plate handling, retention, and deletion behavior. Never silently upload video.

At the end of each stage, report changed files, key decisions, how to run the project, evaluation performed, and remaining limitations. Do not add live model integration, live navigation, or real-data collection unless the user requests it.
