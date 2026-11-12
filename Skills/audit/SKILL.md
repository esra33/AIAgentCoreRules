---
name: audit
description: Independent judgement review of changed C# files - single responsibility, interface boundaries, resource symmetry, method design and host project rules - reported with file:line. Runs as a fresh subagent, once per plan step or publish batch, never as a self-review by the context that wrote the code. Use at a process's audit checkpoint, in Phase 7 verification, or when the engineer runs /audit (e.g. before a PR).
argument-hint: "[file ...]  (default: changed .cs files)"
context: fork
agent: general-purpose
model: sonnet
---

# Audit

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
MetaRouter.md).

The reviewer is not the author. The mechanical tags are already enforced by tools; this brief is
the judgement the tools cannot make.

```yaml
how_to_run:   # the caller's side
  fresh_subagent: "Invoke /audit <files> with the Skill tool. The frontmatter (context: fork) runs it as a fresh subagent that sees only CLAUDE.md and this brief, never the conversation (verified 2026-11-11). It runs in the background: wait for its notification before the step that depends on it. Never apply this brief inline in the context that wrote the code — that is a self-review, and /end-session counts it as a skipped audit."
  by_hand:        "The engineer runs /audit the same way, e.g. before a PR."
  cadence:        "Once per LargeTask plan step, SmallTask/BugFix 5b checkpoint, or /publish-batch batch — over all of its changed C# files in one run, not per file. Phase 7: once over every file the feature touched."
  fan_out:        "More than 8 files → the audit subagent splits them across Agent subagents (groups of files, this same brief) and merges their reports into one."
  mechanical:     "[EXPLICIT] [ALLMAN] [ACCESS] [FIELD] [DI] [LOG] [ASYNC] (async void shape) are cslint's: the PostToolUse hook runs it on every .cs edit. Run `python3 <core>/Tools/unity-tools/cslint.py <files>` first and include its output in the report; do not re-derive those tags by reading."
  typecheck:      "Not this brief's job — the session hooks take the baseline and block the stop until it has run."

scope:
  files:   "$ARGUMENTS, or every changed .cs file from `git status --porcelain` when empty"
  load:    [Rules/CodingStandards.md, Rules/ArchitecturalPrinciples.md, Rules/ResourceManagementRules.md, Rules/CoreTags.md]
  also:    "The host project's always-on rules (its CLAUDE.md imports) and, for a test file, Rules/TestingRules.md plus the host testing setup. Read each file in full; read a called method's body before judging its use."
checks:   # judgement only
  - "[SRP] one reason to change per class and method; a name that needs 'And' → split"
  - "[IFACE] no cast to a concrete type inside a high-level system; a dependency is the narrowest interface that serves"
  - "[RES] [SYM] every acquisition (subscription, load, timer, guard) released in the same scope; subscribe/unsubscribe in the same method pair"
  - "[ASYNC] judgement: an allowed async void (override bridge, handler) has a full try/catch; no fire-and-forget Task discards; ordering in multi-step flows"
  - "Method design: composers sequence only, leaves touch data only; method order public override → public → protected → private; naming"
  - "[GEN] no hand edits to generated files"
  - "Host rules: debug/mock/test-helper code inside #if !RC; Logger channel setup (attribute + const + field); config through the host's loader; [LOG] catch shape (Breadcrumb vs Error + Exception)"
```

Report:

```yaml
audit_report:
  files_checked:  []
  cslint:         "output of the cslint run, or 'clean'"
  violations:     # rule tag · file:line · what · minimal fix
    - ""
  clean:          []
```

Report only. Do not edit unless the engineer asks; when fixing, apply [SURG] — change only the
violating lines.
