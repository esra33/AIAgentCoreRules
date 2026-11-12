# Audit: did retro and meta-review proposals land, and did they work?

Read-only audit, 2026-11-10. Data: 3 meta reviews (2026-10-02, 10-09, 10-16), 191 session folders
(2026-09-25 to 2026-11-10), 124 `retro.md`, git history of AIAgentCoreRules (219 commits) and
TripleMatchAiMetaData (129 commits). Working files (parsers, extracted JSON) are in
`/Users/aramirez/.claude/jobs/b2cfdac5/tmp/w/`.

**There has been no meta review since 2026-10-16** (window 10-12..10-16). That is 3.5 weeks and
about 130 sessions with no review. Every "re-check at the next review" item on the 10-16 list is
therefore still unchecked. The memory file `open-meta-review-tickets.md` was last updated
2026-10-19 and still calls 10-16 the latest review.

Method caveats:
- The retro parser reads the `Proposed changes`, `Corrections`, `Router check`, `Applied` and
  `Discovery gaps` sections (123 of 124 retros have all five).
- Theme tagging uses regexes, so the counts are indicative. The recurrence verdicts below were
  checked by hand against correction rows and dates.
- Retros dated before about 10-12 have no `Applied` section. Their proposals show as
  "undecided" even when they were implemented later. For example, e2c2's 09-29 proposals were
  implemented in `8add120` on 10-02.

---

## 1. Meta-review tickets (38)

### 2026-10-02 (14 tickets)

| Ticket | Change | Status | Evidence | Did it work? |
|---|---|---|---|---|
| MR-01 | typecheck false pass in worktrees | Implemented | Meta `b56b9c2` (10-05) | Partly. Worktree typecheck needed 3 more fixes: asmdef wiring `56c2e69` (10-29), `--include-new` limit doc (11-10), asmdef-reference warning `aa2c8f2` (11-09). |
| MR-02 | Log corrections live | Implemented | Core `0d0fba1` | Agent and retro sources work. **Engineer source: 0 entries across the whole period** (session.json inaccuracies). |
| MR-03 A–D | One session per phase, gate retro, `/active-features` | Implemented | `f43b7ac`, `5fe7ae1`, `ed46da3` | Yes. 25 phase-scoped retros ("Retrospective — GameProgressSaveSlim — Phase N") show part B exercised. |
| MR-04 | ExternalDocPass for Confluence churn | Implemented | `315fd00`, meta `9ee0c40` | Partly. Publish errors recurred (see the Confluence row in §2). The "≤2 fetches" half was never measured and was closed by redefining the budget (MR-16-09). |
| MR-05 | Load the owning SystemIndex entry before exploring | Implemented | `54eb911` | **No.** Late or missed owning-system loads recur after 10-05: 10-07, 10-09, 10-28, 11-02, 11-04, 11-05, 11-06 (×2), 11-09 (×3). |
| MR-06 | `/audit` checkpoint in small tasks and feature phases | Implemented | `1f6a9a5` | Partly. Small tasks comply. Feature and large-task lanes audit "inline instead of the skill" (11-06 3dbf, 11-09 4407). A `[DI]` violation reached a draft on 11-06. |
| MR-07 | Large sessions end without retro | Merged into MR-03 | — | Partly. 10 sessions over 5M tokens still have no retro, including a 70.4M feature session (11-03 a8083556) and a 43.1M lane-less one. |
| MR-08 | No stub session folders | Implemented | `b2f1220` | Yes for empty folders. 19 lane-less sessions still exist, all without retro. |
| MR-09 | TestingSetup harness notes | Implemented | Meta `3a749e1` | Yes, no recurrence. |
| MR-10 | InvestigationMode chat exception | Implemented | `605bcb5` | Yes. |
| MR-11 | Gotcha comments in game code | Implemented | `c968ef9cd3` | Yes. |
| MR-12 | Meta report window filter | Implemented | `32c4fa7` | Yes. |
| MR-13 | Fresh session for long builds | Implemented | `8a8aa3e` | Unclear. Median peak context rose from 62k (week of 10-26) to 180k (11-02) and 158k (11-09). |
| MR-14 | MissionSystemUnitTests leak (game) | Code done | `bd914a80be`, now in origin/develop | The engineer's Test Runner run was never recorded. |

