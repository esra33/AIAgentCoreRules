#!/usr/bin/env python3
"""Read-only audit: runnable tools / skills vs manual equivalents in Claude Code transcripts.

Streams every *.jsonl under the project transcript dir (top-level sessions + subagents/),
classifies each assistant tool_use, and writes audit_tools.md next to this script.
"""
import collections
import datetime as dt
import glob
import json
import os
import re
import sys

PROJ = "/Users/aramirez/.claude/projects/-Users-aramirez-Documents-Projects-TripleMatch3D"
SESS_DIR = "/Users/aramirez/Documents/Projects/TripleMatch3D/GitIgnoreReports/Sessions"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_tools.md")

# ---------------------------------------------------------------- tool catalogue
SCRIPT_TOOLS = {
    # key: (group, regex on bash command)
    "typecheck.py": ("unity-tools", r"typecheck\.py"),
    "codeindex.py": ("unity-tools", r"codeindex\.py"),
    "usages.py": ("unity-tools", r"\busages\.py"),
    "unitysource.py": ("unity-tools", r"unitysource\.py"),
    "code-graph": ("code-graph", r"code-graph\.sh|graph_control\.py|graph_server\.py|/api/(type|graph|search)\b"),
    "doc_review.py": ("doc-review", r"doc_review\.py"),
    "preview-control": ("doc-review", r"preview[-_]control\.(sh|py)"),
    "progress_view.py": ("doc-review", r"progress_view\.py"),
    "perf_view.py": ("doc-review", r"perf_view\.py"),
    "feature_state.py": ("feature-state", r"feature_state\.py"),
    "legacy_migration.py": ("feature-state", r"legacy_migration\.py|migrate_phase_reports\.sh"),
    "session_lifecycle.py": ("session-lifecycle", r"session_lifecycle\.py"),
    "token_breakdown.py": ("session-lifecycle", r"token_breakdown\.py"),
    "retro_page.py": ("session-lifecycle", r"retro_page\.py"),
    "session_meta_report.py": ("session-analysis", r"session_meta_report\.py"),
    "session-support": ("session-support", r"session_monitor\.py|session_workflow_support\.py|session-support/session-support"),
    "export_confluence.py": ("docs-export", r"export_confluence\.py"),
    "mermaid_preview.py": ("mermaid-preview", r"mermaid_preview\.py"),
    "new_session.py": ("new-session", r"new_session\.py"),
    "install.py": ("setup", r"setup/install\.py|\binstall\.py\b"),
    "project_config.py": ("setup", r"project_config\.py"),
}
SCRIPT_RX = {k: re.compile(v) for k, (_, v) in SCRIPT_TOOLS.items()}
CORE_SKILLS = sorted(os.listdir("/Users/aramirez/Documents/Projects/AIAgentCoreRules/Skills"))
CORE_SKILLS += ["preview-feature"]  # old name of start-preview-server

# ---------------------------------------------------------------- manual patterns
PASCAL = re.compile(r"\b(I[A-Z][a-z]\w+|[A-Z][a-z0-9]+[A-Z]\w+)\b")
GREP_CMD = re.compile(r"(^|[|;&(]\s*|\s)(grep|rg|ag|git grep)\s")
CS_TARGET = re.compile(r"Assets/|\.cs\b|--include=?['\"]?\*\.cs|-t\s*cs|--type[= ]cs|Scripts/")
NON_CS_TARGET = re.compile(r"GitIgnoredExternals|AIAgentCoreRules|TripleMatchAiMetaData|\.md\b|\.jsonl|\.json\b|GitIgnoreReports|Features/|\.py\b")
TYPE_HINT = re.compile(r"class\s|interface\s|:\s*I[A-Z]|implements|\bnew\s+[A-Z]|<[A-Z]\w+>|\bI[A-Z][a-z]\w+")
FIND_CS = re.compile(r"\bfind\s+[^|;]*(Assets|Scripts)[^|;]*-name\s+['\"]?[^'\"\s]*(\.cs|[A-Z])")
EDITOR_LOG = re.compile(r"Editor\.log")
BUILD_CMD = re.compile(r"\b(dotnet\s+build|msbuild|xbuild|\bcsc\b|mcs\s)")
WT_ADD = re.compile(r"git\s+worktree\s+add")
WT_REMOVE = re.compile(r"git\s+worktree\s+remove|git\s+branch\s+-D")
CAT_CS_WHOLE = re.compile(r"(^|[;&|]\s*)cat\s+[^|;&]*\.cs\b")
CAT_CS_PART = re.compile(r"(^|[;&]\s*|&&\s*)(sed\s+-n|head|tail|awk)\s[^|;&]*\.cs\b")
SEG_SPLIT = re.compile(r"\s*(?:;|&&|\|\||\||\$\(|\n)\s*")
ADHOC_PY = re.compile(r"python3?\s+(-c\b|-\s*<<|<<)|python3?\s+/tmp/|python3?\s+\S*/tmp/\S+\.py|cat\s*>\s*\S+\.py")
STATE_FILE = re.compile(r"(state\.json|_Progress\.md)")
STATE_MUTATE_BASH = re.compile(r"(sed\s+-i|>\s*\S*(state\.json|_Progress\.md)|json\.dump|write_text|open\([^)]*['\"]w)")

