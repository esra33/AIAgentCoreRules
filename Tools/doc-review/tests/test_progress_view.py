"""Progress tab tests: progress_view.py's model (phases, steps, gate still to pass, task list) built
from a self-made CreateFeature process folder, plus the server's auto-detection of the tab.

    python3 -m unittest discover -s Tools/doc-review/tests -p 'test_*.py'
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import pr_notes  # noqa: E402
import review_server  # noqa: E402
from progress_view import build_model, find_progress_file, pr_refresh_stamp, watched_paths  # noqa: E402

INDEX_MD = """# CreateFeature

```yaml
phases:
  1_intake:
    file: ./Phase1_Intake.md
    goal: Intake goal
    gate: Intake gate text

  2_discovery:
    file: ./Phase2_Discovery.md
    goal: Discovery goal
    gate: Discovery gate text

  3_design:
    file: ./Phase3_Design.md
    gate: Design gate text

  4_implementation:
    file: ./Phase4_Implementation.md
    gate: Implementation gate text
```
"""

PHASE_FILES = {
    "Phase1_Intake.md": "## apply: on-demand\n## Sub-phase 1a — GDD Conversion\n"
                        "## Sub-phase 1b — TDD Section-by-Section\n### Section: Objective\n### Section: Architecture\n"
                        "### Section: Development Plan — Stage Levels\n### Section: Edge Cases\n"
                        "## Sub-phase 1c — Consistency and Gap Review\n"
                        "## Gate 1 — Intake Complete\n"
                        "## Router check (used by /end-session)\n",
    "Phase2_Discovery.md": "## Load Rules\n## Explore the Codebase\n## Gate 2 — Discovery Report\n",
    "Phase3_Design.md": "## Step 1 — Design Proposal\n## Step 2 — Architecture Diagrams\n## Gate 3 — Design Approved\n",
    "Phase4_Implementation.md": "## Per-File Checklist\n## Gate 4 — Implementation Complete\n",
}

PROGRESS_MD = """# Demo — Progress

```yaml
feature:        "Demo"
current_phase:  "{current}"
status:         "in_progress"
updated_at:     "2026-10-26T10:00"
```

## Checkpoint

```yaml
checkpoint:
  done:
{done}
  in_flight: "none"
  next: "Do the next thing"
```

## Gates Passed

{gates}
"""

TASK_LIST_MD = """```yaml
- stage: "V1 — Stage one"
  tasks:
    - {id: 1, status: "[x]", title: "First",  task: "a"}
    - {id: 2, status: "[~]", title: "Second", task: "b"}
    - {id: 3, status: "[ ]", title: "Third",  task: "c"}
```
"""


MULTILINE_TASK_LIST_MD = """```yaml
stages:
  - stage: "Stage 1 — Multi-line"
    tasks:
      - task: "First"
        assignee: "Someone"
        status: "[x]"
      - task: "Second"
        status: "[ ]"
```
"""


TDD_MD = """# Demo TDD

### V9 — Not in the plan

| Title | Task | Status |
| --- | --- | --- |
| Stray | x | [ ] |

## Development Plan — Stages

Intro paragraph.

### V0 — Core

**Level of effort:** S

| Title | Task | Assignee | Status |
| --- | --- | --- | --- |
| Contracts | New asmdef | A | [x] |
| Router | Save router | A | [~] |

### V1 — Flow

