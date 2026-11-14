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
