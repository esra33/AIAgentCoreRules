#!/usr/bin/env node
// Puppeteer smoke test for the LocalDocReviewV1 in-page comment UI (task 19). Everything here is
// end-to-end, real-browser coverage that a unittest can't give: actual mouse events dispatched
// against real rendered DOM, driving the full engineer flow through a real server.
//
// Run:
//   node Tools/doc-review/tests/smoke/review_ui_smoke.js
//
// Requires Google Chrome installed, and puppeteer available somewhere under ~/.npm/_npx/ --
// `npx --yes puppeteer --version` once is enough to populate that cache if this script reports
// it missing. Writes its own fixture (md + sequence + flowchart) to a temp dir; no --demo or
// other external dependency.
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir, homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const TOOL_DIR = dirname(dirname(dirname(fileURLToPath(import.meta.url))));

function findPuppeteerEntry() {
  const npxCacheDir = join(homedir(), ".npm", "_npx");
  if (!existsSync(npxCacheDir)) {
    return null;
  }
  for (const entry of readdirSync(npxCacheDir)) {
    const candidate = join(npxCacheDir, entry, "node_modules", "puppeteer", "lib", "puppeteer", "puppeteer.js");
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

const puppeteerEntry = findPuppeteerEntry();
if (!puppeteerEntry) {
  console.error(
    "[review_ui_smoke] puppeteer not found under ~/.npm/_npx -- run `npx --yes puppeteer --version` once, then retry."
  );
  process.exit(1);
}
const puppeteer = (await import(pathToFileURL(puppeteerEntry).href)).default;

const results = [];
function check(cond, msg) {
  results.push({ ok: !!cond, msg });
  console.log(`[review_ui_smoke] ${cond ? "OK" : "FAIL"}: ${msg}`);
}

function waitForServerUrl(proc) {
  return new Promise((resolve, reject) => {
    let buf = "";
    proc.stdout.on("data", (chunk) => {
      buf += chunk.toString();
      const match = buf.match(/http:\/\/127\.0\.0\.1:\d+\//);
      if (match) {
        resolve(match[0]);
      }
    });
    proc.stderr.on("data", (chunk) => process.stderr.write(chunk));
    proc.on("exit", (code) => reject(new Error(`doc_review.py serve exited early (code ${code})`)));
    setTimeout(() => reject(new Error("timed out waiting for the server to print its URL")), 10000);
  });
}

function waitForPanel(page, predicateSource, timeout = 4000) {
  return page.waitForFunction(
    `(() => { const html = document.getElementById("docreview-panel")?.innerHTML || ""; return (${predicateSource})(html); })()`,
    { timeout }
  );
}

async function waitForSidecar(sidecarPath, predicate, timeout = 4000) {
  const deadline = Date.now() + timeout;
  for (;;) {
    if (existsSync(sidecarPath)) {
      const data = JSON.parse(readFileSync(sidecarPath, "utf8"));
      if (predicate(data)) {
        return data;
      }
    }
    if (Date.now() > deadline) {
      throw new Error(`timed out waiting for sidecar condition (${sidecarPath})`);
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

async function clickAndWaitForPopover(page, clientX, clientY) {
  await page.mouse.move(clientX, clientY);
  await page.mouse.down();
  await page.mouse.up();
  await page.waitForSelector(".docreview-popover", { timeout: 2000 });
}

async function submitPopover(page, text) {
  await page.type(".docreview-popover-input", text);
  await page.click(".docreview-popover-submit");
  await page.waitForFunction(() => !document.querySelector(".docreview-popover"), { timeout: 2000 });
}

// Selects the first occurrence of `text` in the active markdown panel, as if the engineer had
// dragged over it, and dispatches the mouseup text_anchors.js listens for. Only for a selection
// that lives entirely in one text node -- a cross-block selection (E14) builds its own Range.
async function selectTextInActivePanel(page, text) {
  await page.evaluate((needle) => {
    const root = document.querySelector(".panel.active .markdown");
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const idx = node.nodeValue.indexOf(needle);
      if (idx !== -1) {
        const range = document.createRange();
        range.setStart(node, idx);
        range.setEnd(node, idx + needle.length);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
        return;
      }
    }
    throw new Error(`selectTextInActivePanel: ${JSON.stringify(needle)} not found in the active markdown panel`);
  }, text);
}

// Browser progression stays read-only; updates below use the agent's public CLI.
async function integrationChecklistSmoke(browser) {
  const fixture = mkdtempSync(join(tmpdir(), "integration-checklist-smoke-"));
  const stateTool = join(TOOL_DIR, "..", "feature-state", "feature_state.py");
  const root = join(fixture, "Features");
  execFileSync("python3", ["-c", `
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
import feature_state
for name in ('Alpha', 'Beta'):
    folder = Path(sys.argv[2]) / name
    state = feature_state.create_state(folder, name)
    state['current_phase'] = '6_integration'
    feature_state.save_state(folder, state)
`, stateTool, root]);
  const items = [
    {id: "factory", title: "Factory <registration>", status: "done", notes: '<script>window.checklistInjected=true</script> & evidence'},
    {id: "compile", title: "Compile package", status: "in_progress", notes: "Compiler evidence pending"},
    {id: "manual", title: "Host acceptance", status: "todo", notes: ""},
    {id: "generation", title: "Code generation", status: "not_applicable", notes: "No generators required"}
  ];
  function recordItems() {
    const directory = join(root, "Alpha");
    const revision = JSON.parse(readFileSync(join(directory, "state.json"), "utf8")).revision;
    const payload = join(fixture, "items.json");
    writeFileSync(payload, JSON.stringify({items}));
    execFileSync("python3", [stateTool, "integration-checklist", directory, "--payload", payload, "--revision", String(revision)]);
  }
  recordItems();
  const proc = spawn("python3", ["doc_review.py", "serve-project", fixture, "--features-root", root], {cwd: TOOL_DIR});
  let page;
  try {
    const url = await waitForServerUrl(proc);
    page = await browser.newPage();
    await page.goto(url + "?feature=Alpha", {waitUntil: "networkidle0"});
    await page.click('.tab[data-i="1"]');
    await page.waitForSelector('.panel.active .integration-checklist li.in_progress');
    check(await page.$eval('.checklist-counts', el => el.textContent.includes("1 completed, 1 not applicable, 2 remaining (4 total)")), "checklist shows separate outcome counts");
    check(await page.$eval('.checklist-current', el => el.textContent === "Current: Compile package"), "checklist identifies persisted current item");
    check(await page.$eval('[data-checklist-id="factory"]', el => el.textContent.includes("Factory <registration>")) &&
      await page.evaluate(() => !window.checklistInjected && !document.querySelector('.integration-checklist script')), "checklist title and notes are escaped text");
    await page.click('details[data-key="integration:factory"] summary');
    await page.evaluate(() => {
      window.checklistMutations = 0;
      window.checklistObserver = new MutationObserver(records => { window.checklistMutations += records.length; });
      window.checklistObserver.observe(document.querySelector('.integration-checklist'), {subtree: true, childList: true, attributes: true, characterData: true});
    });
    await new Promise(resolve => setTimeout(resolve, 2300));
    check(await page.evaluate(() => window.checklistMutations === 0), "idle polling does not mutate unchanged checklist");
    items[1].status = "done";
    items[2].status = "in_progress";
    recordItems();
    await page.waitForFunction(() => document.querySelector('.checklist-current')?.textContent === "Current: Host acceptance", {timeout: 5000});
    check(await page.$eval('details[data-key="integration:factory"]', el => el.open), "open checklist evidence survives source refresh");
    check(await page.$eval('.checklist-counts', el => el.textContent.includes("2 completed, 1 not applicable, 1 remaining")), "CLI update refreshes checklist counts");
    await page.goto(url + "?feature=Beta", {waitUntil: "networkidle0"});
    await page.click('.tab[data-i="1"]');
    check(await page.$eval('.integration-checklist', el => el.textContent.includes("Checklist not recorded")), "feature switch isolates checklist state");
    await page.goto(url + "?feature=Alpha", {waitUntil: "networkidle0"});
    await page.reload({waitUntil: "networkidle0"});
    await page.click('.tab[data-i="1"]');
    check(await page.$eval('.checklist-current', el => el.textContent === "Current: Host acceptance"), "walkthrough survives feature switch and reload");
  } finally {
    if (page) await page.close();
    proc.kill("SIGTERM");
    rmSync(fixture, {recursive: true, force: true});
  }
}

// --- Fixture: writes its own files, no --demo dependency. ---
const tmp = mkdtempSync(join(tmpdir(), "review-ui-smoke-"));
const docPath = join(tmp, "Doc.md");
const seqPath = join(tmp, "seq.mmd"); // tab index 1
const flowPath = join(tmp, "flow.mmd"); // tab index 2 -- the "non-first diagram tab" this task calls for
const classPath = join(tmp, "class.mmd"); // tab index 3 -- task 27's node-id fix (classId-<id>-<n>)
const ORIGINAL_DOC_TEXT =
  "# Smoke Doc\n\n" +
  "The quick brown fox jumps over the lazy dog.\n\n" +
  "Second paragraph for multi-block selection.\n\n" +
  "This sentence about to be orphaned soon.\n\n" +
  "A spare sentence for the draft-abandon test.\n\n" +
  "Another spare sentence for the server-error test.\n";
// U12/E14/E7/E21 each get their own dedicated sentence below so one check's DOM mutation (a
// highlight mark, a deleted line) can never shift what another check is searching for.
writeFileSync(docPath, ORIGINAL_DOC_TEXT);
writeFileSync(seqPath, "sequenceDiagram\n  A->>B: ping\n  B->>A: pong\n");
writeFileSync(flowPath, "graph TD\n  Start[Start] --> End[End]\n");
writeFileSync(classPath, "classDiagram\n  class Widget {\n    <<module>>\n    +render()\n  }\n  class Gadget {\n    +use()\n  }\n  Widget --> Gadget\n");

const server = spawn("python3", ["doc_review.py", "serve", docPath, seqPath, flowPath, classPath], { cwd: TOOL_DIR });
let browser;
let hardFailure = null;

try {
  const url = await waitForServerUrl(server);
  browser = await puppeteer.launch({ channel: "chrome", headless: true });
  const page = await browser.newPage();
  page.on("pageerror", (err) => console.log("[review_ui_smoke] PAGE ERROR:", err.message));
  await page.goto(url, { waitUntil: "networkidle0" });
  await waitForPanel(page, "(html) => html.includes('Drafts')");

  // --- U2/task 8: select -> comment -> sidecar. ---
  await selectTextInActivePanel(page, "quick brown fox");
  await page.waitForSelector(".docreview-popover", { timeout: 2000 });
  await submitPopover(page, "please double check this fox");

  let sidecar = JSON.parse(readFileSync(join(tmp, "Doc.md.review.json"), "utf8"));
  const textThread = sidecar.threads.find((t) => t.anchor.kind === "text");
  check(!!textThread, "text selection created a thread in the sidecar");
  check(textThread?.anchor.quote === "quick brown fox", "the sidecar anchor's quote matches the selection");
  check(textThread?.replies[0]?.text === "please double check this fox", "the sidecar thread has the submitted reply text");

  // --- U3/task 9: click a node on a NON-FIRST diagram tab -> element_id in the anchor. ---
  // flow.mmd is tab index 2 (doc=0, seq=1, flow=2) -- this is the "non-first diagram tab" this
  // task calls out, which is exactly where V0's lazy-render-on-activation gotcha bites: a diagram
  // rendered while hidden (not yet the active tab) measures text via a zero-size getBBox() and
  // comes out blank, so this path is worth covering on its own, not just tab index 1.
  await page.click('[data-i="2"]');
  await page.waitForFunction(
    () => document.querySelector(".panel.active .diagram svg") !== null,
    { timeout: 2000 }
  );
  const nodeCenter = await page.evaluate(() => {
    const node = document.querySelector('g.node[id*="flowchart-Start-"]');
    const rect = node.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  });
  await clickAndWaitForPopover(page, nodeCenter.x, nodeCenter.y);
  await submitPopover(page, "check this node");

  sidecar = JSON.parse(readFileSync(join(tmp, "Doc.md.review.json"), "utf8"));
  const nodeThread = sidecar.threads.find((t) => t.anchor.kind === "diagram" && t.anchor.file === "flow.mmd");
  check(!!nodeThread, "a diagram-node click on tab index 2 created a thread in the sidecar");
  check(nodeThread?.anchor.source_id === "Start", "the node anchor's source_id matches the clicked node");
  check(!!nodeThread?.anchor.element_id, "the node anchor carries an element_id");

  // --- task 27 (node-id fix): a classDiagram node's id is "classId-<id>-<n>", not flowchart's
  // "-flowchart-<id>-<n>" -- clicking one used to capture no source_id at all and fall back to a
  // multi-line concatenated label that could never match a single source line, orphaning every
  // classDiagram comment (found via dogfooding this feature's own Architecture.md diagram).
  await page.click('[data-i="3"]');
  await page.waitForFunction(() => document.querySelector(".panel.active .diagram svg") !== null, { timeout: 2000 });
  const classNodeCenter = await page.evaluate(() => {
    const node = document.querySelector('g.node[id*="classId-Widget-"]');
    const rect = node.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  });
  await clickAndWaitForPopover(page, classNodeCenter.x, classNodeCenter.y);
  await submitPopover(page, "check this class box");

  sidecar = JSON.parse(readFileSync(join(tmp, "Doc.md.review.json"), "utf8"));
  const classThread = sidecar.threads.find((t) => t.anchor.kind === "diagram" && t.anchor.file === "class.mmd");
  check(!!classThread, "a classDiagram node click created a thread in the sidecar");
  check(classThread?.anchor.source_id === "Widget", `the classDiagram node anchor's source_id must be captured, got: ${classThread?.anchor.source_id}`);

  const classState = await page.evaluate(async () => (await (await fetch("/api/state")).json()));
  const classResolution = classState.threads.find((t) => t.id === classThread.id)?.resolution;
  check(classResolution?.status === "resolved", `a classDiagram node comment must resolve, not orphan: ${JSON.stringify(classResolution)}`);

  // --- U8/U9/task 10: reply and a status change through the panel, both land in the sidecar. ---
  await waitForPanel(page, `(html) => html.includes(${JSON.stringify(nodeThread.id)})`);
  await page.evaluate((id) => {
    const textarea = document.querySelector(`.docreview-card[data-thread-id="${id}"] .docreview-reply-input`);
    textarea.value = "panel reply";
    textarea.dispatchEvent(new Event("input"));
  }, nodeThread.id);
  await page.click(`.docreview-card[data-thread-id="${nodeThread.id}"] .docreview-reply-btn`);
  await waitForPanel(page, "(html) => html.includes('panel reply')");

  await page.evaluate((id) => {
    const card = document.querySelector(`.docreview-card[data-thread-id="${id}"]`);
    const btn = Array.from(card.querySelectorAll(".docreview-status-btn")).find((b) => b.dataset.status === "resolved");
    btn.click();
  }, nodeThread.id);

  const sidecarPath = join(tmp, "Doc.md.review.json");
  const resolved = await waitForSidecar(
    sidecarPath,
    (data) => data.threads.find((t) => t.id === nodeThread.id)?.status === "resolved"
  );
  const resolvedThread = resolved.threads.find((t) => t.id === nodeThread.id);
  check(resolvedThread?.replies.some((r) => r.text === "panel reply"), "the panel-submitted reply landed in the sidecar");
  check(resolvedThread?.status === "resolved", "the panel's Resolve button set the sidecar status to resolved");

  // --- E14: a selection spanning multiple blocks (two paragraphs) must not crash and must still
  // resolve -- text_anchors.js's highlightRange() falls back to extractContents() for exactly
  // this case, since Range.surroundContents() rejects a range that partially selects an element
  // boundary. ---
  await page.click('[data-i="0"]');
  await page.waitForFunction(() => document.querySelector(".panel.active .markdown") !== null, { timeout: 2000 });
  await page.evaluate(() => {
    const root = document.querySelector(".panel.active .markdown");
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    const startNode = nodes.find((x) => x.nodeValue.includes("lazy dog."));
    const endNode = nodes.find((x) => x.nodeValue.includes("Second paragraph"));
    if (!startNode || !endNode) {
      throw new Error("E14 fixture text not found");
    }
    const range = document.createRange();
    range.setStart(startNode, startNode.nodeValue.indexOf("lazy dog."));
    range.setEnd(endNode, endNode.nodeValue.indexOf("Second paragraph") + "Second paragraph".length);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await page.waitForSelector(".docreview-popover", { timeout: 2000 });
  await submitPopover(page, "multi-block comment");

  let sidecarNow = JSON.parse(readFileSync(sidecarPath, "utf8"));
  const multiBlockThread = sidecarNow.threads.find(
    (t) => t.anchor.kind === "text" && t.anchor.file === "Doc.md" && t.id !== textThread.id
  );
  check(!!multiBlockThread, "a selection spanning two paragraphs created a thread, not a crash");
  check(multiBlockThread?.replies[0]?.text === "multi-block comment", "the cross-block comment text was saved");

  const multiBlockState = await page.evaluate(async () => (await (await fetch("/api/state")).json()));
  const multiBlockResolution = multiBlockState.threads.find((t) => t.id === multiBlockThread.id)?.resolution;
  check(multiBlockResolution?.status === "resolved",
    `a selection spanning two blocks must still resolve, not orphan: ${JSON.stringify(multiBlockResolution)}`);
  const multiBlockHighlightDrawn = await page.evaluate(
    (id) => !!document.querySelector(`mark.docreview-highlight[data-thread-id="${id}"]`),
    multiBlockThread.id
  );
  check(multiBlockHighlightDrawn, "overlays.js redrew a highlight for the cross-block quote without crashing");

  // --- E7: abandoning a popover (no Cancel, no Submit) must persist it to localStorage as a
  // draft, which must reappear as a sidebar Draft card after a reload. ---
  await selectTextInActivePanel(page, "A spare sentence for the draft-abandon test.");
  await page.waitForSelector(".docreview-popover", { timeout: 2000 });
  await page.type(".docreview-popover-input", "draft to survive reload");
  // Abandon without Cancel/Submit: clear the selection and click elsewhere -- the mouseup handler
  // then captures a null anchor (E15's own path) and calls closePopover(), which persists the
  // still-open draft via onPopoverDismissed (text_anchors.js).
  await page.evaluate(() => window.getSelection().removeAllRanges());
  await page.mouse.click(10, 10);
  await page.waitForFunction(() => !document.querySelector(".docreview-popover"), { timeout: 2000 });

  await page.reload({ waitUntil: "networkidle0" });
  await waitForPanel(page, `(html) => html.includes("draft to survive reload")`);
  const restoredDraftText = await page.$eval(".docreview-draft-card .docreview-draft-input", (el) => el.value);
  check(restoredDraftText === "draft to survive reload",
    "an abandoned popover's draft was restored from localStorage as a sidebar Draft card after reload");

  // --- E15: an empty selection must not open a popover. (Also exercised implicitly by E7's
  // abandon-click above, which relies on the same captureSelectionAnchor() null path -- this
  // check isolates it as its own UseCases row.) ---
  await page.evaluate(() => {
    window.getSelection().removeAllRanges();
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await new Promise((resolve) => setTimeout(resolve, 200));
  check(!(await page.$(".docreview-popover")), "an empty selection must not open a popover");

  // --- U12: an orphaned thread's sidebar Orphaned section; engineer replies, then Resolve closes
  // it (moves it out of Orphaned into Resolved, same as any other thread). ---
  const orphanAnchor = { kind: "text", file: "Doc.md", quote: "This sentence about to be orphaned soon." };
  const orphanCreate = await page.evaluate(async (anchor) => {
    const res = await fetch("/api/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anchor, text: "will this survive?" }),
    });
    return res.json();
  }, orphanAnchor);
  const orphanId = orphanCreate.id;

  // Delete the sentence the thread is anchored to -- the next /api/state poll recomputes its
  // resolution server-side (anchor_resolver), independent of which tab is active.
  writeFileSync(
    docPath,
    "# Smoke Doc\n\n" +
      "The quick brown fox jumps over the lazy dog.\n\n" +
      "Second paragraph for multi-block selection.\n\n" +
      "A spare sentence for the draft-abandon test.\n\n" +
      "Another spare sentence for the server-error test.\n"
  );
  await waitForPanel(page, `(html) => html.includes("Orphaned (1)")`);
  sidecarNow = JSON.parse(readFileSync(sidecarPath, "utf8"));
  check(sidecarNow.threads.find((t) => t.id === orphanId)?.status === "open",
    "the orphaned thread's own status stays open until the engineer acts on it");

  await page.evaluate((id) => {
    const textarea = document.querySelector(`.docreview-card[data-thread-id="${id}"] .docreview-reply-input`);
    textarea.value = "replying to the orphan before resolving";
    textarea.dispatchEvent(new Event("input"));
  }, orphanId);
  await page.click(`.docreview-card[data-thread-id="${orphanId}"] .docreview-reply-btn`);
  await waitForSidecar(sidecarPath, (data) =>
    data.threads.find((t) => t.id === orphanId)?.replies.some((r) => r.text === "replying to the orphan before resolving")
  );

  await page.evaluate((id) => {
    const card = document.querySelector(`.docreview-card[data-thread-id="${id}"]`);
    const btn = Array.from(card.querySelectorAll(".docreview-status-btn")).find((b) => b.dataset.status === "resolved");
    btn.click();
  }, orphanId);
  await waitForSidecar(sidecarPath, (data) => data.threads.find((t) => t.id === orphanId)?.status === "resolved");
  await waitForPanel(page, `(html) => !html.includes("Orphaned")`);
  const panelHtmlAfterResolve = await page.evaluate(() => document.getElementById("docreview-panel").innerHTML);
  check(!panelHtmlAfterResolve.includes("Orphaned"),
    "Resolve on an orphaned thread's card closed it out of the Orphaned section");

  // --- U11: clicking a thread's card in the panel switches to its tab and scrolls (text) or
  // zooms (diagram pin) to it. ---
  await page.click('[data-i="3"]'); // move off tab 0 first so the click below proves it switches
  await page.waitForFunction(() => document.querySelector(".panel.active .diagram svg") !== null, { timeout: 2000 });

  await page.click(`.docreview-card[data-thread-id="${textThread.id}"] .docreview-card-quote`);
  await page.waitForFunction(() => document.querySelector('.tab[data-i="0"]').classList.contains("active"), { timeout: 2000 });
  await new Promise((resolve) => setTimeout(resolve, 300)); // let focusThread's own frame-settle waits run
  const textHighlightPresent = await page.evaluate(
    (id) => !!document.querySelector(`mark.docreview-highlight[data-thread-id="${id}"]`),
    textThread.id
  );
  check(textHighlightPresent, "clicking the text thread's card switched to its tab, to a highlight it can scroll to");

  await page.click('[data-i="0"]'); // leave tab 3 so the click below proves it switches back
  await page.waitForFunction(() => document.querySelector(".panel.active .markdown") !== null, { timeout: 2000 });

  await page.click(`.docreview-card[data-thread-id="${classThread.id}"] .docreview-card-quote`);
  await page.waitForFunction(() => document.querySelector('.tab[data-i="3"]').classList.contains("active"), { timeout: 2000 });
  await new Promise((resolve) => setTimeout(resolve, 300)); // let the zoom()/pan() settle frames apply
  const classZoomAfterFocus = await page.evaluate(() => window.panZoomInstances["d3"]?.getZoom());
  check(classZoomAfterFocus === 2, `clicking the diagram thread's card zoomed to its pin (FOCUS_ZOOM=2), got ${classZoomAfterFocus}`);

  // --- E16: a poll tick triggered by someone else's reply must not erase an unrelated
  // in-progress reply draft (thread_panel.js's pendingReplies, read before every rebuild). ---
  await page.evaluate((id) => {
    const textarea = document.querySelector(`.docreview-card[data-thread-id="${id}"] .docreview-reply-input`);
    textarea.value = "still drafting, do not erase me";
    textarea.dispatchEvent(new Event("input"));
  }, classThread.id);

  execFileSync("python3", ["doc_review.py", "reply", docPath, orphanId, "agent note while engineer was typing"], {
    cwd: TOOL_DIR,
  });
  await waitForSidecar(sidecarPath, (data) =>
    data.threads.find((t) => t.id === orphanId)?.replies.some((r) => r.text === "agent note while engineer was typing")
  );
  await new Promise((resolve) => setTimeout(resolve, 1300)); // let the next 1s poll tick rebuild the panel
  const preservedDraft = await page.evaluate(
    (id) => document.querySelector(`.docreview-card[data-thread-id="${id}"] .docreview-reply-input`)?.value ?? null,
    classThread.id
  );
  check(preservedDraft === "still drafting, do not erase me",
    `an unrelated reply's poll tick must not clear this card's in-progress draft, got: ${JSON.stringify(preservedDraft)}`);

  // --- E18: a pan-drag (mouse moves past the threshold between down and up) must not create a
  // pin, only a stationary click may. ---
  await page.click('[data-i="2"]');
  await page.waitForFunction(() => document.querySelector(".panel.active .diagram svg") !== null, { timeout: 2000 });
  const dragStart = await page.evaluate(() => {
    const node = document.querySelector('g.node[id*="flowchart-Start-"]');
    const rect = node.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  });
  const threadCountBeforeDrag = JSON.parse(readFileSync(sidecarPath, "utf8")).threads.length;

  await page.mouse.move(dragStart.x, dragStart.y);
  await page.mouse.down();
  await page.mouse.move(dragStart.x + 30, dragStart.y + 30, { steps: 5 });
  await page.mouse.up();
  await new Promise((resolve) => setTimeout(resolve, 200));

  check(!(await page.$(".docreview-popover")), "a pan-drag past the threshold must not open a comment popover");
  const threadCountAfterDrag = JSON.parse(readFileSync(sidecarPath, "utf8")).threads.length;
  check(threadCountAfterDrag === threadCountBeforeDrag, "a pan-drag past the threshold must not create a new thread/pin");

  // --- E17: a diagram parse error must hide pins and classify its threads as "failed to render",
  // not Orphaned -- even though the broken content also happens to make the anchor's own
  // source_id/label resolution come back genuinely orphaned (anchor_resolver has no idea the
  // diagram fails to parse; it just greps text). review_ui.js/thread_panel.js's classifyThread
  // checks render-failure before orphan status for exactly this reason. flow.mmd (tab 2) is
  // still valid and active from the E18 drag test above, so this comment anchors to it while it
  // still resolves normally. ---
  const renderFailAnchor = { kind: "diagram", file: "flow.mmd", source_id: "Start", label: "Start", point: { x: 0, y: 0 } };
  const renderFailCreate = await page.evaluate(async (anchor) => {
    const res = await fetch("/api/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anchor, text: "watching this node" }),
    });
    return res.json();
  }, renderFailAnchor);
  const renderFailThreadId = renderFailCreate.id;
  let renderFailState = await page.evaluate(async () => (await (await fetch("/api/state")).json()));
  check(renderFailState.threads.find((t) => t.id === renderFailThreadId)?.resolution?.status === "resolved",
    "sanity check: the render-failure thread resolves normally before the diagram is broken");

  // Same unterminated-bracket fixture test_diagram_validation_boundary.py uses for the CLI side
  // of this edge case -- a genuine mermaid parse error, and (since it drops the "Start" node
  // entirely) also a genuine text-match orphan for the resolver's own logic.
  writeFileSync(flowPath, "graph TD\n  A[Unterminated --> B[End]\n");
  await new Promise((resolve) => setTimeout(resolve, 1300)); // let the next 1s poll tick pick up the new source
  await page.click('[data-i="2"]'); // re-activate: forces the failed render attempt
  await page.waitForFunction(() => document.querySelector("#d2 .error") !== null, { timeout: 3000 });
  await waitForPanel(page, `(html) => html.includes("Diagram failed to render")`);

  renderFailState = await page.evaluate(async () => (await (await fetch("/api/state")).json()));
  check(renderFailState.threads.find((t) => t.id === renderFailThreadId)?.resolution?.status === "orphaned",
    "sanity check: the resolver itself (text-grep only) now genuinely can't find the node -- the UI must override this below");
  const renderFailPanelHtml = await page.evaluate(() => document.getElementById("docreview-panel").innerHTML);
  check(!renderFailPanelHtml.includes("Orphaned"),
    "a diagram parse error must not put the thread in the Orphaned section, even though its own anchor resolution is orphaned");
  const renderFailPinExists = await page.evaluate(
    (id) => !!document.querySelector(`.docreview-pin[data-thread-id="${id}"]`),
    renderFailThreadId
  );
  check(!renderFailPinExists, "a diagram that failed to render must not show a pin for its thread");

  // --- E21: the server becoming unreachable mid-POST must show an error and keep the draft (its
  // text and the open popover), not silently discard it. ---
  await page.click('[data-i="0"]');
  await page.waitForFunction(() => document.querySelector(".panel.active .markdown") !== null, { timeout: 2000 });
  await selectTextInActivePanel(page, "Another spare sentence for the server-error test.");
  await page.waitForSelector(".docreview-popover", { timeout: 2000 });
  await page.type(".docreview-popover-input", "will this survive a dead server?");

  const cdp = await page.target().createCDPSession();
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0,
  });
  await page.click(".docreview-popover-submit");
  await page.waitForFunction(() => {
    const el = document.querySelector(".docreview-popover-error");
    return !!el && !el.hidden;
  }, { timeout: 3000 });
  const popoverStillOpenAfterFailure = await page.$(".docreview-popover");
  const draftTextAfterFailure = await page.$eval(".docreview-popover-input", (el) => el.value);
  check(!!popoverStillOpenAfterFailure, "a failed POST (server unreachable) must leave the popover open, not discard it");
  check(draftTextAfterFailure === "will this survive a dead server?", "the typed draft text survived the failed submit");

  await cdp.send("Network.emulateNetworkConditions", {
    offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1,
  });
  await cdp.detach(); // [RES]: release the session acquired via createCDPSession() above
  await integrationChecklistSmoke(browser);
} catch (err) {
  hardFailure = err;
  console.error("[review_ui_smoke] CRASHED:", err.message);
} finally {
  if (browser) {
    await browser.close();
  }
  server.kill();
  rmSync(tmp, { recursive: true, force: true });
}

const failed = hardFailure || results.some((r) => !r.ok);
console.log(`[review_ui_smoke] ${results.filter((r) => r.ok).length}/${results.length} checks passed${hardFailure ? " (plus a crash)" : ""}`);
process.exit(failed ? 1 : 0);
