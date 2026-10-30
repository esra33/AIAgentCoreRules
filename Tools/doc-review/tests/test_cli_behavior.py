"""Category 2 (Behavior) tests for LocalDocReview -- U4, U6.

    python3 -m unittest discover -s Tools/doc-review/tests -p 'test_*.py'
"""
import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import doc_review  # noqa: E402
from doc_review import cmd_comments, cmd_stop, parse_listen_port, parse_server_processes  # noqa: E402
from sidecar_store import SidecarStore  # noqa: E402

DOC_CONTENT = (
    "# Design\n"
    "\n"
    "The quick brown fox jumps over the lazy dog.\n"
    "\n"
    "## Section Two\n"
    "\n"
    "Another distinct sentence lives here for testing purposes.\n"
)


def run_comments(doc_path: Path, status: str = "all") -> dict:
    args = argparse.Namespace(doc=str(doc_path), status=status, json=True)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cmd_comments(args)
    return json.loads(out.getvalue())


def run_comments_text(doc_path: Path, status: str) -> str:
    args = argparse.Namespace(doc=str(doc_path), status=status, json=False)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cmd_comments(args)
    return out.getvalue()


def doc_review_parser_status_default() -> str:
    # main() builds the parser inline; parse a real argv through it without dispatching.
    captured = {}
    capture = lambda args: captured.setdefault("status", args.status)  # noqa: E731
    with unittest.mock.patch.object(doc_review, "cmd_comments", capture), \
            unittest.mock.patch.object(sys, "argv", ["doc_review.py", "comments", "Design.md"]):
        doc_review.main()
    return captured["status"]


def line_of(text: str) -> int:
    return DOC_CONTENT.splitlines().index(text) + 1


