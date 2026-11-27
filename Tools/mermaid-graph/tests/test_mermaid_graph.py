import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagram import ARROWS, edit, parse
import launcher
from server import Conflict, replace, snapshot


class DiagramTests(unittest.TestCase):
    def test_node_annotations_survive_visual_edits(self):
        source = ("classDiagram\r\nclass Plain\r\nclass Contract {\r\n"
                  "    <<interface>>\r\n    +run()\r\n}\r\n"
                  "<<enumeration>> Color\r\nPlain --> Color\r\n")
        source = edit(source, {"action": "addClass", "newName": "Point", "kind": "struct"})
        source = edit(source, {"action": "renameClass", "name": "Color", "newName": "Shade"})
        source = edit(source, {"action": "addRelationship", "left": "Point", "right": "Contract", "arrow": "..|>"})
        graph = parse(source)
        self.assertFalse(graph["diagnostics"])
        self.assertEqual({record["name"]: record["kind"] for record in graph["classes"]},
                         {"Plain": "class", "Contract": "interface", "Shade": "enum", "Point": "struct"})
        self.assertIn("<<enumeration>> Shade\r\nPlain --> Shade\r\n", source)
        self.assertTrue(source.endswith("class Point {\r\n    <<struct>>\r\n}\r\nPoint ..|> Contract\r\n"))
        self.assertNotIn("Shade", edit(source, {"action": "deleteClass", "name": "Shade"}))

    def test_rename_and_delete_touch_only_related_source(self):
        source = ("classDiagram\r\n  class A {\r\n    %% keep this\r\n"
                  "    +run()\r\n  }\r\n  A : +count\r\n"
                  '  A "1" *-- "0..*" B : uses A\r\n  A ..> A\r\n'
                  "  class Other")
        graph = parse(source)
        self.assertEqual(graph["diagnostics"], [])
        self.assertEqual(graph["classes"][0]["declarations"], [{"startLine": 2, "endLine": 5}])
        renamed = edit(source, {"action": "renameClass", "name": "A", "newName": "Service"})
        expected = (source.replace("class A", "class Service").replace("  A :", "  Service :")
                    .replace('  A "1"', '  Service "1"').replace("A ..> A", "Service ..> Service"))
        self.assertEqual(renamed, expected)
        self.assertEqual(edit(renamed, {"action": "deleteClass", "name": "Service"}),
                         "classDiagram\r\n    %% keep this\r\n  class Other")

    def test_all_arrows_and_unsafe_statements(self):
        source = "classDiagram\n" + "".join(f"A {arrow} B\n" for arrow in ARROWS)
        self.assertEqual([(edge["kind"], edge["direction"]) for edge in parse(source)["relationships"]],
                         list(ARROWS.values()))
        for syntax in ('namespace Feature {', 'class A["Title"]', 'accTitle: diagram', 'A --> B %% comment',
                       'A --> B : first; B --> C'):
            with self.subTest(syntax=syntax):
                draft = source + syntax
                self.assertTrue(parse(draft)["diagnostics"])
                with self.assertRaisesRegex(ValueError, "Visual edits are disabled"):
                    edit(draft, {"action": "deleteClass", "name": "A"})

    def test_external_change_between_snapshot_and_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.mmd"
            path.write_text("classDiagram\nclass A\n")
            revision = snapshot(path)[1]
            fsync = os.fsync

            def change_on_disk(descriptor):
                fsync(descriptor)
                path.write_text("classDiagram\nclass External\n")

            with patch("server.os.fsync", side_effect=change_on_disk):
                with self.assertRaises(Conflict):
                    replace(path, "classDiagram\nclass Draft\n", revision)
            self.assertEqual(path.read_text(), "classDiagram\nclass External\n")
            self.assertEqual(list(path.parent.iterdir()), [path])


