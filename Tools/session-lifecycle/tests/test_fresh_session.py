"""Regression tests for the fresh-session offers.

MR-20261016-02: a session switched lane at ~150M tokens and was resumed after idle gaps with no
offer to start fresh, so cold-cache turns re-read the whole context.

    python3 -m unittest discover -s Tools/session-lifecycle/tests -p 'test_*.py'
"""

import argparse
import contextlib
import datetime
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


class LaneChangeOfferTests(unittest.TestCase):
    def offer(self, total):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            session_lifecycle.offer_fresh_session({"tokens": {"total_tokens": total}}, "bug_fix")
        return stderr.getvalue()

    def test_large_session_gets_the_offer(self):
        self.assertIn('/new-session "/bug-fix <symptom>"', self.offer(41200000))

    def test_small_session_stays_silent(self):
        self.assertEqual(self.offer(5000000), "")


class IdleGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="idle-gap-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.transcript = os.path.join(self.tmp, "s.jsonl")
        patcher = mock.patch.dict(os.environ, {"SESSION_REPORTS_ROOT": os.path.join(self.tmp, "Sessions")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def hook(self, minutes_ago, context):
        stamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
        with open(self.transcript, "w") as handle:
            handle.write(json.dumps({"type": "assistant", "timestamp": stamp.isoformat().replace("+00:00", "Z"),
                                     "message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": context}}}) + "\n")
            handle.write(json.dumps({"type": "user", "message": {"content": "next"}}) + "\n")
        stdout = io.StringIO()
        payload = io.StringIO(json.dumps({"session_id": "s", "transcript_path": self.transcript}))
        with mock.patch.object(sys, "stdin", payload), contextlib.redirect_stdout(stdout):
            self.assertEqual(session_lifecycle.cmd_hook_prompt(argparse.Namespace(reports_root=None)), 0)
        return stdout.getvalue()

    def test_gap_past_cache_ttl_on_large_context_is_noted(self):
        output = self.hook(130, 400000)
        self.assertIn("2h 10m", output)
        self.assertIn("/new-session", output)

    def test_short_gap_is_silent(self):
        self.assertEqual(self.hook(5, 400000), "")

    def test_small_context_is_silent(self):
        self.assertEqual(self.hook(130, 20000), "")


class ContextWarningTests(IdleGapTests):
    """2026-11-02: 87% of context tokens were spent in calls already at >= 90% of the median session
    peak context, so hook-prompt warns the engineer and the agent once the context crosses it."""

    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, "Sessions")
        self.folder = self.session_folder("current", "s", None)

    def session_folder(self, name, session_id, peak, ended=True):
        folder = os.path.join(self.root, name)
        os.makedirs(folder)
        state = {"session_id": session_id, "breakdown": {"peak_context": peak} if peak else {}}
        if peak and ended:
            state["ended_at"] = "2026-11-01T10:00:00-07:00"
        with open(os.path.join(folder, "session.json"), "w") as handle:
            json.dump(state, handle)
        return folder

    def references(self, count, peak=100000):
        for index in range(count):
            self.session_folder("other%d" % index, "o%d" % index, peak)

    def test_crossing_warns_engineer_and_agent_once(self):
        self.references(5)
        output = json.loads(self.hook(1, 95000))
        self.assertIn("Context-size warning", output["systemMessage"])
        self.assertIn("100k median", output["systemMessage"])
        self.assertIn("do not reset mid-step", output["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.hook(1, 120000), "")

    def test_rearms_after_context_drops(self):
        self.references(5)
        self.assertNotEqual(self.hook(1, 95000), "")
        self.assertEqual(self.hook(1, 30000), "")
        self.assertFalse(os.path.isfile(os.path.join(self.folder, session_lifecycle.CONTEXT_WARNING_MARKER)))
        self.assertIn("Context-size warning", self.hook(1, 95000))

    def test_below_threshold_is_silent(self):
        self.references(5)
        self.assertEqual(self.hook(1, 85000), "")

    def test_too_few_reference_sessions_is_silent(self):
        self.references(4)
        self.session_folder("uncompiled", "u", None)
        self.assertEqual(self.hook(1, 500000), "")

    def test_running_sessions_do_not_count_as_references(self):
        """Their peaks are partial; the Performance tab leaves them out too."""
        self.references(4)
        self.session_folder("running", "r", 100000, ended=False)
        self.assertEqual(self.hook(1, 500000), "")

    def test_idle_gap_and_warning_share_one_output(self):
        self.references(5)
        output = json.loads(self.hook(130, 400000))
        self.assertIn("Idle-gap note", output["hookSpecificOutput"]["additionalContext"])
        self.assertIn("Context-size warning", output["hookSpecificOutput"]["additionalContext"])


class ShellRuleReadTests(unittest.TestCase):
    """MR-20261016-05: rule and process files read via cat/sed only reach the router trace by inference."""

    def hook(self, command):
        stdout = io.StringIO()
        payload = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
        # cmd_hook_bash now logs a firing to hooks.log; stubbed out so this helper never writes
        # into the real project's live GitIgnoreReports/Sessions/hooks.log.
        with mock.patch.object(sys, "stdin", payload), contextlib.redirect_stdout(stdout), \
             mock.patch.object(session_lifecycle, "hook_log"):
            self.assertEqual(session_lifecycle.cmd_hook_bash(argparse.Namespace(reports_root=None)), 0)
        return stdout.getvalue()

    def test_sed_of_a_process_file_gets_the_reminder(self):
        output = json.loads(self.hook("sed -n 1,5p GitIgnoredExternals/AIAgentCoreRules/Processes/BugFix.md"))
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertIn("Processes/BugFix.md", output["hookSpecificOutput"]["additionalContext"])

    def test_grep_and_non_rule_reads_are_silent(self):
        for command in ("grep -n hypothesis Rules/StopAndVerify.md", "cat Documentation/04_BugFix.md",
                        "head -5 Tools/session-lifecycle/session_lifecycle.py", "git status | tail -3"):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), "")

    def test_quoted_or_heredoc_mentions_are_silent(self):
        """Retro 000c8ff2 #4: a heredoc that only quoted a sed command fired the reminder."""
        for command in ("python3 t.py note \"ran `sed -n 1,5p Processes/BugFix.md`\"",
                        "echo 'cat Rules/CodingStandards.md'",
                        "cat > t.md <<'EOF'\nsed -n 1,5p Processes/BugFix.md\nEOF\npython3 t.py"):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), "")

    def test_reads_after_a_separator_or_quoted_path_still_warn(self):
        for command in ("cd x && cat Rules/CodingStandards.md", "ls; head -5 Processes/SmallTask.md | grep x",
                        "cat \"Rules/CodingStandards.md\""):
            with self.subTest(command=command):
                self.assertNotEqual(self.hook(command), "")


