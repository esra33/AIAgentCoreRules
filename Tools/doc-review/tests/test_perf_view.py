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
                           "Conversation growth": total - total // 10 - ad_hoc}}


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

    def test_active_session_with_a_known_model_gets_a_context_window_gauge(self):
        self.write_session("2026-11-17_0900_live", "eeeeeeee5", "2026-11-17T09:00:00-07:00", model="claude-sonnet-5",
                           breakdown=dict(breakdown(4000, 1000), last_context=150000))
        session = perf_view.build_model(self.root)["sessions"][0]
        self.assertEqual({"model": "claude-sonnet-5", "max": 300000, "used": 150000, "free": 150000, "share": 0.5},
                          session["context_window"])

    def test_ended_session_gets_no_context_window_gauge(self):
        self.write_session("2026-11-17_0900_done", "eeeeeeee5", "2026-11-17T09:00:00-07:00", model="claude-sonnet-5",
                           ended_at="2026-11-17T10:00:00-07:00", breakdown=dict(breakdown(4000, 1000), last_context=150000))
        session = perf_view.build_model(self.root)["sessions"][0]
        self.assertIsNone(session["context_window"])

    def test_active_session_without_a_recorded_model_gets_no_context_window_gauge(self):
        self.write_session("2026-11-17_0900_nomodel", "eeeeeeee5", "2026-11-17T09:00:00-07:00",
                           breakdown=dict(breakdown(4000, 1000), last_context=150000))
        session = perf_view.build_model(self.root)["sessions"][0]
        self.assertIsNone(session["context_window"])

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


class TestContextWarning(PerfViewTestCase):
    """Same threshold as hook-prompt: 90% of the median peak per-call context of finished sessions."""

    def write_finished(self, count, peak=100000):
        for index in range(count):
            self.write_session("2026-10-0%d_0900_done" % (index + 1), "f%07d" % index, "2026-10-0%dT09:00:00-07:00" % (index + 1),
                               age_seconds=86400, ended_at="x", breakdown=dict(breakdown(1000, 0), peak_context=peak))

    def write_live(self, last_context):
        self.write_session("2026-10-09_0900_live", "live0001", "2026-10-09T09:00:00-07:00",
                           breakdown=dict(breakdown(4000, 0), peak_context=last_context, last_context=last_context))

    def test_active_session_over_threshold_is_flagged(self):
        self.write_finished(5)
        self.write_live(95000)
        model = perf_view.build_model(self.root)
        self.assertEqual(90000, model["context_warning"]["threshold"])
        self.assertEqual(100000, model["context_warning"]["median_peak"])
        self.assertEqual(5, model["context_warning"]["sessions"])
        flags = {s["id"]: s["over_context"] for s in model["sessions"]}
        self.assertTrue(flags["live0001"])
        self.assertFalse(any(flag for sid, flag in flags.items() if sid != "live0001"))

    def test_active_session_peak_does_not_move_the_threshold(self):
        self.write_finished(5)
        self.write_live(900000)
        self.assertEqual(90000, perf_view.build_model(self.root)["context_warning"]["threshold"])

    def test_below_threshold_is_not_flagged(self):
        self.write_finished(5)
        self.write_live(85000)
        self.assertFalse(any(s["over_context"] for s in perf_view.build_model(self.root)["sessions"]))

    def test_too_few_finished_sessions_gives_no_threshold(self):
        self.write_finished(4)
        self.write_live(500000)
        model = perf_view.build_model(self.root)
        self.assertIsNone(model["context_warning"]["threshold"])
        self.assertFalse(any(s["over_context"] for s in model["sessions"]))

    def test_older_breakdowns_default_to_zero_context(self):
        self.write_three()
        session = perf_view.build_model(self.root)["sessions"][0]
        self.assertEqual((0, 0), (session["peak_context"], session["last_context"]))


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
        self.assertIn("function perfContextWarning(", page)
        source = json.loads(review_server._collect_sources(review_server._tabs([self.doc]))["d1"])
        self.assertIn("Runnable tools", source["standardized_names"])



def call(message_id, stamp, tokens):
    """One assistant transcript line: tokens split as 10 uncached input + the rest cache read."""
    iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(stamp))
    return json.dumps({"type": "assistant", "timestamp": iso, "message": {
        "id": message_id, "usage": {"input_tokens": 10, "cache_read_input_tokens": tokens - 10}}}) + "\n"