class CommentsReadyFilterTests(unittest.TestCase):
    """U4: engineer marks threads Ready, agent runs `comments --status ready`."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-behavior-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.doc_path = self.tmp / "Design.md"
        self.doc_path.write_text(DOC_CONTENT)
        self.store = SidecarStore(self.doc_path)

    def add(self, quote: str, status: str) -> str:
        thread_id = self.store.add_thread(
            {"kind": "text", "file": self.doc_path.name, "quote": quote}, "engineer", "comment on: " + quote,
        )
        if status != "open":
            self.store.set_status(thread_id, status, "engineer")
        return thread_id

    def test_comments_filteredByReadyStatus_listsOnlyReadyThreadsResolvedToFileLine(self):
        open_quote = "The quick brown fox jumps over the lazy dog."
        ready_quote = "Another distinct sentence lives here for testing purposes."
        resolved_quote = "## Section Two"
        self.add(open_quote, "open")
        ready_id = self.add(ready_quote, "ready")
        self.add(resolved_quote, "resolved")

        result = run_comments(self.doc_path, status="ready")

        self.assertEqual(len(result["threads"]), 1, "only the ready thread must be listed, not open or resolved")
        listed = result["threads"][0]
        self.assertEqual(listed["id"], ready_id)
        self.assertEqual(listed["status"], "ready")
        self.assertEqual(listed["resolution"]["status"], "resolved",
                          "a live quote must resolve to a file:line, not be reported orphaned/ambiguous")
        self.assertEqual(listed["resolution"]["file"], self.doc_path.name)
        self.assertEqual(listed["resolution"]["line"], line_of(ready_quote),
                          "the resolved line must match where the quote actually lives in the doc")

    def test_comments_withStatusAll_listsEveryThreadRegardlessOfStatus(self):
        self.add("The quick brown fox jumps over the lazy dog.", "open")
        self.add("Another distinct sentence lives here for testing purposes.", "ready")
        self.add("## Section Two", "resolved")

        result = run_comments(self.doc_path, status="all")

        self.assertEqual(len(result["threads"]), 3, "--status all must not drop any thread")

    def test_comments_json_includesRepliesAndCreatedBy(self):
        thread_id = self.add("The quick brown fox jumps over the lazy dog.", "open")
        self.store.add_reply(thread_id, "agent", "done")

        listed = run_comments(self.doc_path)["threads"][0]

        self.assertEqual(listed["created_by"], "engineer")
        self.assertEqual([(r["author"], r["text"]) for r in listed["replies"]],
                         [("engineer", "comment on: The quick brown fox jumps over the lazy dog."), ("agent", "done")],
                         "--json must carry the reply bodies, not just the thread id and status")
        self.assertFalse(listed["follow_up"], "the agent spoke last -- nothing to follow up")

    def test_comments_engineerFollowUpOnAddressedThread_isSelectedByOpenFilter(self):
        thread_id = self.add("Another distinct sentence lives here for testing purposes.", "open")
        self.store.add_reply(thread_id, "agent", "fixed")
        self.store.set_status(thread_id, "addressed", "agent")
        self.store.add_reply(thread_id, "engineer", "not quite, also rename it")
        self.add("## Section Two", "resolved")

        result = run_comments(self.doc_path, status="open")

        self.assertEqual([t["id"] for t in result["threads"]], [thread_id],
                         "an engineer reply after the agent's must surface under --status open")
        self.assertTrue(result["threads"][0]["follow_up"])

    def test_comments_textMode_printsLastReplyUnderThread(self):
        thread_id = self.add("The quick brown fox jumps over the lazy dog.", "open")
        self.store.add_reply(thread_id, "agent", "done")
        self.store.add_reply(thread_id, "engineer", "one more thing")
        args = argparse.Namespace(doc=str(self.doc_path), status="all", json=False)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_comments(args)

        self.assertIn("last reply (follow-up) engineer: one more thing", out.getvalue())

    def test_comments_textMode_printsOriginalCommentBeforeLastReply(self):
        quote = "The quick brown fox jumps over the lazy dog."
        thread_id = self.add(quote, "open")
        self.store.add_reply(thread_id, "agent", "done")
        text = run_comments_text(self.doc_path, status="all")

        self.assertIn("comment engineer: comment on: " + quote, text,
                      "the original ask must stay visible once the thread has replies")
        self.assertLess(text.index("comment engineer:"), text.index("last reply agent: done"))

    def test_comments_textMode_singleComment_printsNoSeparateLastReply(self):
        self.add("The quick brown fox jumps over the lazy dog.", "open")

        text = run_comments_text(self.doc_path, status="all")

        self.assertNotIn("last reply", text, "a lone comment is not repeated as its own last reply")


class CommentsActionableDefaultTests(unittest.TestCase):
    """The default filter lists only threads that still need the agent."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-behavior-actionable-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.doc_path = self.tmp / "Design.md"
        self.doc_path.write_text(DOC_CONTENT)
        self.store = SidecarStore(self.doc_path)

    def add(self, quote: str, status: str) -> str:
        thread_id = self.store.add_thread({"kind": "text", "file": self.doc_path.name, "quote": quote}, "engineer", "c")
        if status != "open":
            self.store.set_status(thread_id, status, "engineer" if status != "addressed" else "agent")
        return thread_id

    def test_comments_parserDefault_isActionable(self):
        self.assertEqual(doc_review_parser_status_default(), "actionable",
                         "a bare `comments <doc>` must list only what still needs the agent")

    def test_comments_actionable_listsOpenReadyAndFollowUps_hidesAddressedAndResolved(self):
        open_id = self.add("The quick brown fox jumps over the lazy dog.", "open")
        ready_id = self.add("Another distinct sentence lives here for testing purposes.", "ready")
        follow_up_id = self.add("## Section Two", "open")
        self.store.add_reply(follow_up_id, "agent", "fixed")
        self.store.set_status(follow_up_id, "addressed", "agent")
        self.store.add_reply(follow_up_id, "engineer", "not quite")
        self.add("# Design", "addressed")
        resolved_id = self.add("The quick brown fox jumps over the lazy dog.", "open")
        self.store.set_status(resolved_id, "resolved", "engineer")

        result = run_comments(self.doc_path, status="actionable")

        self.assertEqual(sorted(t["id"] for t in result["threads"]), sorted([open_id, ready_id, follow_up_id]))
        self.assertEqual(result["hidden"], 2, "the addressed and resolved threads are counted, not listed")

    def test_comments_textMode_withHiddenThreads_printsHiddenCountLine(self):
        self.add("The quick brown fox jumps over the lazy dog.", "open")
        resolved_id = self.add("## Section Two", "open")
        self.store.set_status(resolved_id, "resolved", "engineer")

        text = run_comments_text(self.doc_path, status="actionable")

        self.assertIn("1 threads hidden by --status actionable -- --status all to list them", text)

    def test_comments_textMode_nothingHidden_printsNoHiddenLine(self):
        self.add("The quick brown fox jumps over the lazy dog.", "open")

        self.assertNotIn("hidden", run_comments_text(self.doc_path, status="actionable"))


