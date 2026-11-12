"""Smoke tests: every script starts from this folder, and codeindex / usages answer on a tiny
synthetic Unity project (ProjectVersion.txt + one generated-style .csproj). typecheck and
unitysource need an installed Unity editor, so only their --help is covered here."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = ["codeindex.py", "usages.py", "typecheck.py", "unitysource.py", "cslint.py"]

CSPROJ = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup>
    <DefineConstants>UNITY_EDITOR</DefineConstants>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="Assets\\Scripts\\Thing.cs" />
    <Compile Include="Assets\\Scripts\\Caller.cs" />
  </ItemGroup>
</Project>
"""

THING = """namespace Demo
{
    public interface IThing
    {
        void Run();
    }

    public class Thing : IThing
    {
        public void Run()
        {
        }
    }
}
"""

CALLER = """namespace Demo
{
    public class Caller
    {
        private readonly IThing _thing = new Thing();

        public void Go()
        {
            _thing.Run();
        }
    }
}
"""


def run(script, *args):
    return subprocess.run([sys.executable, str(TOOL_DIR / script), *args],
                          capture_output=True, text=True, timeout=120)


class HelpTests(unittest.TestCase):
    def test_every_script_starts(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                result = run(script, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)


class FakeProjectTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="unity-tools-test-"))
        (self.root / "ProjectSettings").mkdir()
        (self.root / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 2022.3.10f1\n")
        scripts = self.root / "Assets" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "Thing.cs").write_text(THING)
        (scripts / "Caller.cs").write_text(CALLER)
        (self.root / "Assembly-CSharp.csproj").write_text(CSPROJ)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_codeindex_finds_implementer(self):
        result = run("codeindex.py", "--project", str(self.root), "implementers", "IThing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Thing", result.stdout)
        self.assertTrue((self.root / "Library" / "codeindex.sqlite").is_file())

    def test_codeindex_stays_fresh_with_symlinked_folder_outside_root(self):
        # A folder symlinked into Assets/ from outside the project is stored as ../X.cs;
        # it must not be removed and re-added on every refresh.
        outside = Path(tempfile.mkdtemp(prefix="unity-tools-ext-"))
        self.addCleanup(shutil.rmtree, outside, True)
        (outside / "Linked.cs").write_text("namespace Demo\n{\n    public class Linked\n    {\n    }\n}\n")
        (self.root / "Assets" / "Ext").symlink_to(outside, target_is_directory=True)
        csproj = CSPROJ.replace('<Compile Include="Assets\\Scripts\\Caller.cs" />',
                                '<Compile Include="Assets\\Scripts\\Caller.cs" />\n'
                                '    <Compile Include="Assets\\Ext\\Linked.cs" />')
        self.assertIn("Linked.cs", csproj)
        (self.root / "Assembly-CSharp.csproj").write_text(csproj)

        first = run("codeindex.py", "--project", str(self.root), "where", "Linked")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Linked", first.stdout)
        second = run("codeindex.py", "--project", str(self.root), "where", "Linked")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotIn("index refreshed", second.stdout + second.stderr)

    def test_asmdef_reference_missing_from_csproj_is_reported(self):
        sys.path.insert(0, str(TOOL_DIR))
        from _unityproj import Project

        lib = self.root / "Assets" / "Lib"
        lib.mkdir()
        (lib / "Lib.asmdef").write_text('{"name": "Lib"}')
        (lib / "Lib.asmdef.meta").write_text("fileFormatVersion: 2\nguid: ABC123\n")
        user = self.root / "Assets" / "User"
        user.mkdir()
        (user / "User.asmdef").write_text('{"name": "User", "references": ["GUID:abc123"]}')
        empty = CSPROJ.replace("Assets\\Scripts", "Assets\\None")
        (self.root / "Lib.csproj").write_text(empty)
        (self.root / "User.csproj").write_text(empty)

        # Edited before the last project sync: an orphaned .csproj, not a pending reference.
        os.utime(user / "User.asmdef", (1, 1))
        self.assertEqual(Project(str(self.root)).missing_asmdef_references(), [])

        # Edited after the last sync: Unity has not added the reference yet.
        os.utime(user / "User.asmdef", (time.time() + 60, time.time() + 60))
        self.assertEqual(Project(str(self.root)).missing_asmdef_references(), [("User", "Lib")])

        listed = empty.replace("</Project>", '  <ItemGroup>\n    <ProjectReference Include="Lib.csproj" />\n'
                                             "  </ItemGroup>\n</Project>")
        (self.root / "User.csproj").write_text(listed)
        self.assertEqual(Project(str(self.root)).missing_asmdef_references(), [])

    def test_worktree_asmdef_reference_missing_from_main_csproj_is_reported(self):
        sys.path.insert(0, str(TOOL_DIR))
        from _unityproj import Project

        main = self.root
        worktree = Path(tempfile.mkdtemp(prefix="unity-tools-wt-"))
        self.addCleanup(shutil.rmtree, worktree, True)
        for checkout in (main, worktree):
            lib = checkout / "Assets" / "Lib"
            lib.mkdir(parents=True)
            (lib / "Lib.asmdef").write_text('{"name": "Lib"}')
            (lib / "Lib.asmdef.meta").write_text("guid: abc123\n")
            (checkout / "Assets" / "User").mkdir()
            (checkout / "Assets" / "User" / "User.asmdef").write_text('{"name": "User"}')
        os.utime(main / "Assets" / "User" / "User.asmdef", (1, 1))
        empty = CSPROJ.replace("Assets\\Scripts", "Assets\\None")
        (main / "Lib.csproj").write_text(empty)
        (main / "User.csproj").write_text(empty)

        # Fresh worktree files are newer than every .csproj, but match the main checkout.
        self.assertEqual(Project(str(worktree), str(main)).missing_asmdef_references(), [])

        (worktree / "Assets" / "User" / "User.asmdef").write_text(
            '{"name": "User", "references": ["GUID:abc123"]}')
        self.assertEqual(Project(str(worktree), str(main)).missing_asmdef_references(),
                         [("User", "Lib")])

    def test_usages_finds_member_call(self):
        result = run("usages.py", "--project", str(self.root), "IThing", "--members", "Run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Caller.cs", result.stdout)


if __name__ == "__main__":
    unittest.main()