### 2026-10-09 (14 tickets)

| Ticket | Status | Evidence / gap |
|---|---|---|
| MR-01 reports root follows cwd | Implemented | `6aea479`. No nested folders since. |
| MR-02 MissionSystem `Math.Max` bug advice | Implemented | Meta `f1ee32e`. The game fix `68f5bde0bd` is now in HEAD and origin/develop (LeaderboardMission.cs:78 uses per-uid counted score). |
| MR-03 unpushed work | Implemented | Process change `4bd3039`: repo state is no longer ticketed. Both rule repos are clean except 2 modified meta files (AgentCodeGenTools.md, DebugTooling.md). |
| MR-04 lane rename breaks feature session list | Implemented | `0e0d6e5` |
| MR-05 decide every retro proposal | Implemented, and **it worked** | Tool side in `2f0ba35`. Undecided proposals were 87 before 10-23 and only 8 (3 retros) after. 55 commits since 10-17 cite a retro id. |
| MR-06 stale knowledge (10 items) | **Partial: about 4 of 10** | Done: Miro (`58bed58`), Mermaid (`8259c19`), GameplayRound (superseded by `Systems/RoundLifecycle.md`, `dc0e0b1`), codegen (partly, via `Systems/AgentCodeGenTools.md`, `01c4246`). Open: `SystemPatterns/CodeGenerationPattern.md` (absent); ParserGeneratorWindow class name (MagicMatchProjectRules.md:39 unchanged); "GEM events built with `new` need DummyGemEventPointer" note (not in TestingSetup.md); AndreaInstructions "USING_TOOLS not set" (AndreaTools.cs:1 has `#define USING_TOOLS`, so the "plain typecheck compiles it OUT" warning looks stale); tool-window model; `git add -f` note. |
| MR-07 SmallTask checkpoints | **Not done** | SmallTask.md:51 still reads "Wait for OK only if more than 2 files…". There is no "re-run /audit after each revision" line in 5b_audit (:61-65). |
| MR-08 load knowledge before design (Phase 1) | Implemented | `8c119f3` (10-28), Phase1_Intake.md:104. Plus `bdcce4c` for Phase 3 (11-04). |
| MR-09 Miro cost / payload | Partial | Miro review pass landed. No "never print a payload before sending" rule exists. |
| MR-10 token inflation | Implemented as MR-16-01 | `2f0ba35` |
| MR-11 worktree landing friction | Partial | Argument order, retro fallback, layer worktree recipe and stash/MERGE_HEAD handling all landed (land-worktree SKILL.md:30-33). **`.obsidian/workspace.json` is still tracked in TripleMatchAiMetaData** (`git ls-files`); core fixed it in `fac9338`. |
| MR-12 engineer logs corrections live | **Not done (habit)** | 0 engineer-sourced inaccuracies in every week through 11-10. |
| MR-13 DT-20145 abandoned diagnosis | Not done / unknown | No session touched it. |
| MR-14 LevelProgress `[DI]` exception | Not done; likely obsolete | `grep LevelProgress Rules/MagicMatchProjectRules.md` is empty. GameProgressSave was superseded by GameProgressSaveSlim, but the engineer should close it explicitly. |

### 2026-10-16 (10 tickets)

All ten were marked "done, uncommitted" on 10-19 and landed in core **`2f0ba35` (2026-10-20)**. Checked with `git log -S`: `hook-bash`, "before the subcommand" and `undecided_retros` all first appear there. `[BEHAV]` is at StopAndVerify.md:92, and "Best Practices" is in Documentation/03:54.

