"""Preview launcher tests: a healthy server counts as stale once any tool module is newer than its
recorded start time (Python never reloads modules), plus a real start → edit → start restart.

    python3 -m unittest discover -s Tools/doc-review/tests -p 'test_*.py'
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from urllib.request import urlopen

TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import preview_control  # noqa: E402


class StaleTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.tools = self.root / 'tools'
        self.tools.mkdir()
        self.module = self.tools / 'view.py'
        self.module.write_text('')
        self.state_path = self.root / 'server.json'
        self.state_path.write_text('{}')

    def set_mtime(self, path, value):
        os.utime(path, (value, value))

    def test_fresh_when_code_older_than_start(self):
        self.set_mtime(self.module, 1000)
        self.assertFalse(preview_control.stale({'started': 2000}, self.state_path, (self.tools,)))

    def test_stale_when_code_newer_than_start(self):
        self.set_mtime(self.module, 3000)
        self.assertTrue(preview_control.stale({'started': 2000}, self.state_path, (self.tools,)))

    def test_legacy_state_falls_back_to_server_json_mtime(self):
        self.set_mtime(self.state_path, 2000)
        self.set_mtime(self.module, 3000)
        self.assertTrue(preview_control.stale({}, self.state_path, (self.tools,)))
        self.set_mtime(self.module, 1000)
        self.assertFalse(preview_control.stale({}, self.state_path, (self.tools,)))

    def test_missing_tool_dir_is_ignored(self):
        self.assertFalse(preview_control.stale({'started': 2000}, self.state_path, (self.root / 'absent',)))


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project)
        self.tools = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tools)
        self.module = self.tools / 'view.py'
        self.module.write_text('')
        os.utime(self.module, (1000, 1000))
        self.addCleanup(self.run_control, 'stop')

    def run_control(self, action):
        output = io.StringIO()
        with mock.patch.object(preview_control, 'TOOL_DIRS', (self.tools,)), redirect_stdout(output):
            preview_control.control(action, self.project)
        return output.getvalue().splitlines()

    def test_start_restarts_after_tool_code_changes(self):
        first = self.run_control('start')
        self.assertEqual(first, self.run_control('start'))
        os.utime(self.module, (time.time() + 5, time.time() + 5))
        restarted = self.run_control('start')
        self.assertEqual(restarted[0], 'restarted (tool code changed)')
        state = json.loads((self.project / '.doc-review' / 'server.json').read_text())
        self.assertEqual(restarted[1], state['url'])
        self.assertIn('started', state)


class ParallelProjectTests(unittest.TestCase):
    def test_shared_launcher_manages_two_projects_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            projects = [root / 'First project', root / 'Second project']
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', SESSION_FEATURES_ROOT='')

            def command(action, project):
                return ['bash', str(TOOL_DIR / 'preview-control.sh'), action, '--project', str(project)]

            def run(action, project):
                return subprocess.run(command(action, project), env=environment, cwd=root,
                                      capture_output=True, text=True, check=True, timeout=20).stdout.strip()

            def health(url):
                with urlopen(url + 'api/health', timeout=3) as response:
                    return json.load(response)

            for project in projects:
                project.mkdir()
            try:
                with subprocess.Popen(command('start', projects[0]), env=environment, cwd=root,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as first:
                    second_url = run('start', projects[1])
                    stdout, stderr = first.communicate(timeout=20)
                    self.assertEqual(first.returncode, 0, stderr)
                first_url = stdout.strip()
                self.assertNotEqual(first_url, second_url)
                identities = [health(first_url), health(second_url)]
                self.assertNotEqual(identities[0]['pid'], identities[1]['pid'])
                for project, url, identity in zip(projects, (first_url, second_url), identities):
                    self.assertEqual(identity['project'], str(project))
                    self.assertEqual(run('start', project), url)
                self.assertEqual(run('stop', projects[0]), 'Stopped')
                self.assertEqual(run('status', projects[0]), 'Stopped')
                self.assertEqual(run('status', projects[1]), 'Running: ' + second_url)
                self.assertEqual(health(second_url), identities[1])
            finally:
                for project in projects:
                    run('stop', project)


if __name__ == '__main__':
    unittest.main()
