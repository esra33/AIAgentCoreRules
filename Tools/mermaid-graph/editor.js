"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  source: "", saved: "", revision: null, graph: null, selection: null, focus: null,
  manualPositions: new Map(), busy: false, pending: false, timer: null, parseVersion: 0,
  drawing: false, pointerLink: null, browserLink: null,
};
const workspace = $("workspace");
const nodeKinds = { class: "Class", interface: "Interface", struct: "Struct", enum: "Enum" };
const kindColor = (kind) => getComputedStyle(document.documentElement).getPropertyValue("--kind-" + kind).trim();
const arrows = {
  inheritance: ["triangle", "hollow"],
  realization: ["triangle", "hollow"],
  composition: ["diamond", "filled"],
  aggregation: ["diamond", "hollow"],
  association: ["vee", "filled"],
  dependency: ["vee", "filled"],
};
const relationshipTypes = $("relationship-types");
const enabledRelationships = new Set(Object.keys(arrows));
for (const kind of enabledRelationships) {
  const label = document.createElement("label");
  const toggle = document.createElement("input");
  toggle.type = "checkbox";
  toggle.checked = true;
  toggle.onchange = () => {
    if (toggle.checked) enabledRelationships.add(kind);
    else enabledRelationships.delete(kind);
    filterGraph();
    renderDetail();
  };
  label.append(toggle, kind[0].toUpperCase() + kind.slice(1));
  relationshipTypes.querySelector(".actions").append(label);
}
const edgeStyle = {
  "width": 1.5, "line-color": "#839ab4", "curve-style": "bezier",
  "source-arrow-color": "#839ab4", "target-arrow-color": "#839ab4",
  "line-style": (edge) => edge.data("arrow").includes("..") ? "dashed" : "solid",
  "label": "data(label)", "source-label": "data(leftMultiplicity)", "target-label": "data(rightMultiplicity)",
  "source-text-offset": 17, "target-text-offset": 17,
  "font-size": 11, "color": "#e8eef6", "text-background-color": "#101722",
  "text-background-opacity": 0.9, "text-background-padding": 2,
};
for (const [side, direction] of [["source", "left"], ["target", "right"]]) {
  edgeStyle[side + "-arrow-shape"] = (edge) =>
    edge.data("direction") === direction ? arrows[edge.data("kind")][0] : "none";
  edgeStyle[side + "-arrow-fill"] = (edge) => arrows[edge.data("kind")][1];
}
const cy = typeof cytoscape === "function" ? cytoscape({
  container: $("cy"), wheelSensitivity: 0.3, minZoom: 0.06, maxZoom: 2.5, boxSelectionEnabled: false,
  style: [
    { selector: "node", style: {
      "shape": "round-rectangle", "width": "label", "height": 26, "padding": 9,
      "label": "data(name)", "color": "#ffffff", "font-size": 13, "text-valign": "center",
      "background-color": kindColor("class"), "border-width": 1, "border-color": "#819fbf",
    } },
    { selector: 'node[kind = "interface"]', style: { "shape": "round-tag", "background-color": kindColor("interface") } },
    { selector: 'node[kind = "struct"]', style: { "shape": "rectangle", "background-color": kindColor("struct"), "color": "#24180d" } },
    { selector: 'node[kind = "enum"]', style: { "shape": "rectangle", "background-color": kindColor("enum"), "color": "#24180d" } },
    { selector: "node.implicit", style: { "border-style": "dashed" } },
    { selector: "node.focus-root", style: { "border-width": 3, "border-color": "#ffd166" } },
    { selector: "node:selected", style: { "border-width": 3, "border-color": "#8bcdff" } },
    { selector: "edge", style: edgeStyle },
    { selector: "edge:selected", style: { "width": 3, "line-color": "#8bcdff" } },
    { selector: ".filtered", style: { "display": "none" } },
  ],
}) : null;

function nodeId(name) { return "class:" + name; }
function edgeId(line) { return "relationship:" + line; }
function dirty() { return state.source !== state.saved; }
function canEdit() { return state.graph && !state.graph.diagnostics.length && !state.busy && !state.pending; }

