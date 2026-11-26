// Click target -> diagram anchor (node / edge / sequence message / empty space); click point ->
// diagram-space coordinates that stay valid across pan/zoom.
import { postComment } from "./api.js";
import { discardNewThreadDraft, generateDraftId, saveNewThreadDraft } from "./drafts.js";

const POPOVER_WIDTH = 280;
const DRAG_THRESHOLD_PX = 5;

let popoverEl = null;
let mouseDownAt = null; // {x, y}: tracks whether a mouseup is a click or the end of a pan-drag
// Set while a popover is open, to whatever should happen if it's dismissed WITHOUT an explicit
// Cancel or a successful Submit (Escape, clicking elsewhere, or the tab/page closing) -- E7/Q5:
// an abandoned-but-not-discarded draft must survive, reappearing as a sidebar Draft card.
let onPopoverDismissed = null;

window.addEventListener("beforeunload", () => onPopoverDismissed?.());

function activeDiagramPanel() {
  return document.querySelector(".panel.active .diagram");
}

function screenToDiagramPoint(panelEl, clientX, clientY) {
  // svg-pan-zoom pans/zooms via its own instance state, not the root <svg>'s own CTM (verified:
  // getScreenCTM()-based inversion drifted ~40px after a real pan+zoom in headless Chrome). The
  // instance's own getPan()/getZoom() getters, exposed on window.panZoomInstances by
  // review_server.py, give a point that is stable across pan/zoom instead.
  const svg = panelEl.querySelector("svg");
  const rect = svg.getBoundingClientRect();
  const instance = window.panZoomInstances && window.panZoomInstances[panelEl.id];
  const zoom = instance ? instance.getZoom() : 1;
  const pan = instance ? instance.getPan() : { x: 0, y: 0 };
  return { x: (clientX - rect.left - pan.x) / zoom, y: (clientY - rect.top - pan.y) / zoom };
}

export function nodeSourceId(nodeEl) {
  // mermaid 11.15.0: a flowchart node's id is "<svgId>-flowchart-<sourceId>-<n>"; a classDiagram
  // node's is "<svgId>-classId-<sourceId>-<n>" (confirmed via headless render of both). Edges are
  // out of scope here -- classDiagram relations use a completely different id/class scheme
  // ("id_<from>_<to>_<n>", class "relation") than flowchart's "L_<from>_<to>_<n>" -- task 27.
  const match = nodeEl.id.match(/-(?:flowchart|classId)-(.+)-\d+$/);
  return match ? match[1] : null;
}

function knownNodeIdsIn(svgRoot) {
  const ids = new Set();
  svgRoot.querySelectorAll("g.node").forEach((el) => {
    const id = nodeSourceId(el);
    if (id) {
      ids.add(id);
    }
  });
  return ids;
}

function parseEdgeDataId(dataId, knownNodeIds) {
  // Format "L_<from>_<to>_<n>" -- <from>/<to> can themselves contain underscores (e.g. the
  // project's own "old_id" fixture), so a naive split("_") is ambiguous. Disambiguate against
  // the diagram's actual node ids instead, preferring the longest candidate match.
  const match = dataId && dataId.match(/^L_(.*)_\d+$/);
  if (!match) {
    return null;
  }
  const fromTo = match[1];
  const candidates = Array.from(knownNodeIds).sort((a, b) => b.length - a.length);
  for (const from of candidates) {
    if (fromTo === from) {
      continue; // "to" can't be empty
    }
    if (fromTo.startsWith(from + "_")) {
      const to = fromTo.slice(from.length + 1);
      if (knownNodeIds.has(to)) {
        return { from, to };
      }
    }
  }
  return null;
}

function findEdgePath(svgRoot, target) {
  const direct = target.closest("path.flowchart-link");
  if (direct) {
    return direct;
  }
  // A click on the edge's own label (a sibling g.edgeLabel, not a descendant of the path) must
  // count as clicking the edge too -- the thin path is an easy miss otherwise.
  const labelGroup = target.closest("g.edgeLabel");
  const dataId = labelGroup && labelGroup.querySelector("g.label[data-id]")?.getAttribute("data-id");
  return dataId ? svgRoot.querySelector(`path.flowchart-link[data-id="${CSS.escape(dataId)}"]`) : null;
}

function findSequenceMessage(target) {
  const text = target.closest("text.messageText");
  if (text) {
    return text;
  }
  // mermaid pairs each message's text with the NEXT sibling line (data-id "i<k>") in DOM order
  // (verified in headless Chrome) -- a click on the line itself must count as the message too.
  const line = target.closest("line[data-id]");
  const prev = line && /^i\d+$/.test(line.getAttribute("data-id") || "") ? line.previousElementSibling : null;
  return prev && prev.matches("text.messageText") ? prev : null;
}

function messageOccurrenceIndex(svgRoot, messageTextEl) {
  const label = messageTextEl.textContent.trim();
  const sameLabel = Array.from(svgRoot.querySelectorAll("text.messageText")).filter(
    (el) => el.textContent.trim() === label
  );
  return sameLabel.indexOf(messageTextEl);
}

