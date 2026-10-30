# [FeatureName] — Progress

Resume state for the CreateFeature process. Written at every gate and by `/checkpoint`; read by
`/resume-work [FeatureName]`. Keep it short — it is reloaded at the start of every session.

```yaml
feature:        "[FeatureName]"
current_phase:  "1_intake"          # phase key from CreateFeature/index.md
status:         "in_progress"       # in_progress | at_gate | complete | abandoned | superseded | on_hold (last three: /close-feature, undone by /reopen-feature)
updated_at:     ""                  # ISO timestamp of the last write
artifacts:      []                  # files in this folder the next phase needs, e.g. [FeatureName]_TDD.md
sessions:       []                  # session folder names that worked on this feature — Phase 8 reads these
sources_of_truth: []                # documents edited outside this folder, with the version last read, e.g.
                                    #   - {kind: confluence, id: "4787830785", title: "<Feature> TDD", version: 14}
                                    # /resume-work compares versions; update the version at every /checkpoint and gate
pull_requests:                      # Phase 4: PR numbers per TDD V-phase; the doc-review Progress tab shows their comments, e.g.
                                    #   V0: [9923, 9930]
batches:                            # Phase 4: per task id, written by /publish-batch; batch <merged + 1> of <len(plan)> is current, e.g.
                                    #   T3:
                                    #     branch:  "feature/[FeatureName]/T3"
                                    #     base:    "user/<engineer>/<branch>"
                                    #     plan:    ["IFooService + data types", "FooManager + tests", "Registration glue"]
                                    #     merged:  1
                                    #     open_pr: 9941
                                    #     prs:     [9930, 9941]
step_status:                        # current phase's steps by key (1a, Step 3, Category 2): in_progress | done; reset when a phase starts
                                    #   1b: in_progress
tdd_sections:                       # Sub-phase 1b: TDD section → drafting (written, not yet agreed) | approved (engineer agreed)
                                    #   Objective: approved
                                    #   Architecture: drafting
```

---

## Checkpoint

Where work stopped inside the current phase. Replaced (not appended) on every `/checkpoint`;
cleared when the phase's gate passes.

```yaml
checkpoint:
  saved_at:          ""
  done:              []   # steps / files completed and engineer-acknowledged this phase
  in_flight:         ""   # the step or file being worked on, and how far it got
  next:              ""   # the very next action on resume
  pending_decisions: []   # questions waiting on the engineer
  context_notes:     []   # facts learned this phase that are not yet in any artifact
```

---

## Gates Passed

One `phase_handoff` block per gate, appended in order. Never edit a past block — record a
reversal as a new note in the current checkpoint.

<!-- gate blocks are appended below this line -->
