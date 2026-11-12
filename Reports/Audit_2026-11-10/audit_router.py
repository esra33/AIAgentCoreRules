#!/usr/bin/env python3
"""Read-only audit of AI-agent rules framework usage from session metrics.

Reads  GitIgnoreReports/Sessions/*/{session.json,metrics.md,retro.md,context-warning.json} + hooks.log
and the rule repos (git for file creation dates). Writes only the markdown report given by --out.
"""
import argparse, collections, datetime, glob, json, os, re, statistics, subprocess

SESS = "/Users/aramirez/Documents/Projects/TripleMatch3D/GitIgnoreReports/Sessions"
CORE = "/Users/aramirez/Documents/Projects/AIAgentCoreRules"
META = "/Users/aramirez/Documents/Projects/TripleMatchAiMetaData"
OUT = "/Users/aramirez/.claude/jobs/b2cfdac5/tmp/audit_router.md"

LANE_PROCESS = {
    "small_task": "AIAgentCoreRules/Processes/SmallTask.md",
    "large_task": "AIAgentCoreRules/Processes/LargeTask.md",
    "bug_fix": "AIAgentCoreRules/Processes/BugFix.md",
    "investigation": "AIAgentCoreRules/Rules/InvestigationMode.md",
    "feature": "AIAgentCoreRules/Processes/CreateFeature/index.md",
}
# Mechanical subset of each lane's Router check expected_loads (the rest are conditional / semantic).
LANE_EXPECTED = {
    "small_task": [LANE_PROCESS["small_task"], "AIAgentCoreRules/Rules/CodingStandards.md*", "Systems/*"],
    "large_task": [LANE_PROCESS["large_task"], "AIAgentCoreRules/Rules/ChangeClassification.md",
                   "AIAgentCoreRules/Rules/CodingStandards.md*", "Systems/*"],
    "bug_fix": [LANE_PROCESS["bug_fix"], "AIAgentCoreRules/Rules/CodingStandards.md*",
                "AIAgentCoreRules/Rules/TestingRules.md*", "TripleMatchAiMetaData/Rules/TestingSetup.md*", "Systems/*"],
    "investigation": [LANE_PROCESS["investigation"], "Systems/*"],
    "feature": [LANE_PROCESS["feature"], "AIAgentCoreRules/Processes/CreateFeature/Phase*"],
}
ALWAYS_ON = {"AIAgentCoreRules/Rules/MetaRouter.md", "AIAgentCoreRules/Rules/StopAndVerify.md",
             "AIAgentCoreRules/Rules/CoreTags.md", "TripleMatchAiMetaData/Rules/MagicMatchProjectRules.md",
             "TripleMatchAiMetaData/SystemIndex.md"}
CHANGE_POINTS = [("2026-10-16", "BugFix meta-retro changes"), ("2026-10-20", "multi-retro + meta retro"),
                 ("2026-10-28", "wave of retro-applied SmallTask/end-session changes"),
                 ("2026-11-05", "LargeTask lane added")]


def pct(a, b):
    return "%.0f%%" % (100.0 * a / b) if b else "–"


