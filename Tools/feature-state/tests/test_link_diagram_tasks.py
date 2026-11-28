"""End-to-end example for linking TDD tasks to a preview class node."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS / "feature-state"))
sys.path.insert(0, str(TOOLS / "doc-review"))
from feature_state import create_state, load_state  # noqa: E402
from project_server import diagram_progress  # noqa: E402


class LinkDiagramTasksTests(unittest.TestCase):
    def test_two_tasks_show_fifty_percent_without_changing_diagram(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "Example"
            directory.mkdir()
            state = create_state(directory)
            state["artifact_roles"] = {
                "tdd": "Example_TDD.md",
                "concrete_class_diagram": "Architecture.mmd",
            }
            state["tasks"] = [
                {"id": "T1", "title": "Implement", "status": "done"},
                {"id": "T2", "title": "Verify", "status": "todo"},
            ]
            (directory / "state.json").write_text(json.dumps(state))
            (directory / "Example_TDD.md").write_text(
                "| Task | Files | Status |\n| --- | --- | --- |\n"
                "| T1 | Implement `Engine.cs` | done |\n"
                "| T2 | Verify `Engine.cs` | todo |\n"
            )
            diagram = directory / "Architecture.mmd"
            original = "classDiagram\nclass Engine\n"
            diagram.write_text(original)
            command = [sys.executable, "-B", str(TOOLS / "link-diagram-tasks" / "link_diagram_tasks.py"), str(directory)]
            dry = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(dry.stdout, "T1  concrete_class_diagram  Engine\nT2  concrete_class_diagram  Engine\nDry run. Use --apply to update 2 tasks.\n")
            self.assertNotIn("diagram_nodes", (directory / "state.json").read_text())
            applied = subprocess.run(command + ["--apply"], capture_output=True, text=True, check=True)
            self.assertIn("Updated 2 tasks.", applied.stdout)
            result = load_state(directory)
            self.assertEqual([task["status"] for task in result["tasks"]], ["done", "todo"])
            self.assertEqual([task["diagram_nodes"] for task in result["tasks"]],
                             [{"concrete_class_diagram": ["Engine"]}] * 2)
            counts = diagram_progress(result, [{"id": "diagram", "kind": "mmd", "role": "concrete_class_diagram"}])
            self.assertEqual(counts["diagram"]["Engine"]["done"], 1)
            self.assertEqual(counts["diagram"]["Engine"]["total"], 2)
            self.assertEqual(round(100 * counts["diagram"]["Engine"]["done"] /
                                   counts["diagram"]["Engine"]["total"]), 50)
            self.assertEqual(diagram.read_text(), original)


if __name__ == "__main__":
    unittest.main()