| Ticket | Landed | Re-verified? | Did it work? |
|---|---|---|---|
| 01 token totals 2.1× inflated | yes | yes (recompiled) | Yes. No later telemetry-inflation complaints. |
| 02 fresh session at lane change / idle gap | yes | no | **Unclear to negative.** Peak context kept rising, and a 70M session ran without a retro. |
| 03 apply proposals in a fresh session | yes | **No. The "<10% after-retro share" check needs a meta review, and none has run.** | Unknown. |
| 04 `[BEHAV]` hypothesis rule | yes | grep only | **No.** At least 9 unverified-claim corrections after it (§2). |
| 05 shell-read hook | yes | replay only | **Detects but does not prevent.** 5 shell reads after it; on 11-06 the hook flagged 2 of them in real time. |
| 06 background retro filing (`retro --from`) | yes | "not yet seen live" | Retro filing: no further complaints. Background isolation as a whole still recurs (§2). |
| 07 CLI call shape | yes | yes | Mostly. `unitysource.py --project` was guessed again on 11-09 (a different tool). |
| 08 Documentation/03 Best Practices | yes | yes | Yes. |
| 09 Confluence fetch budget vs verify | yes | **Not checked live** | Placeholder bodies were sent again on 11-04 (e6c8) after a 10-20 placeholder fix, so publish discipline still fails. |
| 10 meta report `pending` parsing | yes | yes | Yes. |

---

## 2. Retro proposal themes and recurrence

Totals: 327 proposals across 124 retros (2.6 per retro, 11 retros with none):

| Status | Proposals | Share |
|---|---|---|
| Applied | 207 | 63% |
| Undecided | 95 | 29%, nearly all before 10-23 |
| Rejected | 10 | |
| Deferred | 7 | |
| Pending or open | 8 | |

111 correction rows. Root-cause labels:

| Label | Count |
|---|---|
| rule-ignored | 30 |
| scope-misread | 26 |
| missing-rule | 14 |
| missing-index-entry | 9 |
| signature-guessed | 7 |
| unlabeled | ~25 |