land_sessions = set()
RULE_TOOL_MENTION = re.compile(r"codeindex\.py|usages\.py|typecheck\.py|/uses\b|/discover\b|unitysource\.py")


def week_of(ts):
    try:
        d = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None, None
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}", d


def load_lanes():
    lanes = {}
    for sj in glob.glob(os.path.join(SESS_DIR, "*", "session.json")):
        try:
            with open(sj) as fh:
                d = json.load(fh)
            sid = d.get("session_id")
            if sid:
                lanes[sid] = (d.get("lane"), os.path.basename(os.path.dirname(sj)))
        except Exception:
            pass
    return lanes


def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    out.append(b.get("text", ""))
                elif b.get("type") == "tool_result":
                    out.append(text_of(b.get("content")))
    return "\n".join(out)


class Event:
    __slots__ = ("sid", "file", "sub", "ts", "week", "kind", "detail", "idx")

    def __init__(self, sid, file, sub, ts, week, kind, detail, idx):
        self.sid, self.file, self.sub, self.ts, self.week = sid, file, sub, ts, week
        self.kind, self.detail, self.idx = kind, detail, idx


def classify_bash(cmd):
    """Return list of (kind, detail)."""
    out = []
    for k, rx in SCRIPT_RX.items():
        if rx.search(cmd):
            out.append(("tool:" + k, cmd[:160]))
    is_tool = bool(out)
    if not is_tool:
        for seg in SEG_SPLIT.split(cmd):
            seg = seg.strip().lstrip("(").strip()
            m = re.match(r"(?:cd\s+\S+\s*)?(grep|rg|ag|git\s+grep|egrep)\b(.*)", seg)
            if not m:
                continue
            tool, rest = m.group(1), m.group(2)
            recursive = tool != "grep" and tool != "egrep" or re.search(r"\s-[a-zA-Z]*[rR]", rest)
            cs = CS_TARGET.search(rest) and not NON_CS_TARGET.search(rest)
            single_file = re.search(r"\S+\.cs['\"]?(\s|$)", rest) and not recursive
            if not cs and not recursive:
                continue  # piped filter or non-C# grep
            if single_file:
                out.append(("manual:grep_in_cs_file", seg[:200]))
            elif cs or (recursive and not NON_CS_TARGET.search(rest) and re.search(r"\s\.\.?/?(\s|$)|Packages", rest)):
                if TYPE_HINT.search(rest) or PASCAL.search(rest):
                    out.append(("manual:grep_type_cs", seg[:200]))
                else:
                    out.append(("other:grep_recursive_other", seg[:200]))
    if FIND_CS.search(cmd) and not is_tool:
        out.append(("manual:find_cs_file", cmd[:200]))
    if EDITOR_LOG.search(cmd):
        out.append(("manual:editor_log", cmd[:200]))
    if BUILD_CMD.search(cmd) and not is_tool:
        out.append(("manual:build_cmd", cmd[:200]))
    if WT_ADD.search(cmd):
        out.append(("manual:git_worktree_add", cmd[:200]))
    if WT_REMOVE.search(cmd):
        out.append(("manual:git_worktree_remove", cmd[:200]))
    if CAT_CS_WHOLE.search(cmd) and not is_tool:
        out.append(("manual:shell_cat_cs_whole", cmd[:200]))
    elif CAT_CS_PART.search(cmd) and not is_tool:
        out.append(("other:shell_read_cs_range", cmd[:200]))
    if ADHOC_PY.search(cmd) and not is_tool:
        sub = "generic"
        low = cmd.lower()
        if ".jsonl" in low or "transcript" in low or "usage" in low and "token" in low:
            sub = "transcripts/tokens"
        elif "state.json" in low or "_progress" in low:
            sub = "feature-state"
        elif re.search(r"\.cs\b", low):
            sub = "cs-parse"
        elif "review.json" in low or "doc_review" in low:
            sub = "doc-review"
        if "aiagentcorerules" in low or "/tests" in low or "sys.path.insert" in low:
            sub = "tool-dev/test"
        out.append(("manual:adhoc_python:" + sub, cmd[:200]))
    if STATE_FILE.search(cmd) and STATE_MUTATE_BASH.search(cmd) and "feature_state.py" not in cmd:
        out.append(("manual:state_edit_bash", cmd[:200]))
    return out


