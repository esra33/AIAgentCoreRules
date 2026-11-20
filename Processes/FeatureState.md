# Shared feature-state protocol

## Authoritative feature state

`<feature-directory>/state.json` is authoritative. `<Name>_Progress.md` is a generated
human-readable projection, never an agent editing target. Any references below to editing
progress, its header, checkpoint, or gate blocks mean updating those logical fields through
the tool, not editing Markdown or JSON directly. This storage protocol supersedes legacy
Markdown-writing instructions and examples below.

Run the shared CLI from the project root, resolving `<state-tool>` to
`Tools/feature-state/feature_state.py` under AIAgentCoreRules:

- Read only the needed data: `python3 <state-tool> get <feature-directory> --section checkpoint`
  (omit `--section` for operational state; `legacy_notes` are excluded by default).
  Use `--section legacy_notes` or `--include-legacy` only when historical raw text is needed.
  Read the current `revision`
  before each mutation.
- Write an exact JSON payload to a temporary file, then run
  `python3 <state-tool> <operation> <feature-directory> --payload <file> --revision <N>`.
  A revision conflict means reread and reconcile; never blindly retry old values.
- Existing Markdown without state: report migration required. Run `migrate <feature-directory>`
  for a dry run; apply explicitly with `--apply` only within an authorized migration.
  Never silently convert or recreate an existing feature.
- Session membership is a `sessions` list update through `checkpoint`; preserve existing
  entries and deduplicate by session id8. Do not invent unavailable session metrics.
- Ordinary checkpoint updates may include `checkpoint`, `step_status`, `tdd_sections`,
  `artifacts`, `sources_of_truth`, `sessions`, and active `status`. Preserve fields not being
  changed. Checkpoint content follows the process and engineer acknowledgments below.
- Gates use `gate` with `phase_completed`, `gate_confirmed_by`, `next_phase` and the handoff
  details. `phase_completed` uses a label beginning with `Phase N` (for example, `"Phase 7 — Verification"`),
  not the machine key used by `current_phase`; `next_phase` uses the exact next machine key
  (for example, `"8_retrospective"`). Phase 8 omits `next_phase` and completes the feature.
  Call only after explicit engineer approval; never rewrite or duplicate prior gates.
- PR linkage uses `pr` with `{"phase":"V0","number":123}`. Batch updates use `batch` with
  `{"task_id":"T1","value":{...}}`; preserve the complete existing batch value.
- Task status uses `task` with `id` and `status` (`todo`, `partial`, `done`), retaining task
  metadata. The payload may also include `title` (and other task fields); it is merged into the
  existing entry by `id`, never replacing the whole task list. There is no delete: retiring a
  task-list row means repurposing its id for new work (new `title`/`status`), not removing it.
  Artifact roles use `artifact` with `role` and a feature-relative `path`.
- Each successful mutation regenerates Progress Markdown. Do not parse it back into state.

Lifecycle skills retain all engineer approvals. Pass payloads as JSON objects, never inline shell substitutions.


## Field consumers

For each top-level `state.json` key: which operation/skill writes it, and which skill or tool
reads it back for display or resume. Check here before adding a new field or a new reader —
most additions need both a writer op and a resume-work/progress_view.py reader, and missing
either one was the root cause of two Corrections in the 2026-11-18 retro that added
`tasks[].table_approved`/`artifact_roles`.

| Key | Writer(s) | Reader(s) | Notes |
| --- | --- | --- | --- |
| `schema_version` | `create` | `validate_state` only | No skill displays it. |
| `revision` | `create`; every mutating op (+1) | every skill via `get` before mutating | Optimistic-concurrency token. |
| `feature` | `create` | progress_view.py, resume-work, project_server.py, `list_features` | Must equal the feature directory name. |
| `current_phase` | `create`; `gate` | progress_view.py, resume-work, `list_features`, project_server.py | `checkpoint`'s own wording suggests it also updates this; its `allowed` set does not — treat as `gate`-only. |
| `status` | `create`; `checkpoint`; `gate`; `close`/`reopen` | progress_view.py, resume-work, active-features, close-feature/reopen-feature, `list_features` | |
| `updated_at` | auto-stamped by every mutation | active-features, resume-work drift check, `list_features` sort | Never set directly by a payload. |
| `artifacts` | `checkpoint`, `phase-report`, `milestone-report`, `artifact` | `validate_state` path-safety check only | Not rendered by any skill; resume-work reads `checkpoint.done` instead. |
| `sessions` | `checkpoint`, `feature-pr`, `close-feature`, `reopen-feature` | resume-work, publish-batch, feature-pr, perf_view.py | Deduplicated by session id8. |
| `sources_of_truth` | `checkpoint` | resume-work (local-first drift note) | |
| `pull_requests` | `pr` (feature-pr, publish-batch) | progress_view.py, feature-pr | Keyed by `V<n>` phase. |
| `batches` | `batch` (publish-batch) | progress_view.py, publish-batch's own `get` | |
| `step_status` | `checkpoint`; cleared by `gate` | progress_view.py step badges | |
| `tdd_sections` | `checkpoint`; cleared by `gate` | progress_view.py section badges | |
| `checkpoint` | `checkpoint`; cleared by `gate` | resume-work, progress_view.py, `list_features` summary | |
| `gates` | `gate` | progress_view.py, resume-work, `render_progress` | `gate_confirmed_by`/`phase_completed` are per-record fields, not top-level keys. |
| `closed` | `close`/`reopen`; `migrate` | `render_progress`; reopen-feature re-parses that generated text | |
| `tasks` | `task` | progress_view.py (`task_table_approved`, task states) | `tasks[].table_approved` is set via `task`; read by progress_view.py and resume-work's Task Table Proposal resume rule. |
| `artifact_roles` | `artifact`; `migrate` (filename-convention defaults) | resume-work (reload a persisted per-task artifact by role); project_server.py tabs | Any new per-task artifact needs a role here or resume-work re-derives it from the TDD instead of reusing the file. |
| `phase_reports` | `phase-report` | `gate` (required for phases ≥2); project_server.py tabs | Not read by progress_view.py's Progress tab. |
| `milestone_reports` | `milestone-report` | project_server.py tabs | Ad hoc, e.g. a V-stage summary. |
| `integration_checklist` | `integration-checklist` (Phase 6 only) | progress_view.py Phase 6 card | Restricted to active Phase 6. |
| `legacy_notes` | `migrate` | `render_progress`; `get --section legacy_notes` | Excluded by default from `get` and from mutation return payloads. |

## Integration checklist

The optional `integration_checklist` ordered list defaults to empty for historical features.
Each item has a unique nonempty string `id`, nonempty string `title`, `status` of `todo`,
`in_progress`, `done` or `not_applicable`, and string `notes`. At most one item is
`in_progress`; `not_applicable` requires a nonblank reason in `notes`.

Read it with `get <feature-directory> --section integration_checklist`. Replace only this
list through `integration-checklist <feature-directory> --payload <file> --revision <N>`
using an exact object `{"items": [...]}`. This operation is restricted to active Phase 6
(`in_progress` or `at_gate`); stale revisions and invalid items leave state and generated
Progress unchanged. Reconcile before retrying. The agent updates the checklist as the
engineer walks through items; preview progression is read-only. Gate 6 still requires
explicit engineer approval. Checklist history survives gate transitions. Missing historical
checklists display “Checklist not recorded”; never infer prior outcomes. Generated Progress
includes the ordered checklist and notes; do not edit it directly.