function availability() {
  $("save").disabled = !state.revision || !dirty() || state.busy;
  $("reload").disabled = state.busy;
  $("source").readOnly = state.busy;
  for (const element of document.querySelectorAll("[data-edit]")) element.disabled = !canEdit();
  $("add-edge").disabled = !canEdit() || !state.graph.classes.length;
  const canDraw = Boolean(cy && canEdit() && state.graph.classes.length);
  $("link-tool").disabled = !canDraw;
  $("draw-arrow").disabled = !canDraw;
  $("focus").disabled = !cy || !state.selection?.name;
  workspace.classList.toggle("drawing", state.drawing && canDraw);
  for (const entry of $("node-list").querySelectorAll(".node-entry")) {
    entry.draggable = canDraw && Boolean(state.selection?.name) && entry.dataset.name !== state.selection.name;
  }
  updateWorkspaceNote();
}

function error(message = "") {
  $("error").textContent = message;
  $("error").hidden = !message;
}

async function api(path, method = "GET", payload) {
  const options = { method };
  if (payload) {
    options.headers = { "Content-Type": "application/json", "X-Mermaid-Editor": "1" };
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}

function normalized(source) { return source.replace(/\r\n?/g, "\n"); }

// Textareas normalize line endings. Keep the original endings on unaffected lines.
function applyTextarea(source, value) {
  const previous = normalized(source);
  if (previous === value) return source;
  let prefix = 0;
  while (prefix < previous.length && previous[prefix] === value[prefix]) prefix++;
  let suffix = 0;
  while (suffix < Math.min(previous.length, value.length) - prefix &&
         previous[previous.length - 1 - suffix] === value[value.length - 1 - suffix]) suffix++;
  const offsets = [0];
  let offset = 0;
  for (const unit of source.match(/\r\n|[\s\S]/g) || []) {
    offsets.push(offset += unit.length);
  }
  const start = offsets[prefix];
  const end = offsets[previous.length - suffix];
  const newline = source.slice(start, end).match(/\r\n|\r|\n/)?.[0] ||
    source.match(/\r\n|\r|\n/)?.[0] || "\n";
  return source.slice(0, start) + value.slice(prefix, value.length - suffix).replace(/\n/g, newline) + source.slice(end);
}

function describe(edge) {
  return [
    edge.left, edge.leftMultiplicity ? '"' + edge.leftMultiplicity + '"' : "",
    edge.arrow, edge.rightMultiplicity ? '"' + edge.rightMultiplicity + '"' : "", edge.right,
    edge.label ? " : " + edge.label : "",
  ].filter(Boolean).join(" ");
}

function editButton(label, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.dataset.edit = "";
  button.addEventListener("click", action);
  return button;
}

function list(title, items) {
  const heading = document.createElement("h3");
  heading.textContent = title;
  const entries = document.createElement("ul");
  for (const item of items) {
    const li = document.createElement("li");
    if (typeof item === "string") li.textContent = item;
    else li.append(item);
    entries.append(li);
  }
  $("detail").append(heading, entries);
}

function renderDetail() {
  const graph = state.graph;
  const name = state.selection?.name;
  const record = graph?.classes.find((item) => item.name === name);
  const edge = graph?.relationships.find((item) => item.startLine === state.selection?.line);
  $("selection-actions").replaceChildren();
  $("detail").replaceChildren();
  if (record) {
    $("selection").textContent = name;
    const attached = graph.relationships.filter((item) => item.left === name || item.right === name);
    $("selection-actions").append(
      editButton("Rename", () => showClass(name)),
      editButton("Delete", () => {
        const lines = attached.map((item) => "Line " + item.startLine + " · " + describe(item));
        const details = lines.length ? "\n\nAttached relationships to remove\n" + lines.join("\n") : "\n\nNo attached relationships.";
        if (confirm("Delete class " + name + "?" + details)) visualEdit({ action: "deleteClass", name });
      }),
    );
    list(nodeKinds[record.kind || "class"] + " members",
      record.members.length ? record.members.map((member) => member.text) : ["No members"]);
    const visible = attached.filter((item) => enabledRelationships.has(item.kind));
    list("Relationships", visible.length ? visible.map((item) => {
      const button = document.createElement("button");
      button.textContent = describe(item);
      button.title = "Line " + item.startLine;
      button.onclick = () => select({ line: item.startLine });
      return button;
    }) : [attached.length ? "No matching relationships" : "No relationships"]);
  } else if (edge) {
    $("selection").textContent = edge.kind[0].toUpperCase() + edge.kind.slice(1);
    $("detail").textContent = describe(edge);
    $("selection-actions").append(
      editButton("Edit", () => showEdge(edge)),
      editButton("Remove", () => visualEdit({ action: "deleteRelationship", line: edge.startLine })),
    );
  } else {
    $("selection").textContent = "Selection";
    $("detail").textContent = "Select a class or relationship.";
  }
  availability();
}

function select(selection) {
  state.selection = selection;
  filterGraph();
  if (cy) {
    cy.elements(":selected").unselect();
    const id = selection?.name ? nodeId(selection.name) : edgeId(selection?.line);
    cy.getElementById(id).select();
  }
  for (const entry of $("node-list").querySelectorAll(".node-entry")) {
    entry.setAttribute("aria-pressed", String(entry.dataset.name === selection?.name));
  }
  renderDetail();
}

function fit() {
  const visible = cy?.elements().not(".filtered");
  if (!visible?.length) return;
  cy.resize();
  cy.fit(visible, 42);
  if (cy.zoom() > 1.6) {
    const center = { x: cy.width() / 2, y: cy.height() / 2 };
    cy.zoom({ level: 1.6, renderedPosition: center });
  }
}

function filterGraph() {
  $("focus-controls").hidden = !state.focus;
  const selected = state.selection?.name;
  relationshipTypes.hidden = !selected && !state.focus;
  if (!cy) return;
  cy.batch(() => {
    cy.elements().removeClass("filtered focus-root");
    const disabledEdges = cy.edges().filter((edge) => !enabledRelationships.has(edge.data("kind")));
    if (!state.focus) {
      if (selected) cy.getElementById(nodeId(selected)).connectedEdges().intersect(disabledEdges).addClass("filtered");
      return;
    }
    const root = cy.getElementById(nodeId(state.focus)).addClass("focus-root");
    let nodes = root;
    let frontier = root;
    for (let level = 0; level < Number($("depth").value) && frontier.length; level++) {
      frontier = frontier.connectedEdges().difference(disabledEdges).connectedNodes().difference(nodes);
      nodes = nodes.union(frontier);
    }
    const visibleEdges = nodes.connectedEdges().difference(disabledEdges).filter((edge) =>
      nodes.contains(edge.source()) && nodes.contains(edge.target()));
    cy.elements().difference(nodes.union(visibleEdges)).addClass("filtered");
  });
  updateWorkspaceNote();
}

function renderGraph(graph, fitView = false, reuseLayout = false) {
  const oldGraph = state.graph;
  state.graph = graph;
  const names = new Set(graph.classes.map((record) => record.name));
  if (!names.has(state.focus)) state.focus = null;
  if (state.selection?.name && !names.has(state.selection.name)) state.selection = null;
  for (const name of state.manualPositions.keys()) {
    if (!names.has(name)) state.manualPositions.delete(name);
  }
  if (cy) {
    const positions = new Map(cy.nodes().map((node) => [node.data("name"), node.position()]));
    const oldEdge = oldGraph?.relationships.find((edge) => edge.startLine === state.selection?.line);
    if (state.selection?.line && reuseLayout) {
      const same = graph.relationships.find((edge) => edge.startLine === oldEdge?.startLine && describe(edge) === describe(oldEdge));
      state.selection = same ? { line: same.startLine } : null;
    }
    cy.batch(() => {
      cy.elements().remove();
      cy.add(graph.classes.map((record) => ({
        group: "nodes", data: { id: nodeId(record.name), name: record.name, kind: record.kind || "class" },
        classes: record.declarations.length ? "" : "implicit",
      })));
      cy.add(graph.relationships.map((edge) => ({
        group: "edges", data: { ...edge, id: edgeId(edge.startLine), source: nodeId(edge.left), target: nodeId(edge.right) },
      })));
    });
    if (cy.nodes().length) {
      if (!reuseLayout || cy.nodes().some((node) => !positions.has(node.data("name")))) {
        const roots = cy.nodes().filter((node) => node.incomers("edge").length === 0);
        cy.layout({ name: "breadthfirst", directed: true, roots: roots.length ? roots : undefined,
          spacingFactor: 1.25, fit: false, animate: false }).run();
      } else {
        cy.nodes().positions((node) => positions.get(node.data("name")));
      }
      for (const [name, position] of state.manualPositions) cy.getElementById(nodeId(name)).position(position);
    }
  }
  const diagnostics = graph.diagnostics;
  $("diagnostics").hidden = !diagnostics.length;
  $("diagnostics").textContent = diagnostics.length ?
    ["Visual edits are disabled. You can edit and save Mermaid source.",
      ...diagnostics.map((item) => "Line " + item.line + " · " + item.message)].join("\n") : "";
  select(state.selection);
  if (fitView || (!oldGraph?.classes.length && graph.classes.length)) fit();
  search(false);
}

cy?.on("tap", "node", (event) => select({ name: event.target.data("name") }));
cy?.on("tap", "edge", (event) => select({ line: event.target.data("startLine") }));
cy?.on("tap", (event) => { if (event.target === cy) select(null); });
function focusClass(name) {
  state.focus = name;
  select({ name });
  fit();
}
cy?.on("dbltap", "node", (event) => focusClass(event.target.data("name")));
cy?.on("dragfree", "node", (event) => state.manualPositions.set(event.target.data("name"), event.target.position()));
$("fit").onclick = fit;
$("focus").onclick = () => focusClass(state.selection.name);
$("depth").onchange = () => { filterGraph(); fit(); };
$("full").onclick = () => { state.focus = null; filterGraph(); fit(); };

function findClass(name) {
  if (!name) return;
  if (cy) {
    const node = cy.getElementById(nodeId(name));
    if (node.hasClass("filtered")) {
      state.focus = null;
      filterGraph();
    }
    cy.center(node);
  }
  select({ name });
}

function search(activate) {
  const query = $("search").value.trim().toLowerCase();
  const records = (state.graph?.classes || []).filter(({ name }) => name.toLowerCase().includes(query))
    .sort((first, second) => first.name.localeCompare(second.name));
  if ($("node-browser").hidden) {
    $("matches").replaceChildren(new Option(records.length ? "Choose a node…" : "No matching nodes", ""));
    if (query) for (const { name } of records) $("matches").add(new Option(name, name));
  }
  $("matches").hidden = !query || !$("node-browser").hidden;
  renderNodeBrowser(records);
  if (activate && query) findClass((records.find(({ name }) => name.toLowerCase() === query) || records[0])?.name);
}

function renderNodeBrowser(records) {
  const fragment = document.createDocumentFragment();
  for (const { name, kind = "class" } of records) {
    const row = document.createElement("li");
    const entry = document.createElement("button");
    const badge = document.createElement("span");
    badge.className = "kind-badge kind-" + kind;
    badge.textContent = nodeKinds[kind][0];
    badge.setAttribute("aria-label", nodeKinds[kind]);
    entry.className = "node-entry";
    entry.dataset.name = name;
    entry.setAttribute("aria-pressed", String(name === state.selection?.name));
    entry.append(badge, document.createTextNode(name));
    row.append(entry);
    fragment.append(row);
  }
  if (!records.length) {
    const empty = document.createElement("li");
    empty.textContent = "No matching nodes.";
    fragment.append(empty);
  }
  $("node-list").replaceChildren(fragment);
  availability();
}

$("search").oninput = () => search(false);
$("search").onkeydown = (event) => { if (event.key === "Enter") search(true); };
$("matches").onchange = (event) => findClass(event.target.value);

function showClass(name) {
  const form = $("class-form");
  form.dataset.name = name || "";
  $("class-title").textContent = name ? "Rename " + name : "Add node";
  $("new-kind").hidden = Boolean(name);
  form.elements.kind.value = "class";
  form.elements.newName.value = name || "";
  $("class-dialog").showModal();
  form.elements.newName.select();
}

function showEdge(edge) {
  const form = $("edge-form");
  $("edge-title").textContent = edge ? "Edit relationship" : "Add relationship";
  const names = state.graph.classes.map((record) => record.name).sort();
  form.dataset.line = edge?.startLine || "";
  for (const key of ["left", "right"]) form.elements[key].replaceChildren(...names.map((name) => new Option(name, name)));
  form.elements.left.value = edge?.left || state.selection?.name || names[0];
  form.elements.right.value = edge?.right || names.find((name) => name !== form.elements.left.value) || names[0];
  form.elements.arrow.value = edge?.arrow || $("draw-arrow").value;
  for (const key of ["leftMultiplicity", "rightMultiplicity", "label"]) form.elements[key].value = edge?.[key] || "";
  $("edge-dialog").showModal();
}

$("add-class").onclick = () => showClass();
$("add-edge").onclick = () => showEdge(null);
for (const button of document.querySelectorAll("[data-close]")) button.onclick = () => button.closest("dialog").close();
$("class-form").onsubmit = (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const name = form.dataset.name;
  const newName = form.elements.newName.value;
  if (name === newName) { $("class-dialog").close(); return; }
  $("class-dialog").close();
  visualEdit({ name, newName, kind: form.elements.kind.value, action: name ? "renameClass" : "addClass" });
};
$("edge-form").onsubmit = (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const line = Number(form.dataset.line);
  $("edge-dialog").close();
  visualEdit({ ...Object.fromEntries(new FormData(form)), line, action: line ? "editRelationship" : "addRelationship" });
};

function indicateDraft() { $("status").textContent = dirty() ? "Unsaved changes" : "Saved"; }

async function visualEdit(change, keepSelectedNode = false) {
  if (!canEdit()) return;
  state.busy = true;
  availability();
  error();
  try {
    const result = await api("/api/edit", "POST", { source: state.source, change });
    state.source = result.source;
    $("source").value = state.source;
    if (change.action === "renameClass") {
      if (state.manualPositions.has(change.name)) {
        state.manualPositions.set(change.newName, state.manualPositions.get(change.name));
        state.manualPositions.delete(change.name);
      }
      if (state.focus === change.name) state.focus = change.newName;
      state.selection = { name: change.newName };
    } else if (change.action === "addClass") {
      state.focus = null;
      state.selection = { name: change.newName };
    } else if (change.action === "deleteClass" || change.action === "deleteRelationship") {
      state.selection = null;
    } else if (change.action === "addRelationship" && !keepSelectedNode) {
      state.selection = { line: result.relationships.at(-1).startLine };
    }
    renderGraph(result, change.action === "addClass", keepSelectedNode);
    indicateDraft();
  } catch (failure) {
    error(failure.message);
  } finally {
    state.busy = false;
    availability();
  }
}

$("source").oninput = () => {
  state.source = applyTextarea(state.source, $("source").value);
  state.pending = true;
  const version = ++state.parseVersion;
  clearTimeout(state.timer);
  indicateDraft();
  availability();
  state.timer = setTimeout(async () => {
    try {
      const data = await api("/api/parse", "POST", { source: state.source });
      if (version !== state.parseVersion) return;
      state.pending = false;
      renderGraph(data, false, true);
    } catch (failure) {
      if (version === state.parseVersion) error(failure.message);
    }
  }, 200);
};

$("save").onclick = async () => {
  state.busy = true;
  availability();
  error();
  try {
    const { revision } = await api("/api/diagram", "PUT", { source: state.source, revision: state.revision });
    state.revision = revision;
    state.saved = state.source;
    indicateDraft();
  } catch (failure) {
    error(failure.message);
  } finally {
    state.busy = false;
    availability();
  }
};

async function load() {
  if (dirty() && !confirm("Discard unsaved changes and reload the file from disk?")) return;
  state.busy = true;
  availability();
  error();
  try {
    const data = await api("/api/diagram");
    clearTimeout(state.timer);
    ++state.parseVersion;
    state.pending = false;
    state.revision = data.revision;
    state.source = state.saved = data.source;
    state.focus = state.selection = null;
    $("file").textContent = data.file;
    $("source").disabled = false;
    $("source").value = data.source;
    renderGraph(data, true);
    indicateDraft();
  } catch (failure) {
    error(failure.message);
    if (!state.revision) $("status").textContent = "Could not load diagram";
  } finally {
    state.busy = false;
    availability();
  }
}

$("reload").onclick = load;

for (const name of ["nodes", "details", "source"]) {
  const toggle = $("toggle-" + name);
  const panel = $(toggle.getAttribute("aria-controls"));
  toggle.onclick = () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
    $("right-panel").hidden = $("details-panel").hidden && $("source-panel").hidden;
    if (name === "nodes") search(false);
  };
}
if (cy) new ResizeObserver(() => cy.resize()).observe(workspace);

