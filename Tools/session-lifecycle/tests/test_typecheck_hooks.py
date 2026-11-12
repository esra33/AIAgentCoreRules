"""Part 3 of the 2026-11-10 audit: the typecheck baseline (hook-edit), the cslint hook (hook-lint) and
the end check (hook-stop-check), plus typecheck runs read back from the transcript for metrics."""
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import session_lifecycle  # noqa: E402

SESSION = "cccccccc-1111-2222-3333-444444444444"


def tool_use(use_id, command, stamp):
    return {"type": "assistant", "timestamp": stamp, "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": use_id, "name": "Bash", "input": {"command": command}}]}}


def tool_result(use_id, text, stamp):
    return {"type": "user", "timestamp": stamp, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": use_id, "content": text, "is_error": False}]}}


class HookTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="typecheck-hooks-")
        self.project = os.path.join(self.tmp, "Game")
        os.makedirs(os.path.join(self.project, "ProjectSettings"))
        os.makedirs(os.path.join(self.project, "Assets", "Scripts"))
        with open(os.path.join(self.project, "ProjectSettings", "ProjectVersion.txt"), "w") as handle:
            handle.write("m_EditorVersion: 6000.0.0f1\n")
        self.cs = os.path.join(self.project, "Assets", "Scripts", "Thing.cs")
        with open(self.cs, "w") as handle:
            handle.write("public class Thing\n{\n    private void M()\n    {\n        var x = 1;\n    }\n}\n")
        self.reports = os.path.join(self.tmp, "reports")
        self.transcript = os.path.join(self.tmp, SESSION + ".jsonl")
        self.write_transcript([{"type": "user", "timestamp": "2026-11-10T10:00:00Z",
                                "message": {"role": "user", "content": "fix it"}}])
        self.env = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.project})
        self.env.start()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_transcript(self, entries):
        with open(self.transcript, "w") as handle:
            handle.write("".join(json.dumps(e) + "\n" for e in entries))

    def run_hook(self, func, payload):
        payload = dict({"session_id": SESSION, "transcript_path": self.transcript}, **payload)
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(stdout):
            self.assertEqual(func(argparse.Namespace(reports_root=self.reports)), 0)
        text = stdout.getvalue().strip()
        return json.loads(text) if text else None

    def edit(self, path=None):
        return self.run_hook(session_lifecycle.cmd_hook_edit, {"tool_name": "Edit", "tool_input": {"file_path": path or self.cs}})

    def state(self):
        return session_lifecycle.load_typecheck(session_lifecycle.find_folder(self.reports, SESSION))


class EditHookTests(HookTestCase):
    def test_first_cs_edit_runs_the_baseline_once(self):
        baseline = {"when": "2026-11-10T10:00:00+00:00", "file": self.cs, "root": self.project,
                    "result": "failed: Assembly-CSharp", "seconds": 2.9, "errors": ["Thing.cs(5,9): error CS0103: x"]}
        with mock.patch.object(session_lifecycle, "run_baseline", return_value=baseline) as run:
            first = self.edit()
            second = self.edit()
        run.assert_called_once_with(self.cs, self.project)
        context = first["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Typecheck baseline", context)
        self.assertIn("failed: Assembly-CSharp", context)
        self.assertIn("predate your edits", context)
        self.assertIn("error CS0103", context)
        self.assertIsNone(second)
        self.assertEqual(self.state()["last_cs_edit"]["file"], self.cs)

    def test_non_cs_and_non_unity_edits_are_ignored(self):
        outside = os.path.join(self.tmp, "Loose.cs")
        with open(outside, "w") as handle:
            handle.write("class Loose {}\n")
        with mock.patch.object(session_lifecycle, "run_baseline") as run:
            self.assertIsNone(self.edit(os.path.join(self.project, "README.md")))
            self.assertIsNone(self.edit(outside))
        run.assert_not_called()
        self.assertIsNone(session_lifecycle.find_folder(self.reports, SESSION))


class LintHookTests(HookTestCase):
    def test_violations_are_injected_and_counted(self):
        session_lifecycle.ensure_folder(self.reports, SESSION, self.transcript, self.project)
        output = self.run_hook(session_lifecycle.cmd_hook_lint, {"tool_name": "Write", "tool_input": {"file_path": self.cs}})
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("Assets/Scripts/Thing.cs:5: [EXPLICIT]", context)
        self.assertEqual(self.state()["lint"], {"runs": 1, "violations": 1})

    def test_clean_file_is_silent(self):
        with open(self.cs, "w") as handle:
            handle.write("public class Thing\n{\n}\n")
        self.assertIsNone(self.run_hook(session_lifecycle.cmd_hook_lint, {"tool_input": {"file_path": self.cs}}))


