"""Integration checks for first-install host metadata placement."""

import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


INSTALLER = Path(__file__).with_name("install.py")
CORE_ROOT = INSTALLER.parents[2]


class MetadataInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.externals = self.root / "GitIgnoreExternals"
        self.externals.mkdir()
        (self.externals / "AIAgentCoreRules").symlink_to(CORE_ROOT, target_is_directory=True)

    def run_install(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(INSTALLER), "--project", str(self.root), *args],
            capture_output=True, text=True,
        )

    def test_project_location_creates_committable_metadata_and_wires_agents(self):
        result = self.run_install("install", "--agent", "both", "--metadata-location", "project")
        self.assertEqual(result.returncode, 0, result.stderr)
        host = self.root / "AIMetaData"
        self.assertTrue((host / "Rules/ProjectRules.md").is_file())
        self.assertTrue((host / "SystemIndex.md").is_file())
        self.assertIn("@AIMetaData/SystemIndex.md", (self.root / "CLAUDE.md").read_text())
        self.assertIn("AIMetaData/SystemIndex.md", (self.root / "AGENTS.md").read_text())
        self.assertIn("AIMetaData/", subprocess.run(
            ["git", "status", "--short", "--untracked-files=normal"], cwd=self.root,
            capture_output=True, text=True, check=True,
        ).stdout)
        settings = json.loads((self.root / ".claude/settings.json").read_text())
        self.assertIn("GitIgnoreExternals", settings["worktree"]["symlinkDirectories"])
        self.assertEqual(self.run_install("install", "--agent", "both").returncode, 0)

    def test_externals_location_and_check_preview(self):
        preview = self.run_install("check", "--metadata-location", "externals")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("GitIgnoreExternals/AIMetaData/SystemIndex.md", preview.stdout)
        self.assertFalse((self.externals / "AIMetaData").exists())
        result = self.run_install("install", "--metadata-location", "externals")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.externals / "AIMetaData/SystemIndex.md").exists())
        self.assertIn("@GitIgnoreExternals/AIMetaData/SystemIndex.md", (self.root / "CLAUDE.md").read_text())

    def test_unconfigured_noninteractive_install_requires_location(self):
        result = self.run_install("install")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--metadata-location", result.stderr)
        self.assertFalse((self.root / "AIMetaData").exists())

    def test_project_location_rejects_ignored_metadata(self):
        (self.root / ".gitignore").write_text("AIMetaData/\n")
        result = self.run_install("install", "--metadata-location", "project")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ignored by git", result.stderr)
        self.assertFalse((self.root / "AIMetaData").exists())

    def test_existing_external_layer_does_not_prompt_or_move(self):
        legacy = self.externals / "ExistingHost"
        legacy.mkdir()
        (legacy / "SystemIndex.md").write_text("# Existing index\n")
        result = self.run_install("install")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "AIMetaData").exists())
        self.assertFalse((self.externals / "AIMetaData").exists())

    def test_other_external_tool_does_not_hide_location_picker(self):
        (self.externals / "OtherTool").mkdir()
        result = self.run_install("install")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--metadata-location", result.stderr)

    def test_picker_selects_project_root(self):
        spec = importlib.util.spec_from_file_location("setup_install", INSTALLER)
        installer = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(INSTALLER.parent))
        try:
            spec.loader.exec_module(installer)
        finally:
            sys.path.pop(0)
        layers = installer.find_layers(str(self.root))
        args = type("Args", (), {"metadata_location": None, "dry_run": False})()
        with mock.patch.object(installer.sys.stdin, "isatty", return_value=True), \
             mock.patch("builtins.input", return_value="2"):
            self.assertEqual(installer.choose_host_location(args, str(self.root), layers), "project")


if __name__ == "__main__":
    unittest.main()