function updateWorkspaceNote() {
  const focus = state.focus ? "Focused on " + state.focus + " · depth " + $("depth").value + ". " : "";
  const message = !cy ? "Cytoscape could not load. The Mermaid source editor is available." :
    state.browserLink ? "Drop in the workspace to link from " + state.browserLink.left + " to " + state.browserLink.right + "." :
    state.drawing && canEdit() ? "Drag from the left endpoint to the right endpoint. Press Escape to stop drawing." :
    state.selection?.name && !$("node-browser").hidden && canEdit() ?
      "Drag another node from the Nodes panel to link from " + state.selection.name + "." :
      "Double-click a node to focus its relationships.";
  const note = $("graph-note");
  if (note.textContent !== focus + message) note.textContent = focus + message;
}

$("draw-arrow").replaceChildren(...Array.from($("edge-form").elements.arrow.options, (option) => option.cloneNode(true)));
$("draw-arrow").value = "-->";

function toggleDrawing(enabled) {
  state.drawing = enabled;
  if (!enabled) clearPointerLink();
  $("link-tool").setAttribute("aria-pressed", String(enabled));
  availability();
}

$("link-tool").onclick = () => toggleDrawing(!state.drawing);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.drawing && !document.querySelector("dialog[open]")) toggleDrawing(false);
});

