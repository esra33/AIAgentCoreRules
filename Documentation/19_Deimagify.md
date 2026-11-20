# Deimagify

Caches a Markdown description of an image or PDF — screenshots, mockups, storyboards, routing
diagrams — keyed by the file's content hash, so the agent reads and interprets it once instead
of on every turn. For a storyboard or flow document, the description also includes a Mermaid
flowchart decomposing it into screens and transitions, as a starting draft, with the diagram
auto-extracted into a separate `.mmd` file for viewing.

Code: `Tools/deimagify/deimagify.py` (cache management only — stdlib, no image/PDF parsing of
its own). Wrapped by the [[Skills/deimagify/SKILL|/deimagify]] skill, which does the actual
reading and describing with the agent's native multimodal `Read` tool.

## What it does

The tool never opens the image or PDF. It hashes the file's bytes (SHA-256) and stores or
retrieves a Markdown file at `~/.claude/deimagify-cache/<hash>.md`, plus a sibling
`<hash>.mmd` (auto-extracted from any `` ```mermaid `` fence in the description), plus an
`index.json` with `source_path` / `size_bytes` / `cached_at` per hash. Content-hash keying means
a moved or copied file still hits cache, and a changed file (different bytes) is a fresh miss
automatically — there's no path-based staleness to track.

The skill is the part that actually reads: on a cache miss it Reads the image or PDF (batching
a long PDF in page ranges), writes a structured description (`## What this is`, `## Contents`),
and — only when the document is a storyboard or flow/routing diagram — a `## Flow` section with
a Mermaid `flowchart` plus an `## Open validation` note flagging it as an unverified first-pass
draft, never a confirmed model of the real system. The `store` command automatically extracts
the Mermaid code into a separate `.mmd` file so it can be rendered by the doc-review preview
server.

## Commands

```bash
python3 Tools/deimagify/deimagify.py check <path>                  # hash + report hit/miss
python3 Tools/deimagify/deimagify.py store <path> --from <md-file> # cache a description (+ auto-extract diagram)
python3 Tools/deimagify/deimagify.py store <path> --from -         # from stdin
python3 Tools/deimagify/deimagify.py forget <path>                 # drop the cached entry
python3 Tools/deimagify/deimagify.py list                          # show every cached entry
```

| Flag | Meaning |
|---|---|
| `store --from <path\|->` | Required. The Markdown description to cache for this file's current hash. Any `` ```mermaid `` fence is auto-extracted to `<hash>.mmd`. |
| `store --force` | Overwrite an already-cached entry instead of refusing. |

## Why a global, content-hash-keyed cache

The files this is meant for (a pasted storyboard panel, a PDF dropped in `~/Downloads`) often
live outside any git repo and outside any single project, so a per-project or sidecar-file cache
would miss most of the real use cases. `~/.claude/deimagify-cache/` is shared across every
project and survives the file being renamed, moved, or re-pasted — only the bytes matter.

## Viewing a Flow diagram

When a description includes a `## Flow` section with a Mermaid flowchart, the diagram is
auto-extracted on `store` into a sibling `.mmd` file. To view it rendered in a browser:

```bash
python3 Tools/doc-review/doc_review.py serve <hash>.md <hash>.mmd --port 8080
```

The preview server accepts any file paths — it is not restricted to `Features/` folders, so
pointing it directly at cache files inside `~/.claude/deimagify-cache/` works. The server
renders the `.mmd` file as a Mermaid diagram tab alongside the Markdown description.

## Review step (the skill's job, not the tool's)

The cached description is the agent's own interpretation from one Read pass — the tool has no
way to verify it matches the source. A `## Flow` Mermaid diagram is a draft, not a validated
model: before relying on it, check it against the project's real use-case scenarios or
state/flow code. If a cached description turns out wrong, `forget` the entry and redo it; a
changed file invalidates itself.

## Non-goals

- Not OCR or pixel diffing.
- No auto-trigger on every image/PDF `Read` — manual invocation only (`/deimagify <path>`).
  Wiring it into a `PreToolUse` hook on `Read` would be a separate, larger change.
- Does not store the original image/PDF bytes, only the written description.
