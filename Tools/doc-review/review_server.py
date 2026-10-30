"""Render a doc + its diagrams as a tabbed page, live (HTTP server) or once (--static).

Live mode binds to 127.0.0.1 only (hard-coded, no flag can change it) and serves the comment
API the browser UI will use (V1). Static mode is what mermaid_preview.py's thin alias calls --
same rendering, no server, no comments. See LocalDocReview_TDD.md Architecture and Best Practices.
"""
import functools
import html
import http.server
import json
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional

import perf_view
from anchor_resolver import resolve_thread
from progress_view import build_model, find_progress_file, pr_refresh_stamp, watched_paths
from sidecar_store import SidecarStore

MERMAID_CDN = "https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.15.0/mermaid.min.js"
MARKED_CDN = "https://cdnjs.cloudflare.com/ajax/libs/marked/18.1.1/lib/marked.umd.min.js"
SVG_PAN_ZOOM_CDN = "https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_CONTENT_TYPE_BY_SUFFIX = {".js": "text/javascript", ".css": "text/css"}
POLL_INTERVAL_MS = 1000

PAGE_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Doc review{live_suffix}</title>
<script src="{marked_cdn}"></script>
<script src="{mermaid_cdn}"></script>
<script src="{panzoom_cdn}"></script>
{live_head_extra}
<style>
  /* Deliberately dark-only: color-scheme: light dark previously let the browser apply its own
     dark-mode default TEXT color to marked's unstyled output while this CSS kept light-mode
     BACKGROUNDS, producing white-on-white. Declaring dark only, with every color explicit below,
     removes that mismatch instead of fighting it. */
  :root {{ color-scheme: dark; }}
  html, body {{ height: 100%; margin: 0; }}
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #15171c; color: #e4e6eb;
          display: flex; flex-direction: column; }}
  header {{ padding: 12px 16px; background: #1f2430; color: #eee; font-size: 14px; flex: none; }}
  header .hint {{ color: #9aa3b5; margin-left: 10px; }}
  .content-row {{ display: flex; flex: 1; min-height: 0; }}
  .main-column {{ display: flex; flex-direction: column; flex: 1; min-width: 0; }}
  .tabs {{ display: flex; gap: 4px; padding: 8px 16px 0; background: #1f2430; flex: none; }}
  .tab {{ background: #2a3040; color: #ccc; border: none; padding: 8px 14px; border-radius: 6px 6px 0 0;
          cursor: pointer; font-size: 13px; }}
  .tab.active {{ background: #20242e; color: #fff; font-weight: 600; }}
  .panel {{ display: none; flex: 1; min-height: 0; padding: 16px; box-sizing: border-box; overflow: auto; }}
  .panel.active {{ display: block; }}
  .diagram {{ background: #20242e; width: 100%; height: 100%; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.4);
              box-sizing: border-box; overflow: hidden; }}
  .diagram svg {{ width: 100%; height: 100%; }}
  .markdown {{ background: #20242e; color: #e4e6eb; max-width: 900px; margin: 0 auto; padding: 24px 32px;
               border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.4); box-sizing: border-box; line-height: 1.55; }}
  .markdown h1, .markdown h2, .markdown h3, .markdown h4 {{ color: #fff; border-bottom: 1px solid #333944; padding-bottom: 6px; }}
  .markdown a {{ color: #6cb6ff; }}
  .markdown code {{ background: #2a303c; color: #f0c674; padding: 2px 5px; border-radius: 4px; font-size: 0.9em; }}
  .markdown pre {{ background: #181b22; padding: 12px 16px; border-radius: 6px; overflow-x: auto; }}
  .markdown pre code {{ background: none; padding: 0; color: #e4e6eb; }}
  .markdown table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  .markdown th, .markdown td {{ border: 1px solid #333944; padding: 6px 10px; text-align: left; }}
  .markdown th {{ background: #262b35; }}
  .markdown blockquote {{ border-left: 3px solid #4a5468; margin: 0; padding: 4px 16px; color: #b7bcc7; }}
  .markdown hr {{ border: none; border-top: 1px solid #333944; }}
  .error {{ color: #ff6b6b; font-family: monospace; white-space: pre-wrap; padding: 16px; }}
  /* Progress tab: green = done (same --ok green as retro_page.py's dark theme), red = gate still to pass. */
  .progress-view {{ --ok: #5fd394; --gate: #ff6b6b; --current: #6cb6ff; background: #20242e; color: #e4e6eb;
                    max-width: 900px; margin: 0 auto; padding: 24px 32px; border-radius: 8px;
                    box-shadow: 0 1px 4px rgba(0,0,0,.4); box-sizing: border-box; line-height: 1.5; }}
  .progress-view h1 {{ margin: 0 0 4px; font-size: 22px; color: #fff; }}
  .progress-view .meta {{ color: #9aa3b5; font-size: 13px; margin-bottom: 18px; }}
  .phase {{ border: 1px solid #333944; border-left: 4px solid #333944; border-radius: 6px; padding: 10px 14px; margin: 10px 0; }}
  .phase.completed {{ border-left-color: var(--ok); }}
  .phase.current {{ border-color: var(--current); border-left-color: var(--current); background: #23304a; }}
  .phase h2 {{ margin: 0; font-size: 16px; color: #fff; display: flex; align-items: center; gap: 8px; }}
  .phase .pill {{ font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 10px; }}
  .phase .pill.current {{ background: var(--current); color: #10141c; }}
  .mark {{ display: inline-block; width: 1.2em; text-align: center; color: #5c6577; }}
  .mark.done {{ color: var(--ok); font-weight: 700; }}
  .mark.partial {{ color: #f0c674; }}
  .phase ul {{ list-style: none; margin: 6px 0 0; padding-left: 4px; font-size: 14px; }}
  .phase li.done {{ color: #b7bcc7; }}
  /* Sub-phase 1c's consistency-review findings, nested under its step once Gate 1 is written;
     also Sub-phase 1b's TDD section checklist. */
  .phase ul.findings {{ list-style: none; margin: 4px 0 2px 20px; padding: 0; font-size: 13px; color: #b7bcc7; }}
  .phase ul.findings li {{ margin: 2px 0; }}
  .phase .stage {{ margin: 8px 0 0 4px; font-size: 13px; color: #9aa3b5; font-weight: 600; }}
  .phase .stage + ul {{ padding-left: 16px; }}
  .gate {{ margin-top: 8px; font-size: 13px; color: #9aa3b5; }}
  .gate.pending {{ color: var(--gate); font-weight: 600; }}
  /* Implementation V-phases from the TDD: a Tasks and a PR notes collapsible each. */
  .dev-phase details {{ margin: 4px 0 0 20px; font-size: 13px; }}
  .dev-phase summary {{ cursor: pointer; color: #b7bcc7; }}
  .dev-phase .pr {{ margin: 6px 0 0 4px; }}
  .dev-phase .pr a {{ color: #6cb6ff; }}
  .dev-phase .pill.pr-state {{ background: #333944; color: #e4e6eb; }}
  .dev-phase .note {{ border-left: 2px solid #333944; margin: 6px 0 0 8px; padding: 2px 10px; }}
  .dev-phase .note-meta {{ color: #9aa3b5; font-size: 12px; }}
  .dev-phase .note-meta a {{ color: #9aa3b5; }}
  .dev-phase .note-body {{ white-space: pre-wrap; color: #e4e6eb; }}
  .dev-phase .empty {{ color: #5c6577; margin: 4px 0 0 4px; }}
  /* /publish-batch progress on a task: batch N of M, linked to the batch's open PR. */
  .phase .pill.batch {{ background: #333944; color: #e4e6eb; }}
  .phase .pill.batch.done {{ background: var(--ok); color: #10141c; }}
  .phase .pill.batch a {{ color: #6cb6ff; }}
{perf_css}
</style>
</head>
<body>
<header>{header_text}
  <span class="hint">scroll/pinch to zoom on diagrams &middot; drag to pan &middot; bottom-left icons to reset</span>
</header>
<div class="content-row">
<div class="main-column">
<div class="tabs">
{tab_buttons}
</div>
{panels}
</div>
{live_sidebar_slot}
</div>
<script>
  mermaid.initialize({{ startOnLoad: false, theme: "dark" }});
  const tabKinds = {tab_kinds_js};
  const sources = {sources_js};
  const panZoomInstances = {{}};
  window.panZoomInstances = panZoomInstances; // read by static/diagram_anchors.js (live mode only)
  const renderedSourceFor = {{}};

  function renderMarkdown(id, src) {{
    const target = document.getElementById(id);
    try {{
      target.innerHTML = marked.parse(src);
    }} catch (err) {{
      // A failure here must not stop renderAll()'s forEach from reaching the other tabs.
      target.innerHTML = '<div class="error">' + (err && err.message ? err.message : err) + '</div>';
    }}
    document.dispatchEvent(new CustomEvent("docreview:rendered", {{ detail: {{ tabId: id }} }}));
  }}

  async function renderDiagram(id, src) {{
    const target = document.getElementById(id);
    const existing = panZoomInstances[id];
    const savedPan = existing ? existing.getPan() : null;
    const savedZoom = existing ? existing.getZoom() : null;
    const bodyChildrenBefore = new Set(document.body.children);
    try {{
      const {{ svg }} = await mermaid.render(id + "-svg", src);
      target.innerHTML = svg;
      const svgEl = target.querySelector("svg");
      svgEl.removeAttribute("width");
      svgEl.removeAttribute("height");
      const instance = svgPanZoom(svgEl, {{
        zoomEnabled: true, panEnabled: true, controlIconsEnabled: true,
        fit: true, center: true, minZoom: 0.2, maxZoom: 20,
      }});
      if (savedPan && savedZoom) {{
        instance.zoom(savedZoom);
        instance.pan(savedPan);
      }}
      panZoomInstances[id] = instance;
    }} catch (err) {{
      target.innerHTML = '<div class="error">' + (err && err.message ? err.message : err) + '</div>';
      delete panZoomInstances[id];
      // mermaid.render() can leave its own temporary rendering container behind in <body> when it
      // throws partway through (observed directly: a stray "d<id>-svg" div, duplicating the error
      // message outside this panel and -- worse -- stealing flex height from .content-row). Clean
      // up whatever appeared as a side effect of this call rather than guessing mermaid's naming.
      Array.from(document.body.children).forEach((el) => {{
        if (!bodyChildrenBefore.has(el)) {{
          el.remove();
        }}
      }});
    }}
    document.dispatchEvent(new CustomEvent("docreview:rendered", {{ detail: {{ tabId: id }} }}));
  }}

  function escapeHtml(text) {{
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }}

  function markHtml(state) {{
    const glyph = state === "done" ? "✓" : state === "partial" ? "~" : "○";
    return '<span class="mark ' + state + '">' + glyph + '</span>';
  }}

  function batchHtml(batch) {{
    if (!batch) return '';
    if (batch.done) return ' <span class="pill batch done">batches done (' + batch.total + ')</span>';
    const pr = batch.open_pr == null ? '' : ' · ' + (batch.open_pr_url
      ? '<a href="' + escapeHtml(batch.open_pr_url) + '" target="_blank" rel="noopener">#' + escapeHtml(batch.open_pr) + '</a>'
      : '#' + escapeHtml(batch.open_pr));
    return ' <span class="pill batch" title="' + escapeHtml(batch.title) + '">batch ' + batch.current + ' of ' + batch.total + pr + '</span>';
  }}

  function taskHtml(task) {{
    return '<li class="' + task.status + '">' + markHtml(task.status) + escapeHtml((task.id ? task.id + ' · ' : '') + task.title)
      + batchHtml(task.batch) + '</li>';
  }}

  function devPhaseHtml(dev) {{
    const done = dev.tasks.filter((task) => task.status === "done").length;
    const allDone = dev.tasks.length > 0 && done === dev.tasks.length;
    const parts = ['<div class="dev-phase"><div class="stage">' + markHtml(allDone ? "done" : "todo") + escapeHtml(dev.title) + '</div>',
      '<details data-key="' + escapeHtml(dev.key) + ':tasks"' + (dev.open ? ' open' : '') + '><summary>Tasks ('
        + done + '/' + dev.tasks.length + ')</summary><ul>'];
    dev.tasks.forEach((task) => parts.push(taskHtml(task)));
    const prs = dev.pull_requests || [];
    const noteCount = prs.reduce((sum, pr) => sum + pr.notes.length, 0);
    parts.push('</ul></details><details data-key="' + escapeHtml(dev.key) + ':prs"><summary>PR notes ('
      + prs.length + ' PR' + (prs.length === 1 ? '' : 's') + ', ' + noteCount + ' note' + (noteCount === 1 ? '' : 's') + ')</summary>');
    if (!prs.length) {{
      parts.push('<div class="empty">No PRs linked. Add <code>' + escapeHtml(dev.key) + ': [1234]</code> under <code>pull_requests:</code> in the progress file.</div>');
    }}
    prs.forEach((pr) => {{
      parts.push('<div class="pr"><a href="' + escapeHtml(pr.url) + '" target="_blank" rel="noopener">#' + escapeHtml(pr.number)
        + (pr.title ? ' ' + escapeHtml(pr.title) : '') + '</a>' + (pr.state ? ' <span class="pill pr-state">' + escapeHtml(pr.state) + '</span>' : ''));
      if (pr.error) parts.push('<div class="error">' + escapeHtml(pr.error) + '</div>');
      if (!pr.error && !pr.notes.length) parts.push('<div class="empty">No comments yet.</div>');
      pr.notes.forEach((note) => {{
        const where = note.location || note.kind + (note.state ? ' ' + note.state.toLowerCase() : '');
        const whereHtml = note.url ? '<a href="' + escapeHtml(note.url) + '" target="_blank" rel="noopener">' + escapeHtml(where) + '</a>' : escapeHtml(where);
        parts.push('<div class="note"><div class="note-meta">' + escapeHtml(note.author) + ' &middot; ' + escapeHtml(note.created_at.slice(0, 10))
          + ' &middot; ' + whereHtml + '</div><div class="note-body">' + escapeHtml(note.body) + '</div></div>');
      }});
      parts.push('</div>');
    }});
    parts.push('</details></div>');
    return parts.join("");
  }}

  function renderProgress(id, src) {{
    const target = document.getElementById(id);
    try {{
      const model = JSON.parse(src);
      const parts = ['<h1>' + escapeHtml(model.feature) + '</h1>',
        '<div class="meta">status: ' + escapeHtml(model.status) + ' &middot; updated ' + escapeHtml(model.updated_at)
          + (model.next ? '<br>next: ' + escapeHtml(model.next) : '') + '</div>'];
      model.phases.forEach((phase) => {{
        const classes = ["phase"];
        if (phase.completed) classes.push("completed");
        if (phase.current) classes.push("current");
        parts.push('<section class="' + classes.join(" ") + '"><h2>' + markHtml(phase.completed ? "done" : "todo")
          + escapeHtml(phase.title) + (phase.current ? ' <span class="pill current">current</span>' : '') + '</h2><ul>');
        phase.steps.forEach((step) => {{
          const state = step.state || (step.done ? "done" : "todo");
          parts.push('<li class="' + state + '">' + markHtml(state) + escapeHtml(step.title));
          // Sub-phase 1b's TDD sections: approved (✓) / drafting (~) from tdd_sections, else checked once the TDD fills them in.
          const sections = step.sections || [];
          if (sections.length) {{
            parts.push('<ul class="findings">');
            sections.forEach((section) => {{
              const sectionState = section.state || (section.done ? "done" : "todo");
              parts.push('<li class="' + sectionState + '">' + markHtml(sectionState) + escapeHtml(section.title) + '</li>');
            }});
            parts.push('</ul>');
          }}
          const findings = step.findings || [];
          if (findings.length) {{
            parts.push('<ul class="findings">');
            findings.forEach((finding) => parts.push('<li>' + escapeHtml(finding) + '</li>'));
            parts.push('</ul>');
          }}
          parts.push('</li>');
        }});
        parts.push('</ul>');
        // The TDD's V-phases replace the task list when the TDD has them.
        const devPhases = phase.dev_phases || [];
        (devPhases.length ? [] : phase.stages).forEach((stage) => {{
          parts.push('<div class="stage">' + escapeHtml(stage.title) + '</div><ul>');
          stage.tasks.forEach((task) => parts.push(taskHtml(task)));
          parts.push('</ul>');
        }});
        devPhases.forEach((dev) => parts.push(devPhaseHtml(dev)));
        const pending = phase.key === model.next_gate_phase;
        parts.push('<div class="gate' + (pending ? ' pending' : '') + '">Gate' + (pending ? ' to pass next' : '')
          + ': ' + escapeHtml(phase.gate) + '</div></section>');
      }});
      // A refresh rebuilds the tab; keep the collapsibles the engineer opened or closed by hand.
      const openState = {{}};
      target.querySelectorAll("details[data-key]").forEach((el) => {{ openState[el.dataset.key] = el.open; }});
      target.innerHTML = parts.join("");
      target.querySelectorAll("details[data-key]").forEach((el) => {{
        if (el.dataset.key in openState) el.open = openState[el.dataset.key];
      }});
    }} catch (err) {{
      target.innerHTML = '<div class="error">' + escapeHtml(err && err.message ? err.message : err) + '</div>';
    }}
  }}
{perf_script}
  function renderTab(id) {{
    if (tabKinds[id] === "md") {{
      renderMarkdown(id, sources[id]);
    }} else if (tabKinds[id] === "progress") {{
      renderProgress(id, sources[id]);
    }} else if (tabKinds[id] === "perf") {{
      renderPerf(id, sources[id]);
    }} else {{
      renderedSourceFor[id] = sources[id];
      renderDiagram(id, sources[id]);
    }}
  }}

  function isActiveTabId(id) {{
    const active = document.querySelector(".tab.active");
    return !!active && active.dataset.i === id.slice(1);
  }}

  function renderAll() {{
    // Diagrams render lazily, on first activation: mermaid.render() measures text via
    // getBBox(), which returns a degenerate (zero-size) result for an element still inside a
    // display:none ancestor, so a diagram rendered here for a not-yet-selected tab comes out
    // blank even though svgPanZoom reports success. Markdown has no such measurement step, so
    // it stays eager.
    Object.keys(sources).forEach((id) => {{
      if (tabKinds[id] !== "mmd") {{
        renderTab(id);
      }}
    }});
  }}

  function activate(idx) {{
    document.querySelectorAll(".tab").forEach((el, i) => el.classList.toggle("active", i === idx));
    document.querySelectorAll(".panel").forEach((el, i) => el.classList.toggle("active", i === idx));
    const id = "d" + idx;
    if (tabKinds[id] !== "mmd") {{
      return;
    }}
    if (renderedSourceFor[id] !== sources[id]) {{
      renderTab(id);  // first view of this diagram, or its source changed while it was hidden
      return;
    }}
    const inst = panZoomInstances[id];
    if (inst) {{
      inst.resize();
      inst.fit();
      inst.center();
    }}
  }}
  document.querySelectorAll(".tab").forEach((el, i) => el.addEventListener("click", () => activate(i)));
  activate(0);
  renderAll();
  window.addEventListener("resize", () => {{
    const activeIdx = [...document.querySelectorAll(".tab")].findIndex(el => el.classList.contains("active"));
    if (activeIdx >= 0) activate(activeIdx);
  }});
  {live_script}
</script>
{live_module_script}
</body>
</html>
"""

LIVE_SCRIPT_TEMPLATE = """
  let knownMtimes = {{}};
  async function pollState() {{
    try {{
      const res = await fetch("/api/state");
      const state = await res.json();
      document.dispatchEvent(new CustomEvent("docreview:state", {{ detail: {{ threads: state.threads }} }}));
      const changedIds = [];
      for (const [id, path] of Object.entries(tabPaths)) {{
        const mtime = state.mtimes[path];
        if (knownMtimes[id] !== undefined && mtime !== knownMtimes[id]) {{
          changedIds.push(id);
        }}
        knownMtimes[id] = mtime;
      }}
      if (changedIds.length > 0) {{
        const freshSources = await (await fetch("/api/sources")).json();
        changedIds.forEach((id) => {{
          sources[id] = freshSources[id];
          // Markdown is always safe to redraw. A hidden diagram tab is left with its cache
          // just updated -- activate() renders it fresh, correctly, once it's actually selected.
          if (tabKinds[id] !== "mmd" || isActiveTabId(id)) {{
            renderTab(id);
          }}
        }});
      }}
    }} catch (err) {{
      // server unreachable mid-poll (e.g. shutting down) -- skip this round, try again next tick
    }}
  }}
  setInterval(pollState, {poll_interval_ms});
  pollState();
"""

# Performance tab. Not .format()ed, so braces are single; injected into PAGE_TEMPLATE as values.
# Category colours = retro_page.py's dark --s1..--s5 (validated against #20242e), greys for the rest.
PERF_CSS = """
  .perf-view { --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181; --n1: #6e6d68; --n2: #4e5260;
               --curve: #3987e5; --active: #f0c674; background: #20242e; color: #e4e6eb; max-width: 960px; margin: 0 auto;
               padding: 24px 32px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.4); box-sizing: border-box; line-height: 1.5; }
  .perf-view h1 { margin: 0 0 4px; font-size: 22px; color: #fff; }
  .perf-view h2 { margin: 22px 0 8px; font-size: 16px; color: #fff; }
  .perf-view .meta { color: #9aa3b5; font-size: 13px; }
  .perf-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin: 14px 0; }
  .perf-tile { border: 1px solid #333944; border-radius: 6px; padding: 8px 12px; }
  .perf-tile .label { color: #9aa3b5; font-size: 12px; }
  .perf-tile .value { color: #fff; font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .perf-curve svg { width: 100%; height: auto; display: block; }
  .perf-curve text { fill: #9aa3b5; font-size: 11px; }
  .perf-curve .note { color: #9aa3b5; font-size: 12px; margin-top: 4px; }
  .perf-stack { display: flex; gap: 2px; height: 12px; margin: 8px 0; }
  .perf-stack span { display: block; height: 100%; min-width: 2px; }
  .perf-stack span:first-child { border-radius: 4px 0 0 4px; }
  .perf-stack span:last-child { border-radius: 0 4px 4px 0; }
  .perf-table { border-collapse: collapse; width: 100%; font-size: 13px; font-variant-numeric: tabular-nums; }
  .perf-table th, .perf-table td { border-bottom: 1px solid #333944; padding: 4px 8px; text-align: right; }
  .perf-table th:first-child, .perf-table td:first-child { text-align: left; }
  .perf-table th { color: #9aa3b5; font-weight: 600; }
  .perf-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
  .perf-session { border: 1px solid #333944; border-left: 4px solid #333944; border-radius: 6px; margin: 8px 0; padding: 6px 12px; }
  .perf-session.active { border-left-color: var(--active); background: #2a2a24; }
  .perf-session summary { cursor: pointer; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
  .perf-session summary .when { color: #9aa3b5; font-size: 12px; font-variant-numeric: tabular-nums; }
  .perf-session summary .title { color: #fff; flex: 1; min-width: 200px; }
  .perf-session summary .total { color: #e4e6eb; font-weight: 600; font-variant-numeric: tabular-nums; }
  .perf-pill { font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 10px; background: #333944; color: #e4e6eb; }
  .perf-pill.active { background: var(--active); color: #10141c; }
  .perf-view .empty { color: #5c6577; }
  .perf-scope { display: inline-flex; border: 1px solid #333944; border-radius: 6px; overflow: hidden; margin: 10px 0 0; }
  .perf-scope button { background: none; border: 0; color: #9aa3b5; font: inherit; font-size: 13px; padding: 4px 12px; cursor: pointer; }
  .perf-scope button.on { background: #333944; color: #fff; }
"""

PERF_SCRIPT = """
  function perfCompact(n) {
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (abs >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(Math.round(n));
  }

  function perfPercent(share) {
    return (100 * share).toFixed(1) + "%";
  }

  function perfColors(model) {
    // Fixed order: standardized categories take --s1..--s5 by their token_breakdown.py order, the rest grey.
    const colors = {};
    model.standardized_names.forEach((name, i) => { colors[name] = "var(--s" + (i + 1) + ")"; });
    let grey = 1;
    model.overview.categories.forEach((category) => {
      if (!(category.name in colors)) colors[category.name] = "var(--n" + Math.min(grey++, 2) + ")";
    });
    return colors;
  }

  function perfStack(categories, colors) {
    const parts = categories.filter((c) => c.share > 0).map((c) =>
      '<span style="flex:' + c.share + ';background:' + (colors[c.name] || "var(--n1)") + '" title="'
        + escapeHtml(c.name + ": " + perfPercent(c.share)) + '"></span>');
    return '<div class="perf-stack">' + parts.join("") + '</div>';
  }

  function perfCategoryTable(categories, colors, withAverage) {
    const rows = categories.map((c) => '<tr><td><span class="perf-swatch" style="background:' + (colors[c.name] || "var(--n1)")
      + '"></span>' + escapeHtml(c.name) + '</td><td>' + perfCompact(c.tokens) + '</td>'
      + (withAverage ? '<td>' + perfCompact(c.average) + '</td>' : '') + '<td>' + perfPercent(c.share) + '</td></tr>');
    return '<table class="perf-table"><tr><th>Category</th><th>Tokens</th>' + (withAverage ? '<th>Avg / session</th>' : '')
      + '<th>Share</th></tr>' + rows.join("") + '</table>';
  }

  function perfBellCurve(points) {
    // Session totals span orders of magnitude, so the normal curve is fitted to log10(tokens)
    // (a log-normal fit) and drawn on a log axis; on a linear axis most of its area sits below zero.
    if (points.length < 2) return '<div class="empty">Need two compiled sessions for a distribution.</div>';
    const logs = points.map((p) => Math.log10(p.total));
    const mu = logs.reduce((a, b) => a + b, 0) / logs.length;
    const sigma = Math.sqrt(logs.reduce((a, b) => a + (b - mu) * (b - mu), 0) / logs.length) || 0.1;
    const lo = Math.floor(Math.min(...logs, mu - 2.5 * sigma));
    const hi = Math.ceil(Math.max(...logs, mu + 2.5 * sigma));
    const W = 800, H = 260, left = 16, right = 16, top = 16, plotBottom = 200;
    const x = (v) => left + (v - lo) / (hi - lo) * (W - left - right);
    const pdf = (v) => Math.exp(-0.5 * ((v - mu) / sigma) ** 2) / (sigma * Math.sqrt(2 * Math.PI));
    const binWidth = 0.25;
    const bins = {};
    logs.forEach((v) => { const b = Math.floor(v / binWidth); bins[b] = (bins[b] || 0) + 1; });
    // Histogram as a density, so its area matches the curve's.
    const density = (count) => count / (logs.length * binWidth);
    const yMax = 1.1 * Math.max(pdf(mu), ...Object.values(bins).map(density));
    const y = (d) => plotBottom - d / yMax * (plotBottom - top);
    const parts = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Distribution of session token totals">'];
    parts.push('<rect x="' + x(mu - sigma) + '" y="' + top + '" width="' + (x(mu + sigma) - x(mu - sigma)) + '" height="'
      + (plotBottom - top) + '" fill="#3987e5" opacity="0.08"><title>±1σ: ' + perfCompact(10 ** (mu - sigma)) + ' – '
      + perfCompact(10 ** (mu + sigma)) + ' tokens</title></rect>');
    Object.entries(bins).forEach(([b, count]) => {
      const x0 = x(b * binWidth) + 1, x1 = x((+b + 1) * binWidth) - 1;
      parts.push('<rect x="' + x0 + '" y="' + y(density(count)) + '" width="' + Math.max(x1 - x0, 1) + '" height="'
        + (plotBottom - y(density(count))) + '" rx="2" fill="#4e5260"><title>' + count + ' session' + (count === 1 ? '' : 's')
        + ': ' + perfCompact(10 ** (b * binWidth)) + ' – ' + perfCompact(10 ** ((+b + 1) * binWidth)) + '</title></rect>');
    });
    const curve = [];
    for (let i = 0; i <= 160; i++) {
      const v = lo + (hi - lo) * i / 160;
      curve.push((i ? "L" : "M") + x(v).toFixed(1) + "," + y(pdf(v)).toFixed(1));
    }
    parts.push('<path d="' + curve.join("") + '" fill="none" stroke="var(--curve)" stroke-width="2"/>');
    parts.push('<line x1="' + x(mu) + '" x2="' + x(mu) + '" y1="' + top + '" y2="' + plotBottom
      + '" stroke="#e4e6eb" stroke-dasharray="4 4" stroke-width="1"/>');
    parts.push('<text x="' + (x(mu) + 4) + '" y="' + (top + 10) + '">typical ' + perfCompact(10 ** mu) + '</text>');
    parts.push('<line x1="' + left + '" x2="' + (W - right) + '" y1="' + plotBottom + '" y2="' + plotBottom + '" stroke="#333944"/>');
    for (let p = lo; p <= hi; p++) {
      parts.push('<line x1="' + x(p) + '" x2="' + x(p) + '" y1="' + plotBottom + '" y2="' + (plotBottom + 4) + '" stroke="#5c6577"/>');
      parts.push('<text x="' + x(p) + '" y="' + (plotBottom + 16) + '" text-anchor="middle">' + perfCompact(10 ** p) + '</text>');
    }
    // One dot per session under the axis; the active one is larger and labelled.
    points.forEach((p, i) => {
      const cx = x(logs[i]).toFixed(1);
      const tip = '<title>' + escapeHtml(p.id + (p.active ? ' (active)' : '') + ': ' + perfCompact(p.total) + ' tokens') + '</title>';
      parts.push('<g><circle cx="' + cx + '" cy="236" r="9" fill="transparent">' + tip + '</circle><circle cx="' + cx
        + '" cy="236" r="' + (p.active ? 6 : 4) + '" fill="' + (p.active ? 'var(--active)' : '#9aa3b5') + '" stroke="#20242e" stroke-width="2"'
        + ' opacity="' + (p.active ? 1 : 0.7) + '">' + tip + '</circle></g>');
      if (p.active) parts.push('<text x="' + cx + '" y="254" text-anchor="middle" style="fill:var(--active)">active</text>');
    });
    parts.push('</svg>');
    return parts.join("");
  }

  function perfSession(session, colors) {
    const when = (session.started_at || "").slice(0, 16).replace("T", " ");
    const parts = ['<details class="perf-session' + (session.active ? ' active' : '') + '" data-key="' + escapeHtml(session.folder) + '"'
      + (session.active ? ' open' : '') + '><summary><span class="when">' + escapeHtml(when) + '</span>'
      + '<span class="title">' + escapeHtml(session.title || session.folder) + '</span>'
      + (session.active ? '<span class="perf-pill active">active</span>' : '')
      + (session.lane ? '<span class="perf-pill">' + escapeHtml(session.lane) + '</span>' : '')
      + '<span class="total">' + (session.compiled ? perfCompact(session.total) : '–') + '</span></summary>'];
    if (!session.compiled) {
      parts.push('<div class="empty">Token breakdown not compiled' + (session.error ? ': ' + escapeHtml(session.error) : ' yet') + '.</div>');
    } else {
      parts.push('<div class="meta">' + session.calls + ' model calls &middot; standardized operations '
        + perfPercent(session.total ? session.standardized / session.total : 0) + ' &middot; compiled '
        + escapeHtml((session.compiled_at || "").slice(0, 16).replace("T", " ")) + ' &middot; ' + escapeHtml(session.folder) + '</div>');
      parts.push(perfStack(session.categories, colors));
      parts.push(perfCategoryTable(session.categories, colors, false));
      const d = session.doc_review;
      if (d && (d.count || d.miro_confluence.count)) {
        const commands = Object.entries(d.commands).map(([name, n]) => escapeHtml(name) + ' ×' + n).join(", ");
        parts.push('<div class="meta">Doc review preview: ' + d.count + ' call(s)' + (commands ? ' (' + commands + ')' : '')
          + ', ' + perfCompact(d.tokens) + ' tokens &middot; via Miro/Confluence ≈ ' + perfCompact(d.equivalent)
          + ' tokens, ' + d.round_trips + ' round-trips &middot; Miro/Confluence MCP calls: ' + d.miro_confluence.count
          + ', ' + perfCompact(d.miro_confluence.tokens) + ' tokens</div>');
      }
    }
    parts.push('</details>');
    return parts.join("");
  }

  function perfDocReview(d, tile) {
    // Estimates: preview calls as measured; Miro/Confluence = token_breakdown.MIRO_CONFLUENCE_BY_COMMAND per call.
    if (!d || !(d.count || d.miro_confluence.count)) return '';
    return '<h2>Doc review preview vs Miro/Confluence</h2><div class="perf-tiles">'
      + tile("Preview tokens", perfCompact(d.tokens) + ' <span class="meta">' + d.count + ' calls</span>')
      + tile("Same via Miro/Confluence", '≈ ' + perfCompact(d.equivalent) + ' <span class="meta">+' + d.round_trips + ' trips</span>')
      + tile("Saved (est.)", perfCompact(Math.max(d.equivalent - d.tokens, 0)))
      + tile("Miro/Confluence used", perfCompact(d.miro_confluence.tokens) + ' <span class="meta">' + d.miro_confluence.count + ' calls</span>')
      + '</div><div class="meta">Preview: doc_review.py / mermaid_preview.py calls in ' + d.sessions + ' session(s). '
      + 'Miro/Confluence estimate: averages of real MCP calls per operation (serve = page update + diagram upload, '
      + 'comments = comment fetches, reply = comment post), listed in each retrospective\\'s savings note. '
      + 'Used: measured Miro/Confluence MCP calls in ' + d.miro_confluence.sessions + ' session(s).</div>';
  }

  // Per tab: "feature" (only the served feature's sessions) or "all". Kept across live refreshes.
  const perfScopes = {};

  function perfScopeToggle(model, scope) {
    const count = model.sessions.filter((s) => s.in_feature).length;
    const button = (value, label) => '<button type="button" data-scope="' + value + '"' + (scope === value ? ' class="on"' : '')
      + '>' + label + '</button>';
    return '<div class="perf-scope">' + button("feature", escapeHtml(model.feature) + ' &middot; ' + count)
      + button("all", 'All sessions &middot; ' + model.sessions.length) + '</div>';
  }

  function renderPerf(id, src) {
    const target = document.getElementById(id);
    try {
      const model = JSON.parse(src);
      const scope = model.feature ? (perfScopes[id] || "feature") : "all";
      const o = scope === "feature" ? model.feature_overview : model.overview;
      const sessions = scope === "feature" ? model.sessions.filter((s) => s.in_feature) : model.sessions;
      const colors = perfColors(model);
      const tile = (label, value) => '<div class="perf-tile"><div class="label">' + label + '</div><div class="value">' + value + '</div></div>';
      const parts = ['<h1>Session performance</h1><div class="meta">Estimated tokens per session (the retrospective\\'s breakdown) &middot; '
        + escapeHtml(model.root) + '</div>'
        + (model.feature ? perfScopeToggle(model, scope)
          + '<div class="meta">Feature sessions: tagged with set --feature, or listed under sessions: in the Progress file.</div>' : ''),
        '<div class="perf-tiles">' + tile("Sessions", o.compiled + (o.sessions > o.compiled ? ' <span class="meta">/ ' + o.sessions + '</span>' : ''))
          + tile("Total tokens", perfCompact(o.total)) + tile("Average / session", perfCompact(o.mean))
          + tile("Median", perfCompact(o.median)) + tile("Std deviation", perfCompact(o.stdev))
          + tile("Standardized", perfPercent(o.total ? o.standardized / o.total : 0)) + '</div>',
        '<h2>Distribution of session totals</h2><div class="perf-curve">' + perfBellCurve(o.totals)
          + '<div class="note">Bars: sessions per bin. Curve: normal fit to log10(tokens). Band: ±1σ. Dots: one per session.</div></div>',
        '<h2>Tokens by category, ' + (scope === "feature" ? 'feature' : 'all') + ' sessions</h2>' + perfStack(o.categories, colors) + perfCategoryTable(o.categories, colors, true),
        perfDocReview(o.doc_review, tile),
        '<h2>Sessions, newest first</h2>'];
      if (o.sessions > o.compiled) {
        parts.push('<div class="meta">' + (o.sessions - o.compiled) + ' session(s) without a compiled breakdown are listed but left out of the statistics.</div>');
      }
      if (!sessions.length) parts.push('<div class="empty">No sessions tagged with this feature yet.</div>');
      sessions.forEach((session) => parts.push(perfSession(session, colors)));
      // A refresh rebuilds the tab; keep the collapsibles the engineer opened or closed by hand.
      const openState = {};
      target.querySelectorAll("details[data-key]").forEach((el) => { openState[el.dataset.key] = el.open; });
      target.innerHTML = parts.join("");
      target.querySelectorAll("details[data-key]").forEach((el) => {
        if (el.dataset.key in openState) el.open = openState[el.dataset.key];
      });
      target.querySelectorAll(".perf-scope button").forEach((el) => {
        el.addEventListener("click", () => { perfScopes[id] = el.dataset.scope; renderPerf(id, src); });
      });
    } catch (err) {
      target.innerHTML = '<div class="error">' + escapeHtml(err && err.message ? err.message : err) + '</div>';
    }
  }
"""


def serve_doc(paths: List[Path], port: Optional[int] = None, open_browser: bool = False) -> None:
    store = SidecarStore(paths[0])
    handler_factory = functools.partial(ReviewRequestHandler, doc_paths=paths, store=store)
    httpd = _bind_server(handler_factory, port)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(url, flush=True)
    if open_browser:
        _open_url(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def render_static(paths: List[Path], output_path: Optional[Path] = None, open_browser: bool = False) -> Path:
    out_path = output_path or (paths[0].parent / "_doc_review_preview.html")
    out_path.write_text(build_page(paths, live=False))
    print(str(out_path))
    if open_browser:
        if sys.platform == "darwin":
            subprocess.run(["open", str(out_path)], check=False)
        else:
            webbrowser.open(out_path.resolve().as_uri())
    return out_path


class ReviewRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, doc_paths: List[Path], store: SidecarStore, static_dir: Path = STATIC_DIR, **kwargs):
        # Set before super().__init__: BaseHTTPRequestHandler.__init__ handles the request
        # immediately, so these must already be in place -- same pattern SimpleHTTPRequestHandler
        # uses for its `directory` argument.
        self._doc_paths = doc_paths
        self._store = store
        self._static_files = _static_allowlist(static_dir)
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path in ("/", ""):
            self._send_html(build_page(self._doc_paths, live=True))
        elif self.path == "/api/state":
            self._send_json(self._state())
        elif self.path == "/api/sources":
            self._send_json(_collect_sources(_tabs(self._doc_paths)))
        elif self.path.startswith("/static/"):
            self._handle_static(self.path[len("/static/"):])
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/comment":
            self._handle_comment()
        elif self.path == "/api/status":
            self._handle_status()
        elif self.path == "/api/reply":
            self._handle_reply()
        else:
            self.send_error(404)

    def log_message(self, format_string, *args):  # noqa: A002 - matches BaseHTTPRequestHandler's signature
        pass  # stdout is reserved for the server URL the engineer scripts against

    def _state(self) -> Dict:
        base_dir = self._doc_paths[0].parent
        threads = self._store.load()["threads"]
        for thread in threads:
            thread["resolution"] = resolve_thread(base_dir, thread)
        return {"mtimes": _collect_mtimes(_tabs(self._doc_paths)), "threads": threads}

    def _handle_comment(self):
        body = self._read_json_body()
        if body is None:
            return
        anchor = body.get("anchor")
        if not anchor:
            self._send_json({"error": "missing anchor"}, status=400)
            return
        thread_id = self._store.add_thread(anchor, "engineer", body.get("text", ""))
        self._send_json({"id": thread_id})

    def _handle_status(self):
        body = self._read_json_body()
        if body is None:
            return
        thread_id, status = body.get("id"), body.get("status")
        if not thread_id or not status:
            self._send_json({"error": "missing id or status"}, status=400)
            return
        try:
            self._store.set_status(thread_id, status, "engineer")
            self._send_json({"ok": True})
        except PermissionError as e:
            self._send_json({"error": str(e)}, status=403)
        except KeyError as e:
            self._send_json({"error": str(e)}, status=404)

    def _handle_reply(self):
        body = self._read_json_body()
        if body is None:
            return
        thread_id, text = body.get("id"), body.get("text")
        if not thread_id or not text:
            self._send_json({"error": "missing id or text"}, status=400)
            return
        try:
            self._store.add_reply(thread_id, "engineer", text)
            self._send_json({"ok": True})
        except KeyError as e:
            self._send_json({"error": str(e)}, status=404)

    def _handle_static(self, name: str):
        # name is looked up in an allowlist keyed by plain filename, built once from static_dir's
        # actual contents -- "../../etc/passwd" is simply not a key in that dict, so this is
        # traversal-safe by construction, with no path-component validation needed.
        file_path = self._static_files.get(name)
        if file_path is None:
            self.send_error(404)
            return
        content_type = STATIC_CONTENT_TYPE_BY_SUFFIX.get(file_path.suffix, "application/octet-stream")
        self._send_bytes(file_path.read_bytes(), content_type, 200)

    def _read_json_body(self) -> Optional[Dict]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON body"}, status=400)
            return None

    def _send_html(self, body: str, status: int = 200):
        self._send_bytes(body.encode("utf-8"), "text/html; charset=utf-8", status)

    def _send_json(self, data: Dict, status: int = 200):
        self._send_bytes(json.dumps(data).encode("utf-8"), "application/json", status)

    def _send_bytes(self, payload: bytes, content_type: str, status: int):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def build_page(paths: List[Path], live: bool) -> str:
    tabs = _tabs(paths)
    tab_buttons = "\n".join(
        f'<button class="tab{" active" if i == 0 else ""}" data-i="{i}">{html.escape(tab["title"])}</button>'
        for i, tab in enumerate(tabs)
    )
    panels = "\n".join(_panel_html(i, tab) for i, tab in enumerate(tabs))
    tab_paths_js = json.dumps({tab["id"]: _mtime_key(tab) for tab in tabs})
    doc_review_js = json.dumps({"tabs": [{"id": tab["id"], "file": tab["file"], "kind": tab["kind"]} for tab in tabs]})

    live_script = ""
    live_head_extra = ""
    live_module_script = ""
    live_sidebar_slot = ""
    if live:
        live_script = (
            f"const tabPaths = {tab_paths_js};\n"
            f"window.docReview = {doc_review_js};\n"
            + LIVE_SCRIPT_TEMPLATE.format(poll_interval_ms=POLL_INTERVAL_MS)
        )
        live_head_extra = '<link rel="stylesheet" href="/static/review_ui.css">'
        live_module_script = '<script type="module" src="/static/review_ui.js"></script>'
        live_sidebar_slot = '<aside id="docreview-panel"></aside>'

    return PAGE_TEMPLATE.format(
        live_suffix=" (live)" if live else "",
        marked_cdn=MARKED_CDN,
        mermaid_cdn=MERMAID_CDN,
        panzoom_cdn=SVG_PAN_ZOOM_CDN,
        header_text="LocalDocReview -- live server, not published anywhere"
        if live
        else "LocalDocReview -- static preview, not published anywhere",
        tab_buttons=tab_buttons,
        panels=panels,
        tab_kinds_js=json.dumps({tab["id"]: tab["kind"] for tab in tabs}),
        sources_js=json.dumps(_collect_sources(tabs)),
        live_script=live_script,
        live_head_extra=live_head_extra,
        live_module_script=live_module_script,
        live_sidebar_slot=live_sidebar_slot,
        perf_css=PERF_CSS,
        perf_script=PERF_SCRIPT,
    )


def _tabs(paths: List[Path]) -> List[Dict]:
    base_dir = paths[0].parent
    tabs = [
        {
            "title": path.stem,
            "kind": "md" if path.suffix == ".md" else "mmd",
            "path": path,
            "file": _relative_to_doc_folder(path, base_dir),
        }
        for path in paths
    ]
    progress_path = find_progress_file(paths[0])
    if progress_path is not None:
        # Auto-added first for a feature doc: phases/steps/gates from CreateFeature, state from Progress.md.
        # Its file key carries "#progress" because the static/*.js tab lookups match anchor.file with
        # find(): a thread anchored in a Progress.md md tab must not resolve to this tab, which precedes it.
        tabs.insert(
            0,
            {
                "title": "Progress",
                "kind": "progress",
                "path": progress_path,
                "file": _relative_to_doc_folder(progress_path, base_dir) + "#progress",
            },
        )
    reports_root = perf_view.find_reports_root(paths[0])
    if reports_root is not None:
        # Auto-added last, so the doc (or Progress) stays the first tab. Its file key is not a real file:
        # nothing anchors comments to it, and it must never match a doc tab's key.
        # With a Progress file the tab also scopes to that feature's sessions (perf_view.feature_filter).
        tabs.append({"title": "Performance", "kind": "perf", "path": reports_root, "file": "#performance",
                     "progress": progress_path})
    for i, tab in enumerate(tabs):
        tab["id"] = f"d{i}"
    return tabs


def _static_allowlist(static_dir: Path) -> Dict[str, Path]:
    if not static_dir.is_dir():
        return {}
    return {entry.name: entry for entry in static_dir.iterdir() if entry.is_file()}


def _relative_to_doc_folder(path: Path, base_dir: Path) -> str:
    # anchor.file (anchor_resolver.py) is always relative to the doc's own folder; a tab's path
    # is whatever was passed on the CLI (absolute, or relative to the CWD), so the two must be
    # reconciled here rather than assumed to already match.
    try:
        return str(path.resolve().relative_to(base_dir.resolve()))
    except ValueError:
        return path.name


def _collect_sources(tabs: List[Dict]) -> Dict[str, str]:
    return {tab["id"]: _tab_source(tab) for tab in tabs}


def _collect_mtimes(tabs: List[Dict]) -> Dict[str, float]:
    return {_mtime_key(tab): _tab_mtime(tab) for tab in tabs}


def _tab_source(tab: Dict) -> str:
    if tab["kind"] == "progress":
        return json.dumps(build_model(tab["path"]))
    if tab["kind"] == "perf":
        return json.dumps(perf_view.build_model(tab["path"], progress_path=tab.get("progress")))
    return tab["path"].read_text()


def _tab_mtime(tab: Dict) -> float:
    if tab["kind"] == "progress":
        newest_file = max(path.stat().st_mtime for path in watched_paths(tab["path"]))
        return max(newest_file, pr_refresh_stamp(tab["path"]))
    if tab["kind"] == "perf":
        watched = perf_view.watched_paths(tab["path"])
        if tab.get("progress") is not None and tab["progress"].is_file():
            watched.append(tab["progress"])   # its "sessions:" list changes which sessions are in the feature
        return max(path.stat().st_mtime for path in watched)
    return tab["path"].stat().st_mtime


def _mtime_key(tab: Dict) -> str:
    # The Progress tab watches several files and may share its Progress.md path with a plain md tab,
    # so it gets its own key rather than colliding with that tab's.
    if tab["kind"] in ("progress", "perf"):
        return str(tab["path"]) + "#" + tab["kind"]
    return str(tab["path"])


def _panel_html(i: int, tab: Dict) -> str:
    active = " active" if i == 0 else ""
    css_class = {"md": "markdown", "progress": "progress-view", "perf": "perf-view"}.get(tab["kind"], "diagram")
    return f'<div class="panel{active}"><div class="{css_class}" id="d{i}"></div></div>'


def _bind_server(handler_factory, port: Optional[int]) -> http.server.ThreadingHTTPServer:
    if port is not None:
        try:
            return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_factory)
        except OSError:
            print(f"Port {port} is in use -- picking a free one instead.")
    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_factory)


def _open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        webbrowser.open(url)