| Task | Status |
|---|---|
| `Serve` on [PR 9923](https://example.com/9923) | [ ] |

## Risks

| Title | Status |
| --- | --- |
| Not a task | [ ] |
"""

BATCHES_TDD_MD = """## Development Plan

### V0 — Core

| # | Title | Status |
| --- | --- | --- |
| T1 | Contracts | [x] |
| T2 | Router | [~] |
| T3 | Untouched | [ ] |
"""

BATCHES_YAML = """batches:                 # Phase 4: per task id, written by /publish-batch
                         #   T9:
                         #     plan: ["commented out"]
  T1:
    branch:  "feature/Demo/T1"
    plan:    ["Contracts", "Tests"]
    merged:  2
    open_pr: null
    prs:     [21, 22]
  T2:
    branch:  "feature/Demo/T2"
    base:    "user/me/demo"
    plan:    ["Router interface", 'Router impl', "Glue"]
    merged:  1
    open_pr: 31
    prs:     [30, 31]
  1:
    plan:    ["Only batch"]
    merged:  0
    open_pr: null
next_field: "not part of the block"
"""

TEMPLATE_TDD_MD = """# Technical Design Document — [Feature Name]

## Objective
[Insert summary of the system]

## Development plan

### Stage Level (ie V0, V1 …)
| # | Title |
| --- | --- |
| T1 | Sample task |

## Edge Cases [Optional]
| 1 | Sample edge case | |
"""

SECTIONS_TDD_MD = """# Demo TDD

## Objective
Saves the round so a crash resumes it.

## Development Plan — Stage Levels
### V0 — Core
| # | Title |
| --- | --- |
| T1 | Contracts |

## Edge Cases
| 1 | Sample edge case | |
"""

PULL_REQUESTS_YAML = """pull_requests:
  V0: [11, 12]
  V7: [99]
"""


def _gate_block(label, findings=()):
    findings_yaml = ""
    if findings:
        items = "\n".join(f'    - "{finding}"' for finding in findings)
        findings_yaml = f"\n  consistency_findings:\n{items}"
    return f'```yaml\nphase_handoff:\n  phase_completed:   "{label}"\n  open_items: []{findings_yaml}\n```\n'


class ProgressViewTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.process_dir = self.tmp / "CreateFeature"
        self.process_dir.mkdir()
        (self.process_dir / "index.md").write_text(INDEX_MD)
        for name, text in PHASE_FILES.items():
            (self.process_dir / name).write_text(text)
        self.feature_dir = self.tmp / "Demo"
        self.feature_dir.mkdir()
        self.doc_path = self.feature_dir / "Demo_TDD.md"
        self.doc_path.write_text("# Demo TDD\n")
        self.progress_path = self.feature_dir / "Demo_Progress.md"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_progress(self, current, done=(), gates=()):
        done_text = "\n".join(f'    - "{item}"' for item in done)
        gate_blocks = [_gate_block(*g) if isinstance(g, tuple) else _gate_block(g) for g in gates]
        text = PROGRESS_MD.format(current=current, done=done_text, gates="\n".join(gate_blocks))
        text = text.replace("  done:\n\n", "  done: []\n")  # no items -> the template's "done: []" form
        self.progress_path.write_text(text)

    def model(self):
        return build_model(self.progress_path, self.process_dir)

    def phase(self, model, key):
        return next(phase for phase in model["phases"] if phase["key"] == key)


class BuildModelTests(ProgressViewTestBase):
    def test_phases_come_from_index_with_their_gates(self):
        self.write_progress("1_intake")
        model = self.model()
        self.assertEqual([p["key"] for p in model["phases"]], ["1_intake", "2_discovery", "3_design", "4_implementation"])
        self.assertEqual(self.phase(model, "2_discovery")["title"], "Phase 2 — Discovery")
        self.assertEqual(self.phase(model, "2_discovery")["gate"], "Discovery gate text")

    def test_steps_skip_apply_gate_router_and_subsections(self):
        self.write_progress("1_intake")
        titles = [s["title"] for s in self.phase(self.model(), "1_intake")["steps"]]
        self.assertEqual(titles, ["Sub-phase 1a — GDD Conversion", "Sub-phase 1b — TDD Section-by-Section",
                                   "Sub-phase 1c — Consistency and Gap Review"])

    def test_completed_phases_are_those_with_a_handoff_block_and_all_their_steps_are_done(self):
        self.write_progress("3_design", gates=["Phase 1 — Intake", "Phase 2 — Discovery"])
        model = self.model()
        self.assertTrue(self.phase(model, "1_intake")["completed"])
        self.assertTrue(all(s["done"] for s in self.phase(model, "2_discovery")["steps"]))
        self.assertFalse(self.phase(model, "3_design")["completed"])
        self.assertTrue(self.phase(model, "3_design")["current"])

    def test_current_phase_steps_are_checked_from_checkpoint_done_by_key_or_name(self):
        self.write_progress("3_design", done=["Step 1 drafted and approved"])
        steps = self.phase(self.model(), "3_design")["steps"]
        self.assertEqual([s["done"] for s in steps], [True, False])
        self.write_progress("3_design", done=["Architecture diagrams rendered"])
        steps = self.phase(self.model(), "3_design")["steps"]
        self.assertEqual([s["done"] for s in steps], [False, True])

    def test_checkpoint_done_does_not_check_steps_of_other_unfinished_phases(self):
        self.write_progress("1_intake", done=["Step 1 of something"])
        self.assertFalse(any(s["done"] for s in self.phase(self.model(), "3_design")["steps"]))

    def test_empty_done_list_checks_nothing(self):
        self.write_progress("1_intake")
        self.assertFalse(any(s["done"] for s in self.phase(self.model(), "1_intake")["steps"]))

    def test_next_gate_is_the_current_phase_until_its_handoff_is_written(self):
        self.write_progress("2_discovery", gates=["Phase 1 — Intake"])
        self.assertEqual(self.model()["next_gate_phase"], "2_discovery")
        self.write_progress("2_discovery", gates=["Phase 1 — Intake", "Phase 2 — Discovery"])
        self.assertEqual(self.model()["next_gate_phase"], "3_design")

    def test_next_gate_is_none_when_every_phase_is_complete(self):
        self.write_progress("4_implementation", gates=[f"Phase {n} — X" for n in range(1, 5)])
        self.assertIsNone(self.model()["next_gate_phase"])

    def test_task_list_is_nested_under_implementation_only(self):
        self.write_progress("1_intake")
        (self.feature_dir / "Demo_TaskList.md").write_text(TASK_LIST_MD)
        model = self.model()
        stages = self.phase(model, "4_implementation")["stages"]
        self.assertEqual(stages[0]["title"], "V1 — Stage one")
        self.assertEqual([t["status"] for t in stages[0]["tasks"]], ["done", "partial", "todo"])
        self.assertEqual(self.phase(model, "1_intake")["stages"], [])

    def test_multi_line_task_list_form_parses_task_text_and_status(self):
        self.write_progress("4_implementation")
        (self.feature_dir / "Demo_TaskList.md").write_text(MULTILINE_TASK_LIST_MD)
        stages = self.phase(self.model(), "4_implementation")["stages"]
        self.assertEqual(stages[0]["title"], "Stage 1 — Multi-line")
        self.assertEqual([(t["id"], t["title"], t["status"]) for t in stages[0]["tasks"]],
                         [("", "First", "done"), ("", "Second", "todo")])

    def test_tdd_v_phases_are_nested_under_implementation_with_table_tasks(self):
        self.write_progress("4_implementation")
        self.doc_path.write_text(TDD_MD)
        model = self.model()
        dev_phases = self.phase(model, "4_implementation")["dev_phases"]
        self.assertEqual([d["key"] for d in dev_phases], ["V0", "V1"])  # the V9 outside the plan is ignored
        self.assertEqual(dev_phases[0]["title"], "V0 — Core")
        self.assertEqual([(t["id"], t["title"], t["status"]) for t in dev_phases[0]["tasks"]],
                         [("", "Contracts", "done"), ("", "Router", "partial")])
        self.assertEqual([t["title"] for t in dev_phases[1]["tasks"]], ["Serve on PR 9923"])  # link + backticks stripped
        self.assertEqual(self.phase(model, "1_intake")["dev_phases"], [])

    def test_first_v_phase_with_unfinished_tasks_starts_open(self):
        self.write_progress("4_implementation")
        self.doc_path.write_text(TDD_MD.replace("[~]", "[x]"))
        dev_phases = self.phase(self.model(), "4_implementation")["dev_phases"]
        self.assertEqual([d["open"] for d in dev_phases], [False, True])

    def test_pull_requests_are_fetched_per_v_phase_from_the_progress_file(self):
        self.write_progress("4_implementation")
        self.progress_path.write_text(self.progress_path.read_text() + "\n```yaml\n" + PULL_REQUESTS_YAML + "```\n")
        self.doc_path.write_text(TDD_MD)
        calls = []

        def fake_fetch(number, repo_dir):
            calls.append((number, repo_dir))
            return {"number": number, "notes": []}

        model = build_model(self.progress_path, self.process_dir, fetch_pr=fake_fetch)
        dev_phases = self.phase(model, "4_implementation")["dev_phases"]
        self.assertEqual([[pr["number"] for pr in d["pull_requests"]] for d in dev_phases], [[11, 12], []])
        self.assertEqual({repo_dir for _, repo_dir in calls}, {self.feature_dir})

    def write_batches(self):
        self.write_progress("4_implementation")
        self.progress_path.write_text(self.progress_path.read_text() + "\n```yaml\n" + BATCHES_YAML + "```\n")

    def test_batches_show_batch_n_of_m_on_the_matching_tdd_task(self):
        self.write_batches()
        self.doc_path.write_text(BATCHES_TDD_MD)
        model = build_model(self.progress_path, self.process_dir, pr_url=lambda n, d: f"https://gh/pull/{n}")
        tasks = self.phase(model, "4_implementation")["dev_phases"][0]["tasks"]
        self.assertEqual(tasks[1]["batch"], {"current": 2, "total": 3, "done": False, "title": "Router impl",
                                             "open_pr": 31, "open_pr_url": "https://gh/pull/31"})
        self.assertIsNone(tasks[2]["batch"])

    def test_batches_are_done_when_every_planned_batch_merged(self):
        self.write_batches()
        self.doc_path.write_text(BATCHES_TDD_MD)
        task = self.phase(self.model(), "4_implementation")["dev_phases"][0]["tasks"][0]
        self.assertEqual(task["batch"], {"current": 2, "total": 2, "done": True, "title": "",
                                         "open_pr": None, "open_pr_url": ""})

    def test_batches_attach_to_task_list_ids_and_ignore_comment_lines(self):
        self.write_batches()
        (self.feature_dir / "Demo_TaskList.md").write_text(TASK_LIST_MD)
        tasks = self.phase(self.model(), "4_implementation")["stages"][0]["tasks"]
        self.assertEqual(tasks[0]["batch"]["title"], "Only batch")
        self.assertEqual((tasks[0]["batch"]["current"], tasks[0]["batch"]["total"]), (1, 1))
        self.assertEqual([t["batch"] for t in tasks[1:]], [None, None])

    def test_no_batches_block_leaves_every_task_without_a_batch(self):
        self.write_progress("4_implementation")
        self.doc_path.write_text(BATCHES_TDD_MD)
        tasks = self.phase(self.model(), "4_implementation")["dev_phases"][0]["tasks"]
        self.assertEqual([t["batch"] for t in tasks], [None, None, None])

    def test_pr_refresh_stamp_only_when_prs_are_linked(self):
        self.write_progress("4_implementation")
        self.assertEqual(pr_refresh_stamp(self.progress_path), 0.0)
        self.progress_path.write_text(self.progress_path.read_text() + "\n```yaml\n" + PULL_REQUESTS_YAML + "```\n")
        self.assertGreater(pr_refresh_stamp(self.progress_path), 0.0)

    def test_consistency_findings_are_nested_under_the_1c_step_once_the_gate_is_written(self):
        findings = ["✅ No conflicts found", "⚠️ Final Touches gap acknowledged"]
        self.write_progress("2_discovery", gates=[("Phase 1 — Intake", findings)])
        steps = self.phase(self.model(), "1_intake")["steps"]
        step_1c = next(s for s in steps if s["key"] == "1c")
        self.assertEqual(step_1c["findings"], findings)
        self.assertTrue(all(s["findings"] == [] for s in steps if s["key"] != "1c"))

    def test_consistency_findings_are_empty_before_the_gate_is_written(self):
        self.write_progress("1_intake")
        steps = self.phase(self.model(), "1_intake")["steps"]
        step_1c = next(s for s in steps if s["key"] == "1c")
        self.assertEqual(step_1c["findings"], [])

    def append_yaml(self, block):
        self.progress_path.write_text(self.progress_path.read_text() + "\n```yaml\n" + block + "```\n")

    def test_step_status_block_replaces_the_checkpoint_done_match(self):
        self.write_progress("1_intake", done=["1c mentioned but not recorded"])
        self.append_yaml("step_status:             # current phase only\n  1a: done\n  \"1b\": in_progress  # drafting\n"
                         "  1z: done\nnext_field: \"not part of the block\"\n")
        steps = self.phase(self.model(), "1_intake")["steps"]
        self.assertEqual([(s["key"], s["state"], s["done"]) for s in steps],
                         [("1a", "done", True), ("1b", "partial", False), ("1c", "todo", False)])

    def test_step_status_matches_by_title_and_only_in_the_current_phase(self):
        self.write_progress("3_design", gates=["Phase 1 — Intake", "Phase 2 — Discovery"])
        self.append_yaml("step_status:\n  Step 1: done\n  Architecture diagrams: in_progress\n")
        model = self.model()
        self.assertEqual([s["state"] for s in self.phase(model, "3_design")["steps"]], ["done", "partial"])
        self.assertTrue(all(s["state"] == "done" for s in self.phase(model, "2_discovery")["steps"]))
        self.assertTrue(all(s["state"] == "todo" for s in self.phase(model, "4_implementation")["steps"]))

    def test_empty_step_status_block_checks_nothing(self):
        self.write_progress("1_intake", done=["1a converted"])
        self.append_yaml("step_status:\n")
        self.assertTrue(all(s["state"] == "todo" for s in self.phase(self.model(), "1_intake")["steps"]))

    def test_header_fields(self):
        self.write_progress("1_intake")
        model = self.model()
        self.assertEqual((model["feature"], model["status"], model["next"]), ("Demo", "in_progress", "Do the next thing"))


class TddSectionTests(ProgressViewTestBase):
    def setUp(self):
        super().setUp()
        (self.tmp / "Templates").mkdir()
        (self.tmp / "Templates" / "TDD_Template.md").write_text(TEMPLATE_TDD_MD)

    def sections(self):
        steps = self.phase(self.model(), "1_intake")["steps"]
        self.assertTrue(all(s["sections"] == [] for s in steps if s["key"] != "1b"))
        return {s["title"]: s["done"] for s in next(s for s in steps if s["key"] == "1b")["sections"]}

    def test_1b_lists_the_phase_file_sections_in_order(self):
        self.write_progress("1_intake")
        self.assertEqual(list(self.sections()), ["Objective", "Architecture", "Development Plan — Stage Levels",
                                                  "Edge Cases"])

    def test_section_is_checked_when_the_tdd_body_differs_from_the_template(self):
        self.write_progress("1_intake")
        self.doc_path.write_text(SECTIONS_TDD_MD)
        self.assertEqual(self.sections(), {"Objective": True, "Architecture": False,
                                           "Development Plan — Stage Levels": True, "Edge Cases": False})

    def test_placeholder_copied_from_the_template_is_not_checked(self):
        self.write_progress("1_intake")
        self.doc_path.write_text(TEMPLATE_TDD_MD)
        self.assertFalse(any(self.sections().values()))

    def test_heading_prefix_matches_the_template_shape_and_ignores_fenced_headings(self):
        self.write_progress("1_intake")
        self.doc_path.write_text("## Development plan\n### Stage Level (ie V0)\n| T1 | Real task |\n"
                                 "## Architecture\n```yaml\n## not a heading\n```\n")
        sections = self.sections()
        self.assertTrue(sections["Development Plan — Stage Levels"])
        self.assertTrue(sections["Architecture"])

    def test_bracketed_placeholder_only_body_is_not_checked_but_a_link_is(self):
        self.write_progress("1_intake")
        self.doc_path.write_text("## Objective\n[TBD — pending engineer answers (see Checkpoint)]\n"
                                 "## Architecture\n- [Design doc](https://example.com/doc)\n## Edge Cases\n[TBD]\n")
        self.assertEqual(self.sections(), {"Objective": False, "Architecture": True,
                                           "Development Plan — Stage Levels": False, "Edge Cases": False})

    def section_states(self):
        steps = self.phase(self.model(), "1_intake")["steps"]
        return {s["title"]: s["state"] for s in next(s for s in steps if s["key"] == "1b")["sections"]}

    def test_tdd_sections_block_replaces_the_tdd_body_check(self):
        self.write_progress("1_intake")
        self.doc_path.write_text(SECTIONS_TDD_MD)  # Objective and Development Plan have bodies
        self.progress_path.write_text(self.progress_path.read_text() + "\n```yaml\ntdd_sections:\n  Objective: approved\n"
                                      "  \"Development Plan — Stage Levels\": drafting\n  Edge Cases: bogus\n```\n")
        self.assertEqual(self.section_states(), {"Objective": "done", "Architecture": "todo",
                                                 "Development Plan — Stage Levels": "partial", "Edge Cases": "todo"})

    def test_completed_intake_checks_every_section(self):
        self.write_progress("2_discovery", gates=["Phase 1 — Intake"])
        self.assertTrue(all(self.sections().values()))
        self.progress_path.write_text(self.progress_path.read_text() + "\n```yaml\ntdd_sections:\n  Objective: drafting\n```\n")
        self.assertTrue(all(state == "done" for state in self.section_states().values()))

    def test_template_is_watched(self):
        self.write_progress("1_intake")
        names = {path.name for path in watched_paths(self.progress_path, self.process_dir)}
        self.assertIn("TDD_Template.md", names)


class DetectionTests(ProgressViewTestBase):
    def test_find_progress_file_next_to_the_doc(self):
        self.assertIsNone(find_progress_file(self.doc_path))
        self.write_progress("1_intake")
        self.assertEqual(find_progress_file(self.doc_path), self.progress_path.resolve())

    def test_watched_paths_include_task_list_and_process_files(self):
        self.write_progress("1_intake")
        (self.feature_dir / "Demo_TaskList.md").write_text(TASK_LIST_MD)
        names = {path.name for path in watched_paths(self.progress_path, self.process_dir)}
        self.assertTrue({"Demo_Progress.md", "Demo_TaskList.md", "index.md", "Phase3_Design.md"} <= names)


class ServerTabTests(ProgressViewTestBase):
    def test_no_progress_tab_without_a_progress_file(self):
        tabs = review_server._tabs([self.doc_path])
        self.assertEqual([t["kind"] for t in tabs], ["md"])

    def test_progress_tab_is_first_with_a_json_source_and_its_own_mtime_key(self):
        self.write_progress("1_intake")
        tabs = review_server._tabs([self.doc_path, self.progress_path])
        self.assertEqual([t["kind"] for t in tabs], ["progress", "md", "md"])
        self.assertEqual([t["id"] for t in tabs], ["d0", "d1", "d2"])
        mtimes = review_server._collect_mtimes(tabs)
        self.assertEqual(len(mtimes), 3)  # the md tab of Progress.md and the Progress tab do not collide
        source = json.loads(review_server._collect_sources(tabs)[tabs[0]["id"]])
        self.assertEqual(source["feature"], "Demo")

    def test_progress_tab_file_key_does_not_shadow_the_progress_md_tab(self):
        self.write_progress("1_intake")
        tabs = review_server._tabs([self.doc_path, self.progress_path])
        # static/*.js resolve anchor.file with find(), so the first tab with a matching file wins.
        first_match = next(t for t in tabs if t["file"] == tabs[2]["file"])
        self.assertEqual(first_match["kind"], "md")

    def test_progress_tab_mtime_follows_the_newest_watched_file(self):
        self.write_progress("1_intake")
        tab = review_server._tabs([self.doc_path])[0]
        task_list = self.feature_dir / "Demo_TaskList.md"
        task_list.write_text(TASK_LIST_MD)
        future = self.progress_path.stat().st_mtime + 100
        os.utime(task_list, (future, future))
        self.assertEqual(review_server._tab_mtime(tab), future)

    def test_progress_tab_mtime_moves_with_the_pr_refresh_window(self):
        self.write_progress("1_intake")
        self.progress_path.write_text(self.progress_path.read_text() + "\n```yaml\n" + PULL_REQUESTS_YAML + "```\n")
        tab = review_server._tabs([self.doc_path])[0]
        real_window = pr_notes.refresh_window
        pr_notes.refresh_window = lambda: 10 ** 9  # a window far later than any watched file's mtime
        try:
            self.assertEqual(review_server._tab_mtime(tab), 10 ** 9 * pr_notes.REFRESH_SECONDS)
        finally:
            pr_notes.refresh_window = real_window

    def test_page_has_progress_panel(self):
        self.write_progress("1_intake")
        page = review_server.build_page([self.doc_path], live=False)
        self.assertIn('class="progress-view"', page)
        self.assertIn(">Progress</button>", page)


class PrNotesTests(unittest.TestCase):
    VIEW = {"number": 7, "title": "Add router", "url": "https://gh/pr/7", "state": "OPEN",
            "comments": [{"author": {"login": "ann"}, "createdAt": "2026-10-02T00:00:00Z", "body": "Looks good", "url": "u1"}],
            "reviews": [{"author": {"login": "bob"}, "submittedAt": "2026-10-01T00:00:00Z", "body": "Two nits", "state": "COMMENTED"},
                        {"author": {"login": "bob"}, "submittedAt": "2026-10-03T00:00:00Z", "body": "", "state": "APPROVED"}]}
    INLINE_PAGES = [[{"user": {"login": "cy"}, "created_at": "2026-10-01T12:00:00Z", "body": "Rename this",
                      "html_url": "u2", "path": "A.cs", "line": 12}]]

    def setUp(self):
        self._real_gh_json = pr_notes._gh_json
        pr_notes._cache.clear()
        pr_notes._repo_urls.clear()
        self.calls = 0

        def fake_gh_json(args, repo_dir):
            self.calls += 1
            return self.VIEW if args[0] == "pr" else self.INLINE_PAGES

        pr_notes._gh_json = fake_gh_json

    def tearDown(self):
        pr_notes._gh_json = self._real_gh_json
        pr_notes._cache.clear()
        pr_notes._repo_urls.clear()

    def test_pr_url_comes_from_the_github_origin_remote(self):
        remotes = {"/ssh": "git@github.com:acme/game.git\n", "/https": "https://github.com/acme/game\n",
                   "/other": "https://gitlab.com/acme/game.git\n"}
        with mock.patch.object(pr_notes.subprocess, "run",
                               side_effect=lambda args, cwd, **_: mock.Mock(returncode=0, stdout=remotes[cwd])):
            self.assertEqual(pr_notes.pr_url(5, Path("/ssh")), "https://github.com/acme/game/pull/5")
            self.assertEqual(pr_notes.pr_url(6, Path("/https")), "https://github.com/acme/game/pull/6")
            self.assertEqual(pr_notes.pr_url(7, Path("/other")), "")

    def test_notes_merge_comments_review_bodies_and_inline_comments_by_date(self):
        pr = pr_notes.fetch_pr_notes(7, Path("."))
        self.assertEqual((pr["title"], pr["state"], pr["error"]), ("Add router", "OPEN", ""))
        self.assertEqual([(n["kind"], n["author"], n["location"]) for n in pr["notes"]],
                         [("review", "bob", ""), ("inline", "cy", "A.cs:12"), ("comment", "ann", "")])  # empty review body dropped

    def test_fetch_is_cached_within_a_refresh_window(self):
        pr_notes.fetch_pr_notes(7, Path("."))
        pr_notes.fetch_pr_notes(7, Path("."))
        self.assertEqual(self.calls, 2)  # one pr view + one api call, not repeated

    def test_gh_failure_becomes_an_error_entry(self):
        def failing(args, repo_dir):
            raise ValueError("gh pr failed: not logged in")

        pr_notes._gh_json = failing
        pr = pr_notes.fetch_pr_notes(8, Path("."))
        self.assertEqual((pr["number"], pr["error"], pr["notes"]), (8, "gh pr failed: not logged in", []))


if __name__ == "__main__":
    unittest.main()
