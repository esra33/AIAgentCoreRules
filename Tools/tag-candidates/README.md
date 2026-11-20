# Tag Candidates

Finds repeated or near-duplicate passages across a project's rule markdown files and stages
`[TAG]`-style extraction candidates for human review. **Never writes to the files it scans** —
output is a report only; extracting an approved candidate into `CoreTags.md` (or another tag
table) and rewriting the call sites is a separate, manual, reviewed step.

Wrapped by the `find-tag-candidates` skill (`../../Skills/find-tag-candidates/SKILL.md`) for
rerunnable use inside a session; this README documents the underlying CLI for direct runs.

## Why

A rule repeated near-verbatim across several files is a maintenance liability (edit one copy,
forget the others) and a token cost (the same idea paid for in full every time it's read instead
of once via a tag reference). `CoreTags.md` already does this by hand for the highest-frequency
concepts; this tool finds more candidates mechanically.

## What it detects

Two deterministic signals, no fuzzy ML:

1. **Exact repeated n-gram** (default 8 words) occurring in ≥2 distinct files.
2. **Near-duplicate chunks** — paragraph/bullet-level text blocks compared cross-file with
   `difflib.SequenceMatcher`, default similarity ratio ≥ 0.72.

Each candidate is then checked against `CoreTags.md`'s existing table: if it closely matches an
existing tag's definition, it's classified `already-tagged` (fix: add a `[TAG]` reference at the
call site, no new tag needed) instead of `new-candidate` (fix: extract a new tag, then reference
it everywhere it was repeated).

**Known limitation:** the already-tagged check compares the candidate's matched text against the
*whole* `CoreTags.md` row for a tag using a whole-string similarity ratio, which under-scores a
short candidate against a tag whose row carries a lot of extra elaboration beyond its core rule
(e.g. `[TRIM]`'s row). A real repeat of a long tag's definition can land in `new-candidate`
instead of `already-tagged` — still surfaced, just in the wrong bucket. Reviewing the occurrence
lines (not just trusting the bucket label) catches this.

**Syntactic similarity is not semantic identity.** Every candidate needs a human (or an agent
acting as reviewer) to confirm the matched passages actually mean the same thing before any tag
is extracted or referenced — the thresholds are tuned to be a reasonable starting point, not a
guarantee.

## Usage

```bash
# Default corpus: resolve the host project's always-loaded CLAUDE.md import chain
python3 Tools/tag-candidates/tag_candidates.py --root /path/to/host/project

# Explicit file list (any corpus, not just the always-loaded chain)
python3 Tools/tag-candidates/tag_candidates.py Rules/A.md Rules/B.md Systems/C.md

# Write both report formats to disk
python3 Tools/tag-candidates/tag_candidates.py --root /path/to/host/project \
  --out-json /tmp/tag_candidates/report.json --out-md /tmp/tag_candidates/report.md
```

| Flag | Default | Meaning |
|---|---|---|
| `files` (positional) | none | Explicit markdown files to scan. Overrides `--root`/`--claude-md` resolution. |
| `--root` | `.` | Project root used to resolve the default corpus. |
| `--claude-md` | `<root>/CLAUDE.md` | Root file whose flat `@path` import lines become the default corpus. Only a flat list is resolved — imports nested inside the imported files themselves are not followed. |
| `--core-tags` | `Rules/CoreTags.md` relative to this tool | Tag table to cross-check candidates against. |
| `--ngram` | `8` | Word count for the exact-repeat signal. |
| `--threshold` | `0.72` | `difflib` similarity ratio for the near-duplicate signal. |
| `--min-words` | `6` | Minimum words for a chunk to be considered at all. |
| `--tag-match-threshold` | `0.5` | Similarity ratio to classify a candidate as already covered by an existing tag. |
| `--out-json` / `--out-md` | none (stdout only) | Optional paths to also write the report to disk. |

## Output shape

```json
{
  "candidates": [
    {
      "text": "...",
      "signal": "exact-ngram | near-duplicate",
      "classification": "new-candidate | already-tagged",
      "suggested_tag": "FOOBAR",
      "matched_tag": null,
      "occurrences": [{"file": "...", "line": 12}]
    }
  ]
}
```

The Markdown report groups candidates under "New tag candidates" and "Already covered by an
existing tag", each with the repeated text, its `file:line` occurrences, and (for new
candidates) a heuristically suggested tag name — a starting point to rename, not a final answer.

## Tests

```bash
python3 -m unittest discover -s Tools/tag-candidates/tests -p 'test_*.py'
```

Fixtures only — never run against real project files inside the test suite itself.