| Theme | Retros raising | First → last | Main fixes (commit, date) | Recurred after fix? |
|---|---|---|---|---|
| Missing or stale Systems/ knowledge | ~68 (109 proposals, 77 applied) | 09-28 → 11-10 | ~60 meta-repo commits, e.g. RoundLifecycle `dc0e0b1`, DebugTooling/Airtable `6972ff5`, AgentCodeGenTools `01c4246`, StateV3DataRules `c25b6c6` | **Same fact: no.** New facts in the same system: yes. LocalDocReview.md has 30 commits and still produced 4 missing-index corrections (10-27 ×2, 10-29, 11-03). This works as a per-fact cache, not as prevention. |
| Owning Systems entry not loaded first / late load | ~22 (9 router misses) | 09-28 → 11-09 | MR-05 `54eb911` (10-05), SmallTask `ce37d15` (10-17), resume-work (10-26), Phase 3 `bdcce4c` (11-04), LargeTask `5638d47` (11-09) | **Yes, repeatedly.** Each new lane or process gets its own patch, and misses continue: 11-05 db84, 11-06 3dbf ×2, 11-09 9683 ×2, 11-09 4407. |
| Unverified runtime/API claims ([BEHAV], signature-guessed) | ~25 (23 corrections) | 10-01 → 11-10 | `[BEHAV]` in `2f0ba35` (10-20); TDD-claims extension `5b1c76b` (11-09) | **Yes.** After 10-20: 3f0e (×2), 5544 (×2), b95f, 70eb (×2), 7575, d125, ed82, bcd1. Retros label these "rule-ignored ([BEHAV])", so the rule is known and still not applied. |
| Scope misread / over-build / not reusing an existing utility | ~31 (38 corrections) | 10-05 → 11-09 | `[SHAPE]` scope gate; "existing utility first" `cc7a86f` (10-17); scope-gate skip clause (10-27); threshold/cost line (11-02) | **Yes.** This is the largest correction category, and it is flat over time: 80cd 10-29 ("existing utility first" ignored), 324a 11-02, 940d 11-04, 3dbf ×2 11-06, 0807 11-09, ed82 11-09. No structural fix exists. |
| Design doc asserts unconfirmed decisions or facts | 6 | 10-23 → 11-10 | Proposal 1d9e #4 (Phase 3 "leave Decisions empty"), never applied; architecture-actionables memory (10-29); Phase 1 sources-of-truth check `2860e36` (11-03); `5b1c76b` (11-09) | **Yes:** 911d 10-29, 698e 11-02 (approved and then wrong), ed82 11-09, bcd1 11-10. |
| Worktree / land-worktree / layer-repo git friction | ~39 (52 proposals, 37 applied) | 09-28 → 11-10 | 16 commits to land-worktree SKILL (0 → 1,201 words); SmallTask layer-worktree rules `c078e28`, `5c04da6`, `07de697` | **Yes, whack-a-mole.** The relative-path bug was fixed in SmallTask (`5c04da6`, 10-29) and recurred on 11-04 through end-session SKILL's separate copy of the same command (`6186565`). New variants were still raised on 11-06 (×2) and 11-10. |
| Background-job isolation (cannot write GitIgnore*, `! cp`) | ~10 | 10-05 → 11-10 | Memory `feature-doc-phases-run-foreground`; MR-16-06 `retro --from`; LargeTask `8f38334` (11-09); SmallTask `048f2f3`, `4649449` (11-10) | **Yes:** d013 10-20, 4b0e 11-09, fa1d 11-10, cdb3 11-10 ("memory already covered it"). Rules are being added for each lane separately. |
| Documentation/ mirror drift | ~56 (regex is broad; ~6 real corrections) | 09-28 → 11-05 | MetaRouter rule (`8add120`, 10-02); end-session "File cell lists every copy" `94a8271` (11-05) | The prose rule did not hold (048c 10-28 and 447c 10-29 are both "rule-ignored"). **The template fix worked:** no drift correction after 11-05, and later proposals name Documentation/ in the File cell. |
| Shell reads of rule files / edit without Read | ~11 | 09-29 → 11-06 | MetaRouter "Read before edit" (`8add120`); hook-bash `2f0ba35` (10-20) | **Yes, with detection.** 10-28 05b6, 11-03 3c01, 11-03 afd9 (Edit rejected), 11-06 648f and 966f (both flagged by the hook). Low cost now. |
| `/audit` skipped or run inline | ~16 | 09-28 → 11-09 | `1f6a9a5` (10-05); `expected_without_csharp` | Small task: fixed. Feature and large task: **recurs** (inline audits 11-06, 11-09). The MR-09-07 re-audit-after-revision rule was never added. |
| typecheck / unity-tools gaps | ~20 | 09-28 → 11-10 | `b56b9c2`, `56c2e69`, `aa2c8f2`, `3ea349e`, `270bac5` | No "forgot to typecheck" corrections at all. The problem is tool limits around worktrees and asmdefs, and each fix exposed the next one. Working, still incomplete. |
| Session telemetry / token accounting | ~35 | 09-28 → 11-09 | MR-02-02, MR-09-10 → MR-16-01 (`2f0ba35`), context warning `7252e64` (11-02) | Inflation is fixed. The meta-tooling itself takes a large share of proposals: about 38, or 12%, are about the tracking system. |
| Context bloat / fresh session | 6 | 10-19 → 11-09 | MR-02-13, MR-16-02/03, `e441c23` `/new-session`, `7252e64` | **Not evidently working.** Median peak context: 62k → 180k → 158k. Weekly token spend: 401M → 733M → 323M (partial week). |
| Confluence/Miro publish churn | ~22 | 10-05 → 11-09 | `315fd00`, `58bed58`, `9ef23e7` (10-22 body verification), `b338bf0` (11-04) | **Yes.** Placeholder body sent 10-20 (4815), fix added, placeholder sent again 11-04 (e6c8, "rule-ignored"). No publish incident since 11-04, but there have been few publishes. |
| StateV3 / codegen pipeline | ~21 | 09-28 → 11-10 | StateV3DataRules `c25b6c6` (11-06), PlayerDataPattern `8ddc004` (11-09), `38cdde0` (11-10) | Recurred 11-09 and 11-10, after the 11-06 rule, because the wrong pipeline came from the TDD itself. Too early to judge the 11-09 fix. |
| Secrets | 2 | 10-13 | `[SECRET]` (`3b2ab84`, 10-16) | **No recurrence.** It worked, though n=1. The 11-09 ssh-keygen case was a TTY issue, not a leak. |
| Prize-state push | 2 mentions | 09-28 | MagicMatchProjectRules §VII (meta `212a0f7`, 09-29) | **No recurrence.** It worked. The only later mentions are missed ScreenNavigation loads (10-16, 11-09), not violations. |
| IL2CPP / device | 4 | 10-16 → 11-03 | §VIII (`6972ff5`) | No recurrence of the code-page or JNI-size bug. The JNI null-argument proposal (3f0e, 10-20) was never applied. |

