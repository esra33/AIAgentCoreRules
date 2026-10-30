"""Build the Progress tab's model: CreateFeature phases, their steps, and where a feature stands.

Stdlib only, no PyYAML -- the progress, task-list and index files are matched line by line, the
same way session_lifecycle.py reads them. Sources:
  - Processes/CreateFeature/index.md      phase keys, files and gate one-liners
  - Processes/CreateFeature/Phase*.md     steps = the "## " headings (minus apply/Gate/Router check)
  - <Name>_Progress.md                    current_phase, status, phase_handoff blocks, checkpoint.done
  - <Name>_TaskList.md (optional)         stages + tasks, nested under the implementation phase
  - <Name>_TDD.md (optional)              "### V<n> — ..." development phases and their task tables,
                                          nested under the implementation phase (replace the task list)
  - Progress.md pull_requests block       "  V0: [9923, 9930]" -> each PR's notes, fetched with gh (pr_notes.py)
  - Progress.md batches block             "  T3:" -> branch, plan, merged, open_pr (written by /publish-batch);
                                          batch <merged + 1> of <len(plan)> on the task with that id
  - Progress.md phase_handoff block       "  consistency_findings: [...]" -> Sub-phase 1c's findings
                                          (each pre-tagged ✅/⚠️/❌ by the agent), nested under the "1c" step
  - Phase*.md "### Section: <Name>"       a step's TDD section checklist (Sub-phase 1b); a section is checked when
                                          its phase is completed, or the TDD's matching heading has a body that
                                          differs from Processes/Templates/TDD_Template.md's and is not only
                                          "[...]" placeholders
  - Progress.md step_status block         "  1b: in_progress" -> the current phase's step states, recorded by the
                                          agent (done | in_progress); replaces the checkpoint.done match when present
  - Progress.md tdd_sections block        "  Architecture: drafting" -> section states (approved | drafting);
                                          replaces the TDD-body check when present
"""
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pr_notes

CREATE_FEATURE_DIR = Path(__file__).resolve().parents[2] / "Processes" / "CreateFeature"
IMPLEMENTATION_PHASE_KEY = "4_implementation"
CONSISTENCY_STEP_KEY = "1c"

PHASE_KEY_LINE = re.compile(r"^  (\d+)_(\w+):\s*$")
PHASE_FIELD_LINE = re.compile(r"^    (file|gate):\s*(.+?)\s*$")
STEP_HEADING = re.compile(r"^## (.+?)\s*$")
SECTION_HEADING = re.compile(r"^### Section:\s*(.+?)\s*$")
MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BRACKETED_TEXT = re.compile(r"\[[^\]]*\]|\([^)]*\)")
PLACEHOLDER_TEXT = re.compile(r"\[[^\]]*\](?!\()")  # "[TBD]", but not a markdown link's "[text](url)"
SKIPPED_HEADING = re.compile(r"^(apply:|Gate \d|Router check)")
STEP_KEY = re.compile(r"^(?:Sub-phase\s+(\d+[a-z])|(Step\s+\d+|Category\s+\d+))\b")
PHASE_COMPLETED_LINE = re.compile(r'^\s*phase_completed:\s*"Phase\s+(\d+)\b')
TASK_LINE = re.compile(r'^\s*-\s*\{id:\s*([^,]+),\s*status:\s*"\[(.)\]",\s*title:\s*"([^"]*)"')
TASK_TEXT_LINE = re.compile(r'^\s*-\s*task:\s*"([^"]*)"')
TASK_STATUS_LINE = re.compile(r'^\s+status:\s*"\[(.)\]"')
STAGE_LINE = re.compile(r'^\s*-\s*stage:\s*"([^"]*)"')
DONE_ITEM_LINE = re.compile(r'^\s{4}-\s*"(.*)"\s*$')
TASK_STATUS_BY_MARK = {"x": "done", "~": "partial", " ": "todo"}
DEV_PLAN_HEADING = re.compile(r"^##\s+Development plan\b", re.IGNORECASE)
DEV_PHASE_HEADING = re.compile(r"^###\s+(V\d+[a-z]?)\b.*$")
TABLE_SEPARATOR_ROW = re.compile(r"^[\s|:-]+$")
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
PR_PHASE_LINE = re.compile(r"^\s+(V\d+[a-z]?):\s*\[([^\]]*)\]")
CONSISTENCY_FINDINGS_LINE = re.compile(r"^\s{2}consistency_findings:\s*$")
CONSISTENCY_FINDINGS_EMPTY_LINE = re.compile(r"^\s{2}consistency_findings:\s*\[\s*\]\s*$")
BATCHES_LINE = re.compile(r"^batches:\s*(#.*)?$")
BATCH_TASK_LINE = re.compile(r"^  (\S+?):\s*(#.*)?$")
BATCH_FIELD_LINE = re.compile(r"^    (\w+):\s*(.*?)\s*$")
QUOTED_ITEM = re.compile(r'"([^"]*)"|\'([^\']*)\'')
STATUS_ENTRY_LINE = re.compile(r"^  ([^\s#][^:]*?):\s*([\w-]+)\s*(?:#.*)?$")
STEP_STATE_BY_STATUS = {"done": "done", "in_progress": "partial"}
SECTION_STATE_BY_STATUS = {"approved": "done", "drafting": "partial"}


