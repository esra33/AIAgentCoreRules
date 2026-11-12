"""token_breakdown's code-graph saving and missed index opportunities (grep over C#, codeindex chains,
whole-file .cs reads for shape), from a self-made transcript.

    python3 -m unittest discover -s Tools/session-lifecycle/tests -p 'test_*.py'
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))
import session_lifecycle  # noqa: E402
import token_breakdown  # noqa: E402

BIG_RESULT = "x" * 20000        # ~5,000 tokens


def assistant(message_id, tool_uses):
    return {"type": "assistant", "message": {
        "id": message_id, "usage": {"input_tokens": 1000, "output_tokens": 10},
        "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}
                    for tool_id, name, tool_input in tool_uses]}}


def result(tool_id, text):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": text}]}}


def bash(command):
    return ("Bash", {"command": command})


class CodeGraphBreakdownTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.transcript = os.path.join(self.folder, "session.jsonl")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def analyse(self, steps, grep_suggestions=session_lifecycle.type_grep_suggestions):
        """steps: [(tool name, input, result text)], one model call each, plus a closing call."""
        entries = []
        for index, (name, tool_input, text) in enumerate(steps):
            entries += [assistant("m%d" % index, [("t%d" % index, name, tool_input)]), result("t%d" % index, text)]
        entries.append(assistant("end", []))
        with open(self.transcript, "w") as handle:
            handle.write("\n".join(json.dumps(entry) for entry in entries) + "\n")
        return token_breakdown.analyse(self.transcript, "session", [], grep_suggestions)

    def test_code_graph_routes_count_as_a_saving(self):
        breakdown = self.analyse([
            bash('curl -s "$URL/api/type?name=IEventManager&members=0"') + ("{}",),
            bash('curl -s "$URL/api/graph?name=Screen&direction=down&depth=1"') + ("{}",),
            bash('curl -s "$URL/api/search?q=GemEvent"') + ("{}",)])
        saving = breakdown["savings"][token_breakdown.CODE_GRAPH_SAVING]
        self.assertEqual(saving["count"], 3)
        self.assertEqual(saving["round_trips"], 3 + 4 + 1)
        self.assertGreater(saving["tokens"], 0)
        self.assertIn("code-graph /api/type", breakdown["assumptions"])

    def test_doc_review_and_health_routes_are_not_lookups(self):
        breakdown = self.analyse([
            bash('curl -s "http://127.0.0.1:8000/api/sources?feature=X"') + ("{}",),
            bash('curl -s "$URL/api/health"') + ("{}",)])
        self.assertEqual(breakdown["savings"][token_breakdown.CODE_GRAPH_SAVING]["count"], 0)

    def test_only_a_curl_at_a_command_position_counts(self):
        breakdown = self.analyse([
            bash('git commit -m "counts curl /api/type as a saving"') + ("ok",),
            bash('echo "curl /api/type"') + ("ok",),
            bash('curl -s "$URL/api/type?name=X&members=0"') + ("{}",),
            bash('cd x && curl -s "$URL/api/graph?name=Y"') + ("{}",)])
        self.assertEqual(breakdown["savings"][token_breakdown.CODE_GRAPH_SAVING]["count"], 2)

    def test_type_grep_over_cs_is_missed_and_free_text_is_not(self):
        breakdown = self.analyse([
            bash('grep -rn "class LivesManager" Assets/Scripts') + (BIG_RESULT,),
            bash('grep -rn "could not load" Assets/Scripts') + (BIG_RESULT,)])
        missed = breakdown["missed"][token_breakdown.MISSED_GREP]
        self.assertEqual(missed["count"], 1)
        self.assertGreater(missed["tokens"], 0)
        self.assertIn("/api/type?name=LivesManager", missed["examples"][0])

    def test_without_a_grep_matcher_no_grep_is_missed(self):
        breakdown = self.analyse([bash('grep -rn "class LivesManager" Assets/Scripts') + (BIG_RESULT,)],
                                 grep_suggestions=None)
        self.assertEqual(breakdown["missed"][token_breakdown.MISSED_GREP]["count"], 0)

    def test_codeindex_chain_on_one_type(self):
        breakdown = self.analyse([
            bash("python3 tools/codeindex.py where Screen") + ("a",),
            bash("python3 tools/codeindex.py members Screen --inherited") + ("b",),
            bash("python3 tools/codeindex.py subclasses Screen") + ("c",),
            bash("python3 tools/codeindex.py where LivesManager") + ("d",),
            bash("python3 tools/codeindex.py show Screen.Open") + ("e",)])
        missed = breakdown["missed"][token_breakdown.MISSED_CHAIN]
        self.assertEqual(missed["count"], 1)
        self.assertEqual(missed["round_trips"], 2)
        self.assertIn("3 codeindex calls on `Screen`", missed["examples"][0])

    def test_whole_cs_read_without_edit_is_missed(self):
        shape = os.path.join(self.folder, "LivesManager.cs")
        edited = os.path.join(self.folder, "StoreManager.cs")
        breakdown = self.analyse([
            ("Read", {"file_path": shape}, BIG_RESULT),
            ("Read", {"file_path": edited}, BIG_RESULT),
            ("Edit", {"file_path": edited, "old_string": "a", "new_string": "b"}, "ok"),
            ("Read", {"file_path": shape, "offset": 10, "limit": 20}, BIG_RESULT)])
        missed = breakdown["missed"][token_breakdown.MISSED_READ]
        self.assertEqual(missed["count"], 1)
        self.assertIn("LivesManager.cs", missed["examples"][0])

    def test_metrics_lines_render_the_missed_table(self):
        breakdown = self.analyse([bash('grep -rn "class LivesManager" Assets/Scripts') + (BIG_RESULT,)])
        text = "\n".join(session_lifecycle.missed_lines(breakdown["missed"]))
        self.assertIn("| Type/member grep over C# | 1 |", text)
        self.assertIn("/api/type?name=LivesManager", text)
        self.assertIn("none", "\n".join(session_lifecycle.missed_lines(self.analyse([])["missed"])))


if __name__ == "__main__":
    unittest.main()