function positionInWorkspace(event) {
  const bounds = workspace.getBoundingClientRect();
  return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
}

function nodeAt(point) {
  const bounds = workspace.getBoundingClientRect();
  if (point.x < 0 || point.y < 0 || point.x >= bounds.width || point.y >= bounds.height) return null;
  let closest = null;
  let distance = Infinity;
  for (const node of cy.nodes().not(".filtered")) {
    const { x1, x2, y1, y2 } = node.renderedBoundingBox({ includeLabels: false, includeOverlays: false });
    if (point.x < x1 || point.x > x2 || point.y < y1 || point.y > y2) continue;
    const center = node.renderedPosition();
    const offset = Math.hypot(point.x - center.x, point.y - center.y);
    if (offset < distance) {
      closest = node;
      distance = offset;
    }
  }
  return closest;
}

function linkNodes(left, right) {
  if (!left || !right || left === right || !canEdit()) return;
  visualEdit({ action: "addRelationship", left, right, arrow: $("draw-arrow").value }, true);
}

function clearPointerLink() {
  const pointer = state.pointerLink;
  state.pointerLink = null;
  $("link-preview").hidden = true;
  if (pointer && workspace.hasPointerCapture(pointer.id)) workspace.releasePointerCapture(pointer.id);
}

workspace.addEventListener("pointerdown", (event) => {
  if (!state.drawing || !canEdit() || event.button !== 0 || !event.isPrimary) return;
  const node = nodeAt(positionInWorkspace(event));
  if (!node) return;
  event.preventDefault();
  event.stopPropagation();
  const name = node.data("name");
  select({ name });
  state.pointerLink = { id: event.pointerId, name, start: node.renderedPosition() };
  workspace.setPointerCapture(event.pointerId);
}, true);