def find_progress_file(doc_path: Path) -> Optional[Path]:
    """The first <Name>_Progress.md next to the served doc, or None if it is not a feature doc."""
    matches = sorted(doc_path.resolve().parent.glob("*_Progress.md"))
    return matches[0] if matches else None


def task_list_path(progress_path: Path) -> Path:
    return progress_path.with_name(progress_path.name[: -len("_Progress.md")] + "_TaskList.md")


def tdd_path(progress_path: Path) -> Path:
    return progress_path.with_name(progress_path.name[: -len("_Progress.md")] + "_TDD.md")


def template_path(process_dir: Path) -> Path:
    return process_dir.parent / "Templates" / "TDD_Template.md"


def watched_paths(progress_path: Path, process_dir: Path = CREATE_FEATURE_DIR) -> List[Path]:
    """Every file the model is built from -- the tab re-renders when any of them changes."""
    candidates = [progress_path, task_list_path(progress_path), tdd_path(progress_path), process_dir / "index.md",
                  template_path(process_dir)]
    candidates += sorted(process_dir.glob("Phase*.md"))
    return [path for path in candidates if path.is_file()]


def pr_refresh_stamp(progress_path: Path) -> float:
    """Start of the current PR refresh window when Progress.md links PRs, else 0 -- folded into the
    tab's mtime so PR comments posted on GitHub reach the page without any local file changing."""
    if not _pull_requests(progress_path.read_text()):
        return 0.0
    return float(pr_notes.refresh_window() * pr_notes.REFRESH_SECONDS)


