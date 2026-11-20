---
name: find-tag-candidates
description: Scan a project's rule markdown files for repeated or near-duplicate passages and stage [TAG] extraction candidates for human review, cross-checked against CoreTags.md. Report only — never edits CoreTags.md or any source rule file. Rerunnable. Use when the engineer runs /find-tag-candidates, asks to find repeated rule text, or wants to shrink the always-loaded CLAUDE.md import chain.
argument-hint: "[file ...]  (default: the host project's always-loaded CLAUDE.md import chain)"
---

# Find Tag Candidates

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
`MetaRouter.md`).

```yaml
how_to_run:
  tool:      "python3 <core>/Tools/tag-candidates/tag_candidates.py --root <host-project-root> [file ...]"
  default_corpus: "No files given → the tool parses the host project's root CLAUDE.md for its flat @imports and scans exactly that always-loaded chain. Pass explicit files/globs to scan any other corpus instead."
  output:    "Tool prints the Markdown report to stdout and, if --out-json/--out-md are given, writes both formats to disk. Pick an output path per the 'where it lands' note below."
  rerun:     "Safe to run anytime — read-only over the scanned files, writes only to its own report output path, never to CoreTags.md or any source file. Re-run after editing rule files to see whether a known repeat was cleared or a new one appeared."
```

## Steps

1. **Run the tool** against the default corpus (or `$ARGUMENTS` if files were named), writing
   both report formats to a scratch path (see "where it lands" below).
2. **Review every candidate before trusting it.** The tool proves syntactic similarity only — it
   does not know whether two passages mean the same thing. For each candidate:
   - Read both (or all) occurrences in full context (not just the matched excerpt) — the same
     sentence can carry different weight depending on what surrounds it.
   - Drop (don't stage) anything that *looks* similar but means something different in context,
     or where only one occurrence is a true repeat.
   - For a surviving `new-candidate`: confirm the suggested tag name doesn't collide with
     anything already in `Rules/CoreTags.md`, and that the definition can be written as one
     precise line true at every occurrence.
   - For a surviving `already-tagged`: confirm the existing tag's definition really covers the
     candidate's meaning, not just similar wording.
3. **Present a summary table in chat**: pattern (short excerpt) · occurrences (`file:line`) ·
   classification · suggested fix. Note which raw candidates were dropped in review and why.
4. **Never apply the extraction yourself in this skill.** Extracting a new tag into
   `Rules/CoreTags.md` (or a project-specific tag table) and rewriting call sites to reference it
   is a separate, explicitly-approved edit — treat it like any other rule change: state the
   diff, wait for the engineer, then edit with `[SURG]` (only the matched lines, nothing else).

## Where the report lands

- Normal session (not a background job, working in a writable checkout): write under that
  project's own reports convention if one exists (e.g. `GitIgnoreReports/TagCandidates/`),
  otherwise ask the engineer where to put it.
- Background job where the host project's gitignored report folders are not writable even
  through the worktree symlink: write to `$CLAUDE_JOB_DIR/tmp/tag_candidates/` instead, and hand
  off the finished report with a one-line `! cp` command for the engineer to place it wherever
  they want it kept.

## Non-goals

- Not a style/typo linter — only cross-file repetition and near-duplication.
- Not a replacement for `CoreTags.md`'s own judgment-driven tag design — it surfaces candidates,
  it does not decide what a good tag boundary is.
- Does not touch `Documentation/` — syncing a Documentation page after an approved tag
  extraction is the same manual step any other rule-file change already requires.
