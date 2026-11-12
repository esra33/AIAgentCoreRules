"""Run: python3 -m unittest discover -s Tools/feature-state/tests -p 'test_*.py'."""
import concurrent.futures
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feature_state import StateError, create_state, load_state, update_state
from legacy_migration import migrate_feature, parse_legacy_yaml


class FeatureStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "Feature"
        self.directory.mkdir()

    def test_stale_updates_leave_state_and_projection_unchanged(self):
        create_state(self.directory)
        update_state(self.directory, "checkpoint", {"checkpoint": {"next": "Review"}}, 1)
        projection = (self.directory / "Feature_Progress.md").read_text()
        with self.assertRaises(StateError):
            update_state(self.directory, "checkpoint", {"checkpoint": {"next": "Lost update"}}, 1)
        self.assertEqual(load_state(self.directory)["checkpoint"]["next"], "Review")
        self.assertEqual((self.directory / "Feature_Progress.md").read_text(), projection)

    def test_concurrent_writers_exactly_one_commits_same_revision(self):
        create_state(self.directory)
        def write(number):
            try:
                update_state(self.directory, "pr", {"phase": "V0", "number": number}, 1)
                return True
            except StateError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(write, range(1, 9)))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(load_state(self.directory)["revision"], 2)
        self.assertEqual(len(load_state(self.directory)["pull_requests"]["V0"]), 1)

    def test_complete_is_final_and_gate_requires_confirmation(self):
        create_state(self.directory)
        with self.assertRaises(StateError):
            update_state(self.directory, "gate", {"phase_completed": "Phase 1"}, 1)
        update_state(self.directory, "close", {"status": "complete", "reason": "Engineer approved"}, 1)
        with self.assertRaises(StateError):
            update_state(self.directory, "reopen", {}, 2)

    def test_gate_rejects_wrong_phase_and_skipped_next_phase(self):
        create_state(self.directory)
        for payload in ({"phase_completed": "Phase 2", "gate_confirmed_by": "Engineer", "next_phase": "3_design"},
                        {"phase_completed": "Phase 1", "gate_confirmed_by": "Engineer", "next_phase": "4_implementation"}):
            with self.assertRaises(StateError):
                update_state(self.directory, "gate", payload, 1)
        state = update_state(self.directory, "gate", {"phase_completed": "Phase 1", "gate_confirmed_by": "Engineer", "next_phase": "2_discovery"}, 1)
        self.assertEqual(state["current_phase"], "2_discovery")
        self.assertEqual(len(state["gates"]), 1)

    def test_artifact_escape_rejected_without_write(self):
        create_state(self.directory)
        with self.assertRaises(StateError):
            update_state(self.directory, "artifact", {"role": "gdd", "path": "../secret.md"}, 1)
        self.assertEqual(load_state(self.directory)["revision"], 1)

    def test_milestone_report_merges_by_label_and_registers_artifact(self):
        create_state(self.directory)
        state = update_state(self.directory, "milestone-report", {"label": "V0 Summary", "path": "Feature_V0Summary.md"}, 1)
        self.assertEqual(state["milestone_reports"], [{"label": "V0 Summary", "path": "Feature_V0Summary.md"}])
        self.assertIn("Feature_V0Summary.md", state["artifacts"])
        state = update_state(self.directory, "milestone-report", {"label": "V0 Summary", "path": "Feature_V0Summary2.md"}, state["revision"])
        self.assertEqual(state["milestone_reports"], [{"label": "V0 Summary", "path": "Feature_V0Summary2.md"}])
        with self.assertRaises(StateError):
            update_state(self.directory, "milestone-report", {"label": "", "path": "x.md"}, state["revision"])
        with self.assertRaises(StateError):
            update_state(self.directory, "milestone-report", {"label": "Escape", "path": "../secret.md"}, state["revision"])

    def test_missing_milestone_reports_key_loads_as_empty_list(self):
        create_state(self.directory)
        raw = json.loads((self.directory / "state.json").read_text())
        del raw["milestone_reports"]
        (self.directory / "state.json").write_text(json.dumps(raw))
        self.assertEqual(load_state(self.directory)["milestone_reports"], [])

    def legacy(self, extra=""):
        source = self.directory / "Feature_Progress.md"
        text = '''# Feature
```yaml
feature: "Feature"
current_phase: "1_intake"
status: "in_progress"
sessions: [session_12345678]
sources_of_truth:
  - https://example.com
  - {kind: confluence, id: "123", version: 2}
```
## Checkpoint
```yaml
  in_flight:
    - "Draft"
  next: "Review"
```
## Gates Passed
```yaml
phase_handoff:
  phase_completed: "Phase 1 — Intake"
  gate_confirmed_by: "Engineer"
```
## Custom notes
Keep me exactly.
''' + extra
        source.write_text(text)
        return source, text

    def test_migration_dry_run_preserves_unknown_sections_and_is_repeatable(self):
        source, text = self.legacy()
        self.assertEqual(migrate_feature(self.directory)["status"], "ready")
        self.assertFalse((self.directory / "state.json").exists())
        self.assertEqual(source.read_text(), text)
        self.assertEqual(migrate_feature(self.directory, True)["status"], "migrated")
        state = load_state(self.directory)
        self.assertEqual(state["checkpoint"]["in_flight"], ["Draft"])
        self.assertIn("Keep me exactly.", state["legacy_notes"][0])
        self.assertEqual((self.directory / "legacy-backup" / source.name).read_text(), text)
        update_state(self.directory, "checkpoint", {"checkpoint": {"next": "New work"}}, 1)
        self.assertEqual(migrate_feature(self.directory, True)["status"], "already_migrated")
        self.assertEqual(load_state(self.directory)["checkpoint"]["next"], "New work")

    def test_review_migration_disambiguates_ids_rebases_files_and_preserves_status(self):
        self.legacy()
        for name in ("Feature_TDD.md", "Feature_GDD.md"):
            (self.directory / (name + ".review.json")).write_text(json.dumps({"threads": [{
                "id": "t1", "status": "addressed", "anchor": {"kind": "text", "file": name, "quote": "word"},
                "replies": [{"text": "Feedback", "author": "engineer"}]}]}))
        migrate_feature(self.directory, True)
        reviews = json.loads((self.directory / "review.json").read_text())
        self.assertEqual([thread["id"] for thread in reviews["threads"]], ["t1", "t2"])
        self.assertEqual({thread["anchor"]["file"] for thread in reviews["threads"]}, {"Feature_TDD.md", "Feature_GDD.md"})
        self.assertTrue(all(thread["status"] == "addressed" for thread in reviews["threads"]))
        self.assertTrue(all(thread["migration_origin"]["id"] == "t1" for thread in reviews["threads"]))

    def test_unsupported_legacy_syntax_blocks_all_writes(self):
        self.legacy()
        source = self.directory / "Feature_Progress.md"
        source.write_text(source.read_text().replace('next: "Review"', 'next: |\n    ambiguous'))
        self.assertEqual(migrate_feature(self.directory, True)["status"], "blocked")
        self.assertFalse((self.directory / "state.json").exists())
        self.assertFalse((self.directory / "legacy-backup").exists())

    def test_tdd_status_conflict_blocks_migration(self):
        self.legacy()
        (self.directory / "Feature_TaskList.md").write_text('- {id: T1, status: "[ ]", title: "Build"}\n')
        (self.directory / "Feature_TDD.md").write_text('| T1 | Build | Description | Andrea | [x] |\n')
        report = migrate_feature(self.directory, True)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("conflicts", report["errors"][0])
        self.assertFalse((self.directory / "state.json").exists())

    def test_numeric_task_list_ids_import_as_t_ids(self):
        self.legacy()
        (self.directory / "Feature_TaskList.md").write_text(
            '    - {id: 1,  status: "[x]", task: "Build"}\n    - {id: 12, status: "[ ]", task: "Wrap in #if !RC"}\n')
        self.assertEqual(migrate_feature(self.directory, True)["status"], "migrated")
        tasks = load_state(self.directory)["tasks"]
        self.assertEqual([(task["id"], task["status"]) for task in tasks], [("T1", "done"), ("T12", "todo")])
        self.assertEqual(tasks[1]["task"], "Wrap in #if !RC")

    def test_apply_rejects_sources_changed_since_dryrun(self):
        source, text = self.legacy()
        report = migrate_feature(self.directory)
        source.write_text(text + "\nNew context\n")
        applied = migrate_feature(self.directory, True, report["fingerprint"])
        self.assertEqual(applied["status"], "blocked")
        self.assertFalse((self.directory / "state.json").exists())

    def test_migration_refuses_differing_existing_backup(self):
        source, _ = self.legacy()
        backup = self.directory / "legacy-backup"
        backup.mkdir()
        (backup / source.name).write_text("Earlier original")
        self.assertEqual(migrate_feature(self.directory, True)["status"], "blocked")
        self.assertEqual((backup / source.name).read_text(), "Earlier original")
        self.assertFalse((self.directory / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