def build_model(progress_path: Path, process_dir: Path = CREATE_FEATURE_DIR,
                fetch_pr: Callable[[int, Path], Dict] = pr_notes.fetch_pr_notes,
                pr_url: Callable[[int, Path], str] = pr_notes.pr_url) -> Dict:
    progress_text = progress_path.read_text()
    current_key = _quoted_field(progress_text, "current_phase") or ""
    completed_numbers = {int(m.group(1)) for m in map(PHASE_COMPLETED_LINE.match, progress_text.splitlines()) if m}
    done_items = _checkpoint_done(progress_text)
    step_statuses = _status_block(progress_text, "step_status")
    section_statuses = _status_block(progress_text, "tdd_sections")
    consistency_findings = _consistency_findings(progress_text)
    task_list = task_list_path(progress_path)
    stages = _task_stages(task_list.read_text()) if task_list.is_file() else []
    tdd = tdd_path(progress_path)
    dev_phases = _dev_phases(tdd.read_text()) if tdd.is_file() else []
    tdd_bodies = _heading_bodies(tdd.read_text()) if tdd.is_file() else []
    template = template_path(process_dir)
    template_bodies = _heading_bodies(template.read_text()) if template.is_file() else []
    pull_requests = _pull_requests(progress_text)
    for dev_phase in dev_phases:
        dev_phase["pull_requests"] = [fetch_pr(number, progress_path.parent)
                                      for number in pull_requests.get(dev_phase["key"], [])]
    # The V-phase in progress starts with its tasks expanded: the first one with an unfinished task.
    in_progress = next((dev for dev in dev_phases if any(task["status"] != "done" for task in dev["tasks"])), None)
    for dev_phase in dev_phases:
        dev_phase["open"] = dev_phase is in_progress
    batches = _batches(progress_text)
    for task in [task for stage in stages for task in stage["tasks"]] + [task for dev in dev_phases for task in dev["tasks"]]:
        task["batch"] = _batch_view(batches.get(task["id"]), progress_path.parent, pr_url)

    phases = []
    for phase in _index_phases(process_dir):
        completed = phase["number"] in completed_numbers
        is_current = phase["key"] == current_key
        steps = _steps(process_dir / phase["file"])
        for step in steps:
            # Recorded states win; without the block, fall back to the approximate checks. step_status
            # only applies to the current phase -- "Step 1" exists in more than one phase file.
            if completed:
                step["state"] = "done"
            elif step_statuses is not None:
                names = [step["key"], step["title"], step["title"].split(" — ", 1)[-1]]
                step["state"] = _recorded_state(step_statuses, names, STEP_STATE_BY_STATUS) if is_current else "todo"
            else:
                step["state"] = "done" if is_current and _step_mentioned(step, done_items) else "todo"
            step["done"] = step["state"] == "done"
            step["findings"] = consistency_findings if step["key"] == CONSISTENCY_STEP_KEY else []
            for section in step["sections"]:
                if completed:
                    section["state"] = "done"
                elif section_statuses is not None:
                    section["state"] = _recorded_state(section_statuses, [section["title"]], SECTION_STATE_BY_STATUS)
                else:
                    filled = _tdd_section_filled(section["title"], tdd_bodies, template_bodies)
                    section["state"] = "done" if filled else "todo"
                section["done"] = section["state"] == "done"
        phases.append(
            {
                "key": phase["key"],
                "number": phase["number"],
                "title": f"Phase {phase['number']} — {phase['name']}",
                "gate": phase["gate"],
                "completed": completed,
                "current": is_current,
                "steps": steps,
                "stages": stages if phase["key"] == IMPLEMENTATION_PHASE_KEY else [],
                "dev_phases": dev_phases if phase["key"] == IMPLEMENTATION_PHASE_KEY else [],
            }
        )

    return {
        "feature": _quoted_field(progress_text, "feature") or progress_path.stem,
        "status": _quoted_field(progress_text, "status") or "",
        "updated_at": _quoted_field(progress_text, "updated_at") or "",
        "next": _quoted_field(progress_text, "next") or "",
        "current_phase": current_key,
        "next_gate_phase": _next_gate_phase(phases),
        "phases": phases,
    }


def _next_gate_phase(phases: List[Dict]) -> Optional[str]:
    # The gate still to pass: the current phase's own gate, or -- when that block is already
    # written (status at_gate after the handoff, or a skipped phase) -- the first later phase
    # without one.
    start = next((i for i, phase in enumerate(phases) if phase["current"]), 0)
    pending = next((phase for phase in phases[start:] if not phase["completed"]), None)
    return pending["key"] if pending else None