export function captureDiagramClickAnchor(panelEl, event, file) {
  const svgRoot = panelEl.querySelector("svg");
  if (!svgRoot) {
    return null;
  }
  const point = screenToDiagramPoint(panelEl, event.clientX, event.clientY);

  const nodeEl = event.target.closest("g.node");
  if (nodeEl) {
    return {
      kind: "diagram",
      file,
      point,
      element_id: nodeEl.id,
      source_id: nodeSourceId(nodeEl),
      label: nodeEl.textContent.trim(),
    };
  }

  const messageTextEl = findSequenceMessage(event.target);
  if (messageTextEl) {
    return {
      kind: "diagram",
      file,
      point,
      label: messageTextEl.textContent.trim(),
      occurrence_index: messageOccurrenceIndex(svgRoot, messageTextEl),
    };
  }

  const edgeEl = findEdgePath(svgRoot, event.target);
  if (edgeEl) {
    const dataId = edgeEl.getAttribute("data-id");
    const parsed = parseEdgeDataId(dataId, knownNodeIdsIn(svgRoot));
    if (parsed) {
      const sameEdges = Array.from(svgRoot.querySelectorAll("path.flowchart-link")).filter((el) => {
        const p = parseEdgeDataId(el.getAttribute("data-id"), knownNodeIdsIn(svgRoot));
        return p && p.from === parsed.from && p.to === parsed.to;
      });
      const labelEl = svgRoot.querySelector(`g.label[data-id="${CSS.escape(dataId)}"]`);
      return {
        kind: "diagram",
        file,
        point,
        element_id: dataId,
        edge: { from: parsed.from, to: parsed.to, index: sameEdges.indexOf(edgeEl) },
        label: labelEl ? labelEl.textContent.trim() : null,
      };
    }
  }

  // E15-equivalent for diagrams: no known element under the click -> an empty-space pin, with
  // nothing to re-resolve but its point (anchor_resolver.resolve_diagram_anchor treats this as
  // trivially resolved, not orphaned).
  return { kind: "diagram", file, point };
}

function closePopover() {
  if (popoverEl) {
    onPopoverDismissed?.();
    onPopoverDismissed = null;
    popoverEl.remove();
    popoverEl = null;
  }
}

function openPopover(clientX, clientY, anchor, onCommentCreated) {
  closePopover(); // dismisses (and drafts, if non-empty) any popover already open elsewhere
  const draftId = generateDraftId();
  const popover = document.createElement("div");
  popover.className = "docreview-popover";
  popover.style.top = `${clientY + 8}px`;
  popover.style.left = `${Math.max(8, Math.min(clientX, window.innerWidth - POPOVER_WIDTH - 8))}px`;
  popover.innerHTML = `
    <textarea class="docreview-popover-input" placeholder="Add a comment..."></textarea>
    <div class="docreview-popover-error" hidden></div>
    <div class="docreview-popover-actions">
      <button type="button" class="docreview-popover-cancel">Cancel</button>
      <button type="button" class="docreview-popover-submit">Comment</button>
    </div>
  `;
  document.body.appendChild(popover);
  popoverEl = popover;

  const textarea = popover.querySelector(".docreview-popover-input");
  const errorEl = popover.querySelector(".docreview-popover-error");
  textarea.focus();

  onPopoverDismissed = () => {
    const text = textarea.value.trim();
    if (text) {
      saveNewThreadDraft(draftId, anchor, text);
    }
  };

  popover.querySelector(".docreview-popover-cancel").addEventListener("click", () => {
    onPopoverDismissed = null; // an explicit Cancel means don't persist on the way out
    discardNewThreadDraft(draftId);
    closePopover();
  });

  popover.querySelector(".docreview-popover-submit").addEventListener("click", async () => {
    const text = textarea.value.trim();
    if (!text) {
      errorEl.textContent = "Comment can't be empty.";
      errorEl.hidden = false;
      return;
    }
    const result = await postComment(anchor, text);
    if (!result.ok) {
      errorEl.textContent = result.error; // E21: keep the popover (and its draft) open on failure
      errorEl.hidden = false;
      return;
    }
    onPopoverDismissed = null;
    discardNewThreadDraft(draftId); // no-op if this draft was never actually persisted
    closePopover();
    if (onCommentCreated) {
      onCommentCreated(result.data, anchor);
    }
  });
}

export function enableDiagramClickComments({ getActiveTabFile, onCommentCreated }) {
  document.addEventListener("mousedown", (event) => {
    const panel = activeDiagramPanel();
    mouseDownAt = panel && panel.contains(event.target) ? { x: event.clientX, y: event.clientY } : null;
  });

  document.addEventListener("mouseup", (event) => {
    if (popoverEl && popoverEl.contains(event.target)) {
      return;
    }
    const downAt = mouseDownAt;
    mouseDownAt = null;
    const panel = activeDiagramPanel();
    if (!panel || !panel.contains(event.target) || !downAt) {
      closePopover();
      return;
    }
    const moved = Math.hypot(event.clientX - downAt.x, event.clientY - downAt.y);
    if (moved > DRAG_THRESHOLD_PX) {
      return; // E18: a pan-drag must not create a pin
    }
    const anchor = captureDiagramClickAnchor(panel, event, getActiveTabFile());
    openPopover(event.clientX, event.clientY, anchor, onCommentCreated);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePopover();
    }
  });
}
