"""Integration checks for first-install host metadata placement."""

import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


INSTALLER = Path(__file__).with_name("install.py")
CORE_ROOT = INSTALLER.parents[2]
INSTALL_SH = Path(__file__).with_name("install.sh")


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

    def test_documentation_defaults_and_custom_targets_are_persisted(self):
        result = self.run_install("install", "--agent", "codex", "--metadata-location", "project",
                                  "--features-dir", "Assets/Documentation/Features",
                                  "--design-documents-dir", "Assets/Documentation/DesignDocuments")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.root / "ai-agent-core.json"
        value = json.loads(path.read_text())
        self.assertEqual(value["paths"]["features"], "Assets/Documentation/Features")
        value["custom"] = {"keep": True}
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        result = self.run_install("install", "--agent", "codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_bytes(), before)
        result = self.run_install("install", "--agent", "codex", "--features-dir", "Different")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already defines", result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_config_preview_is_read_only_and_bad_paths_do_not_scaffold(self):
        result = self.run_install("check", "--agent", "codex", "--metadata-location", "project",
                                  "--features-dir", "Assets/Documentation/Features")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ai-agent-core.json", result.stdout)
        self.assertFalse((self.root / "ai-agent-core.json").exists())
        self.assertFalse((self.root / "Assets").exists())
        result = self.run_install("install", "--agent", "codex", "--metadata-location", "project",
                                  "--features-dir", "../Outside")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "AIMetaData").exists())
        self.assertFalse((self.root / "ai-agent-core.json").exists())

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

    def test_skill_moved_between_layers_is_relinked_in_one_run(self):
        spec = importlib.util.spec_from_file_location("setup_install", INSTALLER)
        installer = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(INSTALLER.parent))
        try:
            spec.loader.exec_module(installer)
        finally:
            sys.path.pop(0)
        core = self.root / "Core"
        host = self.root / "Host"
        (core / "Skills/uses").mkdir(parents=True)
        (core / "Skills/uses/SKILL.md").write_text("---\nname: uses\n---\n")
        (host / "Skills").mkdir(parents=True)
        skills_dir = self.root / ".claude/skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "uses").symlink_to("../../Host/Skills/uses")   # skill moved Host -> Core
        layers = [("Core", str(core)), ("Host", str(host))]

        preview = []
        installer.install_skills(str(self.root), layers, True, preview)
        self.assertTrue(any("prune stale uses" in line for line in preview), preview)
        self.assertTrue(any(line.startswith("skills: link uses") for line in preview), preview)
        self.assertFalse(any("CONFLICT" in line for line in preview), preview)

        log = []
        installer.install_skills(str(self.root), layers, False, log)
        self.assertEqual((skills_dir / "uses").resolve(), (core / "Skills/uses").resolve())


class BootstrapTests(unittest.TestCase):
    """A project without a linked core, installed from a core checkout outside it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "Game"
        (self.root / "Sub").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
        self.env["GIT_CONFIG_GLOBAL"] = os.devnull   # the engineer's global *GitIgnore* pattern would hide the warning

    def run_script(self, *args, cwd=None, shell=None):
        command = [shell, str(INSTALL_SH)] if shell else [str(INSTALL_SH)]
        return subprocess.run(command + list(args), cwd=cwd or self.root / "Sub", env=self.env,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_install_links_core_into_a_fresh_project(self):
        link = self.root / "GitIgnoredExternals/AIAgentCoreRules"
        preview = self.run_script("check", "--metadata-location", "externals")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("core: link GitIgnoredExternals/AIAgentCoreRules", preview.stdout)
        self.assertIn("not ignored by git", preview.stdout)
        self.assertFalse(link.exists())
        result = self.run_script("--metadata-location", "externals", "--defaults")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(link.resolve(), CORE_ROOT.resolve())
        self.assertTrue((self.root / ".claude/skills/audit").exists())
        again = self.run_script("check")
        self.assertIn("up to date", again.stdout)

    def test_install_from_the_core_checkout_itself_is_refused(self):
        result = self.run_script("check", cwd=CORE_ROOT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkout itself", result.stderr)

    def test_missing_project_folder_is_refused(self):
        result = self.run_script("--project", str(self.root / "Missing"), "check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)
        self.assertFalse((self.root / "Missing").exists())

    def test_script_runs_from_zsh_and_sh(self):
        for shell in ("zsh", "sh"):
            if not shutil.which(shell):
                continue
            result = self.run_script("check", "--metadata-location", "externals", shell=shell)
            self.assertEqual(result.returncode, 0, f"{shell}: {result.stderr}")
            self.assertIn("core: link", result.stdout)

    def test_sourcing_leaves_the_calling_shell_alive_and_unchanged(self):
        shells = {"bash": "bash --norc -i -c", "zsh": "zsh -f -i -c"}
        for shell, launcher in shells.items():
            if not shutil.which(shell):
                continue
            script = f"source '{INSTALL_SH}'; echo alive=$?; [[ -o errexit ]] && echo errexit-on"
            result = subprocess.run(launcher.split() + [script], cwd=self.root, env=self.env,
                                    capture_output=True, text=True, stdin=subprocess.DEVNULL)
            self.assertIn("alive=2", result.stdout, f"{shell}: {result.stderr}")
            self.assertNotIn("errexit-on", result.stdout, shell)
            self.assertIn("instead of sourcing", result.stderr, shell)


class DefaultCommandTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("setup_install", INSTALLER)
        self.installer = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(INSTALLER.parent))
        try:
            spec.loader.exec_module(self.installer)
        finally:
            sys.path.pop(0)

    def test_install_is_inserted_after_global_options(self):
        commands = ("install", "check", "prepare-worktree", "worktrees")
        default = self.installer.with_default_command
        self.assertEqual(default([], commands), ["install"])
        self.assertEqual(default(["--agent", "codex"], commands), ["install", "--agent", "codex"])
        self.assertEqual(default(["--project", "P", "--defaults"], commands), ["--project", "P", "install", "--defaults"])
        self.assertEqual(default(["--project=P"], commands), ["--project=P", "install"])
        self.assertEqual(default(["--project", "P", "check"], commands), ["--project", "P", "check"])
        self.assertEqual(default(["--help"], commands), ["--help"])


if __name__ == "__main__":
    unittest.main()