def _index_phases(process_dir: Path) -> List[Dict]:
    phases: List[Dict] = []
    for line in (process_dir / "index.md").read_text().splitlines():
        key_match = PHASE_KEY_LINE.match(line)
        if key_match:
            name = key_match.group(2).replace("_", " ").title()
            phases.append({"key": f"{key_match.group(1)}_{key_match.group(2)}", "number": int(key_match.group(1)),
                           "name": name, "file": "", "gate": ""})
            continue
        field_match = PHASE_FIELD_LINE.match(line)
        if field_match and phases:
            value = field_match.group(2)
            phases[-1][field_match.group(1)] = value[2:] if value.startswith("./") else value
    return phases


def _steps(phase_path: Path) -> List[Dict]:
    if not phase_path.is_file():
        return []
    steps = []
    for line in phase_path.read_text().splitlines():
        heading = STEP_HEADING.match(line)
        if heading and not SKIPPED_HEADING.match(heading.group(1)):
            title = heading.group(1)
            key_match = STEP_KEY.match(title)
            key = (key_match.group(1) or key_match.group(2)) if key_match else ""
            steps.append({"title": title, "key": key, "sections": []})
            continue
        section = SECTION_HEADING.match(line)
        if section and steps:
            steps[-1]["sections"].append({"title": section.group(1)})
    return steps


def _heading_bodies(markdown: str) -> List[Dict[str, str]]:
    # Every "##".."######" heading (normalised) with its whitespace-collapsed body: the lines up to the
    # next heading of the same or a higher level. Lines inside ``` fences are body, never headings.
    lines = markdown.splitlines()
    headings = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        heading = MARKDOWN_HEADING.match(line) if not in_fence else None
        if heading:
            headings.append((index, len(heading.group(1)), heading.group(2)))
    bodies = []
    for position, (index, level, text) in enumerate(headings):
        end = next((other for other, other_level, _ in headings[position + 1:] if other_level <= level), len(lines))
        if level > 1:
            bodies.append({"name": _normalised(text), "body": " ".join(" ".join(lines[index + 1:end]).split())})
    return bodies


def _normalised(text: str) -> str:
    # "Edge Cases [Optional]" -> "edge cases"; "Development Plan — Stage Levels" -> "development plan stage levels"
    return re.sub(r"[^a-z0-9]+", " ", BRACKETED_TEXT.sub("", text).lower()).strip()


def _matching_body(name: str, bodies: List[Dict[str, str]]) -> Optional[str]:
    # An exact heading first; else one whose words start the other's ("Development plan" for
    # "Development Plan — Stage Levels", "Stage Level" for "Stage Levels").
    wanted = _normalised(name)
    exact = next((entry["body"] for entry in bodies if entry["name"] == wanted), None)
    if exact is not None:
        return exact
    return next((entry["body"] for entry in bodies if entry["name"]
                 and (wanted.startswith(entry["name"]) or entry["name"].startswith(wanted))), None)


def _tdd_section_filled(name: str, tdd_bodies: List[Dict[str, str]], template_bodies: List[Dict[str, str]]) -> bool:
    """Approximate by design: the TDD has the section with a body that is not the template's placeholder
    and is not only "[...]" placeholders (an agent reverting a section to "[TBD]")."""
    body = _matching_body(name, tdd_bodies)
    if not body or not PLACEHOLDER_TEXT.sub("", body).strip(" .:;,-—|"):
        return False
    return body != _matching_body(name, template_bodies)


def _status_block(progress_text: str, name: str) -> Optional[Dict[str, str]]:
    # step_status:                      tdd_sections:
    #   1b: in_progress                   Architecture: drafting
    # Normalised name -> status, or None when the progress file has no such block (the tab then
    # falls back to the approximate checks). Comment and blank lines inside the block are skipped.
    header = re.compile(r"^" + re.escape(name) + r":\s*(#.*)?$")
    statuses: Optional[Dict[str, str]] = None
    for line in progress_text.splitlines():
        if statuses is None:
            if header.match(line):
                statuses = {}
            continue
        if not line.strip() or line.strip().startswith("#"):
            continue
        entry = STATUS_ENTRY_LINE.match(line)
        if not entry:
            break
        statuses[_normalised(entry.group(1).strip().strip("\"'"))] = entry.group(2).lower()
    return statuses


