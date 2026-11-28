import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))
from diagram import parse
import generator


class GenerateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "Example"
        nested = self.source / "nested"
        nested.mkdir(parents=True)
        (self.source / "Main.cs").write_text("""
namespace One
{
    interface IParent {}
    interface IChild : IParent {}
    class Base {}
    class Item {}
    class Wrapper<T> {}
    partial class Service : Base, IChild {
        Item field;
        global::Two.Item Other { get; }
        public Wrapper<Two.Item> Convert(Item item, Base optional = null) => null;
        public T Echo<T>(T value) => value;
    }
    class T {}
}
""")
        (nested / "More.cs").write_text("""
namespace One
{
    partial class Service {
        Item More { get; }
        Missing External { get; }
    }
}
namespace Two { class Item {} }
namespace Three { class Ambiguous { Item Value; } }
""")
        (nested / "Ignored.txt").write_text("class Ignored {}")

    def run_cli(self, source, output):
        return subprocess.run(
            ["bash", str(TOOL / "mermaid-graph.sh"), "generate", str(source), str(output)],
            capture_output=True, text=True, env={**os.environ, "TZ": "Pacific/Honolulu"},
        )

    def test_explicit_output_and_collision(self):
        path = self.root / "diagram.custom"
        result = self.run_cli(self.source, path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(path))
        original = path.read_bytes()
        collision = self.run_cli(self.source, path)
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("already exists", collision.stderr)
        self.assertEqual(path.read_bytes(), original)

    def test_directory_output_uses_utc_date(self):
        with patch.object(generator, "datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 11, 27, 0, 15, tzinfo=timezone.utc)
            path = generator.generate(self.source / "nested" / "..", self.root)
            clock.now.assert_called_once_with(timezone.utc)
        self.assertEqual(path, self.root / "Example_27_11_26.mmd")
        self.assertTrue(path.is_file())

    def test_nodes_members_and_relationships(self):
        path = generator.generate(self.source, self.root / "diagram.mmd")
        graph = parse(path.read_text())
        self.assertEqual(graph["diagnostics"], [])
        nodes = {node["name"]: node for node in graph["classes"]}
        self.assertEqual(set(nodes), {
            "IParent", "IChild", "Base", "One_Item", "Two_Item", "Service",
            "Ambiguous", "T", "Wrapper_1",
        })
        self.assertEqual(nodes["IChild"]["kind"], "interface")
        service = nodes["Service"]
        self.assertEqual(len(service["declarations"]), 1)
        members = {member["text"] for member in service["members"]}
        self.assertIn("Item field", members)
        self.assertIn("Item More", members)
        self.assertIn("public Wrapper<Two.Item> Convert(Item item, Base optional = null)", members)
        edges = {(e["left"], e["arrow"], e["right"]) for e in graph["relationships"]}
        self.assertEqual(edges, {
            ("IChild", "--|>", "IParent"), ("Service", "--|>", "Base"),
            ("Service", "..|>", "IChild"), ("Service", "o--", "One_Item"),
            ("Service", "o--", "Two_Item"), ("Service", "..>", "One_Item"),
            ("Service", "..>", "Two_Item"), ("Service", "..>", "Wrapper_1"),
            ("Service", "..>", "Base"),
        })
        second = generator.generate(self.source, self.root / "second.mmd")
        self.assertEqual(path.read_bytes(), second.read_bytes())

    def test_invalid_source_missing_parent_and_unreadable_source(self):
        output = self.root / "diagram.mmd"
        missing = self.root / "missing"
        empty = self.root / "empty"
        empty.mkdir()
        bad = empty / "Invalid.cs"
        for source, path, message in (
            (missing, output, "Expected a C# source directory"),
            (self.source, missing / "diagram.mmd", "Output parent directory"),
            (empty, output, "No supported C# type declarations"),
        ):
            with self.subTest(message=message):
                result = self.run_cli(source, path)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(path.exists())
        bad.write_bytes(b"\xff")
        result = self.run_cli(empty, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"Cannot read C# source {bad}", result.stderr)
        self.assertFalse(output.exists())

    def test_create_blank_diagram(self):
        command = ["bash", str(TOOL / "mermaid-graph.sh"), "create"]
        created = subprocess.run([*command, str(self.source)], capture_output=True, text=True)
        self.assertEqual(created.returncode, 0, created.stderr)
        path = Path(created.stdout.strip())
        self.assertEqual(path.parent, self.source)
        self.assertRegex(path.name, r"^Example_\d{2}_\d{2}_\d{2}\.mmd$")
        self.assertEqual(path.read_text(), "classDiagram\n")
        self.assertEqual(parse(path.read_text())["diagnostics"], [])

        path.write_text("classDiagram\nclass Saved\n")
        collision = subprocess.run([*command, str(self.source)], capture_output=True, text=True)
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("already exists", collision.stderr)
        self.assertEqual(path.read_text(), "classDiagram\nclass Saved\n")

        for destination in (self.root / "missing", path):
            invalid = subprocess.run([*command, str(destination)], capture_output=True, text=True)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("Expected an existing destination directory", invalid.stderr)
