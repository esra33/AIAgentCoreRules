"""Regression tests for the router trace in metrics.md.

MR-20261016-01: Reads of a tool's .py source under the imported roots were listed as rule loads,
and trace times were the transcript's UTC clock instead of local time.
Retro 000c8ff2 #1: Documentation/ pages (the human mirror of the rules) were listed as loads.

    python3 -m unittest discover -s Tools/session-lifecycle/tests -p 'test_*.py'
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))
import session_lifecycle  # noqa: E402
import token_breakdown  # noqa: E402

SESSION_ID = "bbbbbbbb-0000-0000-0000-000000000000"


class RouterTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="router-trace-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.rules = os.path.join(self.tmp, "Ext", "Layer", "Rules")
        os.makedirs(self.rules)
        for name in ("MetaRouter.md", "BugFix.md", "tool.py"):
            open(os.path.join(self.rules, name), "w").close()
        self.docs = os.path.join(self.tmp, "Ext", "Layer", "Documentation")
        os.makedirs(self.docs)
        open(os.path.join(self.docs, "04_BugFix.md"), "w").close()
        with open(os.path.join(self.tmp, "CLAUDE.md"), "w") as handle:
            handle.write("@Ext/Layer/Rules/MetaRouter.md\n")   # root = Ext/Layer, as for GitIgnoredExternals/<layer>
        self.transcript = os.path.join(self.tmp, SESSION_ID + ".jsonl")
        with open(self.transcript, "w") as handle:
            for i, path in enumerate((os.path.join(self.rules, "tool.py"), os.path.join(self.rules, "BugFix.md"),
                                      os.path.join(self.docs, "04_BugFix.md"))):
                handle.write(json.dumps({"type": "assistant", "timestamp": "2026-10-13T18:42:0%dZ" % i, "message": {
                    "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": path}}]}}) + "\n")
        old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/Los_Angeles"
        time.tzset()
        self.addCleanup(self.restore_tz, old_tz)

    @staticmethod
    def restore_tz(old_tz):
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()

    def trace(self):
        state = {"session_id": SESSION_ID, "transcript_path": self.transcript}
        return session_lifecycle.router_trace(state, self.tmp)[1]

    def test_source_and_documentation_reads_are_not_loads(self):
        """Retro 000c8ff2 #1: Documentation/ mirrors filled the trace with non-routing rows."""
        self.assertEqual([load["file"] for load in self.trace()], ["Layer/Rules/BugFix.md"])

    def test_time_is_local(self):
        self.assertEqual(self.trace()[0]["at"], "11:42:01")

    def test_bash_load_later_read_is_upgraded(self):
        """Retro 824b0189 #2: a file cat'ed first and Read later kept only its Bash row."""
        with open(self.transcript, "w") as handle:
            for i, (name, tool_input) in enumerate((("Bash", {"command": "cat %s" % os.path.join(self.rules, "BugFix.md")}),
                                                     ("Read", {"file_path": os.path.join(self.rules, "BugFix.md")}),
                                                     ("Read", {"file_path": os.path.join(self.rules, "BugFix.md")}))):
                handle.write(json.dumps({"type": "assistant", "timestamp": "2026-10-13T18:42:0%dZ" % i, "message": {
                    "content": [{"type": "tool_use", "name": name, "input": tool_input}]}}) + "\n")
        self.assertEqual([(load["file"], load["via"]) for load in self.trace()],
                         [("Layer/Rules/BugFix.md", "main · Bash → Read")])

    def test_runnable_tool_count_ignores_heredoc_and_quoted_text(self):
        """Retro a08926ea #1: doc strings in heredoc edit scripts inflated codeindex × 59."""
        heredoc = "python3 - <<'EOF'\ns = 'run python3 codeindex.py where X'\npython3 codeindex.py where X\nEOF"
        self.assertEqual(session_lifecycle.runnable_tool_calls(heredoc), {})
        self.assertEqual(session_lifecycle.runnable_tool_calls('echo "use python3 usages.py Foo instead"'), {})
        self.assertEqual(session_lifecycle.runnable_tool_calls(
            "python3 GitIgnoredExternals/AIAgentCoreRules/Tools/unity-tools/codeindex.py where X"), {"codeindex.py": 1})

    def test_breakdown_counts_only_md_reads_as_loads(self):
        roots = [os.path.join(self.tmp, "Ext", "Layer")]
        self.assertEqual(token_breakdown.classify("Read", {"file_path": os.path.join(self.rules, "tool.py")}, roots),
                         token_breakdown.AD_HOC)
        self.assertEqual(token_breakdown.classify("Read", {"file_path": os.path.join(self.rules, "BugFix.md")}, roots),
                         "Rule & process loads")


if __name__ == "__main__":
    unittest.main()
