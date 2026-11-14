# Feature state

`state.json` in each feature directory is authoritative. The tool generates `<Name>_Progress.md` for human review; edits to that projection are overwritten. Runtime uses Python's standard library only.

Resolve the feature root first (run these examples from the project root; replace `<core>`
with the actual AIAgentCoreRules path):

```bash
features_root=$(python3 <core>/Tools/setup/project_config.py --project . get features)
python3 <core>/Tools/feature-state/feature_state.py list --root "$features_root"
python3 <core>/Tools/feature-state/feature_state.py get "$features_root/Example" --section checkpoint
python3 <core>/Tools/feature-state/feature_state.py create "$features_root/Example"
python3 <core>/Tools/feature-state/feature_state.py checkpoint "$features_root/Example" --revision 1 --payload /tmp/checkpoint.json
```

All mutating commands require the revision returned by `get`. A stale revision fails without writing; re-read the selected feature, reconcile your update, then retry. Writes lock a stable side file, validate the entire state, and atomically replace JSON. Reads never modify state. `render DIR --revision N` repairs the Markdown projection without changing the revision.

`list` returns compact summaries, including legacy active features marked `migration_required`. A malformed feature is isolated as an error entry. `get` omits bulky `legacy_notes` by default; read them only explicitly with `--section legacy_notes` or `--include-legacy`. Mutation responses also omit that preserved text.

## Schema version 1

The state preserves the established feature fields: `feature`, `current_phase`, `status`, `updated_at`, `artifacts`, `sessions`, `sources_of_truth`, `pull_requests`, `batches`, `step_status`, `tdd_sections`, and `checkpoint`. It adds `schema_version`, `revision`, `gates` (ordered handoff objects), `closed` (ordered lifecycle history), `tasks`, `artifact_roles` (feature-relative paths), and `legacy_notes`.

Task objects contain an `id` such as `T1`, a `status` of `todo`, `partial`, or `done`, and optional title/assignee/description fields. Artifact paths cannot be absolute or escape the feature folder. Complete features cannot be reopened or mutated.

Commands accept a JSON payload file:

- `checkpoint`: any of `checkpoint`, `step_status`, `tdd_sections`, `artifacts`, `sessions`, `sources_of_truth`, and active `status`.
- `gate`: `phase_completed`, `gate_confirmed_by`, `next_phase`, and handoff details. `phase_completed` is a label beginning with `Phase N` matching the current phase (for example, `"Phase 7 — Verification"`), not its machine key. `next_phase` is the immediate successor machine key (for example, `"8_retrospective"`), as used by `current_phase`. Duplicate gate records are refused. For Phase 8 only, omit `next_phase` (or use null) to complete the feature. Appends the gate and clears checkpoint/step/section state. Engineer confirmation must already have occurred; the tool cannot verify chat approval.
- `close`: closing `status` and engineer-provided `reason`; appends history without changing checkpoint/gates.
- `reopen`: optional `reason`; only abandoned/superseded/on-hold features can reopen.
- `pr`: `phase` such as `V0` and positive integer `number`.
- `batch`: `task_id` and `value` containing the existing batch fields.
- `task`: `id`, `status`, and any other task fields; merges with the existing task.
- `artifact`: `role` and feature-relative `path`.

## Explicit migration

```bash
python3 <core>/Tools/feature-state/feature_state.py migrate "$features_root/Example"
python3 <core>/Tools/feature-state/feature_state.py migrate "$features_root/Example" --apply --expected-fingerprint <dry-run-fingerprint>
python3 <core>/Tools/feature-state/feature_state.py migrate --root "$features_root"
python3 <core>/Tools/feature-state/feature_state.py migrate --root "$features_root" --apply
```

Without `--apply`, migration performs no writes. A fingerprint allows a single-feature apply to reject changes since the reviewed dry-run. Every apply also rechecks its source snapshot before committing. Project migration processes each feature separately and reports any blocked features.

The importer supports the template's bounded YAML subset rather than general YAML. A single-line flow list or mapping is supported; one wrapped over several lines is not, so join it onto one line. Older TaskList ids such as `{id: 1}` import as `T1`, and a `#` inside a quoted value is kept rather than read as a comment. Unsupported syntax, conflicting TDD/TaskList statuses, multiple progress sources, and escaping comment targets block the feature without writes. Resolve those source ambiguities and rerun. Original progress and sidecars are retained byte-for-byte under `legacy-backup`; full legacy progress text is also retained in `legacy_notes` so custom notes are not discarded.

Feature names must match their containing directory. Existing backup files with different content block migration; they are never silently reused or overwritten.

Legacy document sidecars merge into feature-level `review.json`. Every thread keeps its replies, status, and anchor, receives a unique feature-local ID, and records its original sidecar/ID in `migration_origin`. Paths are rebased to the feature directory. Legacy source sidecars remain untouched. An already migrated feature is skipped; rerunning does not overwrite newer JSON state. If an interrupted migration left `review.json` without `state.json`, migration refuses to overwrite it and requires inspection/recovery.

## Tests

```bash
python3 -m unittest discover -s Tools/feature-state/tests -p 'test_*.py'
```

The resolver honors `SESSION_FEATURES_ROOT`, then `paths.features` in the project's
`ai-agent-core.json`, then the legacy `Assets/GitIgnoreAssets/Features` default. Configuration
changes do not relocate existing features. Move complete feature directories explicitly,
preserving `state.json`, generated Progress Markdown, `review.json`, relative anchors, and
existing Unity `.meta` files. Keep `.feature-state.lock` local and out of Git.


`phase-report` accepts phases 2–8. Gate 8 requires a registered Phase 8 report before completion. This is a mutation-time requirement; previously completed feature state remains readable without migration or a retroactive report.


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