workspace.addEventListener("pointermove", (event) => {
  const pointer = state.pointerLink;
  if (pointer?.id !== event.pointerId) return;
  const point = positionInWorkspace(event);
  const dx = point.x - pointer.start.x;
  const dy = point.y - pointer.start.y;
  const preview = $("link-preview");
  preview.hidden = false;
  preview.style.left = pointer.start.x + "px";
  preview.style.top = pointer.start.y + "px";
  preview.style.width = Math.hypot(dx, dy) + "px";
  preview.style.transform = "rotate(" + Math.atan2(dy, dx) + "rad)";
});

workspace.addEventListener("pointerup", (event) => {
  const pointer = state.pointerLink;
  if (pointer?.id !== event.pointerId) return;
  const target = nodeAt(positionInWorkspace(event));
  clearPointerLink();
  linkNodes(pointer.name, target?.data("name"));
});
for (const eventName of ["pointercancel", "lostpointercapture"]) {
  workspace.addEventListener(eventName, (event) => {
    if (state.pointerLink?.id === event.pointerId) clearPointerLink();
  });
}

$("node-list").onclick = (event) => findClass(event.target.closest(".node-entry")?.dataset.name);

function clearBrowserLink() {
  state.browserLink = null;
  workspace.classList.remove("drop-target");
  updateWorkspaceNote();
}

$("node-list").addEventListener("dragstart", (event) => {
  const entry = event.target.closest(".node-entry");
  if (!entry?.draggable || !state.selection?.name || !canEdit()) {
    event.preventDefault();
    return;
  }
  state.browserLink = { left: state.selection.name, right: entry.dataset.name };
  event.dataTransfer.effectAllowed = "link";
  event.dataTransfer.setData("text/plain", state.browserLink.right);
  updateWorkspaceNote();
});
$("node-list").addEventListener("dragend", clearBrowserLink);
workspace.addEventListener("dragover", (event) => {
  if (!state.browserLink || !canEdit()) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "link";
  workspace.classList.add("drop-target");
});
workspace.addEventListener("dragleave", (event) => {
  if (!workspace.contains(event.relatedTarget)) workspace.classList.remove("drop-target");
});
workspace.addEventListener("drop", (event) => {
  if (!state.browserLink) return;
  event.preventDefault();
  const { left, right } = state.browserLink;
  clearBrowserLink();
  linkNodes(left, right);
});

window.addEventListener("beforeunload", (event) => {
  if (dirty()) {
    event.preventDefault();
    event.returnValue = "";
  }
});
updateWorkspaceNote();
load();