Corrections per retro by week: 10-19: 1.3; 10-26: 0.5; 11-02: 0.66; 11-09: 0.93. There is no
downward trend. Every correction is self-reported (agent or retro back-fill), so this is a
lower bound.

---

## 3. Raised repeatedly but never implemented

| Item | Raised | Evidence it is still open |
|---|---|---|
| Re-run `/audit` after every revision; SmallTask "more than 2 files" checkpoint covers rule and doc edits | 4221 (10-09), 90f5 (10-08), MR-09-07, carried MR-16 | SmallTask.md:51 and :61-65 unchanged. |
| Engineer logs `/inaccuracy` live | MR-09-12, carried | 0 engineer entries ever. The metric is fully agent-reported. |
| Untrack `.obsidian/workspace.json` in TripleMatchAiMetaData | 44c9 (10-08), MR-09-11, carried | Still tracked. |
| Stray Obsidian embed inside a hard rule | 1d9e #5 (10-23) | ArchitecturalPrinciples.md:156 reads "not a flag on an existing `![[GameProgressSaveSlim_GDD]]`method." **A corrupted always-loaded rule, unfixed for 18 days.** |
| Phase 3: leave Decisions empty until answered | 1d9e #4 (10-23) | Not in CreateFeature. The same failure recurred 3 times (§2). |
| System entries Config / Auth-connectivity / DCP / LevelManager / RstPlugins | 5544 (10-22), 3f0e (10-20), db87 (10-19) | None exist. 5544's correction was explicitly a missing Config entry. |
| ScreenNavigation `IsCurrentState()` true on Enter; JNI null-argument signature; NotRC label; `.gitignore` case-insensitivity | 3f0e, db87, 1328 | Not found in the rule files. |
| MR-09-06 remainder (CodeGenerationPattern, ParserGeneratorWindow name, DummyGemEventPointer `new` note, AndreaInstructions USING_TOOLS) | 10-07 → 10-16 | See §1. |
| ExternalDocPass "403 / app not installed → check scopes" | 98e9 (10-05) | Not present. |
| "Never print a payload before sending" | MR-09-09 | Not present. |
| `bcd1`/StateV3 TDD Best Practices #4 cleanup | 11-10 | Recent. |

## 4. Implemented but never re-verified

