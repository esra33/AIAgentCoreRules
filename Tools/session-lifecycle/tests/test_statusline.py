"""statusline: saves the plan rate_limits Claude Code pipes in to plan_usage.json for the Performance
tab, keeps the last capture when a payload has none, and prints a short status line.

    python3 -m unittest discover -s Tools/session-lifecycle/tests -p 'test_*.py'
"""

import argparse
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))
import session_lifecycle  # noqa: E402
import token_breakdown  # noqa: E402

LIMITS = {"five_hour": {"used_percentage": 23.5, "resets_at": 1738425600},
          "seven_day": {"used_percentage": 41.2, "resets_at": 1738857600}}


class StatuslineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="statusline-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "Sessions")
        patcher = mock.patch.dict(os.environ, {"SESSION_REPORTS_ROOT": self.root})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capture = os.path.join(self.root, token_breakdown.PLAN_USAGE_FILE)

    def run_statusline(self, payload):
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(stdout):
            self.assertEqual(session_lifecycle.cmd_statusline(argparse.Namespace(reports_root=None)), 0)
        return stdout.getvalue().strip()

    def test_rate_limits_are_saved_and_printed(self):
        line = self.run_statusline({"session_id": "s1", "model": {"display_name": "Opus"}, "rate_limits": LIMITS})
        self.assertEqual("Opus · 5h 24% · 7d 41%", line)
        with open(self.capture) as handle:
            saved = json.load(handle)
        self.assertEqual(("s1", LIMITS), (saved["session_id"], saved["rate_limits"]))
        self.assertIsInstance(saved["captured_at"], float)

    def test_payload_without_rate_limits_keeps_the_last_capture(self):
        self.run_statusline({"session_id": "s1", "rate_limits": LIMITS})
        self.assertEqual("Opus", self.run_statusline({"session_id": "s2", "model": {"display_name": "Opus"}}))
        with open(self.capture) as handle:
            self.assertEqual("s1", json.load(handle)["session_id"])

    def test_bad_input_still_prints(self):
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("not json")), contextlib.redirect_stdout(stdout):
            self.assertEqual(session_lifecycle.cmd_statusline(argparse.Namespace(reports_root=None)), 0)
        self.assertEqual("", stdout.getvalue().strip())
        self.assertFalse(os.path.exists(self.capture))


if __name__ == "__main__":
    unittest.main()