def _recorded_state(statuses: Dict[str, str], names: List[str], state_by_status: Dict[str, str]) -> str:
    """done | partial | todo for the first of names the block lists; unlisted or unknown statuses are todo."""
    status = next((statuses[key] for key in map(_normalised, names) if key and key in statuses), "")
    return state_by_status.get(status, "todo")


def _step_mentioned(step: Dict, done_items: List[str]) -> bool:
    # Approximate by design: checkpoint.done is free text, so a step counts as done when an item
    # names its key ("1a", "Step 3") or its full title after the dash.
    needles = []
    if step["key"]:
        needles.append(re.compile(r"\b" + re.escape(step["key"]) + r"\b", re.IGNORECASE))
    name = step["title"].split(" — ", 1)[-1]
    needles.append(re.compile(re.escape(name), re.IGNORECASE))
    return any(needle.search(item) for item in done_items for needle in needles)


def _checkpoint_done(progress_text: str) -> List[str]:
    items: List[str] = []
    in_done = False
    for line in progress_text.splitlines():
        if re.match(r"^\s{2}done:\s*\[\s*\]\s*$", line):
            return []
        if re.match(r"^\s{2}done:\s*$", line):
            in_done = True
            continue
        if in_done:
            item = DONE_ITEM_LINE.match(line)
            if not item:
                break
            items.append(item.group(1))
    return items


def _consistency_findings(progress_text: str) -> List[str]:
    """Sub-phase 1c's findings, each pre-tagged by the agent with a status emoji (✅/⚠️/❌), written
    into the Gate 1 phase_handoff block once the gate is confirmed -- empty until then."""
    items: List[str] = []
    in_block = False
    for line in progress_text.splitlines():
        if CONSISTENCY_FINDINGS_EMPTY_LINE.match(line):
            return []
        if CONSISTENCY_FINDINGS_LINE.match(line):
            in_block = True
            continue
        if in_block:
            item = DONE_ITEM_LINE.match(line)
            if not item:
                break
            items.append(item.group(1))
    return items


def _task_stages(task_list_text: str) -> List[Dict]:
    stages: List[Dict] = []
    open_task: Optional[Dict] = None  # a multi-line "- task:" entry still waiting for its "status:" line
    for line in task_list_text.splitlines():
        stage = STAGE_LINE.match(line)
        if stage:
            stages.append({"title": stage.group(1).strip(), "tasks": []})
            open_task = None
            continue
        task = TASK_LINE.match(line)
        if task and stages:
            stages[-1]["tasks"].append(
                {"id": task.group(1).strip(), "title": task.group(3).strip(),
                 "status": TASK_STATUS_BY_MARK.get(task.group(2), "todo")}
            )
            open_task = None
            continue
        task_text = TASK_TEXT_LINE.match(line)
        if task_text and stages:
            open_task = {"id": "", "title": task_text.group(1).strip(), "status": "todo"}
            stages[-1]["tasks"].append(open_task)
            continue
        status = TASK_STATUS_LINE.match(line)
        if status and open_task is not None:
            open_task["status"] = TASK_STATUS_BY_MARK.get(status.group(1), "todo")
            open_task = None
    return stages