class StopCheckTests(HookTestCase):
    def setUp(self):
        super().setUp()
        with mock.patch.object(session_lifecycle, "run_baseline",
                               return_value={"when": "x", "file": self.cs, "root": self.project, "result": "clean", "seconds": 1}):
            self.edit()
        folder = session_lifecycle.find_folder(self.reports, SESSION)
        data = session_lifecycle.load_typecheck(folder)
        data["last_cs_edit"]["when"] = "2026-11-10T10:05:00+00:00"
        session_lifecycle.save_typecheck(folder, data)

    def stop(self, **extra):
        return self.run_hook(session_lifecycle.cmd_hook_stop_check, extra)

    def test_blocks_when_no_typecheck_ran_after_the_edit(self):
        command = "python3 GitIgnoredExternals/AIAgentCoreRules/Tools/unity-tools/typecheck.py"
        self.write_transcript([tool_use("t1", command, "2026-11-10T10:01:00Z"),
                               tool_result("t1", "All 2 assemblies type check clean.", "2026-11-10T10:01:05Z")])
        output = self.stop()
        self.assertEqual(output["decision"], "block")
        self.assertIn("typecheck.py", output["reason"])
        self.assertIn("Thing.cs", output["reason"])
        self.assertEqual(self.state()["end_check_blocks"], 1)

    def test_passes_after_a_later_run_and_when_already_blocked(self):
        self.assertEqual(self.stop()["decision"], "block")
        self.assertIsNone(self.stop(stop_hook_active=True))
        self.write_transcript([tool_use("t2", "python3 /abs/Tools/unity-tools/typecheck.py --all", "2026-11-10T10:06:00Z"),
                               tool_result("t2", "FAILED: Assembly-CSharp\n1 checked, 1 failed, 0 skipped.", "2026-11-10T10:06:09Z")])
        self.assertIsNone(self.stop())

    def test_a_list_run_does_not_count(self):
        self.write_transcript([tool_use("t3", "python3 typecheck.py --list", "2026-11-10T10:07:00Z"),
                               tool_result("t3", "Would check 2 assemblies (x):", "2026-11-10T10:07:01Z")])
        self.assertEqual(self.stop()["decision"], "block")

    def test_silent_without_cs_edits(self):
        shutil.rmtree(self.reports)
        self.assertIsNone(self.stop())


class TypecheckRunsTests(HookTestCase):
    def test_runs_read_from_transcript_with_results(self):
        self.write_transcript([
            tool_use("a", "python3 Tools/unity-tools/typecheck.py", "2026-11-10T10:01:00Z"),
            tool_result("a", "All 3 assemblies type check clean.", "2026-11-10T10:01:04Z"),
            tool_use("b", "sed -n 1,20p Tools/unity-tools/typecheck.py", "2026-11-10T10:02:00Z"),
            tool_use("c", "python3 typecheck.py Foo", "2026-11-10T10:03:00Z"),
            tool_result("c", "error: unknown assembly: Foo", "2026-11-10T10:03:01Z"),
        ])
        runs = session_lifecycle.typecheck_runs(self.transcript, SESSION)
        self.assertEqual([(r["id"], r["result"]) for r in runs], [("a", "clean"), ("c", "error")])

    def test_classify(self):
        classify = session_lifecycle.classify_typecheck
        self.assertEqual(classify("No changed .cs files. Nothing to check."), "nothing_checked")
        self.assertEqual(classify("FAILED: A, B\n"), "failed: A, B")
        self.assertEqual(classify("Command running in background with ID: x"), "background")
        self.assertEqual(classify(""), "unknown")
        self.assertEqual(classify("Would check 2 assemblies (x):\n  A  3 sources"), "listed")

    def test_metrics_section(self):
        lines = session_lifecycle.typecheck_lines({"typecheck": {
            "baseline": {"when": "2026-11-10T10:00:00Z", "result": "clean", "seconds": 2.9, "file": self.cs},
            "runs": [{"when": "2026-11-10T10:06:00Z", "result": "clean"}], "end_check_blocks": 1,
            "lint": {"runs": 3, "violations": 2}}})
        text = "\n".join(lines)
        self.assertIn("## Typecheck", text)
        self.assertIn("clean (2.9s, Thing.cs)", text)
        self.assertIn("End-check blocks: 1", text)
        self.assertIn("cslint: 3 run(s), 2 violation(s)", text)
        self.assertIn("none (no .cs edit)", "\n".join(session_lifecycle.typecheck_lines({})))


if __name__ == "__main__":
    unittest.main()