def main():
    lanes = load_lanes()
    files = sorted(glob.glob(os.path.join(PROJ, "*.jsonl")) + glob.glob(os.path.join(PROJ, "*", "subagents", "*.jsonl")))
    events = []  # all classified events
    per_session_seq = collections.defaultdict(list)  # sid -> list of events (incl. neutral) for ordering
    rule_triggers = []  # (sid, file, idx, source)
    session_first_ts = {}
    session_weeks = {}
    user_cmds = collections.Counter()
    user_cmds_week = collections.defaultdict(collections.Counter)
    global land_sessions

    for path in files:
        sub = "/subagents/" in path
        sid = os.path.basename(os.path.dirname(os.path.dirname(path))) if sub else os.path.basename(path)[:-6]
        idx = 0
        pending_md_reads = {}
        try:
            fh = open(path, errors="replace")
        except Exception:
            continue
        with fh:
            for line in fh:
                if '"tool_use"' not in line and '"tool_result"' not in line and "command-name" not in line and "Base directory for this skill" not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = rec.get("timestamp") or ""
                wk, d = week_of(ts) if ts else (None, None)
                if wk and not sub:
                    session_first_ts.setdefault(sid, d)
                    session_weeks.setdefault(sid, wk)
                msg = rec.get("message") or {}
                content = msg.get("content")
                if rec.get("type") == "user":
                    txt = text_of(content) if not isinstance(content, list) or any(
                        isinstance(b, dict) and b.get("type") == "text" for b in content) else ""
                    if txt and not sub:
                        for m in re.finditer(r"<command-name>/?([\w:-]+)</command-name>", txt):
                            user_cmds[m.group(1)] += 1
                            if m.group(1) == "land-worktree":
                                land_sessions.add(sid)
                            user_cmds_week[wk][m.group(1)] += 1
                    if txt and "Base directory for this skill" in txt and RULE_TOOL_MENTION.search(txt):
                        rule_triggers.append((sid, path, idx, "skill-load"))
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "tool_result":
                                tid = b.get("tool_use_id")
                                if tid in pending_md_reads:
                                    rt = text_of(b.get("content"))
                                    if RULE_TOOL_MENTION.search(rt or ""):
                                        rule_triggers.append((sid, path, idx, pending_md_reads[tid]))
                                    pending_md_reads.pop(tid, None)
                    continue
                if rec.get("type") != "assistant" or not isinstance(content, list):
                    continue
                for b in content:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    idx += 1
                    name = b.get("name", "")
                    inp = b.get("input") or {}
                    kinds = []
                    if name == "Bash":
                        cmd = inp.get("command", "") or ""
                        kinds = classify_bash(cmd)
                        # Shell reads of rule .md files can also be triggers
                        if re.search(r"(Rules|Processes|Skills)/[^\s]*\.md|SystemIndex\.md", cmd) and re.match(r"\s*(cat|sed|head)\b", cmd):
                            pending_md_reads[b.get("id")] = "shell-read:" + cmd[:80]
                    elif name == "Read":
                        fp = inp.get("file_path", "") or ""
                        if fp.endswith(".cs"):
                            if inp.get("limit") or inp.get("offset"):
                                kinds.append(("read:cs_partial", fp))
                            else:
                                kinds.append(("manual:read_cs_whole", fp))
                        if "Editor.log" in fp:
                            kinds.append(("manual:editor_log", fp))
                        if fp.endswith(".md") and re.search(r"/(Rules|Processes|Skills)/|SystemIndex\.md|unity-tools/README", fp):
                            pending_md_reads[b.get("id")] = os.path.basename(fp)
                        if "Phase4_Implementation.md" in fp:
                            kinds.append(("marker:phase4", fp))
                        if fp.endswith("LargeTask.md"):
                            kinds.append(("marker:largetask", fp))
                    elif name in ("Edit", "Write", "MultiEdit"):
                        fp = inp.get("file_path", "") or ""
                        if fp.endswith(".cs"):
                            kinds.append(("edit:cs", fp))
                        if fp.endswith("state.json") or fp.endswith("_Progress.md"):
                            kinds.append(("manual:state_edit_tool", fp))
                    elif name in ("Grep", "Glob"):
                        pat = (inp.get("pattern", "") or "") + " " + (inp.get("path", "") or "") + " " + (inp.get("glob", "") or "") + " " + (inp.get("type", "") or "")
                        if name == "Grep" and (CS_TARGET.search(pat) or "cs" == inp.get("type")) and PASCAL.search(inp.get("pattern", "") or ""):
                            kinds.append(("manual:grep_type_cs", pat[:200]))
                        elif name == "Glob" and ".cs" in pat:
                            kinds.append(("manual:find_cs_file", pat[:200]))
                        else:
                            kinds.append(("other:" + name.lower(), pat[:120]))
                    elif name == "Skill":
                        kinds.append(("skill:" + (inp.get("skill") or "?"), inp.get("args", "")[:120] if isinstance(inp.get("args"), str) else ""))
                    elif name in ("Agent", "Task"):
                        st = inp.get("subagent_type") or "general-purpose(default)"
                        prompt = (inp.get("prompt") or "")
                        tag = "agent:" + st
                        kinds.append((tag, (inp.get("description") or "")[:100]))
                        if re.search(r"/audit\b|Skills/audit|audit skill", prompt, re.I) or re.search(r"\baudit\b", inp.get("description") or "", re.I):
                            kinds.append(("audit:via_agent", (inp.get("description") or "")[:100]))
                        if re.search(r"/discover\b|Skills/discover", prompt):
                            kinds.append(("discover:via_agent", (inp.get("description") or "")[:100]))
                    elif name == "EnterWorktree":
                        kinds.append(("tool:EnterWorktree", json.dumps(inp)[:100]))
                    elif name == "ExitWorktree":
                        kinds.append(("tool:ExitWorktree", json.dumps(inp)[:100]))
                    elif name.startswith("mcp__unity-mcp__"):
                        kinds.append(("mcp:" + name.replace("mcp__unity-mcp__", ""), ""))
                    for k, det in kinds:
                        ev = Event(sid, path, sub, ts, wk, k, det, idx)
                        events.append(ev)
                        per_session_seq[sid].append(ev)
    return analyse(events, per_session_seq, rule_triggers, lanes, session_first_ts, session_weeks, user_cmds, user_cmds_week, files)


