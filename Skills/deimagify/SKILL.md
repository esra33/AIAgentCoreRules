---
name: deimagify
description: Cache a durable Markdown description of an image or PDF (screenshots, mockups, storyboards, routing diagrams) keyed by content hash, so the agent reads and interprets it once instead of on every turn. For a storyboard or flow document, also decomposes it into a Mermaid diagram of screens and transitions, as a starting draft. Use when the engineer runs /deimagify <path>, asks to "deimagify" a file, or repeatedly points at the same large image or PDF across turns.
argument-hint: "<path-to-image-or-pdf> [more paths...]"
---

# Deimagify

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
`MetaRouter.md`).

```yaml
how_to_run:
  tool:  "python3 <core>/Tools/deimagify/deimagify.py check|store|forget|list <path> ..."
  cache: "~/.claude/deimagify-cache/<sha256>.md, one per file's content hash, plus a sibling
          <sha256>.mmd auto-extracted from any ```mermaid fence in the description on store,
          plus index.json (path/size/cached-at). Keyed by content hash, not path — a renamed
          or copied file still hits; a changed file (different bytes) is a fresh miss. Lives
          outside every git repo and the host project's gitignored folders, so there is nothing
          to commit and no worktree-isolation concerns."
  does_not_read_images: "The tool itself never opens the image or PDF — it only hashes bytes
          and stores/retrieves text. Reading and describing stays with the agent's native
          multimodal Read tool."
```

## Steps

For each path in `$ARGUMENTS`:

1. **Check the cache first.**
   `python3 <core>/Tools/deimagify/deimagify.py check <path>`
   - `HIT <hash> <cache_path>` followed by the cached Markdown on stdout — present that
     directly to the engineer. Do not re-Read the source file.
   - `MISS <hash> <cache_path>` — continue to step 2.

2. **Read the source file natively.** Use the Read tool on the image, or on the PDF with an
   explicit `pages` range (at most 20 pages per call — batch and concatenate for a longer
   document). If Read errors with "pdftoppm is not installed", that is the Read tool's own
   PDF-rendering dependency (poppler), not a deimagify limitation — tell the engineer to
   install it (`brew install poppler` on macOS) and retry; there is no workaround.

3. **Write a structured Markdown description** — not a summary, a durable substitute for
   looking at the image again:
   - `## What this is` — one line: document type, page/panel count, subject.
   - `## Contents` — per page/panel: what's shown, key UI elements and their state, any
     visible text or labels, and callouts/annotations (pros/cons, decision notes, "why" text)
     transcribed as written, not paraphrased.
   - `## Flow` (storyboards and flow/routing documents only — screens connected by arrows, a
     decision point, a UX routing diagram): a Mermaid `flowchart` decomposing the storyboard
     into nodes (screens/states) and labeled edges (the trigger or condition for each
     transition), using the document's own annotations for edge labels where given. This is a
     **first-pass draft**, not a verified model of the real system.
   - `## Open validation` — required whenever a `## Flow` section is produced: name what the
     Mermaid draft should be checked against (the project's actual use-case scenarios or
     state/flow code) and state plainly that it has not been validated yet.

4. **Store it.** Write the Markdown to a scratch file (the session's own tmp directory, or
   `$CLAUDE_JOB_DIR/tmp` in a background job), then:
   `python3 <core>/Tools/deimagify/deimagify.py store <path> --from <tmp-markdown-file>`
   (`--from -` also accepts stdin.) The tool automatically extracts any `` ```mermaid `` fence
   into a sibling `<hash>.mmd` file — no extra step needed.

5. **Present the description (and any Mermaid diagram) to the engineer.** When a `## Flow`
   section was produced, also give the preview command:
   `python3 <core>/Tools/doc-review/doc_review.py serve <hash>.md <hash>.mmd`
   A later `/deimagify` call on the same bytes is now a cache hit.

## Refreshing a stale description

- The source file's bytes changed → `check` reports a fresh `MISS` automatically; nothing
  extra to do.
- The bytes are unchanged but the cached interpretation was wrong → `forget <path>` first,
  then redo steps 2-4.

## Non-goals

- Not OCR or pixel diffing — the description is the agent's interpretation, at whatever
  fidelity one Read pass gives.
- The Mermaid flow draft is a starting point, not a validated model — treat `## Open
  validation` as a to-do, never as proof the diagram matches the real flow.
- No auto-trigger on every image/PDF Read — this only runs when asked. Wiring it into a
  PreToolUse hook on Read would be a separate, larger change than this skill.
- Does not store the original image/PDF bytes, only the agent's written description — if that
  reading was wrong from the start, `forget` and redo rather than trusting a bad cache entry.
