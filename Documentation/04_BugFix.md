# Bug Fix Process

From a symptom to a verified fix with a regression test. Investigation here is a means to a
fix, not a deliverable — for "should we change X" questions with no bug, use [[06_Investigation|Investigation Mode]].

## Steps

| # | Step | What happens |
|---|---|---|
| 1 | **Symptom** | Restate expected vs actual, repro steps, frequency, build/platform and first-seen version. The agent asks only for what is missing. |
| 2 | **Context** | Read the host project's Systems entry for every system on the failing path (its common gotchas first) before searching its source. A system implicated later, by a survey or a hypothesis, has its entry read at that point, not at fix time. Locate the flow with the host's code-index and usages tools (`codeindex.py`, `usages.py`); wider surveys go to an Explore agent. Check recent commits on the failing path since the first-seen build: a sibling fix may already explain the bug, or be missing from the reported build. For a crash report, read the full native trace (Android tombstone, iOS full crash log), not the summary stacktrace: summary exports cut the crashing thread off at about 64 frames and can drop the managed method names, so the real cycle and its depth only show in the full trace. |
| 3 | **Hypotheses** | Read the method bodies on the failing path; every claim carries `file:line`. Rank 1–3 hypotheses, each with its evidence, what would confirm it and what would rule it out. Check the cheapest confirming evidence first. |
| 4 | **Diagnosis gate** | Present the root cause (or top hypothesis and confidence), the proposed fix, the blast radius and the planned regression test. **No code before the engineer confirms.** |
| 4b | **Fresh session (offered)** | If the session is past about 8 turns, the agent offers to do the fix in a new session, because long sessions make every fix step re-read the whole diagnosis. On yes, it writes `bugfix_handoff.md` in the session folder (root cause, approved fix, files, blast radius, planned test, systems already read, rejected hypotheses), runs `/end-session` for the diagnosis, and prints the command that starts the new session at step 5. |
| 5 | **Fix** | Load the rules the fix touches. Make the smallest change that removes the cause — no drive-by refactors; those are listed as follow-ups. |
| 5b | **Audit** | Run `/audit` once over every changed C# file, including repro tooling and the test file. It runs as a fresh forked subagent; the agent waits for its report. The cslint hook already checked the mechanical tags per edit. Self-review — applying the audit brief inline — is not a substitute and counts as skipped. |
| 6 | **Test** | One regression test that fails without the fix and passes with it. If the bug cannot be unit-tested (timing, platform, Editor-only), write manual repro steps and explain why. For engine or native behaviour, build the repro on the real prefab or live object, not on objects created from scratch. If the engineer already confirmed the bug with a tool, base the repro on how that tool captures its data. |
| 7 | **Verify** | Run the host's compile check (`typecheck.py`). The session hooks took a baseline before the first `.cs` edit and block the stop until a run follows the last edit. The engineer runs the tests and repro steps in Unity and reports the results. |
| 8 | **Close** | Summarise cause, fix, test and follow-ups. Offer `/end-session`. |

## Key rules

- **Corrections lead.** If verification reverses an earlier hypothesis, the agent says so first.
  A wrong root cause that reaches the fix is the most expensive failure in this process.
- **Detours are recorded.** If the engineer asks for side work mid-bug (a repro button, a debug
  command), the agent switches the session lane to `small_task`, follows the [[05_SmallTask|Small Task process]]
  for it, then switches back to `bug_fix`. Both changes are recorded under *Lane changes* in the
  session metrics, and the retrospective checks each part against its own lane. Follow-up work
  on PR review comments counts as a detour too: the agent loads the Small Task process and runs
  `/audit` before committing it, even when a plan file was already approved.
- **A lane switch is offered as a split.** When a session that started in another lane turns into
  a bug fix (a PR review that finds a bug, say), the agent first asks whether to continue there or
  open a fresh session with `/new-session "/bug-fix <symptom>"`. On a session already past ~30M
  tokens, recording the lane change prints that offer, because every call re-reads the whole context.

## What the retrospective expects to see loaded

- The Systems entry for every system on the failing path (if one exists), loaded before that
  system's code was read. A late load counts as a miss.
- Coding Standards
- Testing Rules plus the host project's testing setup
- Resource Management or Multi-Step Operations rules if the fix touched them
- Tools: `usages.py` or `codeindex.py`, `typecheck.py`, `/audit`

When the fix changed no C# (a Python tool, a skill, Markdown), Coding Standards, Testing Rules and
the C# tools are not expected. The changed tool's own tests and a run against copies of real data
are expected instead.

**Source files:** [[BugFix]]

---

← [[03_CreateFeature|Create Feature Process]] · [[00_Overview|Overview]] · [[05_SmallTask|Small Task Process]] →
