"""Launcher tests: staleness by tool-code mtime, and a real start -> reuse -> status -> restart -> stop cycle.

    python3 -m unittest discover -s Tools/code-graph/tests -p 'test_*.py'
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

TESTS_DIR = Path(__file__).resolve().parent
TOOL_DIR = TESTS_DIR.parent
sys.path.insert(0, str(TOOL_DIR))
sys.path.insert(0, str(TESTS_DIR))

import graph_control  # noqa: E402
from test_graph_db import build_fixture_db  # noqa: E402


class StaleTests(unittest.TestCase):
    def setUp(self):
        self.tools = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tools)
        (self.tools / 'web').mkdir()
        self.module = self.tools / 'graph_server.py'
        self.page = self.tools / 'web' / 'index.html'
        for path in (self.module, self.page):
            path.write_text('')
            os.utime(path, (1000, 1000))

    def test_fresh_when_code_older_than_start(self):
        self.assertFalse(graph_control.stale({'started': 2000}, self.tools))

    def test_stale_when_python_or_web_file_is_newer(self):
        os.utime(self.module, (3000, 3000))
        self.assertTrue(graph_control.stale({'started': 2000}, self.tools))
        os.utime(self.module, (1000, 1000))
        os.utime(self.page, (3000, 3000))
        self.assertTrue(graph_control.stale({'started': 2000}, self.tools))

    def test_missing_started_counts_as_stale(self):
        self.assertTrue(graph_control.stale({}, self.tools))


class DefaultRefreshCmdTests(unittest.TestCase):
    def test_rebuilds_the_served_project_and_db(self):
        command = graph_control.default_refresh_cmd(Path('/p r'), Path('/p r/Library/x.sqlite'))
        self.assertEqual(shlex.split(command)[1:], [str(graph_control.CODEINDEX_SCRIPT), 'build', '--force',
                                                    '--project', '/p r', '--db', '/p r/Library/x.sqlite'])

    def test_none_without_codeindex_alongside(self):
        self.assertIsNone(graph_control.default_refresh_cmd(Path('/p'), Path('/p/db'), codeindex='/missing.py'))


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.project)
        (self.project / 'Library').mkdir()
        build_fixture_db(str(self.project / 'Library'))
        self.output = []
        self.addCleanup(self.control, 'stop')

    def control(self, action, **kwargs):
        return graph_control.control(action, self.project, out=self.output.append, **kwargs)

    def test_start_reuse_status_restart_stop(self):
        first = self.control('start')
        self.assertTrue(first['url'].startswith('http://127.0.0.1:'))
        self.assertEqual(first['db'], str(self.project / 'Library' / 'codeindex.sqlite'))
        with urlopen(first['url'] + 'api/status', timeout=5) as response:
            self.assertEqual(json.load(response)['counts']['type'], 8)
        self.assertEqual((self.project / '.code-graph' / '.gitignore').read_text(), '*\n')

        again = self.control('start')
        self.assertEqual(again['pid'], first['pid'])

        status = self.control('status')
        self.assertEqual(status['pid'], first['pid'])
        self.assertIn('codeindex.py build --force --project', self.output[-1])

        refresh_cmd = '%s -c "print(1)"' % sys.executable
        restarted = self.control('start', refresh_cmd=refresh_cmd)
        self.assertNotEqual(restarted['pid'], first['pid'])
        self.assertIn('restarted (--db / --refresh-cmd changed)', self.output)
        with urlopen(restarted['url'] + 'api/status', timeout=5) as response:
            self.assertTrue(json.load(response)['refresh_available'])

        self.control('stop')
        self.assertEqual(self.output[-1], 'Stopped')
        self.assertIsNone(self.control('status'))
        self.assertFalse((self.project / '.code-graph' / 'server.json').exists())

    def test_empty_refresh_cmd_hides_the_button(self):
        state = self.control('start', refresh_cmd='')
        self.control('status')
        self.assertIn('refresh: (not configured)', self.output[-1])
        with urlopen(state['url'] + 'api/refresh', timeout=5) as response:
            self.assertFalse(json.load(response)['available'])

    def test_missing_db_warns_and_refresh_stays_available(self):
        (self.project / 'Library' / 'codeindex.sqlite').unlink()
        warnings = []
        state = self.control('start', warn=warnings.append)
        self.assertEqual(len(warnings), 1)
        self.assertIn('no codeindex DB at', warnings[0])
        with urlopen(state['url'] + 'api/refresh', timeout=5) as response:
            self.assertTrue(json.load(response)['available'])

    def test_stop_when_nothing_runs(self):
        self.control('stop')
        self.assertEqual(self.output[-1], 'No Code Graph server running')

    def test_bash_wrapper_runs_status(self):
        result = subprocess.run(['bash', str(TOOL_DIR / 'code-graph.sh'), 'status', '--project', str(self.project)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'Stopped'))


if __name__ == '__main__':
    unittest.main()