def quant(values, q):
    values = sorted(values)
    if not values:
        return 0
    k = (len(values) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def fmt(n):
    if n is None:
        return "–"
    n = float(n)
    if n >= 1e6:
        return "%.1fM" % (n / 1e6)
    if n >= 1e3:
        return "%.0fk" % (n / 1e3)
    return "%.0f" % n


def norm(path):
    for repo in ("AIAgentCoreRules/", "TripleMatchAiMetaData/"):
        i = path.find(repo)
        if i >= 0:
            return path[i:]
    return path


def week_of(date):
    d = datetime.date.fromisoformat(date)
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def git_first_dates(repo, rels):
    out = {}
    for rel in rels:
        try:
            r = subprocess.run(["git", "-C", repo, "log", "--diff-filter=A", "--follow", "--format=%ad",
                                "--date=short", "--", rel], capture_output=True, text=True, timeout=30)
            dates = r.stdout.split()
            out[rel] = dates[-1] if dates else None
        except Exception:
            out[rel] = None
    return out


def inventory():
    files = {}
    pats = [(CORE, "AIAgentCoreRules", ["Rules/*.md", "Processes/*.md", "Processes/**/*.md"]),
            (META, "TripleMatchAiMetaData", ["Rules/*.md", "Systems/*.md", "Systems/**/*.md",
                                             "SystemPatterns/*.md", "SystemIndex.md"])]
    for repo, name, globs in pats:
        rels = set()
        for g in globs:
            for p in glob.glob(os.path.join(repo, g), recursive=True):
                rels.add(os.path.relpath(p, repo))
        dates = git_first_dates(repo, sorted(rels))
        for rel in rels:
            files["%s/%s" % (name, rel)] = {"created": dates.get(rel), "bytes": os.path.getsize(os.path.join(repo, rel))}
    return files


def parse_metrics(path):
    text = open(path, encoding="utf-8").read()
    m = {"loads": [], "tools": {}, "lane_changes": [], "ended": None, "has_trace": "## Router trace" in text}
    sec = re.search(r"Loaded on demand, in order:(.*?)(\n## |\Z)", text, re.S)
    if sec:
        for line in sec.group(1).splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[0].isdigit():
                m["loads"].append({"file": norm(cells[2].strip("`")), "via": cells[3], "at": cells[1]})
    rt = re.search(r"## Runnable tools(.*?)(\n## |\Z)", text, re.S)
    if rt:
        for tool, n in re.findall(r"`([\w.]+)` × (\d+)", rt.group(1)):
            m["tools"][tool] = int(n)
    lc = re.search(r"## Lane changes(.*?)(\n## |\Z)", text, re.S)
    if lc:
        m["lane_changes"] = [l for l in lc.group(1).splitlines() if l.startswith("- ") and "none" not in l]
    e = re.search(r"\| Ended \| (.*?) \|", text)
    m["ended"] = e.group(1) if e else None
    return m


def classify_loaded(cell):
    c = re.sub(r"[*_`]", "", cell).strip().lower()
    if c.startswith(("✓", "✅")):
        return "yes"
    if c.startswith(("grep only", "equivalent")):
        return "partly"
    if c.startswith(("not run", "not used", "skipped") ) and "correct" not in c:
        return "no"
    for key in ("n/a", "not expected", "not applicable", "not needed", "not due", "—", "none", "correctly", "skipped, correctly"):
        if c.startswith(key):
            return "n/a"
    if re.match(r"^\W*yes\b", c) or c.startswith("✓") or c.startswith("loaded"):
        return "yes" if "late" not in c else "late"
    if c.startswith("late"):
        return "late"
    if c.startswith("partly") or c.startswith("partial"):
        return "partly"
    if c.startswith("ignored"):
        return "ignored"
    if re.match(r"^\W*no\b", c) or c.startswith("✗") or c.startswith("missed") or c.startswith("not loaded"):
        return "no"
    return "other"


PATH_TOKEN = re.compile(r"(?:Rules|Processes|Systems|SystemPatterns|Skills|Tools)/[A-Za-z0-9_./-]+|[A-Za-z0-9_-]+\.(?:md|py)\b|/[a-z-]+")


def parse_retro(path):
    text = open(path, encoding="utf-8").read()
    sec = re.search(r"^## Router check[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    rows = []
    if not sec:
        return None
    for line in sec.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0].lower().startswith("expected"):
            continue
        item = re.sub(r"[*`]", "", cells[0]).strip()
        tok = PATH_TOKEN.search(item)
        key = tok.group(0) if tok else item[:60]
        key = key.split("/")[-1] if key.startswith(("Rules/", "Processes/", "Systems/", "SystemPatterns/")) and False else key
        rows.append({"item": item, "key": key, "status": classify_loaded(cells[1])})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", default=SESS)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    files = inventory()
    sessions = []
    health = collections.defaultdict(list)
    for folder in sorted(glob.glob(os.path.join(args.sessions, "*/"))):
        name = os.path.basename(folder.rstrip("/"))
        sj = os.path.join(folder, "session.json")
        mm = os.path.join(folder, "metrics.md")
        if not os.path.isfile(sj):
            health["no session.json (not a session folder?)"].append(name)
            continue
        st = json.load(open(sj))
        date = name[:10]
        parts = name.split("_")
        folder_lane = parts[2].replace("-", "_") if len(parts) >= 4 else None
        s = {"name": name, "id": name.split("_")[-1], "date": date, "week": week_of(date),
             "lane": st.get("lane") or "unset", "work_type": st.get("work_type") or "unset",
             "folder_lane": folder_lane, "agent": st.get("agent") or "claude(legacy)",
             "end_session_run": st.get("end_session_run"), "state": st}
        bd = st.get("breakdown") or {}
        tk = st.get("tokens") or {}
        s["total"] = bd.get("total") or tk.get("total_tokens")
        s["turns"] = tk.get("turns")
        s["peak"] = bd.get("peak_context")
        s["cats"] = bd.get("categories") or {}
        s["calls"] = bd.get("calls")
        s["metrics"] = parse_metrics(mm) if os.path.isfile(mm) else None
        rp = os.path.join(folder, "retro.md")
        s["retro"] = parse_retro(rp) if os.path.isfile(rp) else None
        s["has_retro"] = os.path.isfile(rp)
        s["ctx_marker"] = os.path.isfile(os.path.join(folder, "context-warning.json"))
        sessions.append(s)

    # hooks.log context-warning firings per session id
    firings = collections.Counter()
    hooks = os.path.join(args.sessions, "hooks.log")
    if os.path.isfile(hooks):
        for line in open(hooks, encoding="utf-8", errors="replace"):
            mt = re.search(r"session=(\w+).*-> context \d+k >= threshold", line)
            if mt:
                firings[mt.group(1)[:8]] += 1

    N = len(sessions)
    L = []
    w = L.append
    w("# Agent rules framework — usage audit from session metrics\n")
    w("Generated %s from %d session folders in `%s`. Read-only." % (datetime.date.today(), N, args.sessions))
    w("Dates are folder-name start dates; weeks start Monday. Lane = `session.json` lane (final value).\n")

    # ------------------------------------------------------------ 1 lanes
    w("## 1. Lane and work-type distribution\n")
    lanes = collections.Counter(s["lane"] for s in sessions)
    w("| Lane | Sessions | Share |\n| --- | ---: | ---: |")
    for k, v in lanes.most_common():
        w("| %s | %d | %s |" % (k, v, pct(v, N)))
    wts = collections.Counter(s["work_type"] for s in sessions)
    w("\nWork types: " + ", ".join("%s %d" % kv for kv in wts.most_common()) + "\n")
    lane_order = ["feature", "small_task", "large_task", "bug_fix", "investigation", "other", "unset"]
    weeks = sorted({s["week"] for s in sessions})
    w("### Weekly lanes\n")
    w("| Week | Total | " + " | ".join(lane_order) + " |")
    w("| --- | ---: | " + " | ".join("---:" for _ in lane_order) + " |")
    for wk in weeks:
        ss = [s for s in sessions if s["week"] == wk]
        c = collections.Counter(s["lane"] for s in ss)
        w("| %s | %d | %s |" % (wk, len(ss), " | ".join(str(c.get(l, 0)) for l in lane_order)))
    wt_order = [k for k, _ in wts.most_common()]
    w("\n### Weekly work types\n")
    w("| Week | " + " | ".join(wt_order) + " |")
    w("| --- | " + " | ".join("---:" for _ in wt_order) + " |")
    for wk in weeks:
        c = collections.Counter(s["work_type"] for s in sessions if s["week"] == wk)
        w("| %s | %s |" % (wk, " | ".join(str(c.get(t, 0)) for t in wt_order)))
    unset = [s for s in sessions if s["lane"] == "unset"]
    w("\n### Sessions with lane unset (%d)\n" % len(unset))
    for s in unset:
        n_loads = len(s["metrics"]["loads"]) if s["metrics"] else 0
        w("- `%s` — total %s, turns %s, loads %d, retro %s" % (s["name"], fmt(s["total"]), s["turns"], n_loads,
                                                            "yes" if s["has_retro"] else "no"))
    mism = [s for s in sessions if s["folder_lane"] and s["folder_lane"] != s["lane"].replace("-", "_")
            and s["folder_lane"] in LANE_PROCESS.keys() | {"other"}]
    w("\nFolder-name lane differs from final session.json lane: %d sessions (lane set or changed after folder creation)." % len(mism))
    multi = [s for s in sessions if s["metrics"] and s["metrics"]["lane_changes"]]
    w("Sessions with recorded lane changes: %d.\n" % len(multi))

    # ------------------------------------------------------------ 2 file loads
    w("## 2. Rule / process / system file loads\n")
    w("Counted from metrics.md *Loaded on demand* rows (main + subagents). A file counts once per session. "
      "`Read` = at least one Read-tool row; Bash rows are the tracker's heuristic (any `.md` path in a command, incl. grep/sed).\n")
    traced = [s for s in sessions if s["metrics"]]
    load_any = collections.Counter()
    load_read = collections.Counter()
    load_main = collections.Counter()
    first_seen = {}
    for s in traced:
        per = {}
        for ld in s["metrics"]["loads"]:
            f = ld["file"]
            per.setdefault(f, set()).add(ld["via"])
        for f, vias in per.items():
            load_any[f] += 1
            if any("Read" in v for v in vias):
                load_read[f] += 1
            if any(v.startswith("main") for v in vias):
                load_main[f] += 1
            first_seen.setdefault(f, s["date"])
    def eligible(f):
        created = (files.get(f) or {}).get("created")
        return sum(1 for s in traced if not created or s["date"] >= created)
    rows = []
    for f, meta in files.items():
        rows.append((f, load_any.get(f, 0), load_read.get(f, 0), eligible(f), meta["created"], meta["bytes"]))
    w("### Most loaded (top 25)\n")
    w("| File | Sessions (any) | via Read | Eligible sessions since created | Rate | Size |")
    w("| --- | ---: | ---: | ---: | ---: | ---: |")
    for f, a, r, e, c, b in sorted(rows, key=lambda x: -x[1])[:25]:
        w("| `%s` | %d | %d | %d | %s | %s B |" % (f, a, r, e, pct(a, e), fmt(b)))
    w("\n### Never loaded (0 sessions)\n")
    w("| File | Created | Eligible sessions | Size |\n| --- | --- | ---: | ---: |")
    never = sorted([x for x in rows if x[1] == 0], key=lambda x: (x[0]))
    for f, a, r, e, c, b in never:
        w("| `%s` | %s | %d | %s B |" % (f, c, e, fmt(b)))
    w("\n### Almost never loaded (1–3 sessions, ≥20 eligible)\n")
    w("| File | Sessions | via Read | Eligible | Created |\n| --- | ---: | ---: | ---: | --- |")
    for f, a, r, e, c, b in sorted([x for x in rows if 1 <= x[1] <= 3 and x[3] >= 20], key=lambda x: x[1]):
        w("| `%s` | %d | %d | %d | %s |" % (f, a, r, e, c))
    w("\n### Traced .md paths outside the rule inventory (feature docs, skills, Documentation/, renamed files)\n")
    ghost = [(f, n) for f, n in load_any.items() if f not in files]
    for f, n in sorted(ghost, key=lambda x: -x[1])[:40]:
        w("- `%s` — %d sessions" % (f, n))
    always_loaded = {f: load_any.get(f, 0) for f in ALWAYS_ON}
    w("\nAlways-on files also re-loaded on demand (redundant loads): " +
      ", ".join("`%s` %d" % (f.split("/")[-1], n) for f, n in sorted(always_loaded.items(), key=lambda x: -x[1])) + "\n")
    via_counts = collections.Counter()
    for s in traced:
        for ld in s["metrics"]["loads"]:
            via_counts[ld["via"]] += 1
    w("Load rows by mechanism: " + ", ".join("%s %d" % kv for kv in via_counts.most_common()) + "\n")
    w("Bash-only share of load rows by week (lower = rule 'load with Read' followed):\n")
    w("| Week | Load rows | Bash-only | Share |\n| --- | ---: | ---: | ---: |")
    for wk in weeks:
        rr = [ld for s in traced if s["week"] == wk for ld in s["metrics"]["loads"]]
        b = sum(1 for ld in rr if ld["via"].endswith("Bash"))
        w("| %s | %d | %d | %s |" % (wk, len(rr), b, pct(b, len(rr))))

    # ------------------------------------------------------------ 3 router check
    w("\n## 3. Router-check compliance\n")
    w("### 3a. Mechanical check from the router trace\n")
    w("Expected = the unconditional part of each lane's `Router check` expected_loads. `*` items are conditional "
      "on C# changes (cannot be told from metrics), so their miss rate is an upper bound. `Systems/*` = any Systems/ entry loaded.\n")
    def loaded(s, pat):
        names = {ld["file"] for ld in s["metrics"]["loads"]}
        p = pat.rstrip("*") if pat.endswith(".md*") else pat
        if p == "Systems/*":
            return any("TripleMatchAiMetaData/Systems/" in n for n in names)
        if p.endswith("Phase*"):
            return any(n.startswith(p[:-1]) for n in names)
        return p in names
    miss_counter = collections.Counter()
    w("| Lane | Sessions | Expected item | Loaded | Missed | Miss rate |\n| --- | ---: | --- | ---: | ---: | ---: |")
    for lane, exp in LANE_EXPECTED.items():
        ss = [s for s in traced if s["lane"] == lane]
        for e in exp:
            hit = sum(1 for s in ss if loaded(s, e))
            miss_counter[(lane, e)] = len(ss) - hit
            w("| %s | %d | `%s` | %d | %d | %s |" % (lane, len(ss), e, hit, len(ss) - hit, pct(len(ss) - hit, len(ss))))
    w("\n**Lane process file loaded, by period** (the core router obligation):\n")
    periods = [("≤2026-10-15", "0000", "2026-10-15"), ("10-16..10-27", "2026-10-16", "2026-10-27"),
               ("10-28..11-04", "2026-10-28", "2026-11-04"), ("11-05..11-10", "2026-11-05", "9999")]
    w("| Period | Process lanes sessions | Process loaded | Rate | Process via Read | Any Systems/ (non-feature) | all mechanical items |")
    w("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for label, a, b in periods:
        ss = [s for s in traced if s["lane"] in LANE_PROCESS and a <= s["date"] <= b]
        hit = [s for s in ss if LANE_PROCESS[s["lane"]] in {ld["file"] for ld in s["metrics"]["loads"]}]
        viaread = [s for s in ss if any(ld["file"] == LANE_PROCESS[s["lane"]] and "Read" in ld["via"]
                                        for ld in s["metrics"]["loads"])]
        nf = [s for s in ss if s["lane"] != "feature"]
        sysd = [s for s in nf if loaded(s, "Systems/*")]
        items = [(s, e) for s in ss for e in LANE_EXPECTED[s["lane"]] if not e.endswith("*") or e == "Systems/*"]
        items = [(s, e) for s, e in items if not (e == "Systems/*" and s["lane"] == "feature")]
        ih = sum(1 for s, e in items if loaded(s, e))
        w("| %s | %d | %d | %s | %d | %s | %s |" % (label, len(ss), len(hit), pct(len(hit), len(ss)), len(viaread),
                                                  pct(len(sysd), len(nf)), pct(ih, len(items))))
    w("\nSessions in a process lane that never loaded their process file:\n")
    for s in traced:
        if s["lane"] in LANE_PROCESS and LANE_PROCESS[s["lane"]] not in {ld["file"] for ld in s["metrics"]["loads"]}:
            w("- `%s` (lane %s, %d loads, total %s)" % (s["name"], s["lane"], len(s["metrics"]["loads"]), fmt(s["total"])))

    w("\n### 3b. Retro-reported Router check results (retro.md tables)\n")
    with_rc = [s for s in sessions if s["retro"]]
    w("Sessions with retro.md: %d; with a parseable Router check table: %d.\n" % (
        sum(1 for s in sessions if s["has_retro"]), sum(1 for s in with_rc if s["retro"])))
    status_by_lane = collections.defaultdict(collections.Counter)
    miss_items = collections.Counter()
    miss_items_lane = collections.defaultdict(collections.Counter)
    for s in with_rc:
        for r in s["retro"]:
            status_by_lane[s["lane"]][r["status"]] += 1
            if r["status"] in ("no", "partly", "late", "ignored"):
                miss_items[r["key"]] += 1
                miss_items_lane[s["lane"]][r["key"]] += 1
    stats = ["yes", "late", "partly", "no", "ignored", "n/a", "other"]
    w("| Lane | Retros | Rows | " + " | ".join(stats) + " | Miss share (no+partly+late+ignored / rows excl n/a) |")
    w("| --- | ---: | ---: | " + " | ".join("---:" for _ in stats) + " | ---: |")
    for lane in lane_order:
        c = status_by_lane.get(lane)
        if not c:
            continue
        nret = sum(1 for s in with_rc if s["lane"] == lane)
        tot = sum(c.values())
        miss = c["no"] + c["partly"] + c["late"] + c["ignored"]
        w("| %s | %d | %d | %s | %s |" % (lane, nret, tot, " | ".join(str(c[k]) for k in stats),
                                          pct(miss, tot - c["n/a"] - c["other"])))
    w("\n**Most frequently missed items (retro tables, all lanes)**\n")
    w("| Item | Misses |\n| --- | ---: |")
    for k, v in miss_items.most_common(25):
        w("| `%s` | %d |" % (k, v))
    w("\n**Per lane top misses**\n")
    for lane, c in miss_items_lane.items():
        w("- %s: " % lane + "; ".join("`%s` %d" % kv for kv in c.most_common(6)))
    w("\n**Retro miss trend by week**\n")
    w("| Week | Retros w/ table | Rows | Misses | Miss share | Sessions with ≥1 miss |\n| --- | ---: | ---: | ---: | ---: | ---: |")
    for wk in weeks:
        ss = [s for s in with_rc if s["week"] == wk]
        rows_ = [r for s in ss for r in s["retro"] if r["status"] not in ("n/a", "other")]
        m = [r for r in rows_ if r["status"] in ("no", "partly", "late", "ignored")]
        sm = sum(1 for s in ss if any(r["status"] in ("no", "partly", "late", "ignored") for r in s["retro"]))
        w("| %s | %d | %d | %d | %s | %s |" % (wk, len(ss), len(rows_), len(m), pct(len(m), len(rows_)), pct(sm, len(ss))))
    w("\nUnclassified Loaded? cells (status `other`) examples:\n")
    ex = [(s["name"], r["item"][:60]) for s in with_rc for r in s["retro"] if r["status"] == "other"][:8]
    for n, i in ex:
        w("- `%s`: %s" % (n, i))
    w("\nRule change points used for the trend reading: " + "; ".join("%s %s" % c for c in CHANGE_POINTS) + "\n")

    # ------------------------------------------------------------ 4 cost
    w("## 4. Cost\n")
    costed = [s for s in sessions if s["total"]]
    w("Sessions with token totals: %d / %d; with category breakdown: %d; with peak_context: %d.\n" % (
        len(costed), N, sum(1 for s in sessions if s["cats"]), sum(1 for s in sessions if s["peak"])))
    w("| Lane | n | Median total | p90 total | Max | Median peak ctx | p90 peak ctx | Median turns |")
    w("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for lane in lane_order + ["ALL"]:
        ss = [s for s in costed if lane == "ALL" or s["lane"] == lane]
        if not ss:
            continue
        t = [s["total"] for s in ss]
        p = [s["peak"] for s in ss if s["peak"]]
        tu = [s["turns"] for s in ss if s["turns"]]
        w("| %s | %d | %s | %s | %s | %s | %s | %s |" % (lane, len(ss), fmt(statistics.median(t)), fmt(quant(t, .9)),
                                                         fmt(max(t)), fmt(statistics.median(p)) if p else "–",
                                                         fmt(quant(p, .9)) if p else "–",
                                                         "%.0f" % statistics.median(tu) if tu else "–"))
    catd = collections.Counter()
    shares = collections.defaultdict(list)
    for s in sessions:
        tot = sum(s["cats"].values())
        if not tot:
            continue
        for k, v in s["cats"].items():
            catd[k] += v
            shares[k].append(v / tot)
    gt = sum(catd.values())
    w("\n### Token categories (estimated breakdown, %d sessions)\n" % len(shares.get("Conversation & base context", [])))
    w("| Category | Total tokens | Share of all | Median per-session share | p90 share |\n| --- | ---: | ---: | ---: | ---: |")
    for k, v in catd.most_common():
        w("| %s | %s | %s | %s | %s |" % (k, fmt(v), pct(v, gt), pct(statistics.median(shares[k]), 1),
                                         pct(quant(shares[k], .9), 1)))
    w("\nRule & process loads by lane (median share / median absolute):\n")
    w("| Lane | n | Median share | Median tokens | Median loads per session |\n| --- | ---: | ---: | ---: | ---: |")
    for lane in lane_order:
        ss = [s for s in sessions if s["lane"] == lane and s["cats"]]
        if not ss:
            continue
        sh = [s["cats"].get("Rule & process loads", 0) / max(1, sum(s["cats"].values())) for s in ss]
        ab = [s["cats"].get("Rule & process loads", 0) for s in ss]
        nl = [len(s["metrics"]["loads"]) for s in ss if s["metrics"]]
        w("| %s | %d | %s | %s | %s |" % (lane, len(ss), pct(statistics.median(sh), 1), fmt(statistics.median(ab)),
                                          "%.0f" % statistics.median(nl) if nl else "–"))
    w("\nNote: always-on CLAUDE.md imports are part of *Conversation & base context*, not *Rule & process loads*; "
      "their bytes are: %s B total (≈ %s tokens at 4 B/token, re-sent every call).\n" % (
          fmt(sum((files.get(f) or {}).get("bytes", 0) for f in ALWAYS_ON)),
          fmt(sum((files.get(f) or {}).get("bytes", 0) for f in ALWAYS_ON) / 4)))
    # context warnings
    since = [s for s in sessions if s["date"] >= "2026-11-02"]
    fired = [s for s in since if s["ctx_marker"] or firings.get(s["id"][:8])]
    w("### Context-size warnings (feature live since 2026-11-02)\n")
    w("Sessions since 2026-11-02: %d; warning fired in %d (%s); total firings in hooks.log: %d; "
      "marker files present: %d (marker is deleted when context drops below threshold, so the file undercounts)." % (
          len(since), len(fired), pct(len(fired), len(since)), sum(firings.values()),
          sum(1 for s in sessions if s["ctx_marker"])))
    w("By lane: " + ", ".join("%s %d/%d" % (l, sum(1 for s in fired if s["lane"] == l),
                                            sum(1 for s in since if s["lane"] == l)) for l in lane_order
                              if any(s["lane"] == l for s in since)) + "\n")
    w("### Weekly cost\n")
    w("| Week | Sessions | Median total | Sum total | Median peak ctx | Median rule-load share | Median ad-hoc share |")
    w("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for wk in weeks:
        ss = [s for s in costed if s["week"] == wk]
        if not ss:
            continue
        p = [s["peak"] for s in ss if s["peak"]]
        rs = [s["cats"].get("Rule & process loads", 0) / sum(s["cats"].values()) for s in ss if s["cats"] and sum(s["cats"].values())]
        ah = [s["cats"].get("Ad-hoc tool calls", 0) / sum(s["cats"].values()) for s in ss if s["cats"] and sum(s["cats"].values())]
        w("| %s | %d | %s | %s | %s | %s | %s |" % (wk, len(ss), fmt(statistics.median([s["total"] for s in ss])),
                                                   fmt(sum(s["total"] for s in ss)),
                                                   fmt(statistics.median(p)) if p else "–",
                                                   pct(statistics.median(rs), 1) if rs else "–",
                                                   pct(statistics.median(ah), 1) if ah else "–"))
    w("\n### Top 10 sessions by total tokens\n")
    for s in sorted(costed, key=lambda s: -s["total"])[:10]:
        w("- `%s` — %s total, peak %s, %s turns" % (s["name"], fmt(s["total"]), fmt(s["peak"]), s["turns"]))

    # ------------------------------------------------------------ 5 measurement health
    w("\n## 5. Is the measurement working?\n")
    checks = collections.OrderedDict()
    checks["no metrics.md"] = [s for s in sessions if not s["metrics"]]
    checks["empty router trace (0 on-demand loads)"] = [s for s in traced if not s["metrics"]["loads"]]
    checks["lane unset"] = [s for s in sessions if s["lane"] == "unset"]
    checks["no token breakdown (pre-2026-10-07 tool or failed)"] = [s for s in sessions if not s["cats"]]
    checks["tokens.available not true"] = [s for s in sessions if (s["state"].get("tokens") or {}).get("available") is not True]
    checks["no peak_context"] = [s for s in sessions if not s["peak"]]
    checks["total tokens 0/missing"] = [s for s in sessions if not s["total"]]
    checks["turns ≤1 (likely aborted / empty)"] = [s for s in sessions if (s["turns"] or 0) <= 1]
    checks["agent field missing (legacy)"] = [s for s in sessions if not s["state"].get("agent")]
    checks["metrics never compiled at end (Ended = in progress)"] = [s for s in sessions if s["metrics"] and (s["metrics"]["ended"] or "").startswith("in progress")]
    checks["/end-session not run"] = [s for s in sessions if not s["end_session_run"]]
    checks["/end-session not run but retro.md exists"] = [s for s in sessions if not s["end_session_run"] and s["has_retro"]]
    checks["retro.md without parseable Router check table"] = [s for s in sessions if s["has_retro"] and not s["retro"]]
    checks["process lane but process file absent from trace"] = [s for s in traced if s["lane"] in LANE_PROCESS and LANE_PROCESS[s["lane"]] not in {ld["file"] for ld in s["metrics"]["loads"]}]
    checks["folder name without lane segment"] = [s for s in sessions if not s["folder_lane"] or s["folder_lane"] not in set(LANE_PROCESS) | {"other"}]
    checks["transcript file missing on disk"] = [s for s in sessions if s["state"].get("transcript_path") and not os.path.isfile(s["state"]["transcript_path"])]
    ids = collections.Counter(s["state"].get("session_id") for s in sessions)
    checks["duplicate session_id across folders"] = [s for s in sessions if ids[s["state"].get("session_id")] > 1]
    w("| Check | Sessions | Share |\n| --- | ---: | ---: |")
    for k, v in checks.items():
        w("| %s | %d | %s |" % (k, len(v), pct(len(v), N)))
    for k in ["empty router trace (0 on-demand loads)", "lane unset", "no token breakdown (pre-2026-10-07 tool or failed)",
              "duplicate session_id across folders", "transcript file missing on disk", "tokens.available not true"]:
        v = checks[k]
        if v:
            w("\n<details><summary>%s (%d)</summary>\n" % (k, len(v)))
            for s in v:
                w("- `%s` lane=%s total=%s turns=%s" % (s["name"], s["lane"], fmt(s["total"]), s["turns"]))
            w("\n</details>")
    w("\nEmpty traces by lane: " + ", ".join("%s %d" % kv for kv in collections.Counter(
        s["lane"] for s in checks["empty router trace (0 on-demand loads)"]).most_common()))
    w("\nWeekly measurement coverage:\n")
    w("| Week | Sessions | Lane set | Breakdown | Retro | Empty trace |\n| --- | ---: | ---: | ---: | ---: | ---: |")
    for wk in weeks:
        ss = [s for s in sessions if s["week"] == wk]
        w("| %s | %d | %s | %s | %s | %s |" % (wk, len(ss), pct(sum(1 for s in ss if s["lane"] != "unset"), len(ss)),
                                              pct(sum(1 for s in ss if s["cats"]), len(ss)),
                                              pct(sum(1 for s in ss if s["has_retro"]), len(ss)),
                                              pct(sum(1 for s in ss if s["metrics"] and not s["metrics"]["loads"]), len(ss))))
    open(args.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote", args.out, len(L), "lines")


if __name__ == "__main__":
    main()
