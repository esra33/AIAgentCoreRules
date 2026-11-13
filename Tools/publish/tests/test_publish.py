"""Exercise publishing with real disposable Git repositories and a fake GitHub CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "publish.py"
FAKE_GH = '''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
p = pathlib.Path(os.environ['FAKE_GH_STATE'])
s = json.loads(p.read_text())
a = sys.argv[1:]
if a[:2] == ['auth', 'status']:
    sys.exit(1 if s.get('auth_fail') else 0)
if a[:2] == ['repo', 'view']:
    print(json.dumps({'nameWithOwner': 'example/project'}))
elif a[:1] == ['api']:
    print(json.dumps({'name': 'main'}))
elif a[:2] == ['pr', 'list']:
    print(json.dumps(s.get('prs', [])))
elif a[:2] == ['pr', 'create']:
    s['creates'] = s.get('creates', 0) + 1
    if s.get('create_fail'):
        p.write_text(json.dumps(s)); sys.exit(1)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    s['prs'] = [{'number': 42, 'url': 'https://github.com/example/project/pull/42', 'state': 'OPEN', 'headRefOid': sha}]
    p.write_text(json.dumps(s))
    if s.get('create_uncertain'):
        sys.exit(1)
    print(s['prs'][0]['url'])
else:
    sys.stderr.write('Unexpected gh arguments: ' + repr(a)); sys.exit(2)
'''


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.remote = self.root / "remote.git"
        self.git("init", "--bare", str(self.remote), cwd=self.root)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Publisher Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        (self.repo / "selected.txt").write_text("original\n")
        (self.repo / "unrelated.txt").write_text("original\n")
        self.git("add", "selected.txt", "unrelated.txt")
        self.git("commit", "-m", "initial")
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        self.git("config", "url." + str(self.remote) + ".insteadOf", "https://github.com/example/project.git")
        self.git("push", "origin", "main")
        self.git("checkout", "-b", "agent/test")
        self.start = self.git("rev-parse", "HEAD").strip()
        (self.repo / "selected.txt").write_text("published\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        # get-url expands insteadOf. Preserve the production GitHub identity check
        # while routing transport to the disposable local bare repository.
        real_git = shutil.which("git")
        git_wrapper = self.bin / "git"
        git_wrapper.write_text("#!/usr/bin/env python3\nimport os, sys, subprocess\n"
                               "if sys.argv[1:] == ['remote', 'get-url', 'origin']:\n"
                               "    print('https://github.com/example/project.git')\n"
                               "elif sys.argv[1:] == ['remote', 'get-url', '--push', '--all', 'origin']:\n"
                               "    p = subprocess.run([" + repr(real_git) + ", 'config', '--get-all', 'remote.origin.pushurl'], capture_output=True, text=True)\n"
                               "    print(p.stdout.strip() or 'https://github.com/example/project.git')\n"
                               "else:\n"
                               "    os.execv(" + repr(real_git) + ", [" + repr(real_git) + "] + sys.argv[1:])\n")
        git_wrapper.chmod(0o755)
        self.gh_state = self.root / "gh.json"
        self.set_gh({})
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], FAKE_GH_STATE=str(self.gh_state), PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1")
        (self.root / "body.md").write_text("Verified change.\n")
        self.request = self.root / "request.json"
        self.data = {"repo": str(self.repo), "branch": "agent/test", "expected_head": self.start, "base": "main", "files": ["selected.txt"], "commit_message": "Publish selected change", "pr_title": "Selected change", "body_file": "body.md"}
        self.write_request()

    def git(self, *args, cwd=None):
        return subprocess.check_output(["git", *args], cwd=cwd or self.repo, stderr=subprocess.PIPE, text=True).strip()

    def set_gh(self, data):
        self.gh_state.write_text(json.dumps(data))

    def write_request(self):
        self.request.write_text(json.dumps(self.data))

    def invoke(self, command="publish"):
        result = subprocess.run([sys.executable, str(SCRIPT), command, "--request", str(self.request)], env=self.env, capture_output=True, text=True)
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result, json.loads(result.stdout)

    def test_check_does_not_commit_or_stage(self):
        result, _ = self.invoke("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.start)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")

    def test_publish_preserves_dirty_files_and_repeat_does_not_duplicate(self):
        (self.repo / "unrelated.txt").write_text("private work\n")
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(self.git("show", "--format=", "--name-only", "HEAD"), "selected.txt")
        self.assertEqual((self.repo / "unrelated.txt").read_text(), "private work\n")
        published = self.git("rev-parse", "HEAD")
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(self.git("rev-parse", "HEAD"), published)
        self.assertEqual(json.loads(self.gh_state.read_text())["creates"], 1)
        self.assertEqual(self.git("ls-remote", "origin", "refs/heads/agent/test").split()[0], published)

    def test_unrelated_staged_file_blocks_before_commit(self):
        (self.repo / "unrelated.txt").write_text("staged work\n")
        self.git("add", "unrelated.txt")
        result, _ = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.start)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "unrelated.txt")

    def test_auth_failure_blocks_before_commit(self):
        self.set_gh({"auth_fail": True})
        result, _ = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.start)

    def test_new_and_deleted_files_are_published(self):
        (self.repo / "new file.txt").write_text("new\n")
        (self.repo / "selected.txt").unlink()
        self.data["files"] = ["selected.txt", "new file.txt"]
        self.write_request()
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(self.git("show", "HEAD:new file.txt"), "new")
        self.assertNotIn("selected.txt", self.git("ls-tree", "--name-only", "HEAD").splitlines())

    def test_path_escape_and_directory_are_rejected(self):
        for path in ["../body.md", "."]:
            with self.subTest(path=path):
                self.data["files"] = [path]
                self.write_request()
                result, _ = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.git("rev-parse", "HEAD"), self.start)

    def test_create_failure_resumes_without_second_commit(self):
        self.set_gh({"create_fail": True})
        result, _ = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        committed = self.git("rev-parse", "HEAD")
        self.assertNotEqual(committed, self.start)
        self.set_gh({})
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(self.git("rev-parse", "HEAD"), committed)

    def test_uncertain_pr_creation_reconciles_without_duplicate(self):
        self.set_gh({"create_uncertain": True})
        self.invoke()
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(json.loads(self.gh_state.read_text())["creates"], 1)

    def test_closed_unmerged_pr_blocks(self):
        self.set_gh({"prs": [{"number": 42, "url": "https://github.com/example/project/pull/42", "state": "CLOSED", "headRefOid": self.start}]})
        result, _ = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.start)

    def test_push_failure_resumes_committed_change(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        result, _ = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        committed = self.git("rev-parse", "HEAD")
        self.assertNotEqual(committed, self.start)
        hook.unlink()
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(self.git("rev-parse", "HEAD"), committed)

    def test_historical_merged_pr_allows_new_pr(self):
        self.set_gh({"prs": [{"number": 41, "url": "https://github.com/example/project/pull/41", "state": "MERGED", "headRefOid": self.start}]})
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(json.loads(self.gh_state.read_text())["creates"], 1)

    def test_distinct_push_url_blocks_before_commit(self):
        self.git("remote", "set-url", "--push", "origin", "https://github.com/other/project.git")
        result, _ = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.start)

    def test_copied_real_feature_state_is_linked_idempotently(self):
        import importlib.util
        feature_tool = SCRIPT.parents[1] / "feature-state" / "feature_state.py"
        sys.path.insert(0, str(feature_tool.parent))
        self.addCleanup(sys.path.remove, str(feature_tool.parent))
        spec = importlib.util.spec_from_file_location("publisher_test_feature_state", feature_tool)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = Path("/Users/andrea/Documents/Projects/ChatGPTSDK/Assets/Documentation/Features/UnityChatGPT/state.json")
        if not source.exists():
            self.skipTest("real feature fixture unavailable")
        feature_dir = self.root / "UnityChatGPT"
        feature_dir.mkdir()
        shutil.copy2(source, feature_dir / "state.json")
        initial = module.load_state(feature_dir)
        module.update_state(feature_dir, "batch", {"task_id": "T99", "value": {"branch": "agent/test", "base": "main", "plan": ["Test batch"], "merged": 0, "open_pr": None, "prs": []}}, initial["revision"])
        self.data["feature"] = {"directory": str(feature_dir), "task_id": "T99", "batch": 1, "phase": "V0", "session": "publisher_test_12345678"}
        self.write_request()
        for _ in range(2):
            result, output = self.invoke()
            self.assertEqual(result.returncode, 0, output)
        final = module.load_state(feature_dir)
        self.assertEqual(final["batches"]["T99"]["open_pr"], 42)
        self.assertEqual(final["batches"]["T99"]["prs"], [42])
        self.assertEqual(final["pull_requests"]["V0"].count(42), 1)
        self.assertEqual(final["sessions"].count("publisher_test_12345678"), 1)
        self.assertEqual(final["gates"], initial["gates"])
        self.assertEqual(json.loads(source.read_text()), initial)

    def test_base_branch_and_head_mismatch_block(self):
        for key, value in [("branch", "main"), ("expected_head", "0" * 40)]:
            with self.subTest(key=key):
                original = self.data[key]
                self.data[key] = value
                self.write_request()
                result, _ = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.git("rev-parse", "HEAD"), self.start)
                self.data[key] = original


if __name__ == "__main__":
    unittest.main()
