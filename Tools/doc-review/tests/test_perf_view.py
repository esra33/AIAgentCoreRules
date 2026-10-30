"""Performance tab tests: perf_view.py's model (newest-first sessions, overview statistics, active
session, uncompiled sessions) built from self-made session folders, plus the server's tab wiring.

    python3 -m unittest discover -s Tools/doc-review/tests -p 'test_*.py'
"""
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import perf_view  # noqa: E402
import review_server  # noqa: E402


def breakdown(total, ad_hoc, calls=10):
    return {"estimated": True, "total": total, "calls": calls, "standardized": total // 10,
            "categories": {"Runnable tools": total // 10, "Ad-hoc tool calls": ad_hoc,
                           "Conversation & base context": total - total // 10 - ad_hoc}}


class PerfViewTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()) / "GitIgnoreReports" / "Sessions"
        self.root.mkdir(parents=True)
        self.doc = self.root.parent.parent / "doc.md"
        self.doc.write_text("# Doc\n")
        self.env = mock.patch.dict(os.environ, {"SESSION_REPORTS_ROOT": str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root.parent.parent, ignore_errors=True)

    def write_session(self, folder, session_id, started_at, age_seconds=0, **state):
        path = self.root / folder / "session.json"
        path.parent.mkdir()
        path.write_text(json.dumps(dict(session_id=session_id, started_at=started_at, **state)))
        stamp = time.time() - age_seconds
        os.utime(path, (stamp, stamp))
        return path

    def write_three(self):
        self.write_session("2026-10-01_0900_old", "aaaaaaaa1", "2026-10-01T09:00:00-07:00", age_seconds=86400,
                           title="Old", lane="bug_fix", ended_at="2026-10-01T10:00:00-07:00",
                           breakdown=breakdown(1000, 200))
        self.write_session("2026-10-03_0900_live", "cccccccc3", "2026-10-03T09:00:00-07:00",
                           title="Live", lane="small_task", breakdown=breakdown(4000, 1000))
        self.write_session("2026-10-02_0900_none", "bbbbbbbb2", "2026-10-02T09:00:00-07:00", age_seconds=86400,
                           title="Never compiled", breakdown={"error": "no transcript"})


class TestModel(PerfViewTestCase):
    def test_sessions_are_newest_first(self):
        self.write_three()
        model = perf_view.build_model(self.root)
        self.assertEqual(["cccccccc", "bbbbbbbb", "aaaaaaaa"], [s["id"] for s in model["sessions"]])

    def test_active_needs_no_ended_at_and_a_recent_write(self):
        self.write_three()
        self.write_session("2026-09-30_0900_stale", "dddddddd4", "2026-09-30T09:00:00-07:00",
                           age_seconds=perf_view.ACTIVE_WINDOW_SECONDS + 60, breakdown=breakdown(500, 0))
        active = {s["id"]: s["active"] for s in perf_view.build_model(self.root)["sessions"]}
        self.assertEqual({"cccccccc": True, "bbbbbbbb": False, "aaaaaaaa": False, "dddddddd": False}, active)

    def test_overview_skips_uncompiled_sessions(self):
        self.write_three()
        overview = perf_view.build_model(self.root)["overview"]
        self.assertEqual((3, 2, 5000), (overview["sessions"], overview["compiled"], overview["total"]))
        self.assertEqual(2500, overview["mean"])
        self.assertAlmostEqual(statistics.pstdev([1000, 4000]), overview["stdev"])
        self.assertEqual([1000, 4000], sorted(point["total"] for point in overview["totals"]))

    def test_overview_category_totals_and_averages(self):
        self.write_three()
        categories = {c["name"]: c for c in perf_view.build_model(self.root)["overview"]["categories"]}
        self.assertEqual(1200, categories["Ad-hoc tool calls"]["tokens"])
        self.assertEqual(600, categories["Ad-hoc tool calls"]["average"])
        self.assertAlmostEqual(1200 / 5000, categories["Ad-hoc tool calls"]["share"])

    def test_uncompiled_session_keeps_its_error(self):
        self.write_three()
        session = next(s for s in perf_view.build_model(self.root)["sessions"] if s["id"] == "bbbbbbbb")
        self.assertEqual((False, "no transcript", []), (session["compiled"], session["error"], session["categories"]))

    def test_unreadable_session_json_is_skipped(self):
        self.write_three()
        (self.root / "broken").mkdir()
        (self.root / "broken" / "session.json").write_text("{not json")
        self.assertEqual(3, len(perf_view.build_model(self.root)["sessions"]))

    def test_no_compiled_sessions_gives_zero_overview(self):
        self.write_session("x", "eeeeeeee5", "2026-10-01T09:00:00-07:00")
        overview = perf_view.build_model(self.root)["overview"]
        self.assertEqual((0, 0, 0.0, []), (overview["compiled"], overview["total"], overview["mean"], overview["categories"]))

    def test_doc_review_block_defaults_to_zero_for_older_breakdowns(self):
        self.write_three()
        session = perf_view.build_model(self.root)["sessions"][0]
        self.assertEqual((0, 0, 0, {"count": 0, "tokens": 0}),
                         (session["doc_review"]["count"], session["doc_review"]["tokens"],
                          session["doc_review"]["equivalent"], session["doc_review"]["miro_confluence"]))

    def test_overview_sums_doc_review_and_measured_miro_confluence(self):
        self.write_three()
        with_preview = dict(breakdown(2000, 500), doc_review={
            "count": 3, "tokens": 900, "equivalent": 40000, "round_trips": 6, "commands": {"serve": 2, "reply": 1},
            "miro_confluence": {"count": 0, "tokens": 0}})
        with_mcp = dict(breakdown(3000, 500), doc_review={
            "count": 1, "tokens": 100, "equivalent": 2400, "round_trips": 2, "commands": {"comments": 1},
            "miro_confluence": {"count": 4, "tokens": 25000}})
        self.write_session("2026-10-04_0900_a", "ffffffff6", "2026-10-04T09:00:00-07:00", age_seconds=86400,
                           ended_at="2026-10-04T10:00:00-07:00", breakdown=with_preview)
        self.write_session("2026-10-05_0900_b", "gggggggg7", "2026-10-05T09:00:00-07:00", age_seconds=86400,
                           ended_at="2026-10-05T10:00:00-07:00", breakdown=with_mcp)
        doc_review = perf_view.build_model(self.root)["overview"]["doc_review"]
        self.assertEqual((2, 4, 1000, 42400, 8), (doc_review["sessions"], doc_review["count"], doc_review["tokens"],
                                                  doc_review["equivalent"], doc_review["round_trips"]))
        self.assertEqual({"sessions": 1, "count": 4, "tokens": 25000}, doc_review["miro_confluence"])


class TestFeatureScope(PerfViewTestCase):
    def write_progress(self, sessions_text):
        path = self.root.parent.parent / "Demo_Progress.md"
        path.write_text('feature:        "Demo"\ncurrent_phase:  "3_design"\n' + sessions_text + "status: in_progress\n")
        return path

    def write_feature_sessions(self):
        self.write_three()
        self.write_session("2026-10-04_0900_feature_dddddddd", "dddddddd4", "2026-10-04T09:00:00-07:00",
                           age_seconds=86400, feature="Demo", breakdown=breakdown(2000, 100))
        self.write_session("2026-10-05_0900_other_eeeeeeee", "eeeeeeee5", "2026-10-05T09:00:00-07:00",
                           age_seconds=86400, feature="Other", breakdown=breakdown(8000, 100))

    def in_feature(self, progress):
        model = perf_view.build_model(self.root, progress_path=progress)
        return model, sorted(s["id"] for s in model["sessions"] if s["in_feature"])

    def test_no_progress_file_means_no_feature(self):
        self.write_feature_sessions()
        model, ids = self.in_feature(None)
        self.assertEqual(("", [], 0), (model["feature"], ids, model["feature_overview"]["sessions"]))

    def test_tagged_and_inline_listed_sessions_belong(self):
        self.write_feature_sessions()
        progress = self.write_progress('sessions:       ["2026-10-01_0900_bug-fix_aaaaaaaa"]   # renamed "x_ffffffff" ignored\n')
        model, ids = self.in_feature(progress)
        self.assertEqual(("Demo", ["aaaaaaaa", "dddddddd"]), (model["feature"], ids))
        self.assertEqual((2, 3000), (model["feature_overview"]["sessions"], model["feature_overview"]["total"]))
        self.assertEqual(5, model["overview"]["sessions"])

    def test_block_list_with_comments(self):
        self.write_feature_sessions()
        progress = self.write_progress('sessions:\n  - "2026-10-03_0900_small-task_cccccccc"   # a "note"\n'
                                       '  - "2026-10-02_0900_other_bbbbbbbb"\n')
        self.assertEqual(["bbbbbbbb", "cccccccc", "dddddddd"], self.in_feature(progress)[1])

    def test_lines_after_the_block_are_not_sessions(self):
        self.write_feature_sessions()
        progress = self.write_progress('sessions:\n  - "2026-10-03_0900_small-task_cccccccc"\n'
                                       'notes: "2026-10-02_0900_other_bbbbbbbb"\n')
        self.assertEqual(["cccccccc", "dddddddd"], self.in_feature(progress)[1])

    def test_server_scopes_the_tab_to_the_progress_file(self):
        self.write_feature_sessions()
        progress = self.write_progress('sessions: []\n')
        doc = progress.parent / "Demo_TDD.md"
        doc.write_text("# TDD\n")
        tab = review_server._tabs([doc])[-1]
        self.assertEqual(progress.resolve(), tab["progress"])
        self.assertEqual("Demo", json.loads(review_server._tab_source(tab))["feature"])
        before = review_server._tab_mtime(tab)
        os.utime(progress, (before + 5, before + 5))
        self.assertEqual(before + 5, review_server._tab_mtime(tab))


class TestServerTab(PerfViewTestCase):
    def test_no_sessions_means_no_tab(self):
        self.assertIsNone(perf_view.find_reports_root(self.doc))
        self.assertNotIn("perf", [tab["kind"] for tab in review_server._tabs([self.doc])])

    def test_tab_is_added_last(self):
        self.write_three()
        tabs = review_server._tabs([self.doc])
        self.assertEqual(["md", "perf"], [tab["kind"] for tab in tabs])
        self.assertEqual("Performance", tabs[-1]["title"])

    def test_tab_mtime_follows_a_recompiled_session(self):
        self.write_three()
        tab = review_server._tabs([self.doc])[-1]
        before = review_server._tab_mtime(tab)
        path = self.root / "2026-10-01_0900_old" / "session.json"
        os.utime(path, (before + 5, before + 5))
        self.assertEqual(before + 5, review_server._tab_mtime(tab))

    def test_page_renders_the_perf_tab(self):
        self.write_three()
        page = review_server.build_page([self.doc], live=False)
        self.assertIn('class="perf-view"', page)
        self.assertIn("function renderPerf(", page)
        self.assertIn("function perfDocReview(", page)
        source = json.loads(review_server._collect_sources(review_server._tabs([self.doc]))["d1"])
        self.assertIn("Runnable tools", source["standardized_names"])


if __name__ == "__main__":
    unittest.main()
