## apply: on-demand — loaded by [[MetaRouter]] and [[Phase1_Intake]]

# External Doc Pass

For documents that live outside the repository and are reviewed there — a feature TDD on
Confluence, or its architecture diagrams on a Miro board. Every fetch of a large page or board
frame, and every update, re-sends the whole thing through the context (a board read also carries
a large canvas-composer-skill payload on top), so the cost is set by how many round trips happen,
not by how big the change is. Work in **passes**: read once, change locally, write once.

The host project supplies its conventions (page template, style reference, markup, comment
convention) in a doc-conventions rule file listed in its SystemIndex. Load it before the first
publish of a session.

Tag definitions: [[CoreTags]]

---

## Publish (first version, or a full rewrite)

```yaml
publish:
  - "Load the host's doc-conventions file. Read its style reference page once, for structure only."
  - "Build the complete page body locally (a scratch file next to the local source doc), including diagrams. Validate diagrams before publishing if the host names a validator."
  - "If the document has diagrams reviewed on a board, push them in this same pass — see 'Diagrams reviewed on a board' below. Do not push a diagram ahead of the document it illustrates."
  - "Measure the built body before publishing. Over ~50K characters, split it into child pages (the host's doc-conventions file says how) — one call per page."
  - "Before sending: confirm the `body` argument is the real, complete content just built or read back from its file — not a placeholder, a truncated fragment, or escaped markup typed by mistake. This matters most for a large body typed or pasted directly into the tool call rather than loaded from the file that was just built: a publish call cannot be partially reviewed after the fact, only caught before it is sent or fixed after it has already overwritten the live page."
  - "Publish each page in one create or update call, written in the main session. Never hand a body to a subagent to retype."
  - "Verify every publish: fetch the page (or read the create response) and confirm it ends at its last section. A call cut off mid-body still saves a truncated page."
  - "Record the page in the progress file's sources_of_truth: kind, id, title, version returned by the call."
per_call_budget: "~50K characters of body. A 145K body was cut off mid-call and replaced the live page with a truncated one; 127K happened to pass, so a past success does not prove a size is safe."
```

## Review pass (engineer comments)

One pass handles every comment that is ready. Do not fetch or update per comment.

```yaml
review_pass:
  1_read:     "Fetch once: the page body, its inline comments with replies, and its footer comments. That is the whole read budget for the pass."
  2_list:     "Build the pass list: each actionable thread (per the host's resolution convention), what it asks, and where it applies. Threads still under discussion are listed as skipped."
  3_confirm:  "Show the pass list. Ask only about items that are ambiguous or conflict with each other; do not ask per item."
  4_apply:    "Apply every item to the local copy of the body in one go. An item that removes a question also removes every mention of it."
  5_write:    "One update call. If the update fails on a version conflict, re-read once and re-apply; never loop."
  5b_verify:  "Verify the update as for a publish: check the update response first. If it does not show the body ending at its last section, do one verification fetch."
  6_report:   "Reply with: new version, threads addressed (the engineer resolves them; the agent cannot), threads skipped and why. Update sources_of_truth to the new version."
budget:       "Per pass: at most 2 page reads for review (step 1 and one conflict retry) and 1 update. The post-write verification (5b, and Publish's verify) does not count against it — at most one fetch per page written. Exceeding the budget means the pass was split; say why in the report."
```

## Diagrams reviewed on a board (Miro)

A diagram's local source (e.g. `.mmd`) is what gets iterated on — read, edit, re-read it locally
(a local render, not a board round trip) until the content and layout are what it should say. The
board gets pushed to on the same schedule as the document it illustrates, not on every local
revision: a diagram does not earn its own round trip just because the text changed again.

```yaml
diagrams_on_a_board:
  - "Iterate the local source against a local render until it is ready — never push a revision just to see how it looks on the board."
  - "Push to the board as part of the same Publish pass as the document it illustrates (first version, or a full rewrite), per the rule above — not per local revision."
  - "Sticky-note or comment feedback left on the board is a Review pass, exactly like Confluence inline comments: read once, batch every actionable note into one local edit, push once."
  - "A frame already converted to hand-drawn shapes (not a source-rendered diagram widget) is out of scope for an automated push — read it to understand feedback, never overwrite it."
```

## Validating a local diagram

Before any local render, round-trip publish, or board push, confirm a `.mmd` source is
syntactically valid rather than eyeballing it:

```bash
npx --yes @mermaid-js/mermaid-cli -i <file>.mmd -o /tmp/<file>.svg
```

A clean run with no "Parse error" means it's valid. One gotcha worth knowing up front: mermaid's
sequence-diagram grammar treats a bare `;` as a statement terminator even inside `Note` or label
text, so a sentence like "...is skipped for this save; every other bridge still writes..." silently
breaks the parse — use a comma or em dash instead. If `mmdc` reports a parse error whose line
number doesn't match the raw file, bisect by rendering progressively smaller slices of the source
(or a single isolated line) until the exact failing substring is found — the reported line number
is counted against mermaid's pre-processed text, not the file on disk.

If the diagram lives inside an interactive local preview page (tabs, pan-zoom, several diagrams on
one page — not a bare `.mmd`), `mmdc` alone cannot catch runtime/DOM bugs, such as a library
mis-initializing against a hidden, zero-size panel. Drive the page headlessly instead:

```js
// Resolve puppeteer from mermaid-cli's own npx cache — no separate install needed:
//   find ~/.npm/_npx -maxdepth 4 -path "*/node_modules/puppeteer/package.json"
import puppeteer from "<resolved path>/lib/puppeteer/puppeteer.js";
const browser = await puppeteer.launch({ headless: "new" });
const page = await browser.newPage();
page.on("pageerror", err => console.log("[pageerror]", err.message));
await page.goto("file://<absolute path to the .html>", { waitUntil: "networkidle0" });
// page.evaluate(...) to inspect DOM state (transforms, innerHTML, computed style) per tab;
// page.click(...) to simulate the interaction that triggers the bug.
await browser.close();
```

The Chromium binary `mmdc` downloads on first run is reusable for this (cached at
`~/.cache/puppeteer/chrome/...`) — no separate browser download needed.

## Style decisions

A comment like "move the tags before the name" or "colour new classes yellow" is a convention, not
a one-off edit:

```yaml
style_decisions:
  - "Apply it everywhere it fits in the current pass, not only where the comment is anchored."
  - "Propose adding it to the host's doc-conventions file so the next document starts with it. Do not log it as an /iteration."
  - "For a file/type-change color or list-format decision specifically, start from [[ChangeClassification]] rather than inventing one per feature — propose amending it instead of adding a one-off."
```

## Sync with the local source

```yaml
local_sync:
  - "When the external page is the one being reviewed, it is the source of truth: after a pass, bring the local Markdown in line in one edit per file, not per comment."
  - "Never re-publish the local file over the page; that discards the review changes."
```
