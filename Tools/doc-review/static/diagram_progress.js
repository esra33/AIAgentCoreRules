import { nodeSourceId } from "./diagram_anchors.js";

const SVG_NS = "http://www.w3.org/2000/svg";
let latestProgress = {};

function svgElement(name, attributes, content) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }
  if (content !== undefined) {
    element.textContent = content;
  }
  return element;
}

function decorate(tabId) {
  const panel = document.getElementById(tabId);
  if (!panel?.closest(".panel.active")) {
    return;
  }
  const progress = latestProgress[tabId] || {};
  for (const node of panel.querySelectorAll("svg g.node")) {
    const id = nodeSourceId(node);
    const counts = Object.hasOwn(progress, id) ? progress[id] : undefined;
    node.querySelector(":scope > .docreview-node-progress")?.remove();
    if (!counts) {
      continue;
    }
    const { x, y, width, height } = node.getBBox();
    const percent = Math.round(100 * counts.done / counts.total);
    const tooltip = `${counts.done} of ${counts.total} linked tasks complete${counts.active ? " · Active implementation" : ""}`;
    const group = svgElement("g", { class: "docreview-node-progress" });
    const badge = svgElement("g", { transform: `translate(${x + width - 41} ${y - 10})` });
    badge.append(
      svgElement("title", {}, tooltip),
      svgElement("rect", { width: 40, height: 19, rx: 5, style: "fill: #1e293b; stroke: none" }),
      svgElement("text", {
        x: 20, y: 13, "text-anchor": "middle",
        style: "fill: white; font: bold 11px sans-serif; pointer-events: none",
      }, `${percent}%`),
    );
    if (counts.active) {
      group.append(svgElement("rect", {
        x: x - 3, y: y - 3, width: width + 6, height: height + 6, rx: 4,
        style: "fill: none; stroke: #2563eb; stroke-width: 3; stroke-dasharray: 6 3; pointer-events: none",
        class: "docreview-node-active",
      }));
    }
    group.append(badge);
    node.append(group);
  }
}

document.addEventListener("docreview:rendered", ({ detail }) => decorate(detail.tabId));
document.addEventListener("docreview:diagram-activated", ({ detail }) => decorate(detail.tabId));
document.addEventListener("docreview:state", ({ detail }) => {
  const previous = latestProgress;
  latestProgress = detail.diagramProgress || {};
  for (const tabId of new Set([...Object.keys(previous), ...Object.keys(latestProgress)])) {
    if (JSON.stringify(previous[tabId]) !== JSON.stringify(latestProgress[tabId])) {
      decorate(tabId);
    }
  }
});
