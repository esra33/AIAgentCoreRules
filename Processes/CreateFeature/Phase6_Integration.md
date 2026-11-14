## apply: on-demand — loaded by [[CreateFeature/index]]

# Phase 6 — Integration

Goal: Wire the feature into all systems identified in Phase 2. Report each step as it is completed.

---

## Integration Checklist

```yaml
integration_checklist:
  - Registered in all required factories, registries, and manifests.
  - Required code-generation tools executed (parsers, compilers, publishers, conflict resolvers).
  - "[GEN]"
  - Existing callers or dependent systems updated if a public contract changed.
```

---

### Persisted item walkthrough

Before verification, turn the categories above into concrete, ordered checks for this feature.
Initialize `integration_checklist` with the feature-state CLI; never edit state.json or generated
Progress Markdown directly. Include compile/manual checks needed for this feature. A category
can require several concrete items; mark an irrelevant item `not_applicable` with an explanation.

Use `integration-checklist <feature-directory> --payload <file.json> --revision <N>` with
`{"items":[{"id":"factory-registration","title":"Verify factory registration","status":"in_progress","notes":""}]}`.
Read the current revision and preserve the entire ordered list in each replacement payload.
Each item requires a unique nonempty id, nonempty title, status and string notes. Statuses are
`todo`, `in_progress`, `done` and `not_applicable`; only one item can be `in_progress`.

Walk through one item at a time: mark it `in_progress`, report the check/evidence, then record
`done` or explained `not_applicable` and move to the next item. Record results or exact manual
instructions in notes. For an Editor action, wait for the engineer's actual result before
marking it done. Plan shows current item, ordered outcomes, completed/remaining counts and
expandable evidence. The browser is read-only for progression; CLI updates refresh it.
Historical features without item data show “Checklist not recorded”; never reconstruct old
outcomes from a passed gate. Preserve the checklist after Gate 6.

## Gate 6 — Integration Verified

Run `/audit` on every C# file this phase changed (registrations, installers, updated callers);
generated files are excluded ([GEN]). Then run the host compile check (TripleMatch: `typecheck.py`) and report its result. Editor-only
generators (e.g. ParserGeneratorWindow) are run by the engineer — list them with exact menu paths.

Once all integration steps are verified, generate an integration summary as `[FeatureName]_Integration.md`
covering each checklist item and its completion status. Register it:

```
python3 Tools/feature-state/feature_state.py phase-report <feature_dir> \
  --payload '{"phase": "6_integration", "path": "[FeatureName]_Integration.md"}' \
  --revision <N>
```

Resolve every recorded item and summarize accepted deferrals before presenting the report
for engineer approval. Checklist progress does not approve Gate 6.

Confirm with the engineer that all integration steps are complete and the project compiles without errors.