def base_kind(k):
    if k.startswith("manual:adhoc_python"):
        return "manual:adhoc_python"
    return k


def analyse(events, per_session_seq, rule_triggers, lanes, session_first_ts, session_weeks, user_cmds, user_cmds_week, files):
    L = []
    w = L.append
    weeks = sorted({e.week for e in events if e.week})
    total = collections.Counter(base_kind(e.kind) for e in events)
    fine = collections.Counter(e.kind for e in events)
    by_week = collections.defaultdict(collections.Counter)
    for e in events:
        if e.week:
            by_week[e.week][base_kind(e.kind)] += 1
    sessions_with = collections.defaultdict(set)
    for e in events:
        sessions_with[base_kind(e.kind)].add(e.sid)
    top_sessions = sorted({os.path.basename(f)[:-6] for f in files if "/subagents/" not in f})
    n_sub = sum(1 for f in files if "/subagents/" in f)

    w("# Tool / skill usage audit — transcripts vs manual equivalents\n")
    w(f"Generated {dt.datetime.now():%Y-%m-%d %H:%M}. Source: {len(top_sessions)} top-level transcripts + {n_sub} subagent transcripts in `{PROJ}`.")
    w(f"Weeks covered: {weeks[0] if weeks else '-'} .. {weeks[-1] if weeks else '-'}. Classified events: {len(events)}.\n")
    w("Heuristics: grep/rg over C# (Assets/ or *.cs) whose pattern holds a PascalCase/interface name = 'type grep' (should be codeindex/usages). "
      "Whole `.cs` Read = Read with no limit/offset; 'shape-only' = never edited in that session. Ad-hoc python = `python3 -c` / heredoc / /tmp script. "
      "Subagent events are attributed to the parent session id.\n")

    # ---- usage table
    w("## 1. Invocation counts (all weeks)\n")
    w("| Item | Calls | Sessions | " + " | ".join(weeks) + " |")
    w("|---|---:|---:|" + "---:|" * len(weeks))
    keys = [k for k in total if k.split(":")[0] in ("tool", "skill", "mcp", "agent", "manual", "audit", "discover", "read", "edit")]
    order = {"tool": 0, "skill": 1, "mcp": 2, "agent": 3, "audit": 4, "discover": 5, "manual": 6, "read": 7, "edit": 8}
    for k in sorted(keys, key=lambda x: (order[x.split(":")[0]], -total[x])):
        w(f"| {k} | {total[k]} | {len(sessions_with[k])} | " + " | ".join(str(by_week[wk][k]) for wk in weeks) + " |")
    w("")
    w("Ad-hoc python breakdown: " + ", ".join(f"{k.split(':',2)[2]}={v}" for k, v in fine.most_common() if k.startswith("manual:adhoc_python")) + "\n")
    w("### Engineer-typed slash commands (user messages)\n")
    w("| Command | Count | " + " | ".join(weeks) + " |")
    w("|---|---:|" + "---:|" * len(weeks))
    for c, n in user_cmds.most_common():
        w(f"| /{c} | {n} | " + " | ".join(str(user_cmds_week[wk][c]) for wk in weeks) + " |")
    w("")

    # ---- dead tools
    w("## 2. Dead / near-dead tools and skills (agent-initiated calls)\n")
    dead = []
    for k, (grp, _) in SCRIPT_TOOLS.items():
        n = total["tool:" + k]
        if n <= 3:
            dead.append((f"tool:{k} ({grp})", n, len(sessions_with['tool:' + k])))
    for s in CORE_SKILLS:
        n = total["skill:" + s]
        if n <= 3:
            dead.append((f"skill:{s} (user-typed /{s}: {user_cmds[s]})", n, len(sessions_with['skill:' + s])))
    for k in ["mcp:" + x for x in ["TripleMatch_Parsers_Find", "TripleMatch_Parsers_Create", "TripleMatch_Parsers_Aggregate", "TripleMatch_Prize_CreateCode", "TripleMatch_Prize_CreateAssets", "TripleMatch_StateV3_Step", "TripleMatch_WaitForEditorReady"]]:
        if total[k] <= 3:
            dead.append((k, total[k], len(sessions_with[k])))
    w("| Item | Agent calls | Sessions |")
    w("|---|---:|---:|")
    for name, n, s in sorted(dead, key=lambda x: x[1]):
        w(f"| {name} | {n} | {s} |")
    w("")

    # ---- ratios
    w("## 3. Tool vs manual ratios, by week\n")
    pairs = {
        "type lookup: codeindex+usages+code-graph+/uses vs grep-type+find .cs": (
            ["tool:codeindex.py", "tool:usages.py", "tool:code-graph", "skill:uses"],
            ["manual:grep_type_cs", "manual:find_cs_file"]),
        "compile check: typecheck vs Editor.log/build": (["tool:typecheck.py"], ["manual:editor_log", "manual:build_cmd"]),
        "feature state: feature_state.py vs hand-edit state.json/_Progress.md": (["tool:feature_state.py"], ["manual:state_edit_tool", "manual:state_edit_bash"]),
        "survey: /discover vs Explore/general-purpose agents": (["skill:discover", "discover:via_agent"], ["agent:Explore", "agent:general-purpose", "agent:general-purpose(default)"]),
        "worktree: EnterWorktree vs git worktree add": (["tool:EnterWorktree"], ["manual:git_worktree_add"]),
        "shape: codeindex vs whole .cs Read": (["tool:codeindex.py"], ["manual:read_cs_whole"]),
    }
    for title, (tk, mk) in pairs.items():
        w(f"### {title}\n")
        w("| Week | Tool | Manual | Tool share |")
        w("|---|---:|---:|---:|")
        T = M = 0
        for wk in weeks:
            t = sum(by_week[wk][k] for k in tk)
            m = sum(by_week[wk][k] for k in mk)
            T += t
            M += m
            share = f"{100*t/(t+m):.0f}%" if t + m else "-"
            w(f"| {wk} | {t} | {m} | {share} |")
        w(f"| **all** | **{T}** | **{M}** | **{(100*T/(T+M)) if T+M else 0:.0f}%** |\n")

    # ---- whole .cs reads that were never edited
    w("## 4. Whole-file .cs reads\n")
    edited = collections.defaultdict(set)
    for e in events:
        if e.kind == "edit:cs":
            edited[e.sid].add(e.detail)
    whole = [e for e in events if e.kind == "manual:read_cs_whole"]
    shape_only = [e for e in whole if e.detail not in edited[e.sid]]
    partial = total["read:cs_partial"]
    w(f"Whole .cs Reads: {len(whole)} (partial reads with limit/offset: {partial}). Of the whole reads, {len(shape_only)} were of files never edited in that session (candidate shape-only reads; some are legitimately reading bodies).\n")
    cnt = collections.Counter(os.path.basename(e.detail) for e in shape_only)
    w("Most re-read unedited files: " + ", ".join(f"{k}×{v}" for k, v in cnt.most_common(12)) + "\n")
    sc = collections.Counter(e.sid for e in shape_only)
    w("Sessions with most unedited whole .cs reads: " + ", ".join(f"{k[:8]}({v})" for k, v in sc.most_common(8)) + "\n")

    # ---- manual right after rule told to use tool
    w("## 5. Manual approach within 20 tool calls of a rule/skill that names the tool\n")
    trig_by_file = collections.defaultdict(list)
    for sid, path, idx, src in rule_triggers:
        trig_by_file[path].append((idx, src))
    manual_kinds = {"manual:grep_type_cs", "manual:find_cs_file", "manual:editor_log", "manual:build_cmd"}
    hits = []
    for e in events:
        if e.kind not in manual_kinds:
            continue
        for tidx, src in trig_by_file.get(e.file, []):
            if 0 <= e.idx - tidx <= 20:
                hits.append((e, src))
                break
    w(f"Rule/skill loads mentioning codeindex/usages/typecheck/uses/discover: {len(rule_triggers)}. Manual hits right after: {len(hits)} in {len({h[0].sid for h in hits})} sessions.\n")
    w("| Session | Lane | Week | Trigger | Manual call |")
    w("|---|---|---|---|---|")
    seen = collections.Counter()
    for e, src in hits:
        seen[e.sid] += 1
        if seen[e.sid] > 3:
            continue
        lane = (lanes.get(e.sid) or ("?",))[0]
        w(f"| {e.sid[:8]}{' (sub)' if e.sub else ''} | {lane} | {e.week} | {src[:40]} | `{e.detail[:110].replace('|', '/').replace(chr(10), ' ')}` |")
    w("")

    # ---- typecheck at session start / end
    w("## 6. typecheck.py at session start/end (sessions with C# edits)\n")
    rows = []
    for sid, seq in per_session_seq.items():
        cs_edits = [e for e in seq if e.kind == "edit:cs"]
        if not cs_edits:
            continue
        seq_sorted = sorted(seq, key=lambda e: e.ts or "")
        tcs = [e for e in seq_sorted if e.kind == "tool:typecheck.py"]
        first_edit = min(e.ts for e in cs_edits if e.ts)
        last_edit = max(e.ts for e in cs_edits if e.ts)
        before = any(e.ts and e.ts < first_edit for e in tcs)
        after = any(e.ts and e.ts > last_edit for e in tcs)
        rows.append((sid, len(cs_edits), len(tcs), before, after))
    n = len(rows)
    w(f"Sessions with C# edits: {n}. Any typecheck: {sum(1 for r in rows if r[2])}. Baseline before first C# edit: {sum(1 for r in rows if r[3])}. After last C# edit: {sum(1 for r in rows if r[4])}. Neither: {sum(1 for r in rows if not r[2])}.\n")
    w("| Session | Lane | Week | C# edits | typechecks | baseline | after last edit |")
    w("|---|---|---|---:|---:|---|---|")
    for sid, ne, nt, b, a in sorted(rows, key=lambda r: session_weeks.get(r[0], "")):
        lane = (lanes.get(sid) or ("?",))[0]
        w(f"| {sid[:8]} | {lane} | {session_weeks.get(sid,'?')} | {ne} | {nt} | {'Y' if b else '-'} | {'Y' if a else '-'} |")
    w("")

    # ---- /audit per step in Phase 4 / LargeTask
    w("## 7. /audit in Phase 4 and LargeTask sessions\n")
    w("Phase 4 = session Read Phase4_Implementation.md; LargeTask = lane large_task or Read LargeTask.md. Audit = Skill audit, user /audit, or Agent whose prompt/description invokes audit.\n")
    w("| Session | Kind | Week | distinct C# files edited | audit calls | files/audit |")
    w("|---|---|---|---:|---:|---|")
    tot_f = tot_a = 0
    for sid, seq in sorted(per_session_seq.items(), key=lambda kv: session_weeks.get(kv[0], "")):
        kinds = {e.kind for e in seq}
        lane = (lanes.get(sid) or (None,))[0]
        tags = []
        if "marker:phase4" in kinds:
            tags.append("phase4")
        if lane == "large_task" or "marker:largetask" in kinds:
            tags.append("large_task")
        if not tags:
            continue
        files_ed = {e.detail for e in seq if e.kind == "edit:cs"}
        audits = sum(1 for e in seq if e.kind in ("skill:audit", "audit:via_agent"))
        tot_f += len(files_ed)
        tot_a += audits
        w(f"| {sid[:8]} | {'+'.join(tags)} | {session_weeks.get(sid,'?')} | {len(files_ed)} | {audits} | {'-' if not files_ed else (f'{len(files_ed)/audits:.1f}' if audits else 'NO AUDIT')} |")
    w(f"\nTotals: {tot_f} distinct C# files edited, {tot_a} audit invocations.\n")

    # ---- top manual patterns with examples
    w("## 8. Top manual patterns with example sessions\n")
    mk = [k for k in fine if k.startswith("manual:")]
    for k in sorted(mk, key=lambda x: -fine[x]):
        evs = [e for e in events if e.kind == k]
        sc = collections.Counter(e.sid[:8] for e in evs)
        w(f"### {k} — {fine[k]} calls, {len(sc)} sessions\n")
        w("Top sessions: " + ", ".join(f"{s}({c})" for s, c in sc.most_common(6)) + "\n")
        for e in evs[:: max(1, len(evs) // 4)][:4]:
            w(f"- {e.sid[:8]} {e.week}: `{e.detail[:150].replace(chr(10), ' ')}`")
        w("")

    # ---- per-lane summary
    w("## 9. Per-lane usage of key tools (sessions using / sessions in lane)\n")
    lane_sessions = collections.defaultdict(set)
    for sid in top_sessions:
        lane_sessions[(lanes.get(sid) or ("untracked",))[0] or "unset"].add(sid)
    keyk = ["tool:typecheck.py", "tool:codeindex.py", "tool:usages.py", "skill:discover", "skill:audit", "manual:grep_type_cs", "manual:read_cs_whole"]
    w("| Lane | Sessions | " + " | ".join(keyk) + " |")
    w("|---|---:|" + "---:|" * len(keyk))
    for ln, ss in sorted(lane_sessions.items(), key=lambda x: -len(x[1])):
        w(f"| {ln} | {len(ss)} | " + " | ".join(str(len(sessions_with[k] & ss)) for k in keyk) + " |")
    w("")

    # ---- context splits
    w("## 10. Context splits\n")
    fs = sorted(e.ts for e in events if e.kind == "tool:feature_state.py" and e.ts)
    first_fs = fs[0] if fs else None
    st = [e for e in events if e.kind in ("manual:state_edit_tool", "manual:state_edit_bash")]
    after = [e for e in st if first_fs and e.ts and e.ts > first_fs]
    w(f"feature_state.py first used {first_fs}. Hand edits of state.json/_Progress.md: {len(st)} total, {len(after)} after that date "
      f"(sessions: {', '.join(sorted({e.sid[:8] for e in after})[:12])}).\n")
    aft_c = collections.Counter(os.path.basename(e.detail.split()[0]) if e.kind=='manual:state_edit_tool' else 'bash' for e in after)
    w("After-date hand edits by target: " + ", ".join(f"{k}={v}" for k, v in aft_c.most_common(8)) + "\n")
    lw = {e.sid for e in events if e.kind == "skill:land-worktree"} | land_sessions
    wr = [e for e in events if e.kind == "manual:git_worktree_remove"]
    w(f"git worktree remove / branch -D: {len(wr)} calls; {sum(1 for e in wr if e.sid in lw)} inside sessions that ran /land-worktree (skill-directed), {sum(1 for e in wr if e.sid not in lw)} outside.\n")
    wa = [e for e in events if e.kind == "manual:git_worktree_add"]
    w("git worktree add sessions: " + ", ".join(f"{e.sid[:8]} {e.week}" for e in wa) + "\n")

    # ---- metrics.md token categories
    w("## 11. Session metrics.md token categories (by week of session folder)\n")
    cat_rx = re.compile(r"^\| (Runnable tools|Skills|Subagents|Ad-hoc tool calls|Session lifecycle|Rule & process loads) \|[^|]*\| ([\d,]+) \| ([\d.]+)%")
    tot_rx = re.compile(r"^(?:Total |\| Total tokens \| )([\d,]+)")
    agg = collections.defaultdict(lambda: collections.Counter())
    nsess = collections.Counter()
    for mp in sorted(glob.glob(os.path.join(SESS_DIR, "*", "metrics.md"))):
        folder = os.path.basename(os.path.dirname(mp))
        try:
            d0 = dt.datetime.strptime(folder[:10], "%Y-%m-%d")
        except ValueError:
            continue
        y, wn, _ = d0.isocalendar()
        wk = f"{y}-W{wn:02d}"
        got = False
        for line in open(mp, errors="replace"):
            m = tot_rx.match(line)
            if m:
                agg[wk]["Total"] += int(m.group(1).replace(",", ""))
                got = True
            m = cat_rx.match(line)
            if m:
                agg[wk][m.group(1)] += int(m.group(2).replace(",", ""))
        if got:
            nsess[wk] += 1
    cats = ["Runnable tools", "Skills", "Subagents", "Ad-hoc tool calls"]
    w("| Week | Sessions | " + " | ".join(cats) + " |")
    w("|---|---:|" + "---:|" * len(cats))
    for wk in sorted(agg):
        T = agg[wk]["Total"] or 1
        w(f"| {wk} | {nsess[wk]} | " + " | ".join(f"{100*agg[wk][c]/T:.1f}%" for c in cats) + " |")
    w("")

    with open(OUT, "w") as fh:
        fh.write("\n".join(L))
    # compact stdout
    print("wrote", OUT)
    for k in sorted(keys, key=lambda x: (order[x.split(":")[0]], -total[x])):
        print(f"{k}\t{total[k]}\t{len(sessions_with[k])}")


if __name__ == "__main__":
    main()
