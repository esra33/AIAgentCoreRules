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
    with mock.patch.object(sys, "stdin", payload), contextlib.redirect_stdout(stdout):
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


if __name__ == "__main__":
    unittest.main()