class TestCurrentUsage(PerfViewTestCase):
    NOW = time.mktime((2026, 11, 17, 12, 0, 0, 0, 0, -1))   # local noon, so "today" starts 12 h earlier

    def write_plan(self, captured_at, **limits):
        (self.root / "plan_usage.json").write_text(json.dumps({"captured_at": captured_at, "rate_limits": limits}))

    def test_no_capture_gives_no_plan(self):
        self.assertIsNone(perf_view.build_model(self.root, now=self.NOW)["current"]["plan"])

    def test_plan_keeps_open_windows_and_drops_reset_ones(self):
        self.write_plan(self.NOW - 60,
                        five_hour={"used_percentage": 23.5, "resets_at": self.NOW + 3600},
                        seven_day={"used_percentage": 41.2, "resets_at": self.NOW - 1},
                        spend_limit={"used_percentage": 62.8, "resets_at": self.NOW + 86400,
                                     "used_usd": 314.12, "limit_usd": 500, "period": "monthly"})
        plan = perf_view.build_model(self.root, now=self.NOW)["current"]["plan"]
        self.assertEqual([("five_hour", 23.5), ("spend_limit", 62.8)],
                         [(w["key"], w["used_percentage"]) for w in plan["windows"]])
        self.assertEqual((314.12, 500, "monthly"), (plan["windows"][1]["used_usd"], plan["windows"][1]["limit_usd"],
                                                    plan["windows"][1]["period"]))
        self.assertEqual((60, False), (plan["age_seconds"], plan["stale"]))

    def test_old_capture_is_stale(self):
        self.write_plan(self.NOW - perf_view.PLAN_STALE_SECONDS - 1, five_hour={"used_percentage": 5})
        self.assertTrue(perf_view.build_model(self.root, now=self.NOW)["current"]["plan"]["stale"])

    def test_plan_capture_is_watched(self):
        self.write_three()
        self.assertNotIn(self.root / "plan_usage.json", perf_view.watched_paths(self.root))
        self.write_plan(self.NOW, five_hour={"used_percentage": 5})
        self.assertIn(self.root / "plan_usage.json", perf_view.watched_paths(self.root))

    def test_burn_sums_main_and_subagent_calls_per_window(self):
        transcripts = self.root.parent / "transcripts"
        transcripts.mkdir()
        main = transcripts / "s1.jsonl"
        # 13 h ago (yesterday), 3 h ago, 30 min ago twice (same message id = one call), 10 min ago
        main.write_text(call("m0", self.NOW - 13 * 3600, 999) + call("m1", self.NOW - 3 * 3600, 100)
                        + call("m2", self.NOW - 1800, 200) + call("m2", self.NOW - 1799, 250)
                        + call("m3", self.NOW - 600, 300))
        subagents = transcripts / "s1" / "subagents"
        subagents.mkdir(parents=True)
        (subagents / "agent-x.jsonl").write_text(call("a1", self.NOW - 1200, 1000))
        state = self.write_session("2026-11-17_0900_burn", "s1", "2026-11-17T09:00:00-07:00", transcript_path=str(main))
        os.utime(state, (self.NOW, self.NOW))   # active is judged against the model's clock
        burn = perf_view.build_model(self.root, now=self.NOW)["current"]["burn"]
        windows = {w["key"]: (w["tokens"], w["calls"], w["sessions"]) for w in burn["windows"]}
        self.assertEqual({"last_hour": (1550, 3, 1), "last_5h": (1650, 4, 1), "today": (1650, 4, 1)}, windows)
        self.assertEqual(["last_hour", "last_5h", "today"], [w["key"] for w in burn["windows"]])
        self.assertEqual(1, burn["active_sessions"])

    def test_burn_skips_transcripts_untouched_in_the_window(self):
        old = self.root.parent / "old.jsonl"
        old.write_text(call("m1", self.NOW - 600, 100))
        stamp = self.NOW - 2 * 86400
        os.utime(old, (stamp, stamp))
        self.write_session("2026-11-15_0900_old", "s2", "2026-11-15T09:00:00-07:00", transcript_path=str(old))
        burn = perf_view.build_model(self.root, now=self.NOW)["current"]["burn"]
        self.assertEqual([0, 0, 0], [w["tokens"] for w in burn["windows"]])


if __name__ == "__main__":
    unittest.main()
