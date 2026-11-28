import json
from pathlib import Path
import subprocess
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1]


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = self.root / "Assets"
        self.assets.mkdir()
        (self.root / "ProjectSettings").mkdir()
        self.diagram = self.root / "Design.mmd"
        self.output = self.assets / "Feature"

    def run_scaffold(self, source, *flags, success=True):
        self.diagram.write_text("classDiagram\n" + source)
        result = subprocess.run(
            ["bash", str(TOOL / "mermaid-graph.sh"), "scaffold", str(self.diagram),
             str(self.output), "--namespace", "Game.Feature", *flags],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
        return result.stdout if success else result.stderr

    def test_preview_apply_rerun(self):
        contracts = self.assets / "Contracts"
        contracts.mkdir()
        (contracts / "Contracts.asmdef").write_text('{"name":"Game.Contracts"}')
        (contracts / "Contract.cs").write_text("""
namespace Game.Contracts {
    public interface ISave { bool Save(State state); }
    public abstract class Base { protected abstract void Reset(); }
    public class State {}
}
""")
        graph = """
class ISave
class Base
class State
class Service {
    +Save(State state) bool
    +Reset()
}
Base <|-- Service
Service ..|> ISave
State "0..*" --* Service : states
Service ..> State
"""
        flags = ("--asmdef", "Game.Feature")
        preview = self.run_scaffold(graph, *flags)
        self.assertIn("Would create", preview)
        self.assertIn("Manual dependency", preview)
        self.assertFalse(self.output.exists())
        self.run_scaffold(graph, *flags, "--apply")
        cs = (self.output / "Service.cs").read_text()
        self.assertIn("protected override void Reset()", cs)
        self.assertIn("List<global::Game.Contracts.State> states = new", cs)
        self.assertIn("throw new global::System.NotImplementedException();", cs)
        asmdef = json.loads((self.output / "Game.Feature.asmdef").read_text())
        self.assertEqual(asmdef["references"], ["Game.Contracts"])
        self.assertIn("No files to generate", self.run_scaffold(graph, *flags, "--apply"))

    def test_reports_existing_gap_and_creates_new_type(self):
        existing = self.assets / "Existing.cs"
        existing.write_text("public class Existing {}")
        report = self.run_scaffold("Existing : +Add()\nExisting --> NewType\n", "--apply")
        self.assertIn("Check member", report)
        self.assertIn("Missing association", report)
        self.assertEqual(existing.read_text(), "public class Existing {}")
        self.assertTrue((self.output / "NewType.cs").exists())

    def test_ambiguous_and_collision(self):
        (self.assets / "A.cs").write_text("namespace A { public class Shared {} }")
        (self.assets / "B.cs").write_text("namespace B { public class Shared {} }")
        self.assertIn("Ambiguous type Shared", self.run_scaffold(
            "class Shared\nclass NewType\n", "--apply", success=False))
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        (self.output / "newtype.CS").write_text("reserved")
        self.assertIn("filename collision", self.run_scaffold(
            "class Other\nclass NewType\n", "--apply", success=False))
        self.assertEqual([path.name for path in self.output.iterdir()], ["newtype.CS"])


if __name__ == "__main__":
    unittest.main()
