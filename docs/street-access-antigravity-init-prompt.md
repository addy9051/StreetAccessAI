# Antigravity project initiation prompt

```text
I want to start a new project called StreetAccess in this workspace.

First inspect the repository and the StreetAccess Builder skill at
.agent/skills/street-access-builder/SKILL.md. The repository currently contains
an existing ReturnsShield application. Do not modify, move, or delete its files.
Create StreetAccess as a separate project under ./streetaccess/.

Important model boundary:
- Gemini 3.8 Flash is my Antigravity coding assistant only.
- Do not use Gemini 3.8 Flash, another hosted model, or any model API as the
  StreetAccess runtime perception system in this MVP.
- Do not add model API credentials, GEMINI_API_MODEL, or provider-specific
  runtime dependencies.
- Define a provider-neutral PerceptionAdapter interface and implement only a
  deterministic mock/fixture adapter. Mark all mock observations clearly.
- Keep the interface ready for a future perception provider, but do not choose
  or integrate one without my later instruction.

Product scope:
StreetAccess compares candidate walking routes using human-verified community
reports about pedestrian conditions. It must never claim that a route is safe,
accessible, or obstacle-free. No report means UNKNOWN unless the segment has a
recent recorded survey. Only VERIFIED reports may affect route comparisons.

Build incrementally in this order. Do not scaffold the entire product at once.

Stage 1 — inspect and plan:
1. Summarize the repository structure and identify any instructions that apply.
2. Propose the StreetAccess directory layout, data contracts, and a small
   implementation plan. Do not edit files yet in this stage.
3. Keep this project isolated under ./streetaccess/.

Stage 2 — deterministic core:
After presenting the Stage 1 plan, implement a minimal runnable foundation in
./streetaccess/ containing:
- typed frame-level observation and report models;
- a PerceptionAdapter interface and deterministic fixture adapter;
- server-side validation for frame indices, timestamps, categories, and
  normalized bounding boxes;
- explicit UNKNOWN handling;
- a declarative report state-transition table and role checks;
- append-only audit persistence appropriate for a local MVP;
- a synthetic pedestrian graph and transparent route trade-off comparator.

Do not add Google Routes, maps display, video upload, user accounts, live
crowdsourcing, or any runtime model integration in this stage.

Stage 3 — evaluation and review:
Add focused checks for valid and invalid state transitions, uploader/reviewer
separation, malformed observations, ambiguous spatial matches, unknown route
coverage, stale reports, single-route responses, and deterministic route
comparisons. Keep evaluation separate from the mock perception results. Do not
pretend synthetic or mock data demonstrates real-world model accuracy.

Engineering requirements:
- Use the simplest stack that fits the repository and document how to run it.
- Keep modules separate for perception, verification, routing, evaluation,
  and API.
- Use configurable provisional thresholds; label them as hypotheses, not
  evidence-backed constants.
- Do not estimate real-world width or severity from uncalibrated images.
- Do not silently match a report to one route when multiple nearby segments
  are plausible; return CONFIDENT, AMBIGUOUS, or UNMATCHED.
- Do not let an uploader verify their own report. Invalid transitions must
  fail without changing state or creating an audit entry.
- Explanations shown to users must be generated deterministically from
  verified records and clearly distinguish stale, unknown, and surveyed data.
- Do not collect or upload real street imagery until consent, privacy handling,
  retention, and deletion behavior are specified.

At the end of each stage, summarize files changed, key decisions, how to run
the project, and remaining limitations. Stop after Stage 2 and wait for my
review before proceeding to Stage 3.
```