- MR-16-03: the "<10% tokens after retro" target. It needs a meta review, and none has run since 10-16.
- MR-16-09: verify-after-publish was not checked live, and an 11-04 placeholder incident followed.
- MR-16-06: `retro --from` in a live background `/end-session`. There is no clear evidence in the retros.
- MR-16-02: the idle-gap and lane-change offer. There is no data on whether offers were taken; peak context rose.
- MR-02-04: "≤2 fetches per pass" was never measured, then closed by redefinition.
- MR-02-14: the engineer's MissionSystemUnitTests run.
- MR-02-05, MR-02-06, MR-16-04 and MR-16-05 have grep-only done-whens. The behaviour they target recurs (§2), and no review has said so.
- The ~55 retro-driven commits since 10-17 are each "applied". Nothing aggregates whether the same root cause came back. That aggregation was the meta review's job, and the meta review stopped.

## 5. Retro coverage and quality

Coverage by lane:

| Lane | Retros / sessions | Coverage |
|---|---|---|
| small_task | 36/39 | 92% |
| bug_fix | 10/14 | 71% |
| feature | 40/52 | 77% |
| large_task | 6/9 | 67% |
| other | 29/55 | 53% |
| investigation | 3/3 | 100% |
| none (no lane recorded) | 0/19 | 0% |

- Of the 67 sessions without a retro, 65 never ran `/end-session`. End reasons: "other" 39, prompt_input_exit 14, clear 4, none recorded 10. By tokens they are only 12% of spend (292M of 2.4B), but they include the biggest single sessions: a8083556 feature 70.4M, 2e2966d6 lane-less 43.1M, 8b285bb8 feature 35.8M, 9c50708e large_task 32.4M, d291940c large_task 19.1M, and 70a54416 (the 10-16 meta review itself) 13.3M.
- Weekly retro rate improved from about 53% (late Sep / early Oct) to 69-75% (Oct 19 onward).

Actionable or boilerplate?
- **Actionable:** proposals are concrete (file, exact text, why), 63% were applied, and 98% have been decided since 10-23. Root-cause labels and the `Applied` lines with commit ids make the retros auditable. That is a real strength.
- **Boilerplate:**
  - About 20% of the 831 router-check rows are "not needed / not expected / correct" filler, mainly the repeated `CodingStandards` / `typecheck` / `/audit` "No C#" rows in small tasks.
  - Discovery gaps say "none" in 27 retros, and 67 retros have no corrections. With no engineer-sourced corrections, that is self-assessment.
  - The Cost section is formulaic ("Standardized operations were X%…").
- **Structural weakness:** each retro proposes local text patches. Rule files grow without bound since Oct 5:

  | File | Words on Oct 5 | Words now |
  |---|---|---|
  | SmallTask.md | 432 | 1,396 |
  | StopAndVerify.md | 360 | 1,144 |
  | Phase1_Intake.md | 1,352 | 2,786 |
  | SystemIndex.md | 568 | 1,430 |
  | land-worktree SKILL.md | 0 | 1,201 |

  Behavioural root causes ("rule-ignored" is the top label) are answered with more rule text, which the recurrence data shows does not change behaviour. Fixes that worked were structural: a template field (the Documentation File cell), a hook (shell read), a tool fix (token totals, reports root), or a single-fact knowledge entry.

## Verdict

**Worked:**
- Knowledge-entry fixes for specific facts (the same fact never recurred).
- Hard project rules: prize-state §VII, `[SECRET]`, IL2CPP §VIII.
- Tool and telemetry bug fixes: reports root, token inflation, lane rename, stub folders.
- The proposal decision loop (MR-09-05).
- The Documentation-drift fix once it became a template field.
- Phase-per-session (MR-02-03).

**Did not work (recurred after the fix):**
- Load-the-owning-system-first (5 separate patches).
- `[BEHAV]` / signature guessing.
- Scope misread and reuse-existing-first.
- Background-job isolation.
- Confluence placeholder publishing.
- Design docs asserting unconfirmed decisions.
- Worktree friction (narrow fixes duplicated across files).
- Fresh-session and context-bloat measures.
- Live engineer correction logging (never adopted).

**Gap:** the weekly meta review stopped after 10-16. With it went the only cross-retro recurrence check and the re-verification of every 10-16 ticket.