class InlineMarkerTests(unittest.TestCase):
    """U6: a quick @CLAUDE note in the source is listed alongside sidecar threads."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-behavior-markers-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.doc_path = self.tmp / "Design.md"
        self.diagrams_dir = self.tmp / "Diagrams"
        self.diagrams_dir.mkdir()
        self.diagram_path = self.diagrams_dir / "flow.mmd"

    def test_comments_withInlineMarkersInDocAndDiagram_listsBothAlongsideSidecarThreads(self):
        self.doc_path.write_text(
            "# Design\n\n<!-- @CLAUDE: tighten this paragraph -->\n\nSome body text.\n"
        )
        self.diagram_path.write_text("graph TD\n  A --> B\n%% @CLAUDE: rename node A\n")
        # No sidecar file exists at all yet -- markers must still surface with zero threads.

        result = run_comments(self.doc_path, status="ready")

        self.assertEqual(result["threads"], [], "no threads exist yet -- the ready filter must find none")
        markers_by_file = {m["file"]: m for m in result["inline_markers"]}
        self.assertIn(self.doc_path.name, markers_by_file, "the doc's own inline marker must be discovered")
        self.assertEqual(markers_by_file[self.doc_path.name]["text"], "tighten this paragraph")
        diagram_rel = str(self.diagram_path.relative_to(self.tmp))
        self.assertIn(diagram_rel, markers_by_file,
                      "a diagram under Diagrams/ must be auto-discovered without being a comment anchor")
        self.assertEqual(markers_by_file[diagram_rel]["text"], "rename node A")


PS_OUTPUT = """\
  101 /bin/bash -c cd /x && python3 /t/doc_review.py serve A_GDD.md --port 8765 > server.log 2>&1
  102 /Library/Python.app/Contents/MacOS/Python /t/doc_review.py serve A_GDD.md --port 8765
  103 python3 /t/doc_review.py serve B_TDD.md Diagrams/x.mmd --open
  104 python3 /t/doc_review.py serve C.md --static
  105 python3 /t/doc_review.py comments A_GDD.md
  106 vim doc_review.py
"""


class ServerListingTests(unittest.TestCase):
    """servers / stop: only live Python servers, never the launching shell or a static render."""

    def test_parse_server_processes_skips_shells_static_renders_and_other_subcommands(self):
        self.assertEqual(parse_server_processes(PS_OUTPUT), [{"pid": 102, "doc": "A_GDD.md"}, {"pid": 103, "doc": "B_TDD.md"}])

    def test_parse_listen_port_reads_the_lsof_name_field(self):
        self.assertEqual(parse_listen_port("p102\nf3\nn127.0.0.1:8765\n"), 8765)
        self.assertIsNone(parse_listen_port("p102\n"))

    def run_stop(self, servers, **selector):
        args = argparse.Namespace(**{"port": None, "pid": None, "all": False, **selector})
        killed = []
        real_running, real_kill = doc_review.running_servers, doc_review.os.kill
        doc_review.running_servers = lambda: servers
        doc_review.os.kill = lambda pid, sig: killed.append(pid)
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cmd_stop(args)
        except SystemExit:
            killed.append("exit")
        finally:
            doc_review.running_servers, doc_review.os.kill = real_running, real_kill
        return killed

    def test_stop_without_a_selector_stops_the_only_server_and_refuses_when_several(self):
        one = [{"pid": 7, "port": 8765, "doc": "A.md", "cwd": "/x"}]
        two = one + [{"pid": 8, "port": None, "doc": "B.md", "cwd": "/y"}]
        self.assertEqual(self.run_stop(one), [7])
        self.assertEqual(self.run_stop(two), ["exit"])
        self.assertEqual(self.run_stop(two, port=8765), [7])  # a port-less server never matches --port
        self.assertEqual(self.run_stop(two, pid=8), [8])
        self.assertEqual(self.run_stop(two, all=True), [7, 8])
        self.assertEqual(self.run_stop([]), ["exit"])


if __name__ == "__main__":
    unittest.main()