def _dev_phases(tdd_text: str) -> List[Dict]:
    # "### V<n> — ..." headings inside any "## Development plan..." section; each phase's tasks are the
    # rows of its markdown table, labelled by the Title column (else Task), status from the Status column.
    phases: List[Dict] = []
    in_plan = False
    current: Optional[Dict] = None
    columns: List[str] = []
    for line in tdd_text.splitlines():
        if line.startswith("## "):
            in_plan = bool(DEV_PLAN_HEADING.match(line))
            current = None
            continue
        if not in_plan:
            continue
        if line.startswith("### "):
            heading = DEV_PHASE_HEADING.match(line)
            current = {"key": heading.group(1), "title": line[4:].strip(), "tasks": []} if heading else None
            if current is not None:
                phases.append(current)
            columns = []
            continue
        if current is None or not line.lstrip().startswith("|") or TABLE_SEPARATOR_ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not columns:
            columns = [cell.lower() for cell in cells]
            continue
        current["tasks"].append(_table_task(columns, cells))
    return phases


def _table_task(columns: List[str], cells: List[str]) -> Dict:
    def cell(name: str) -> str:
        return cells[columns.index(name)] if name in columns and columns.index(name) < len(cells) else ""

    label = cell("title") or cell("task") or (cells[0] if cells else "")
    status_mark = re.search(r"\[(.)\]", cell("status"))
    return {"id": cell("#"), "title": MARKDOWN_LINK.sub(r"\1", label).replace("`", ""),
            "status": TASK_STATUS_BY_MARK.get(status_mark.group(1).lower(), "todo") if status_mark else "todo"}


def _pull_requests(progress_text: str) -> Dict[str, List[int]]:
    # pull_requests:
    #   V0: [9923, 9930]
    links: Dict[str, List[int]] = {}
    in_block = False
    for line in progress_text.splitlines():
        if re.match(r"^pull_requests:\s*(#.*)?$", line):
            in_block = True
            continue
        if in_block:
            entry = PR_PHASE_LINE.match(line)
            if not entry:
                break
            links[entry.group(1)] = [int(n) for n in re.findall(r"\d+", entry.group(2))]
    return links


def _batches(progress_text: str) -> Dict[str, Dict[str, str]]:
    # batches:
    #   T3:
    #     plan:    ["Contracts", "Manager"]
    #     merged:  1
    #     open_pr: 9941
    # Raw field strings per task id; comment and blank lines inside the block are skipped.
    tasks: Dict[str, Dict[str, str]] = {}
    in_block = False
    current: Optional[Dict[str, str]] = None
    for line in progress_text.splitlines():
        if BATCHES_LINE.match(line):
            in_block = True
            continue
        if not in_block or not line.strip() or line.strip().startswith("#"):
            continue
        task = BATCH_TASK_LINE.match(line)
        if task:
            current = tasks.setdefault(task.group(1).strip("\"'"), {})
            continue
        field = BATCH_FIELD_LINE.match(line)
        if not field or current is None:
            break
        current[field.group(1)] = field.group(2)
    return tasks


def _batch_view(fields: Optional[Dict[str, str]], repo_dir: Path,
                pr_url: Callable[[int, Path], str]) -> Optional[Dict]:
    """Batch <merged + 1> of <len(plan)> for one task, or None when it has no batch plan yet."""
    if not fields:
        return None
    plan = [double or single for double, single in QUOTED_ITEM.findall(fields.get("plan", ""))]
    if not plan:
        return None
    merged_match = re.match(r"\d+", fields.get("merged", ""))
    merged = min(int(merged_match.group(0)), len(plan)) if merged_match else 0
    open_match = re.match(r"\d+", fields.get("open_pr", ""))
    open_pr = int(open_match.group(0)) if open_match else None
    done = merged == len(plan)
    return {"current": merged + 1 if not done else len(plan), "total": len(plan), "done": done,
            "title": "" if done else plan[merged], "open_pr": open_pr,
            "open_pr_url": pr_url(open_pr, repo_dir) if open_pr is not None else ""}


def _quoted_field(text: str, field: str) -> Optional[str]:
    match = re.search(r'^\s*' + re.escape(field) + r':\s*"([^"]*)"', text, re.MULTILINE)
    return match.group(1) if match else None
