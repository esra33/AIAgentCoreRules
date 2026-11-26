// Composer: wires the modules below to the page's render/state events and DOM. No logic of its
// own beyond that wiring -- see the individual modules for behavior.
import { enableTextSelectionComments } from "./text_anchors.js";
import { enableDiagramClickComments } from "./diagram_anchors.js";
import { redrawOverlays } from "./overlays.js";
import { renderThreadPanel } from "./thread_panel.js";
import "./diagram_progress.js";

const FOCUS_ZOOM = 2;
const FOCUS_SETTLE_FRAMES = 3;

let latestThreads = [];
let lastThreadsSignature = null;
const renderFailedTabIds = new Set();

function threadsSignature(threads) {
  return JSON.stringify(
    threads.map((t) => [t.id, t.status, t.resolution?.status, t.resolution?.line, t.replies.length])
  );
}

function waitFrames(count) {
  return new Promise((resolve) => {
    let remaining = count;
    function step() {
      remaining -= 1;
      if (remaining <= 0) {
        resolve();
      } else {
        requestAnimationFrame(step);
      }
    }
    requestAnimationFrame(step);
  });
}

function activeTabFile(selector) {
  const activePanel = document.querySelector(selector);
  if (!activePanel) {
    return null;
  }
  const tab = (window.docReview?.tabs || []).find((t) => t.id === activePanel.id);
  return tab ? tab.file : null;
}

function refreshPanel() {
  const panelEl = document.getElementById("docreview-panel");
  if (!panelEl) {
    return;
  }
  renderThreadPanel(panelEl, latestThreads, renderFailedTabIds, {
    onChanged: refreshFromServer,
    onThreadFocused: focusThread,
  });
}

async function refreshFromServer() {
  // A reply or status change wants to feel immediate rather than waiting out the rest of the
  // current poll interval -- reuse the exact same state the periodic poll already fetches.
  try {
    const res = await fetch("/api/state");
    const state = await res.json();
    latestThreads = state.threads;
    lastThreadsSignature = threadsSignature(latestThreads);
    refreshPanel();
    redrawOverlays(latestThreads, renderFailedTabIds);
  } catch (err) {
    // the next scheduled poll will pick it back up
  }
}

async function focusThread(threadId) {
  const thread = latestThreads.find((t) => t.id === threadId);
  if (!thread) {
    return;
  }
  const tab = (window.docReview?.tabs || []).find((t) => t.file === thread.anchor.file);
  if (!tab) {
    return; // E20: file not served this run
  }
  const tabIndex = Number(tab.id.slice(1));
  document.querySelector(`.tab[data-i="${tabIndex}"]`)?.click();
  // The tab click's own activate() may call the svg-pan-zoom instance's fit()/center() (when the
  // diagram was already rendered and its source hasn't changed) -- that, like zoom()/pan() below,
  // applies via the browser's own requestAnimationFrame scheduling, not synchronously. Settling a
  // few frames before reading any geometry avoided a stale-state mismatch in a headless-Chrome
  // check (confirmed empirically: reading right after a zoom()/pan() call was off by exactly the
  // zoom-dependent amount a frame later fixed).
  await waitFrames(FOCUS_SETTLE_FRAMES);

  if (thread.anchor.kind === "text") {
    document
      .querySelector(`mark.docreview-highlight[data-thread-id="${threadId}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  const panel = document.getElementById(tab.id);
  const pin = panel?.querySelector(`.docreview-pin[data-thread-id="${threadId}"]`);
  const instance = window.panZoomInstances && window.panZoomInstances[tab.id];
  if (!panel || !pin || !instance) {
    return;
  }
  const svgRect = panel.querySelector("svg").getBoundingClientRect();
  const x = parseFloat(pin.getAttribute("cx"));
  const y = parseFloat(pin.getAttribute("cy"));
  // Inverse of screenToDiagramPoint in diagram_anchors.js: pick the pan that puts this
  // diagram-space point at the viewport's center for the chosen zoom level.
  instance.zoom(FOCUS_ZOOM);
  await waitFrames(FOCUS_SETTLE_FRAMES);
  instance.pan({ x: svgRect.width / 2 - x * FOCUS_ZOOM, y: svgRect.height / 2 - y * FOCUS_ZOOM });
}

document.addEventListener("docreview:rendered", (event) => {
  const tabId = event.detail.tabId;
  const panel = document.getElementById(tabId);
  if (panel?.closest(".diagram")) {
    const failed = !!panel.querySelector(".error");
    if (failed) {
      renderFailedTabIds.add(tabId);
    } else {
      renderFailedTabIds.delete(tabId);
    }
  }
  redrawOverlays(latestThreads, renderFailedTabIds);
  refreshPanel(); // a render-failure transition changes Active vs. the "failed to render" note
});

document.addEventListener("docreview:state", (event) => {
  // This fires every poll tick (every second), forever, whether or not anything actually
  // changed -- rebuilding the panel and re-wrapping every highlight on each tick was both
  // wasteful and user-visible: it silently reset any <details> the engineer had just opened
  // (looked like "Resolved can't be expanded"), and repeatedly unwrapping/rewrapping a highlight
  // whose quote straddles an inline element (code/bold/link) risks compounding DOM churn over
  // time. Skip the whole cycle unless the threads actually differ from last tick.
  const signature = threadsSignature(event.detail.threads);
  if (signature === lastThreadsSignature) {
    return;
  }
  lastThreadsSignature = signature;
  latestThreads = event.detail.threads;
  redrawOverlays(latestThreads, renderFailedTabIds);
  refreshPanel();
});

enableTextSelectionComments({
  getActiveTabFile: () => activeTabFile(".panel.active .markdown"),
  onCommentCreated: refreshFromServer,
});

enableDiagramClickComments({
  getActiveTabFile: () => activeTabFile(".panel.active .diagram"),
  onCommentCreated: refreshFromServer,
});
