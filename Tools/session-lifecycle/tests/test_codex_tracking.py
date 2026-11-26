"""Synthetic Codex transcripts; no user's session or credentials are modified."""
import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import session_lifecycle as lifecycle
import codex_transcript


class CodexTrackingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        environment = patch.dict(os.environ, {"SESSION_MONITOR_STATE_ROOT": str(self.root / "monitor-cache")})
        environment.start()
        self.addCleanup(environment.stop)
        self.thread = "bbbbbbbb-0000-0000-0000-000000000000"
        self.rollout = self.root / ("rollout-2026-10-27-" + self.thread + ".jsonl")
        self.write([{"type": "session_meta", "payload": {"id": self.thread, "source": "cli"}},
                    {"type": "event_msg", "payload": {"type": "user_message", "message": "synthetic"}}])

    def write(self, entries):
        with self.rollout.open("w") as handle:
            for entry in entries:
                entry.setdefault("timestamp", "2026-10-27T12:00:00Z")
                handle.write(json.dumps(entry) + "\n")

    def test_exact_selection_and_missing_id(self):
        self.assertEqual(codex_transcript.locate(self.thread, self.root), str(self.rollout))
        self.assertIsNone(codex_transcript.locate("missing", self.root))
        self.assertEqual(lifecycle.user_turns(str(self.rollout)), 1)

    def test_environment_never_selects_a_newer_unrelated_session(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": self.thread}), \
             patch.object(codex_transcript, "locate", return_value=None):
            self.assertEqual(lifecycle.current_transcript(str(self.root)), (self.thread, None))

    def test_copied_metadata_does_not_attach_to_wrong_filename(self):
        other = self.root / "rollout-copy-bbbbbbbb-1111-1111-1111-111111111111.jsonl"
        other.write_text(self.rollout.read_text())
        self.assertEqual(codex_transcript.locate("bbbbbbbb-1111-1111-1111-111111111111", self.root), str(other))
        self.assertEqual(codex_transcript.locate(self.thread, self.root), str(self.rollout))
        self.assertFalse(codex_transcript.matches(str(other), self.thread))

    def test_guessed_codex_path_must_match_requested_thread(self):
        with patch.object(codex_transcript, "locate", return_value=None):
            self.assertIsNone(lifecycle.locate_transcript("different-thread", str(self.rollout)))

    def test_duplicate_match_is_refused(self):
        directory = self.root / "duplicate"
        directory.mkdir()
        (directory / self.rollout.name).write_text(self.rollout.read_text())
        with self.assertRaises(RuntimeError):
            codex_transcript.locate(self.thread, self.root)

    def test_nested_shell_trace_uses_agents_root_and_is_heuristic(self):
        rules = self.root / "Ext" / "Layer" / "Rules"
        rules.mkdir(parents=True)
        (rules / "MetaRouter.md").write_text("synthetic")
        (self.root / "AGENTS.md").write_text("Use `Ext/Layer/Rules/MetaRouter.md`.")
        self.write([{"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
                    "input": 'text(await tools.exec_command({cmd:"cat Ext/Layer/Rules/MetaRouter.md"}));'}}])
        with self.rollout.open("a") as handle:
            handle.write('{"partial":')
        state = {"session_id": self.thread, "transcript_path": str(self.rollout)}
        loads = lifecycle.router_trace(state, str(self.root))[1]
        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0]["via"], "main · Bash")

    def test_literal_batch_traces_only_existing_imported_files(self):
        rules = self.root / "Ext/Layer/Rules"
        rules.mkdir(parents=True)
        for name in ("MetaRouter.md", "CoreTags.md"):
            (rules / name).touch()
        (self.root / "Outside.md").touch()
        (self.root / "AGENTS.md").write_text("Use `Ext/Layer/Rules/MetaRouter.md`.")
        mapping = ".map(async f=>text((await tools.exec_command({cmd:`cat '${f}'`})).output))"
        source = ('await Promise.allSettled(["Ext/Layer/Rules/MetaRouter.md",'
                  '"Ext/Layer/Rules/CoreTags.md","Ext/Layer/Rules/Missing.md","Outside.md"]'
                  + mapping + ')')
        self.write([{"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
                    "input": source}}])
        state = {"session_id": self.thread, "transcript_path": str(self.rollout)}
        loads = lifecycle.router_trace(state, str(self.root))[1]
        self.assertEqual([(Path(row["file"]).name, row["via"]) for row in loads],
                         [("MetaRouter.md", "main · Bash"), ("CoreTags.md", "main · Bash")])
        self.assertEqual(list(codex_transcript.batched_cat_commands('computedPaths' + mapping)), [])

    def test_end_to_end_set_note_compile_and_claude_regression(self):
        with self.rollout.open("a") as handle:
            for total in (100, 100, 175, 175):
                handle.write(json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {
                    "total_token_usage": {"total_tokens": total, "input_tokens": total - 10,
                                          "cached_input_tokens": 30, "output_tokens": 10}}}}) + "\n")
        args = argparse.Namespace(reports_root=str(self.root / "reports"), session_id=self.thread,
                                  lane="other", work_type="other", name=None, feature=None,
                                  phase=None, title="Synthetic tracking")
        with patch.object(lifecycle, "locate_transcript", return_value=str(self.rollout)), \
             patch.object(lifecycle, "current_project_dir", return_value=str(self.root)):
            lifecycle.cmd_set(args)
            args.kind, args.source, args.text = "inaccuracy", "agent", "Synthetic correction"
            lifecycle.cmd_note(args)
            args.final = False
            lifecycle.cmd_compile(args)
        folder = lifecycle.find_folder(args.reports_root, self.thread)
        state = lifecycle.load_state(folder)
        self.assertEqual(state["agent"], "codex")
        self.assertEqual(len(state["inaccuracies"]), 1)
        self.assertIn("not yet supported for Codex", state["breakdown"]["error"])
        self.assertTrue(state["tokens"]["available"], state["tokens"])
        self.assertEqual(state["tokens"]["total_tokens"], 175)
        self.assertFalse((Path(folder) / "tokens" / "cache").exists())
        state["comparison"] = {"stale": True}
        with patch.object(lifecycle, "locate_transcript", return_value=str(self.rollout)):
            lifecycle.compile_folder(folder, state, str(self.root))
        self.assertNotIn("comparison", state)
        self.assertEqual(codex_transcript.normalize({"type": "assistant"}), {"type": "assistant"})

    def test_hook_payload_tracks_exact_path_without_environment(self):
        args = argparse.Namespace(reports_root=str(self.root / "hook-reports"))
        payload = {"session_id": self.thread, "transcript_path": str(self.rollout)}
        with patch.object(lifecycle, "read_hook_input", return_value=payload), \
             patch.object(lifecycle, "hook_project_dir", return_value=str(self.root)), \
             patch.object(lifecycle, "current_project_dir", return_value=str(self.root)), \
             patch.object(lifecycle, "current_transcript", return_value=(None, None)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                lifecycle.cmd_hook_start(args)
            self.assertIn(self.thread, output.getvalue())
            self.assertIsNone(lifecycle.find_folder(args.reports_root, self.thread))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                lifecycle.cmd_hook_stop(args)
            self.assertEqual(json.loads(output.getvalue()), {})
            folder = lifecycle.find_folder(args.reports_root, self.thread)
            self.assertIsNotNone(folder)
            self.assertEqual(lifecycle.load_state(folder)["agent"], "codex")
            lifecycle.cmd_hook_end(args)
            state = lifecycle.load_state(folder)
            self.assertIn("ended_at", state)
            self.assertEqual(state["transcript_path"], str(self.rollout))


if __name__ == "__main__":
    unittest.main()
