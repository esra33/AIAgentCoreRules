## apply: always

# Stop and Verify Protocol

Run before generating any code. If a check fails, look the missing piece up yourself first (Read, codeindex, /discover). Stop and ask only when it cannot be found.
Tag definitions: [[CoreTags]]

---

## Scope Gate — before exploring, not just before generating

Fires when the request is for a **tool, script, report, or utility**. One question, asked before any
exploration, because the wrong answer discards the exploration too.

```yaml
scope_gate:
  - "[SHAPE] Is the deliverable a one-off answer, or a reusable tool? Ask — do not infer."
  - "[SHAPE] If a tool: where does it run — Editor, runtime, or CLI? This constrains the assembly and the base class."
  - "[SHAPE] If exploration would already answer the question, say so and offer the answer first."
  - "[SHAPE] Skip when the request names an existing tool to extend (e.g. 'add a tab to the preview server'): its location and reusability are already given; state that in the 1_scope restatement instead."
```

Ask it as a plain question and wait. Do not resolve the ambiguity by building both, by planning
the larger one, or by picking the more impressive one.

> Exploration undertaken to scope a tool is often already the tool's output. Check before
> designing the thing that would reproduce work you have just done.

## Pre-Generation Checklist

```yaml
pre_generation:
  - "[CTX] Inventory every interface, class, enum, and base type the solution requires. Confirm each is present in context."
  - "[SIG] Locate every property, method, and field you intend to use in the provided source text."
  - "[BEHAV] Every runtime behaviour the code relies on (copy vs reference, platform support, accepted formats, argument order) is grounded, not assumed."
  - "[SO]  Verify Unity ScriptableObjects use CreateInstance<T>(), never new T()."
  - "[ASYNC] Every new or changed ConfigureAwait(false) must pass the Thread-Affinity Gate below before generating the affected code."
```

## Thread-Affinity Gate — every new or changed `ConfigureAwait(false)`

**Hard rule [ASYNC]: do not add or change a `ConfigureAwait(false)` site until its continuation
is proven safe on every possible execution thread.** Check the following before generating
the affected code and verify them again before presenting it:

- Establish the entry thread/context and trace the continuation through called helpers,
  injected callbacks, events, and `catch`/`finally` cleanup. A helper or delegate can hide a
  thread-affine Unity, Editor, UI or other host API access.
- After this await, no thread-affine access is permitted unless an explicit, verified
  dispatch restores the required thread/context before that access. Otherwise retain ordinary
  `await` on a known required context or separate context-independent work from the host
  continuation. If thread ownership cannot be established, stop the affected change and
  resolve it before generating code; do not assume the path is safe.
- `ConfigureAwait(false)` suppresses context capture for that await; it does not force a
  worker thread. An already-completed task can continue inline. `Task.Run` does not make
  Unity API access safe on a worker, and a callee's configuration does not override its
  caller's separate await. Check both inline completion and suspended continuation paths.
- Check cancellation registrations and disposal independently: `CancellationTokenSource.Cancel`
  invokes callbacks synchronously on the cancelling thread. Do not place contended locks,
  blocking cleanup, or incorrectly threaded host access in a cancellation callback and assume
  the enclosing worker/await boundary protects the caller. Signal an owned async flow when
  cleanup must run elsewhere, and observe that flow through completion.
- Include a brief thread-ownership rationale in the review/checkpoint. For thread-sensitive
  boundaries, add or reuse regression evidence for pending worker completion and already-complete
  awaits, plus cancellation/teardown when relevant. A passing test on one thread or one timing
  path does not replace the source-level check.

## Stop Output Format

When a dependency is missing, first search for it (codeindex.py where, Read, /discover). Only if
it is not in the repository — an external package, an unmerged branch, a server contract —
output this before any code:

> I cannot implement `[Class]` because `[Dependency]` is not in the repository (searched: `[queries run]`). Please provide `[Dependency.cs]` or point me to it.

Do not generate partial code while waiting. Do not guess.

## Post-Generation Verification

```yaml
post_generation:
  - "[SIG]  No API signatures were guessed — every call is grounded in provided source."
  - "[PRES] All existing comments, regions, and TODOs are preserved unchanged."
  - "[SURG] Only the required lines were changed — surrounding code is character-perfect."
  - "[ASYNC] Every new or changed ConfigureAwait(false) passed the Thread-Affinity Gate, including helper/callback access and cancellation/cleanup paths."
```

## Behaviour Claims — any mode

```yaml
behaviour:
  - "[BEHAV] A claim about what an engine, library, API or CLI does at runtime is a hypothesis until grounded: its source (the host's engine-source tool, if any), `--help`, official docs, or a run."
  - "[BEHAV] Until then, say 'hypothesis' and name the check: 'Hypothesis: the getter returns a copy — check: unitysource show <Type> --member <name>'."
  - "[BEHAV] Applies to diagnoses and explanations as much as to code: a 'likely trigger' is a hypothesis, not a cause."
```

## Secrets — any command, any mode

```yaml
secrets:
  - "[SECRET] Never print, echo, log or slice any part of a credential value (token, password, key) — not a prefix, not a length-plus-prefix."
  - "[SECRET] Diagnose a credential with booleans only: e.g. print(value.startswith('ATATT') and len(value) > 100)."
  - "[SECRET] If a fragment was exposed anyway, tell the engineer at once and recommend rotating it."
```

## Tool Output — any command, any mode

A long session resends its whole history every turn; a verbose result paid for once gets paid
for again on every later call that re-reads it, then again as it ages into base conversation
context. Found as a real cost driver in a session retrospective (LocalDocReviewV1, 2026-10-26):
"ad-hoc tool calls" (raw bash/file output not from a tracked helper) were 24% of that session's
tokens on their own, before counting what they compounded into.

```yaml
tool_output:
  - "[TRIM] Default to the minimum output needed to answer the question — pipe through tail/grep/head, use Read with limit/offset, summarize a test run's pass/fail counts instead of pasting the full log."
  - "[TRIM] Multi-round exploratory or trial-and-error work (browser automation probing, iterative debug scripts, anything that needs several retries to get right) belongs in a fork, not the main thread — see [[MetaRouter]]'s [DELEGATE]. Only the final working script and its conclusion need to come back."
  - "[TRIM] Verbosity is fine when the engineer asks for it, or when the raw output is itself the deliverable (a diff under review, a stack trace being diagnosed)."
```