class HookReadTests(unittest.TestCase):
    """Token-usage savings pass, 2026-11-17: a sizeable .cs file read whole (no limit/offset) gets
    a codeindex.py/code-graph.sh nudge for its shape; small files and partial reads stay silent."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hook-read-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.tmp})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def write_cs(self, name, size):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as handle:
            handle.write("x" * size)
        return path

    def hook(self, path, extra_input=None, reports_root=None):
        tool_input = dict({"file_path": path}, **(extra_input or {}))
        stdout = io.StringIO()
        payload = io.StringIO(json.dumps({"tool_name": "Read", "tool_input": tool_input}))
        with mock.patch.object(sys, "stdin", payload), contextlib.redirect_stdout(stdout):
            self.assertEqual(session_lifecycle.cmd_hook_read(argparse.Namespace(reports_root=reports_root)), 0)
        return stdout.getvalue()

    def test_sizeable_whole_file_read_gets_the_nudge(self):
        path = self.write_cs("LivesManager.cs", session_lifecycle.CS_SHAPE_READ_MIN_BYTES)
        output = json.loads(self.hook(path))
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("codeindex.py members LivesManager", context)
        self.assertIn("codeindex.py where LivesManager", context)

    def test_firing_is_logged_so_frequency_can_be_revisited(self):
        """Retro 90556129, proposal #3: CS_SHAPE_READ_MIN_BYTES can't be revisited against real
        firing frequency until hooks.log actually records a firing."""
        reports = os.path.join(self.tmp, "reports")
        path = self.write_cs("LivesManager.cs", session_lifecycle.CS_SHAPE_READ_MIN_BYTES)
        self.hook(path, reports_root=reports)
        with open(os.path.join(reports, "hooks.log")) as handle:
            log = handle.read()
        self.assertIn("read ", log)
        self.assertIn("nudged %d bytes LivesManager.cs" % session_lifecycle.CS_SHAPE_READ_MIN_BYTES, log)

    def test_small_file_is_silent(self):
        path = self.write_cs("Tiny.cs", session_lifecycle.CS_SHAPE_READ_MIN_BYTES - 1)
        self.assertEqual(self.hook(path), "")

    def test_partial_read_is_silent(self):
        path = self.write_cs("LivesManager.cs", session_lifecycle.CS_SHAPE_READ_MIN_BYTES)
        self.assertEqual(self.hook(path, {"limit": 50}), "")
        self.assertEqual(self.hook(path, {"offset": 10}), "")

    def test_non_csharp_file_is_silent(self):
        path = os.path.join(self.tmp, "Notes.md")
        with open(path, "w") as handle:
            handle.write("x" * session_lifecycle.CS_SHAPE_READ_MIN_BYTES)
        self.assertEqual(self.hook(path), "")


class HookBashFiringLogTests(unittest.TestCase):
    """End-session follow-up to retro 90556129, proposal #1: hook-bash had the same gap as
    hook-read — hooks.log only ever recorded its errors, never a real firing."""

    def hook(self, command, reports_root):
        stdout = io.StringIO()
        payload = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
        with mock.patch.object(sys, "stdin", payload), contextlib.redirect_stdout(stdout):
            self.assertEqual(session_lifecycle.cmd_hook_bash(argparse.Namespace(reports_root=reports_root)), 0)
        return stdout.getvalue()

    def test_firing_is_logged_with_which_detectors_fired(self):
        tmp = tempfile.mkdtemp(prefix="hook-bash-log-")
        self.addCleanup(shutil.rmtree, tmp, True)
        reports = os.path.join(tmp, "reports")
        self.hook('sed -n 1,5p Rules/CoreTags.md; grep -rl "class Foo" Assets', reports)
        with open(os.path.join(reports, "hooks.log")) as handle:
            log = handle.read()
        self.assertIn("bash ", log)
        self.assertIn("fired: rule-read, type-grep", log)

    def test_silent_command_logs_nothing(self):
        tmp = tempfile.mkdtemp(prefix="hook-bash-log-")
        self.addCleanup(shutil.rmtree, tmp, True)
        reports = os.path.join(tmp, "reports")
        self.hook("git status", reports)
        self.assertFalse(os.path.isfile(os.path.join(reports, "hooks.log")))


if __name__ == "__main__":
    unittest.main()
