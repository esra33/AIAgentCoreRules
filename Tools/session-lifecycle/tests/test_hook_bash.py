"""hook-bash, audit 2026-11-10: a grep over C# for a type or member name gets the codeindex/usages
command that answers it; free-text greps, greps of command output and non-C# greps stay silent."""
import argparse
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import session_lifecycle  # noqa: E402


def hook(command):
    stdout = io.StringIO()
    payload = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
    # cmd_hook_bash now logs a firing to hooks.log (token-usage savings pass, 2026-11-17 end-session
    # follow-up); hook_log is stubbed out here so this module-level helper never resolves reports_root
    # against the real project and writes into its live GitIgnoreReports/Sessions/hooks.log.
    with mock.patch.object(sys, "stdin", payload), contextlib.redirect_stdout(stdout), \
         mock.patch.object(session_lifecycle, "hook_log"):
        assert session_lifecycle.cmd_hook_bash(argparse.Namespace(reports_root=None)) == 0
    text = stdout.getvalue()
    return json.loads(text)["hookSpecificOutput"]["additionalContext"] if text else ""


class TypeGrepTests(unittest.TestCase):
    def test_declaration_greps_suggest_where_and_show(self):
        cases = {
            'grep -rl "class LivesManager\\b" Assets --include=*.cs': "LivesManager",
            'grep -rn --include=*.cs -E "interface IStateMachine\\b" ..': "IStateMachine",
            "grep -rn 'enum EventStatus' -A14 Assets/Plugins/JamCity/Disney.RainbowCore.Events": "EventStatus",
            'rg -t cs "struct\\s+LevelEndMessage"': "LevelEndMessage",
            'grep -rl "class Skinner<" Assets/Scripts': "Skinner",
        }
        for command, name in cases.items():
            with self.subTest(command=command):
                context = hook(command)
                self.assertIn("codeindex.py where %s" % name, context)
                self.assertIn("codeindex.py show %s" % name, context)

    def test_bare_names_suggest_usages(self):
        for command, name in {
            'grep -rln "IAuthPlayerData" --include=*.cs Assets': "IAuthPlayerData",
            'grep -rn "FetchEvents()" Assets/Scripts --include=*.cs': "FetchEvents",
            'grep -rn "LevelEndMessage(" Assets/Scripts --include=*.cs': "LevelEndMessage",
            'grep -n "GZipStream" Assets/Plugins/JamCity/Zlib/ZlibBaseStream.cs': "GZipStream",
        }.items():
            with self.subTest(command=command):
                self.assertIn("usages.py %s" % name, hook(command))

    def test_attribute_grep_suggests_attributed(self):
        self.assertIn("codeindex.py attributed RootPlayerData",
                      hook('grep -rn "\\[RootPlayerData" --include=*.cs Assets/Plugins'))

    def test_alternation_yields_one_suggestion_per_name(self):
        context = hook('grep -rnE "class Foo|interface IBar" Assets/Scripts')
        self.assertIn("where Foo", context)
        self.assertIn("where IBar", context)

    def test_suggested_path_is_literal(self):
        context = hook('grep -rl "class LivesManager" Assets')
        self.assertNotIn("$", context)
        self.assertIn("unity-tools/codeindex.py", context)

    def test_free_text_output_and_non_csharp_greps_are_silent(self):
        for command in (
            'grep -rn "Config service unavailable" Assets --include=*.cs',
            'grep -rn "#if !RC" Assets/Scripts/Editor',
            'grep -rn "EVENT_TIMER" Assets/Scripts --include=*.cs',
            'grep -rn "class LivesManager" Rules/',
            'git log --oneline | grep "class Foo"',
            "cat Assets/Scripts/Foo.cs | grep LivesManager",
            'echo "grep -rn class Foo Assets"',
            "grep -rn 'unbalanced Assets",
        ):
            with self.subTest(command=command):
                self.assertEqual(hook(command), "")

    def test_rule_read_reminder_still_fires_alongside(self):
        context = hook('sed -n 1,5p Rules/CoreTags.md; grep -rl "class Foo" Assets')
        self.assertIn("Rules/CoreTags.md", context)
        self.assertIn("codeindex.py where Foo", context)


class FeatureDocReadTests(unittest.TestCase):
    """Token-usage savings pass, 2026-11-17: a feature doc (TDD, progress, checkpoint JSON) read
    via cat/sed/head/tail/grep bypasses Read's limit/offset and the partial-file-read saving."""

    def test_cat_of_a_tdd_gets_the_reminder(self):
        context = hook("cat Assets/GitIgnoreAssets/Features/Thing/Thing_TDD.md")
        self.assertIn("Features/Thing/Thing_TDD.md", context)
        self.assertIn("limit/offset", context)

    def test_grep_context_of_a_progress_file_gets_the_reminder(self):
        context = hook('grep -A5 "Phase 4" Assets/GitIgnoreAssets/Features/Thing/Thing_Progress.md')
        self.assertIn("Thing_Progress.md", context)

    def test_head_of_a_checkpoint_json_gets_the_reminder(self):
        context = hook("head -c 2000 Assets/GitIgnoreAssets/Features/Thing/Thing_Checkpoint.json")
        self.assertIn("Thing_Checkpoint.json", context)

    def test_non_feature_doc_reads_are_silent(self):
        for command in (
            "cat Assets/Scripts/Foo.cs",
            "cat Assets/GitIgnoreAssets/features/thing/thing_tdd.md",
            "git log --oneline Assets/GitIgnoreAssets/Features/Thing/Thing_TDD.md",
        ):
            with self.subTest(command=command):
                self.assertEqual(hook(command), "")

    def test_quoted_or_heredoc_mentions_are_silent(self):
        for command in (
            'echo "cat Assets/GitIgnoreAssets/Features/Thing/Thing_TDD.md"',
            "cat > t.md <<'EOF'\nsed -n 1,5p Features/Thing/Thing_Progress.md\nEOF\npython3 t.py",
        ):
            with self.subTest(command=command):
                self.assertEqual(hook(command), "")

    def test_feature_doc_and_type_grep_reminders_coexist(self):
        context = hook('cat Assets/GitIgnoreAssets/Features/Thing/Thing_TDD.md; grep -rl "class Foo" Assets')
        self.assertIn("Thing_TDD.md", context)
        self.assertIn("codeindex.py where Foo", context)


if __name__ == "__main__":
    unittest.main()