class EditorIntegrationTests(unittest.TestCase):
    def test_save_conflict_and_independent_servers(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, "home", return_value=Path(directory)):
            folder = Path(directory)
            original = ("classDiagram\r\n  %% retained\r\n  class A {\r\n    +run()\r\n  }\r\n"
                        "  A --> B : old label\r\n  B ..> C\r\n")
            first, second = folder / "first.mmd", folder / "second.mmd"
            first.write_bytes(original.encode())
            second.write_text("classDiagram\nclass Second\n")
            alias = folder / "alias.mmd"
            alias.symlink_to(first)
            children = []
            popen = subprocess.Popen

            def track_process(*args, **kwargs):
                child = popen(*args, **kwargs)
                children.append(child)
                return child

            def control(action, target=None):
                with (contextlib.redirect_stdout(io.StringIO()) as output,
                      patch.object(launcher.subprocess, "Popen", side_effect=track_process)):
                    launcher.control(action, target)
                return output.getvalue().strip()

            def request(url, endpoint="diagram", method="GET", payload=None, origin=None):
                headers = {}
                if payload is not None:
                    headers = {"Content-Type": "application/json", "X-Mermaid-Editor": "1",
                               "Origin": origin or url.rstrip("/")}
                body = json.dumps(payload).encode() if payload is not None else None
                with launcher.OPENER.open(Request(url + "api/" + endpoint, body, headers, method=method), timeout=2) as response:
                    return json.load(response)

            active = []
            try:
                url = control("start", str(first))
                active.append(url)
                other_url = control("start", str(second))
                active.append(other_url)
                self.assertNotEqual(url, other_url)
                self.assertEqual(control("start", str(alias)), url)
                pid = request(url, "health")["pid"]
                listing = control("list")
                self.assertIn(f"pid {pid}  {url}  {first.resolve()}", listing)
                self.assertIn(f"{other_url}  {second.resolve()}", listing)

                document = request(url)
                draft = document["source"]
                edits = [
                    {"action": "addClass", "newName": "Extra"},
                    {"action": "renameClass", "name": "A", "newName": "Service"},
                    {"action": "editRelationship", "line": 6, "left": "Service", "right": "Extra",
                     "arrow": "--o", "leftMultiplicity": "0..*", "rightMultiplicity": "1", "label": "new label"},
                    {"action": "deleteRelationship", "line": 7},
                ]
                for change in edits:
                    draft = request(url, "edit", "POST", {"source": draft, "change": change})["source"]
                draft = draft.replace("+run()", "+runAgain()")
                expected = ("classDiagram\r\n  %% retained\r\n  class Service {\r\n    +runAgain()\r\n  }\r\n"
                            '  Service "0..*" --o "1" Extra : new label\r\nclass Extra\r\n')
                self.assertEqual(draft, expected)
                payload = {"source": draft, "revision": document["revision"]}
                with self.assertRaises(HTTPError) as rejected:
                    request(url, "diagram", "PUT", payload, origin="https://example.invalid")
                with rejected.exception as response:
                    self.assertEqual(response.code, 403)
                self.assertEqual(first.read_bytes(), original.encode())
                saved = request(url, "diagram", "PUT", payload)
                reopened = request(url)
                self.assertEqual(reopened["revision"], saved["revision"])
                self.assertEqual(reopened["source"], expected)
                self.assertEqual(first.read_bytes(), expected.encode())
                first.write_bytes((expected + "%% external\r\n").encode())
                with self.assertRaises(HTTPError) as conflict:
                    request(url, "diagram", "PUT", {"source": draft + "class Draft", "revision": saved["revision"]})
                with conflict.exception as response:
                    self.assertEqual(response.code, 409)
                self.assertTrue(first.read_bytes().endswith(b"%% external\r\n"))

                control("stop", str(pid))
                active.remove(url)
                self.assertEqual(request(other_url)["classes"][0]["name"], "Second")
                registry = folder / ".mermaid-graph" / "servers.json"
                entries = json.loads(registry.read_text())
                entries[str(first.resolve())] = {"file": str(first.resolve()), "url": other_url, "pid": pid,
                                                  "instance": "stale"}
                registry.write_text(json.dumps(entries))
                self.assertNotIn(str(first.resolve()), control("list"))
                self.assertNotIn(str(first.resolve()), json.loads(registry.read_text()))
            finally:
                for address in active:
                    control("stop", address)
                for child in children:
                    child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
