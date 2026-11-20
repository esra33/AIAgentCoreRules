# Tag Candidates Tool

Finds repeated or near-duplicate passages across a project's rule markdown files and stages
`[TAG]`-style extraction candidates for human review. It exists to find more cases like
`CoreTags.md`'s existing tags mechanically, instead of only by hand. **It never writes to the
files it scans** — output is a staged report; extracting an approved candidate into
`CoreTags.md` and rewriting the call sites is a separate, manual, reviewed edit.

Code: `Tools/tag-candidates/` (CLI flags and output shape in its `README.md`). Wrapped by the
[[Skills/find-tag-candidates/SKILL|/find-tag-candidates]] skill for rerunnable use in a session.

## What it does

Two deterministic signals (no fuzzy ML): exact repeated word-runs (n-grams) across ≥2 files, and
near-duplicate paragraph/bullet chunks compared with `difflib`. Overlapping n-gram windows from
the same underlying repeat are merged into one maximal-span candidate before reporting, so one
real duplicated sentence reports as one candidate, not several sliding-window fragments of it.

Each candidate is then checked against `CoreTags.md`'s table: a close match to an existing tag's
definition is classified `already-tagged` (add a `[TAG]` reference instead of a new tag);
otherwise it's a `new-candidate`. This check compares the candidate's matched text against the
*whole* tag row, so a real repeat of a long tag's elaboration can land in `new-candidate` instead
— still surfaced, just worth a second look rather than trusting the label alone.

## Commands

```bash
# Default corpus: the host project's always-loaded CLAUDE.md import chain
python3 Tools/tag-candidates/tag_candidates.py --root /path/to/host/project

# Any explicit file list
python3 Tools/tag-candidates/tag_candidates.py Rules/A.md Systems/B.md --out-md /tmp/report.md
```

| Flag | Default | Meaning |
|---|---|---|
| `--root` | `.` | Host project root used to resolve the default corpus. |
| `--claude-md` | `<root>/CLAUDE.md` | Parsed for its flat `@path` imports — one level, not nested. |
| `--ngram` / `--threshold` | `8` / `0.72` | Exact n-gram size (words) / near-duplicate ratio. |
| `--tag-match-threshold` | `0.5` | Similarity ratio to call a candidate already-tagged. |
| `--out-json` / `--out-md` | stdout only | Optional paths to also write the report to disk. |

## Review step (the skill's job, not the tool's)

The tool proves syntactic similarity only. Before treating any candidate as safe to extract or
reference: read both occurrences in full context, confirm they mean the same thing (not just
read similarly), and for a `new-candidate`, confirm the suggested tag name doesn't collide with
`CoreTags.md`. See [[Skills/find-tag-candidates/SKILL|/find-tag-candidates]] for the full step
list, including where the staged report lands in a background job.

## Tests

```bash
python3 -m unittest discover -s Tools/tag-candidates/tests -p 'test_*.py'
```

Fixture strings/files only — never run against real project files inside the test suite.
