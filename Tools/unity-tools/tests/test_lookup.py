"""Lookup features that let codeindex / usages replace grep: declaration end lines, type
signatures, attributes, member lookup in `where`, `show`, `members --inherited`, `attributed`,
and usages' per-line references. Parser tests run on strings; CLI tests on a tiny synthetic
Unity project like test_smoke's."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR))
from _csparse import SourceParser  # noqa: E402

PARSED = """[assembly: InternalsVisibleTo("Tests")]
namespace Demo
{
    [Serializable]
    [JsonObject(MemberSerialization.OptIn), Obsolete("a]b")]
    public sealed class Foo : Bar,
        IBaz<int>
    {
        [SerializeField] private int _x;
        [JsonProperty("y")]
        public int Y { get; set; }
        public void Run(int a,
                        int b)
        {
            if (a > b)
            {
            }
        }
        public int Z => _x;
        private readonly List<int> _l = new List<int>
        {
            1, 2
        };
    }

    public enum Mode
    {
        [Description("first")] First,
        Second
    }
}
"""

CSPROJ = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup>
    <Compile Include="Assets\\Scripts\\Shapes.cs" />
    <Compile Include="Assets\\Scripts\\User.cs" />
  </ItemGroup>
</Project>
"""

LONG_PARAMS = ", ".join("int parameterNumber%d" % n for n in range(8))

SHAPES = """namespace Demo
{
    public interface IShape
    {
        float Area();
        string Name { get; }
    }

    public abstract class ShapeBase : IShape
    {
        public abstract float Area();
        public string Name => GetType().Name;
        protected void Log() { }
    }

    [Debuggable(alias = "circle")]
    public class Circle : ShapeBase, UnityEngine.MonoBehaviour
    {
        [SerializeField] private float _radius;

        public override float Area()
        {
            return 3.14f * _radius * _radius;
        }

        public void Resize(%s)
        {
        }
    }
}
""" % LONG_PARAMS

USER = """namespace Demo
{
    public class User
    {
        private readonly IShape _shape = new Circle();

        public float Measure()
        {
            return _shape.Area();
        }

        public string Label()
        {
            return _shape.Name;
        }
    }
}
"""


def run(script, root, *args):
    return subprocess.run([sys.executable, str(TOOL_DIR / script), "--project", str(root), *args],
                          capture_output=True, text=True, timeout=120)


class ParserTests(unittest.TestCase):
    def setUp(self):
        types = SourceParser().parse("Foo.cs", PARSED)
        self.types = {t.name: t for t in types}
        self.foo = self.types["Foo"]
        self.members = {m.name: m for m in self.foo.members}

    def test_type_spans_its_body_and_keeps_a_multi_line_header_as_signature(self):
        self.assertEqual((self.foo.line, self.foo.end_line), (6, 24))
        self.assertEqual(self.foo.signature, "public sealed class Foo : Bar, IBaz<int>")

    def test_member_end_lines(self):
        spans = {name: (m.line, m.end_line) for name, m in self.members.items()}
        self.assertEqual(spans["_x"], (9, 9))
        self.assertEqual(spans["Y"], (11, 11))
        self.assertEqual(spans["Run"], (12, 18))
        self.assertEqual(spans["Z"], (19, 19))
        self.assertEqual(spans["_l"], (20, 23))

    def test_attribute_lines_attach_to_the_next_declaration(self):
        self.assertEqual([name for name, _ in self.foo.attributes],
                         ["Serializable", "JsonObject", "Obsolete"])
        self.assertIn(("Obsolete", 'Obsolete("a]b")'), self.foo.attributes)
        self.assertEqual(self.members["Y"].attributes, [("JsonProperty", 'JsonProperty("y")')])
        self.assertEqual(self.members["Run"].attributes, [])

    def test_inline_attributes_do_not_hide_the_declaration(self):
        self.assertEqual(self.members["_x"].kind, "field")
        self.assertEqual(self.members["_x"].attributes, [("SerializeField", "SerializeField")])
        first = self.types["Mode"].members[0]
        self.assertEqual((first.name, first.attributes),
                         ("First", [("Description", 'Description("first")')]))

    def test_inline_attribute_on_a_type_line(self):
        types = SourceParser().parse("A.cs", "namespace N\n{\n    [Serializable] public class A\n    {\n    }\n}\n")
        self.assertEqual([(t.name, t.attributes, t.end_line) for t in types],
                         [("A", [("Serializable", "Serializable")], 5)])

    def test_assembly_attributes_attach_to_nothing(self):
        for t in self.types.values():
            self.assertNotIn("InternalsVisibleTo", [name for name, _ in t.attributes])


class LookupCliTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="unity-tools-lookup-"))
        (self.root / "ProjectSettings").mkdir()
        (self.root / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 2022.3.10f1\n")
        scripts = self.root / "Assets" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "Shapes.cs").write_text(SHAPES)
        (scripts / "User.cs").write_text(USER)
        (self.root / "Assembly-CSharp.csproj").write_text(CSPROJ)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def ok(self, script, *args):
        result = run(script, self.root, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_where_prints_span_and_full_signature(self):
        out = self.ok("codeindex.py", "where", "Circle")
        self.assertIn("Assets/Scripts/Shapes.cs:17-29", out)
        self.assertIn("public class Circle : ShapeBase, UnityEngine.MonoBehaviour", out)

    def test_where_finds_members_and_type_dot_member(self):
        out = self.ok("codeindex.py", "where", "Area")
        for owner in ("IShape.Area", "ShapeBase.Area", "Circle.Area"):
            self.assertIn(owner, out)
        out = self.ok("codeindex.py", "where", "Circle.Area")
        self.assertIn("Shapes.cs:21-24", out)
        self.assertNotIn("IShape.Area", out)

    def test_long_signature_is_not_truncated(self):
        out = self.ok("codeindex.py", "members", "Circle")
        self.assertIn("int parameterNumber7)", out)
        out = self.ok("codeindex.py", "where", "Resize")
        self.assertIn("int parameterNumber7)", out)

    def test_show_prints_only_the_slice(self):
        out = self.ok("codeindex.py", "show", "Circle.Area")
        self.assertIn("21  ", out)
        self.assertIn("return 3.14f", out)
        self.assertNotIn("Resize", out)
        out = self.ok("codeindex.py", "show", "Circle")
        self.assertIn("[Debuggable", out)          # leading attributes come with the type
        self.assertIn("Resize", out)
        self.assertNotIn("interface IShape", out)

    def test_members_inherited_walks_classes_and_interfaces(self):
        out = self.ok("codeindex.py", "members", "Circle", "--inherited")
        self.assertIn("from ShapeBase", out)
        self.assertIn("from IShape", out)
        self.assertIn("Log", out)
        self.assertIn("not indexed: MonoBehaviour", out)

    def test_attributed_finds_types_and_members_in_either_spelling(self):
        out = self.ok("codeindex.py", "attributed", "Debuggable")
        self.assertIn("Circle", out)
        out = self.ok("codeindex.py", "attributed", "SerializeFieldAttribute")
        self.assertIn("Circle._radius", out)

    def test_usages_prints_reference_lines(self):
        out = self.ok("usages.py", "IShape")
        self.assertIn("Assets/Scripts/User.cs:5:", out)
        self.assertIn("private readonly IShape _shape", out)

    def test_usages_accepts_a_member_and_type_dot_member(self):
        out = self.ok("usages.py", "Area")
        self.assertIn("Assets/Scripts/User.cs:9:", out)
        self.assertIn("Shapes.cs:5", out)                  # declaration, from the index
        out = self.ok("usages.py", "Circle.Area")
        self.assertIn("Shapes.cs:21", out)
        self.assertNotIn("Shapes.cs:5:", out)

    def test_usages_caps_reference_lines(self):
        out = self.ok("usages.py", "_shape", "--limit", "1")
        self.assertIn("more", out)
        out = self.ok("usages.py", "_shape", "--full")
        self.assertNotIn("more", out)


if __name__ == "__main__":
    unittest.main()
