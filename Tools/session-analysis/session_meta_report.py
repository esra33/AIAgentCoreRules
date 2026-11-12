#!/usr/bin/env python3
"""Meta-analysis of session metrics and retrospectives, written as one self-contained HTML page.

Reads every session folder produced by Tools/session-lifecycle:

    <reports root>/Sessions/<date>_<lane>_<name>_<id8>/
        session.json   name, lane, work type, title, times, inaccuracies, iterations, tokens
        retro.md       Router check, Corrections, Discovery gaps, Proposed changes, Applied
        tokens/token-usage-*.md   per-turn "Highest-Cost Turns" table

and reports:

    1. token distribution — per-turn histogram with a fitted normal curve (log scale)
    2. issue heat maps — area x session, root cause x lane
    3. solutions — every proposed change with its status and evidence
    4. what else to improve — recurring open areas, repeated router misses, tracking gaps

Proposal status, in order of trust:
    applied / skipped / pending   the retro's "## Applied" section says so (pending = deferred)
    likely applied      a git commit touched the proposed file after the session ended
    open                neither

Usage:
    python3 session_meta_report.py [--sessions DIR] [--repo DIR ...] [--out FILE]
                                   [--since YYYY-MM-DD] [--until YYYY-MM-DD]

Defaults: --sessions <cwd>/GitIgnoreReports/Sessions, --repo every directory under
<cwd>/GitIgnoredExternals, --out <sessions>/../SessionAnalysis.html. With --since/--until only
sessions started in that window (inclusive) are analysed, and --out defaults to
<sessions>/../MetaReviews/<until or today>_SessionAnalysis.html. Stock python3 only; never
writes anywhere except --out.
"""

import argparse
import datetime
import glob
import html
import json
import math
import os
import re
import subprocess
import sys

ROOT_CAUSES = ["missing-rule", "missing-index-entry", "rule-ignored", "signature-guessed", "scope-misread"]
LANES = ["feature", "bug_fix", "small_task", "large_task", "investigation", "other", "unset"]
# Sessions recorded before work types existed fall back to their lane's work type.
LANE_WORK_TYPE = {"small_task": "small_feature", "large_task": "large_feature", "bug_fix": "bug_fix",
                  "investigation": "question", "feature": "feature", "other": "other"}
PATH_TOKEN = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-]+\.(?:md|py|cs|json|asmdef)\b|(?<![A-Za-z])(?:Tools|Skills|Rules|Processes|Systems|SystemPatterns|Runnable)/[A-Za-z0-9_./-]+")
UNMAPPED = "(gap with no file named)"
REPO_PREFIXES = ("AIAgentCoreRules/", "TripleMatchAiMetaData/", "GitIgnoredExternals/")


# ---------------------------------------------------------------- parsing

def number(cell):
    cell = cell.strip().replace(",", "")
    return int(cell) if cell.isdigit() else None


def sections(text):
    out = {}
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        out[head.strip().lower()] = body
    return out


def table_rows(body):
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|\s*:?-{2,}", line):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip("|"))]
        rows.append(cells)
    return rows[1:] if rows else rows   # drop header


def strip_md(text):
    return re.sub(r"[`*]", "", text).strip()


def area_of(text):
    """Normalise a file/tool mention to a short area label: the file name, so `Runnable/typecheck.py`
    and `typecheck.py` count as one area. SKILL.md and README.md keep their folder."""
    clean = strip_md(text)
    match = PATH_TOKEN.search(clean)
    if match:
        path = match.group(0).strip("./")
        for prefix in REPO_PREFIXES:
            if path.startswith(prefix):
                path = path[len(prefix):]
        for prefix in REPO_PREFIXES:
            if path.startswith(prefix):
                path = path[len(prefix):]
        parts = path.rstrip("/").split("/")
        if "." not in parts[-1]:
            return "/".join(parts[-2:])
        if parts[-1] in ("SKILL.md", "README.md") and len(parts) > 1:
            return "/".join(parts[-2:])
        return parts[-1]
    word = re.match(r"(/?[A-Za-z][\w.-]*)", clean)
    return word.group(1) if word else clean[:40]


def parse_turns(folder):
    turns = {}
    for path in glob.glob(os.path.join(folder, "tokens", "token-usage-*.md")):
        body = sections(open(path, encoding="utf-8").read()).get("highest-cost turns", "")
        for cells in table_rows(body):
            if len(cells) < 10 or not cells[0].startswith("T"):
                continue
            total, uncached, output = number(cells[2]), number(cells[3]), number(cells[4])
            if total is None:
                continue
            turns[cells[0]] = {"turn": cells[0], "total": total,
                               "fresh": (uncached or 0) + (output or 0),
                               "category": cells[8], "tools": number(cells[9]) or 0}
    return sorted(turns.values(), key=lambda t: int(t["turn"][1:]) if t["turn"][1:].isdigit() else 0)


def parse_retro(path):
    text = open(path, encoding="utf-8").read()
    parts = sections(text)
    retro = {"root_causes": [], "router_misses": [], "gaps": [], "proposals": [], "applied": {}}
    # Evidence for "what helped": praise comes from Outcome / Router check / Cost; gaps and proposals
    # mean the element fell short.
    retro["praise_lines"] = [strip_md(l) for key in ("outcome", "router check", "cost", "corrections")
                             for l in parts.get(key, "").splitlines() if l.strip()]
    retro["gap_lines"] = [strip_md(l) for key in ("discovery gaps", "proposed changes")
                          for l in parts.get(key, "").splitlines() if l.strip()]

    corrections = parts.get("corrections", "")
    for cause in ROOT_CAUSES:
        retro["root_causes"] += [cause] * len(re.findall(re.escape(cause), corrections))

    retro["router_hits"] = []
    for cells in table_rows(parts.get("router check", "")):
        if len(cells) >= 2 and re.match(r"^\W*yes\b", strip_md(cells[1]).lower()):
            found = PATH_TOKEN.search(strip_md(cells[0]))
            if found and found.group(0).endswith(".md"):
                retro["router_hits"].append(found.group(0))
        if len(cells) >= 2 and re.match(r"^\W*no\b", strip_md(cells[1]).lower()):
            retro["router_misses"].append({"item": strip_md(cells[0]), "area": area_of(cells[0]),
                                           "note": strip_md(cells[2]) if len(cells) > 2 else ""})

    for line in parts.get("discovery gaps", "").splitlines():
        if re.match(r"^\s*[-*]\s+", line) and not re.match(r"^\s*[-*]\s+none\b", line, re.I):
            item = strip_md(re.sub(r"^\s*[-*]\s+", "", line))
            areas = sorted({area_of(m.group(0)) for m in PATH_TOKEN.finditer(strip_md(line))})
            retro["gaps"].append({"text": item[:220], "areas": areas or [UNMAPPED]})

    for cells in table_rows(parts.get("proposed changes", "")):
        if len(cells) >= 3 and cells[0].strip().isdigit():
            retro["proposals"].append({"n": int(cells[0]), "file": strip_md(cells[1]),
                                       "area": area_of(cells[1]), "change": strip_md(cells[2])[:300],
                                       "why": strip_md(cells[3])[:300] if len(cells) > 3 else ""})

    for line in parts.get("applied", "").splitlines():
        match = re.match(r"^\s*[-*]\s*#(\d+)\s+(applied|skipped|pending)\b:?\s*(.*)", line, re.I)
        if match:
            retro["applied"][int(match.group(1))] = (match.group(2).lower(), strip_md(match.group(3)))

    retro["cost"] = {}
    for line in parts.get("cost", "").splitlines():
        match = re.match(r"^\s*(?:\d+\.|[-*])\s*(\*\*)?\s*(T\d+)\b(.*)", line)
        if match:
            rest = match.group(3)
            # "**T8, 10.08M tokens, 29 tool calls:** the fix ..." — drop the bold heading, keep the explanation
            rest = rest.split("**", 1)[1] if match.group(1) and "**" in rest else rest.split(": ", 1)[-1]
            rest = rest.lstrip(" :.")
            retro["cost"][match.group(2)] = {"verdict": verdict_of(rest), "note": strip_md(rest)[:260]}
    return retro


def verdict_of(text):
    """Classify a retro's judgement of a costly turn: necessary, partly avoidable or avoidable."""
    lower = text.lower()
    necessary = re.search(r"\bnecessary\b", lower) and not re.search(r"\b(not|un)\s*necessary\b", lower)
    if re.search(r"partly necessary|could have|\bbut\b|wasted|slowed|re-reads|would have cut", lower) and necessary:
        return "partly avoidable"
    if re.search(r"avoidable|not necessary|unnecessary|wasted", lower):
        return "avoidable"
    if re.search(r"partly necessary", lower):
        return "partly avoidable"
    return "necessary" if necessary else "no verdict"


# ---------------------------------------------------------------- git evidence

def locate(file_field, repos):
    for match in PATH_TOKEN.finditer(file_field):
        candidate = match.group(0).strip("./")
        for repo in repos:
            name = os.path.basename(repo.rstrip("/")) + "/"
            relative = candidate[len(name):] if candidate.startswith(name) else candidate
            if os.path.exists(os.path.join(repo, relative)):
                return repo, relative
    return None, None


def uncommitted(repo, relative, since):
    try:
        output = subprocess.run(["git", "-C", repo, "status", "--porcelain", "--", relative],
                                capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    modified = os.path.getmtime(os.path.join(repo, relative))
    started = datetime.datetime.fromisoformat(since).timestamp()
    return bool(output.strip()) and modified >= started


def commits_after(repo, relative, since):
    try:
        output = subprocess.run(["git", "-C", repo, "log", "--reverse", "--format=%h|%cI|%s",
                                 "--since=%s" % since, "--", relative],
                                capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.split("|", 2) for line in output.splitlines() if line.count("|") >= 2]


# ---------------------------------------------------------------- transcripts

LIFECYCLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "session-lifecycle")
RUNNABLE = ("typecheck.py", "codeindex.py", "usages.py")
KNOWLEDGE = re.compile(r"(?:^|/)(Systems|SystemPatterns)/(?!README\.md$)|(?:^|/)Rules/(TestingSetup|MagicMatchProjectRules)\.md$|SystemIndex\.md$")
ROUTING = re.compile(r"(?:^|/)(Processes/|Rules/(MetaRouter|StopAndVerify|InvestigationMode|CoreTags)\.md$)")
RULES = re.compile(r"(?:^|/)Rules/[A-Za-z]+\.md$")
METADATA_PATH = re.compile(r"/(AIAgentCoreRules|TripleMatchAiMetaData)/")
MAINTENANCE_SHARE = 0.5   # a session whose edits are mostly metadata files was maintaining the docs, not consuming them
SKILLS = {os.path.basename(p) for p in glob.glob(os.path.join(os.path.dirname(LIFECYCLE_DIR), "..", "Skills", "*"))}


def lifecycle():
    sys.path.insert(0, LIFECYCLE_DIR)
    try:
        import session_lifecycle
        return session_lifecycle
    except ImportError:
        return None
    finally:
        sys.path.pop(0)


def scan_transcripts(state):
    """Runnable runs (with pass/fail), skills and commands used, subagent cost, files loaded."""
    usage = {"runs": {}, "failed_runs": {}, "skills": {}, "subagent_fresh": [], "agents": 0, "loads": [],
             "metadata_edits": 0, "edits": 0, "edited": []}
    module = lifecycle()
    if not module or not state.get("transcript_path"):
        return usage
    project_dir = state.get("project_dir") or os.getcwd()
    try:
        usage["loads"] = sorted({item["file"] for item in module.router_trace(state, project_dir)[1]})
    except Exception:
        pass
    for path, via in module.transcript_files(state.get("transcript_path"), state.get("session_id", "")):
        pending, fresh = {}, 0
        try:
            handle = open(path, encoding="utf-8")
        except OSError:
            continue
        with handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                message = entry.get("message") or {}
                spent = message.get("usage") or {}
                fresh += (spent.get("input_tokens") or 0) + (spent.get("cache_creation_input_tokens") or 0) + (spent.get("output_tokens") or 0)
                content = message.get("content")
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                for block in content if isinstance(content, list) else []:
                    if not isinstance(block, dict):
                        continue
                    kind = block.get("type")
                    if kind == "text" and message.get("role") == "user":
                        for command in re.findall(r"<command-name>/?([\w:-]+)</command-name>", block.get("text", "")):
                            usage["skills"][command] = usage["skills"].get(command, 0) + 1
                    elif kind == "tool_use":
                        name, tool_input = block.get("name"), block.get("input") or {}
                        if name == "Skill":
                            skill = tool_input.get("skill", "?")
                            usage["skills"][skill] = usage["skills"].get(skill, 0) + 1
                        elif name in ("Agent", "Task"):
                            usage["agents"] += 1
                        elif name in ("Edit", "Write"):
                            target = os.path.realpath(tool_input.get("file_path", ""))
                            usage["edits"] += 1
                            usage["edited"].append(os.path.basename(target))
                            if METADATA_PATH.search(target):
                                usage["metadata_edits"] += 1
                        elif name == "Bash":
                            for tool in RUNNABLE:
                                if re.search(r"python3?\s+\S*" + re.escape(tool), tool_input.get("command", "")):
                                    usage["runs"][tool] = usage["runs"].get(tool, 0) + 1
                                    pending[block.get("id")] = tool
                    elif kind == "tool_result" and block.get("tool_use_id") in pending:
                        tool = pending.pop(block["tool_use_id"])
                        text = json.dumps(block.get("content"))
                        if tool == "typecheck.py" and (block.get("is_error") or re.search(r"error CS\d+", text)):
                            usage["failed_runs"][tool] = usage["failed_runs"].get(tool, 0) + 1
        if via == "subagent" and fresh:
            usage["subagent_fresh"].append(fresh)
    return usage


# ---------------------------------------------------------------- savings model

ASSUMPTIONS = {
    "codeindex_calls_replaced": 4,     # one query instead of ~4 greps / partial reads
    "usages_calls_replaced": 6,        # one run instead of ~6 greps across assemblies
    "typecheck_failed_turns_saved": 1, # a caught compile error avoids one Editor round trip with the engineer
    "audit_turns_saved": 0.5,          # an audit before review avoids about half a correction turn
    "doc_hit_surveys_saved": 1.0,      # a knowledge doc a retro credits replaces one discovery survey
    "doc_load_surveys_saved": 0.5,     # a loaded knowledge doc with no retro evidence either way
    "default_survey_fresh": 150000,    # used when no subagent transcripts were measured
}
POSITIVE = re.compile(r"directly shaped|covered|caught|saved|avoided|prevented|helped|grounded|was right|confirmed|found (?:it|the)|shaped", re.I)
NEGATIVE = re.compile(r"had nothing|lacked|no entry|not needed|missing|did not cover|didn't cover|nothing on|miss\b", re.I)


def near(line, name, pattern, window=60, tables=True):
    """Does `line` say `pattern` about `name`? Table rows: `name` in the first cell, `pattern` in the
    others. Prose: `pattern` within `window` characters after `name`."""
    if line.startswith("|"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        return tables and name in cells[0] and bool(pattern.search(" ".join(cells[1:])))
    index = line.find(name)
    return index >= 0 and bool(pattern.search(line[index:index + len(name) + window]))


def median(values, default=0):
    values = sorted(v for v in values if v)
    return values[len(values) // 2] if values else default


def element_kind(path):
    if KNOWLEDGE.search(path):
        return "knowledge doc"
    if ROUTING.search(path):
        return "routing / process"
    if RULES.search(path):
        return "rule"
    return None


def savings(sessions, turns, assumptions):
    a = dict(ASSUMPTIONS, **(assumptions or {}))
    per_call = median([t["fresh"] // t["tools"] for t in turns if t["tools"] and t["fresh"]], 5000)
    per_turn = median([t["fresh"] for t in turns], 50000)
    surveys = [n for s in sessions for n in s["usage"]["subagent_fresh"]]
    per_survey = median(surveys, a["default_survey_fresh"])
    baselines = {"fresh_per_tool_call": per_call, "fresh_per_turn": per_turn, "fresh_per_subagent": per_survey,
                 "measured_subagents": len(surveys)}

    elements = {}

    def credit(name, kind, session, tokens, basis, evidence=None, verdict="helped"):
        e = elements.setdefault(name, {"name": name, "kind": kind, "sessions": set(), "uses": 0, "tokens": 0,
                                       "evidence": [], "basis": basis, "misses": 0, "verdicts": {}})
        e["verdicts"][verdict] = e["verdicts"].get(verdict, 0) + 1
        e["sessions"].add(session["id"])
        e["uses"] += 1
        e["tokens"] += tokens
        if verdict == "insufficient":
            e["misses"] += 1
        if evidence and len(e["evidence"]) < 4:
            e["evidence"].append("%s (%s): %s" % (session["id"], verdict, evidence[:200]))

    for s in sessions:
        u = s["usage"]
        praise, gaps = (s["retro"] or {}).get("praise_lines", []), (s["retro"] or {}).get("gap_lines", [])
        maintenance = u["edits"] > 0 and u["metadata_edits"] / float(u["edits"]) >= MAINTENANCE_SHARE
        for tool, count in u["runs"].items():
            failed = u["failed_runs"].get(tool, 0)
            if tool == "codeindex.py":
                tokens, basis = count * (a["codeindex_calls_replaced"] - 1) * per_call, "(%s − 1) tool calls × %s per call, per query" % (a["codeindex_calls_replaced"], "{:,}".format(per_call))
            elif tool == "usages.py":
                tokens, basis = count * (a["usages_calls_replaced"] - 1) * per_call, "(%s − 1) tool calls × %s per call, per run" % (a["usages_calls_replaced"], "{:,}".format(per_call))
            else:
                tokens, basis = failed * a["typecheck_failed_turns_saved"] * per_turn, "%s turn × %s per turn, per run that caught errors (passing runs: verification only)" % (a["typecheck_failed_turns_saved"], "{:,}".format(per_turn))
            quote = next((l for l in praise if near(l, tool, POSITIVE, tables=False)), None)
            for _ in range(count):
                credit(tool, "Runnable tool", s, 0, basis)
            elements[tool]["tokens"] += tokens
            elements[tool].setdefault("failed", 0)
            elements[tool]["failed"] += failed
            if quote and len(elements[tool]["evidence"]) < 4:
                elements[tool]["evidence"].append("%s: %s" % (s["id"], quote[:200]))
        for skill, count in u["skills"].items():
            if skill not in SKILLS:
                continue
            if skill == "audit":
                tokens = count * a["audit_turns_saved"] * per_turn
                basis = "%s turn × %s per turn, per /audit" % (a["audit_turns_saved"], "{:,}".format(per_turn))
            else:
                tokens, basis = 0, "workflow command — not token-estimated"
            for _ in range(count):
                credit("/" + skill, "skill / command", s, 0, basis)
            elements["/" + skill]["tokens"] += tokens
        if u["agents"]:
            credit("subagents (Explore, fork)", "delegation", s, 0,
                   "keeps survey reads out of the main context — not token-estimated; subagent cost shown as spend")
            elements["subagents (Explore, fork)"]["uses"] += u["agents"] - 1
        # No transcript (e.g. it could not be found): fall back to the retro's Router check "yes" rows.
        loads = u["loads"] or (s["retro"] or {}).get("router_hits", [])
        for path in loads:
            kind = element_kind(path)
            if not kind:
                continue
            stem = os.path.basename(path)[:-3]
            positive = next((l for l in praise if near(l, stem, POSITIVE) and not near(l, stem, NEGATIVE)), None)
            negative = next((l for l in praise if near(l, stem, NEGATIVE)), None) or \
                next((l for l in gaps if stem in l), None)
            if kind == "knowledge doc":
                if maintenance or os.path.basename(path) in u["edited"]:
                    tokens, verdict, quote = 0, "maintenance", None
                elif negative and not positive:
                    tokens, verdict, quote = 0, "insufficient", negative
                elif positive and not negative:
                    tokens, verdict, quote = a["doc_hit_surveys_saved"] * per_survey, "helped", positive
                else:
                    tokens, verdict, quote = a["doc_load_surveys_saved"] * per_survey, "helped, with gaps" if positive else "loaded", positive or negative
                basis = "%s survey (credited) / %s survey (loaded, no evidence) × %s per subagent survey" % (
                    a["doc_hit_surveys_saved"], a["doc_load_surveys_saved"], "{:,}".format(per_survey))
            else:
                tokens, verdict, quote = 0, "loaded", positive
                basis = "routing hit — counted, not token-estimated"
            name = path
            for prefix in REPO_PREFIXES:
                name = name[len(prefix):] if name.startswith(prefix) else name
            credit(name, kind, s, int(tokens), basis, quote, verdict)

    out = []
    for e in elements.values():
        e["sessions"] = sorted(e["sessions"])
        e["tokens"] = int(e["tokens"])
        e["turns_saved"] = round(e["tokens"] / per_turn, 1) if per_turn else 0
        out.append(e)
    out.sort(key=lambda e: (-e["tokens"], -e["uses"]))
    return {"elements": out, "baselines": baselines, "assumptions": a,
            "total": sum(e["tokens"] for e in out), "subagent_spend": sum(surveys)}


# ---------------------------------------------------------------- analysis

def load(sessions_dir, repos):
    sessions = []
    for folder in sorted(glob.glob(os.path.join(sessions_dir, "*", "session.json"))):
        folder = os.path.dirname(folder)
        try:
            state = json.load(open(os.path.join(folder, "session.json"), encoding="utf-8"))
        except ValueError:
            continue
        tokens = state.get("tokens") or {}
        session = {"folder": os.path.basename(folder), "id": state.get("session_id", "")[:8],
                   "lane": state.get("lane") or "unset",
                   "work_type": state.get("work_type") or LANE_WORK_TYPE.get(state.get("lane"), "unset"),
                   # Set by /feature and /resume-work. Older feature-lane sessions only carry the title.
                   "feature": state.get("feature") or (state.get("title") if state.get("lane") == "feature" else None),
                   "phase": state.get("phase"),
                   "title": state.get("name") or state.get("title") or "",
                   "started": state.get("started_at") or "", "ended": state.get("ended_at") or "",
                   "end_session_run": bool(state.get("end_session_run")),
                   "inaccuracies": len(state.get("inaccuracies", [])),
                   # logged during the session (engineer or agent), not back-filled by /end-session
                   "inaccuracies_live": sum(1 for i in state.get("inaccuracies", [])
                                            if i.get("source", "engineer") != "retro"),
                   "iterations": len(state.get("iterations", [])),
                   "lane_changes": state.get("lane_history", []),
                   "tokens": tokens.get("total_tokens") if tokens.get("available") else None,
                   "turn_count": tokens.get("turns"), "subagents": tokens.get("subagents"),
                   "turns": parse_turns(folder), "retro": None,
                   "usage": scan_transcripts(state)}
        retro_path = os.path.join(folder, "retro.md")
        if os.path.exists(retro_path):
            session["retro"] = parse_retro(retro_path)
            since = session["ended"] or datetime.datetime.fromtimestamp(
                os.path.getmtime(retro_path)).astimezone().isoformat()
            for proposal in session["retro"]["proposals"]:
                resolve_status(proposal, session["retro"]["applied"], since, repos)
        sessions.append(session)
    return sessions


def resolve_status(proposal, applied, since, repos):
    if proposal["n"] in applied:
        state, detail = applied[proposal["n"]]
        proposal.update(status=state, evidence="retro Applied section" + (": " + detail if detail else ""))
        return
    repo, relative = locate(proposal["file"], repos)
    if repo:
        commits = commits_after(repo, relative, since)
        if commits:
            sha, date, subject = commits[0]
            proposal.update(status="likely applied",
                            evidence="%s %s %s — %s" % (os.path.basename(repo), sha, date[:10], subject[:120]))
            return
        if uncommitted(repo, relative, since):
            proposal.update(status="likely applied",
                            evidence="%s/%s changed after the session (uncommitted)" % (os.path.basename(repo), relative))
            return
        proposal.update(status="open", evidence="no commit to %s/%s since the session" % (os.path.basename(repo), relative))
        return
    proposal.update(status="open", evidence="file not found in the scanned repositories")


def stats(values):
    values = [v for v in values if v and v > 0]
    if not values:
        return {"n": 0}
    logs = [math.log10(v) for v in values if v > 0]
    mean = sum(logs) / len(logs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in logs) / (len(logs) - 1)) if len(logs) > 1 else 0.0
    ordered = sorted(values)
    return {"n": len(values), "mean_log": mean, "sd_log": sd, "median": ordered[len(ordered) // 2],
            "min": ordered[0], "max": ordered[-1], "sum": sum(values)}


def analyse(sessions):
    turns = []
    for s in sessions:
        cost = (s["retro"] or {}).get("cost", {})
        for t in s["turns"]:
            judged = cost.get(t["turn"], {"verdict": "no verdict", "note": ""})
            turns.append(dict(t, session=s["id"], lane=s["lane"], work_type=s["work_type"], title=s["title"], date=s["started"][:10],
                              feature=s["feature"],
                              feature_phase=("%s · %s" % (s["feature"], s["phase"] or "phase not recorded")) if s["feature"] else None,
                              **judged))
    retros = [s for s in sessions if s["retro"]]

    heat, kinds = {}, {}
    for s in retros:
        mentions = [(p["area"], "proposal") for p in s["retro"]["proposals"]]
        mentions += [(m["area"], "router miss") for m in s["retro"]["router_misses"]]
        mentions += [(a, "discovery gap") for g in s["retro"]["gaps"] for a in g["areas"]]
        for area, kind in mentions:
            heat.setdefault(area, {}).setdefault(s["id"], []).append(kind)
            kinds.setdefault(area, {}).setdefault(kind, 0)
            kinds[area][kind] += 1
    areas = sorted(heat, key=lambda a: (a == UNMAPPED, -sum(len(v) for v in heat[a].values()), a))

    causes = {c: {l: 0 for l in LANES} for c in ROOT_CAUSES}
    for s in retros:
        for cause in s["retro"]["root_causes"]:
            causes[cause][s["lane"] if s["lane"] in LANES else "other"] += 1

    proposals = [dict(p, session=s["id"], lane=s["lane"], title=s["title"], date=s["started"][:10])
                 for s in retros for p in s["retro"]["proposals"]]

    return {"turns": turns, "heat": heat, "areas": areas, "kinds": kinds, "causes": causes,
            "proposals": proposals, "undecided": undecided_retros(retros),
            "improve": improvements(sessions, retros, heat, proposals, turns),
            "worst": worst(sessions, turns),
            "saved": savings(sessions, turns, ASSUMPTIONS_OVERRIDE),
            "turn_stats": {"total": stats([t["total"] for t in turns]), "fresh": stats([t["fresh"] for t in turns if t["fresh"]])},
            "session_stats": stats([s["tokens"] for s in sessions if s["tokens"]])}


AVOIDABLE = ("partly avoidable", "avoidable")
ASSUMPTIONS_OVERRIDE = {}


def worst(sessions, turns):
    """Rankings of the heaviest turns, sessions, categories, lanes and work types."""
    per_session = []
    for s in sessions:
        own = [t for t in turns if t["session"] == s["id"]]
        if not own:
            continue
        fresh = sum(t["fresh"] for t in own)
        per_session.append({"id": s["id"], "lane": s["lane"], "work_type": s["work_type"], "title": s["title"], "date": s["started"][:10],
                            "turns": len(own), "fresh": fresh, "total": sum(t["total"] for t in own),
                            "fresh_per_turn": fresh // len(own),
                            "avoidable": sum(t["fresh"] for t in own if t["verdict"] in AVOIDABLE),
                            "subagents": s["subagents"], "inaccuracies": s["inaccuracies"], "iterations": s["iterations"]})

    def group(key):
        out = {}
        for t in turns:
            if key in ("feature", "feature_phase") and not t[key]:
                continue   # only sessions that belong to a feature
            g = out.setdefault(t[key] or "unknown", {"name": t[key] or "unknown", "turns": 0, "fresh": 0, "total": 0, "max": 0, "tools": 0})
            g["turns"] += 1
            g["fresh"] += t["fresh"]
            g["total"] += t["total"]
            g["tools"] += t["tools"]
            g["max"] = max(g["max"], t["fresh"])
        fresh_sum = sum(g["fresh"] for g in out.values()) or 1
        for g in out.values():
            g["mean"] = g["fresh"] // g["turns"]
            g["share"] = round(100.0 * g["fresh"] / fresh_sum, 1)
        return sorted(out.values(), key=lambda g: -g["fresh"])

    return {"sessions": per_session, "categories": group("category"), "lanes": group("lane"),
            "work_types": group("work_type"),
            "features": group("feature"), "feature_phases": group("feature_phase"),
            "avoidable": sum(t["fresh"] for t in turns if t["verdict"] in AVOIDABLE),
            "judged": sum(1 for t in turns if t["verdict"] != "no verdict")}


def undecided_retros(retros):
    """Retros with a proposal still waiting on the engineer: `pending` in the Applied section
    (deferred on purpose), or no Applied line at all (never decided)."""
    rows = []
    for s in retros:
        recorded = s["retro"]["applied"]
        pending = sorted(n for n, (state, _detail) in recorded.items() if state == "pending")
        undecided = sorted(p["n"] for p in s["retro"]["proposals"] if p["n"] not in recorded)
        if pending or undecided:
            rows.append({"session": s["id"], "date": s["started"][:10], "lane": s["lane"], "title": s["title"],
                         "folder": s["folder"], "pending": pending, "undecided": undecided})
    return rows


def improvements(sessions, retros, heat, proposals, turns):
    items = []
    open_by_area = {}
    for p in proposals:
        if p["status"] == "open":
            open_by_area.setdefault(p["area"], []).append(p)
    for area, group in sorted(open_by_area.items(), key=lambda kv: -sum(len(v) for v in heat.get(kv[0], {}).values())):
        mentions = sum(len(v) for v in heat.get(area, {}).values())
        items.append({"kind": "Open proposal", "weight": mentions,
                      "text": "%s — %d open proposal(s), mentioned %d time(s) across %d session(s): %s"
                              % (area, len(group), mentions, len(heat.get(area, {})), group[0]["change"][:160])})

    misses = {}
    for s in retros:
        for m in s["retro"]["router_misses"]:
            misses.setdefault(m["area"], set()).add(s["id"])
    for area, ids in sorted(misses.items(), key=lambda kv: -len(kv[1])):
        items.append({"kind": "Router miss", "weight": len(ids) * 2,
                      "text": "%s was expected but not loaded or run in %d session(s) (%s). Make it an explicit, checked step in the lane process."
                              % (area, len(ids), ", ".join(sorted(ids)))})

    unset = [s for s in sessions if s["lane"] == "unset"]
    no_end = [s for s in sessions if s["lane"] != "unset" and not s["end_session_run"]]
    no_tokens = [s for s in sessions if s["lane"] != "unset" and s["tokens"] is None]
    unlogged = [s for s in retros if s["retro"]["root_causes"] and s["inaccuracies_live"] == 0]
    if unset:
        items.append({"kind": "Tracking", "weight": len(unset),
                      "text": "%d of %d session folders never recorded a lane (%s). Likely short or subagent sessions — consider having hook-start skip or tag them."
                              % (len(unset), len(sessions), ", ".join(s["id"] for s in unset))})
    if no_end:
        items.append({"kind": "Tracking", "weight": len(no_end),
                      "text": "%d classified session(s) closed without /end-session, so no retrospective: %s."
                              % (len(no_end), ", ".join("%s (%s)" % (s["id"], s["lane"]) for s in no_end))})
    if no_tokens:
        items.append({"kind": "Tracking", "weight": len(no_tokens),
                      "text": "%d classified session(s) have no token data: %s." % (len(no_tokens), ", ".join(s["id"] for s in no_tokens))})
    if unlogged:
        items.append({"kind": "Tracking", "weight": len(unlogged),
                      "text": "%d retro(s) name correction root causes but none were logged live by the engineer or agent (%s) — corrections are being found at retro time."
                              % (len(unlogged), ", ".join(s["id"] for s in unlogged))})

    flagged = sorted((t for t in turns if t["verdict"] in AVOIDABLE), key=lambda t: -t["fresh"])
    for t in flagged[:5]:
        items.append({"kind": "Worst performer", "weight": 4,
                      "text": "%s %s (%s, %s): %s fresh / %s total tokens, judged %s in its retro — %s"
                              % (t["session"], t["turn"], t["lane"], t["category"], "{:,}".format(t["fresh"]),
                                 "{:,}".format(t["total"]), t["verdict"], t["note"][:180])})

    fresh = [t for t in turns if t["fresh"]]
    if len(fresh) > 2:
        logs = [math.log10(t["fresh"]) for t in fresh]
        mean = sum(logs) / len(logs)
        sd = math.sqrt(sum((x - mean) ** 2 for x in logs) / (len(logs) - 1))
        outliers = [t for t in fresh if math.log10(t["fresh"]) > mean + 2 * sd]
        for t in outliers:
            items.append({"kind": "Token outlier", "weight": 3,
                          "text": "%s %s (%s) used %s fresh tokens — more than 2σ above the mean turn."
                                  % (t["session"], t["turn"], t["category"], "{:,}".format(t["fresh"]))})
        by_cat = {}
        for t in fresh:
            by_cat[t["category"]] = by_cat.get(t["category"], 0) + t["fresh"]
        top, amount = max(by_cat.items(), key=lambda kv: kv[1])
        items.append({"kind": "Token share", "weight": 2,
                      "text": "'%s' turns account for %d%% of fresh tokens across all sessions."
                              % (top, round(100.0 * amount / sum(by_cat.values())))})
    return sorted(items, key=lambda i: -i["weight"])


# ---------------------------------------------------------------- html

def render(sessions, result, sources):
    data = json.dumps({"sessions": [{k: s[k] for k in ("id", "folder", "lane", "work_type", "title", "started", "tokens", "turn_count",
                                                     "subagents", "inaccuracies", "iterations", "end_session_run")}
                                    | {"has_retro": bool(s["retro"])} for s in sessions],
                       "result": result, "generated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
                       "sources": sources, "lanes": LANES, "causes": ROOT_CAUSES})
    return TEMPLATE.replace("__DATA__", data.replace("</", "<\\/"))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Session Meta-Analysis</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e2e2dc;--accent:#2f6fdb;--band:#2f6fdb22;--curve:#d9480f;
--h0:#f1f3f5;--h1:#ffe8cc;--h2:#ffc078;--h3:#fd7e14;--h4:#d9480f;--ok:#2b8a3e;--warn:#e67700;--bad:#c92a2a}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--panel:#1f1f1d;--ink:#ecece8;--muted:#a3a39c;--line:#34342f;
--accent:#74a7ff;--band:#74a7ff26;--curve:#ff922b;--h0:#262624;--h1:#4a3217;--h2:#7a4a12;--h3:#b8600c;--h4:#ff922b;--ok:#69db7c;--warn:#ffc078;--bad:#ff8787}}
:root[data-theme="dark"]{--bg:#161615;--panel:#1f1f1d;--ink:#ecece8;--muted:#a3a39c;--line:#34342f;--accent:#74a7ff;--band:#74a7ff26;--curve:#ff922b;
--h0:#262624;--h1:#4a3217;--h2:#7a4a12;--h3:#b8600c;--h4:#ff922b;--ok:#69db7c;--warn:#ffc078;--bad:#ff8787}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:0 0 12px}
.muted{color:var(--muted)}.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;margin:18px 0;overflow-x:auto}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:16px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}.kpi b{display:block;font-size:22px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.heat td.c{text-align:center;min-width:34px;font-weight:600}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid currentColor;white-space:nowrap}
.applied{color:var(--ok)}.likely{color:var(--warn)}.open{color:var(--bad)}.skipped{color:var(--muted)}.pending{color:var(--accent)}
button{font:inherit;background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 10px;cursor:pointer}
button.on{border-color:var(--accent);color:var(--accent)}svg text{fill:var(--muted);font-size:11px}
.legend span{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:middle;margin:0 4px 0 10px}
ol li{margin-bottom:6px}.note{font-size:12px}
</style></head><body><main>
<h1>Session Meta-Analysis</h1>
<div class="muted" id="sub"></div>
<div class="kpis" id="kpis"></div>

<section class="panel"><h2>1 · Token expenditure</h2>
<div><button data-m="fresh" class="on">Fresh tokens (uncached in + output)</button> <button data-m="total">Total tokens (incl. cache reads)</button></div>
<svg id="bell" viewBox="0 0 900 320" width="100%" role="img" aria-label="Histogram of tokens per turn with fitted normal curve"></svg>
<p class="note muted" id="bellnote"></p>
<h3>Per session</h3><svg id="dots" viewBox="0 0 900 110" width="100%" role="img" aria-label="Session token totals"></svg>
</section>

<section class="panel"><h2>2 · Worst performers</h2>
<p class="muted note">Ranked by the metric selected in section 1. Verdicts come from each retro's Cost section: <span class="pill applied">necessary</span> <span class="pill likely">partly avoidable</span> <span class="pill open">avoidable</span> <span class="pill skipped">no verdict</span> (turns the retro did not discuss).</p>
<h3>Heaviest turns</h3><svg id="worstbars" viewBox="0 0 900 330" width="100%" role="img" aria-label="Heaviest turns"></svg>
<div id="worstturns"></div>
<h3>Sessions</h3><div id="worstsessions"></div>
<h3>By turn category</h3><div id="worstcats"></div>
<h3>By lane</h3><div id="worstlanes"></div>
<h3>By work type</h3><div id="worstworktypes"></div>
<h3>By feature</h3><div id="worstfeatures"></div>
<h3>By feature phase</h3><div id="worstfeaturephases"></div>
</section>

<section class="panel"><h2>3 · What saved us</h2>
<p class="muted note" id="savednote"></p>
<svg id="savedbars" viewBox="0 0 900 300" width="100%" role="img" aria-label="Estimated tokens saved per element"></svg>
<div id="savedtable"></div>
<h3>Estimate model</h3><div id="savedmodel"></div>
</section>

<section class="panel"><h2>4 · Where issues concentrate</h2>
<p class="muted note">Mentions per area per session, from retro Proposed changes, Router check misses and Discovery gaps. Hover a cell for the breakdown.</p>
<div id="heatA"></div>
<h3>Correction root causes × lane</h3><div id="heatB"></div>
</section>

<section class="panel"><h2>5 · Solutions proposed and their status</h2>
<p class="muted note">applied/skipped/pending = recorded in the retro's Applied section (pending = deferred on purpose) · likely applied = a commit touched the file after the session (verify) · open = neither.</p>
<h3>Retros with pending or undecided proposals</h3>
<p class="muted note">Pending = deferred in the Applied section · undecided = no Applied line at all. Mark each with <code>session_lifecycle.py retro --folder &lt;id8&gt; --mark N --status …</code>.</p>
<div id="undecided"></div>
<h3>Every proposal</h3>
<div id="props"></div></section>

<section class="panel"><h2>6 · What else could be improved</h2><ol id="improve"></ol></section>
<p class="muted note" id="src"></p>
</main>
<script>
const D=__DATA__, R=D.result, esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt=n=>n==null?"–":n>=1e6?(n/1e6).toFixed(n>=1e7?0:1)+"M":n>=1e3?Math.round(n/1e3)+"k":String(n);
const S=D.sessions, withTok=S.filter(s=>s.tokens), retros=S.filter(s=>s.has_retro);
document.getElementById("sub").textContent=`${S.length} session folders · ${retros.length} retrospectives · ${R.turns.length} measured turns · generated ${D.generated}`;
const P=R.proposals, done=P.filter(p=>p.status==="applied").length, likely=P.filter(p=>p.status==="likely applied").length;
document.getElementById("kpis").innerHTML=[["Sessions with tokens",withTok.length+" / "+S.length],["Total tokens",fmt(withTok.reduce((a,s)=>a+s.tokens,0))],
["Median session",fmt(R.session_stats.median)],["Proposals",P.length],["Applied / likely",done+" / "+likely],["Pending / open",P.filter(p=>p.status==="pending").length+" / "+P.filter(p=>p.status==="open").length],["Flagged avoidable",fmt(R.worst.avoidable)+" fresh"],["Est. saved",fmt(R.saved.total)+" fresh"]]
.map(([k,v])=>`<div class="kpi"><span class="muted">${k}</span><b>${v}</b></div>`).join("");

function bell(metric){
  const svg=document.getElementById("bell"), vals=R.turns.map(t=>t[metric]).filter(v=>v>0), st=R.turn_stats[metric];
  if(vals.length<2){svg.innerHTML='<text x="20" y="40">Not enough turns with token data yet.</text>';return}
  const L=vals.map(Math.log10), lo=Math.floor(Math.min(...L)*2)/2, hi=Math.ceil(Math.max(...L)*2)/2, W=900,H=320,m={l:50,r:20,t:20,b:40};
  const bins=Math.max(6,Math.min(20,Math.round(Math.sqrt(vals.length)*2))), bw=(hi-lo)/bins, counts=Array(bins).fill(0), items=Array.from({length:bins},()=>[]);
  L.forEach((x,i)=>{const b=Math.min(bins-1,Math.floor((x-lo)/bw));counts[b]++;items[b].push(R.turns.filter(t=>t[metric]>0)[i])});
  const pdf=x=>Math.exp(-0.5*((x-st.mean_log)/st.sd_log)**2)/(st.sd_log*Math.sqrt(2*Math.PI))*vals.length*bw;
  const peak=Math.max(...counts, st.sd_log?pdf(st.mean_log):0), X=x=>m.l+(x-lo)/(hi-lo)*(W-m.l-m.r), Y=y=>H-m.b-y/peak*(H-m.t-m.b);
  let g="";
  if(st.sd_log){[[2,"2σ"],[1,"1σ"]].forEach(([k])=>{g+=`<rect x="${X(st.mean_log-k*st.sd_log)}" y="${m.t}" width="${X(st.mean_log+k*st.sd_log)-X(st.mean_log-k*st.sd_log)}" height="${H-m.t-m.b}" fill="var(--band)"/>`})}
  counts.forEach((c,i)=>{const x=X(lo+i*bw),w=X(lo+(i+1)*bw)-x-2;const tip=items[i].map(t=>`${t.session} ${t.turn} ${t.category}: ${fmt(t[metric])}`).join("\n");
    g+=`<rect x="${x+1}" y="${Y(c)}" width="${w}" height="${H-m.b-Y(c)}" fill="var(--accent)" opacity=".75"><title>${esc(fmt(10**(lo+i*bw))+"–"+fmt(10**(lo+(i+1)*bw))+": "+c+" turn(s)\n"+tip)}</title></rect>`});
  if(st.sd_log){let d="";for(let k=0;k<=120;k++){const x=lo+(hi-lo)*k/120;d+=(k?"L":"M")+X(x).toFixed(1)+","+Y(pdf(x)).toFixed(1)}
    g+=`<path d="${d}" fill="none" stroke="var(--curve)" stroke-width="2.5"/><line x1="${X(st.mean_log)}" x2="${X(st.mean_log)}" y1="${m.t}" y2="${H-m.b}" stroke="var(--curve)" stroke-dasharray="4 4"/>`}
  for(let e=Math.ceil(lo);e<=Math.floor(hi);e++){g+=`<line x1="${X(e)}" x2="${X(e)}" y1="${H-m.b}" y2="${H-m.b+5}" stroke="var(--muted)"/><text x="${X(e)}" y="${H-m.b+18}" text-anchor="middle">${fmt(10**e)}</text>`;
    if(e+Math.log10(3)<hi)g+=`<text x="${X(e+Math.log10(3))}" y="${H-m.b+18}" text-anchor="middle" opacity=".6">${fmt(3*10**e)}</text>`}
  g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${H-m.b}" y2="${H-m.b}" stroke="var(--line)"/><text x="${W/2}" y="${H-6}" text-anchor="middle">tokens per turn (log scale)</text><text x="12" y="${m.t+8}">turns</text>`;
  svg.innerHTML=g;
  document.getElementById("bellnote").textContent=`n=${st.n} turns · geometric mean ${fmt(10**st.mean_log)} · median ${fmt(st.median)} · ±1σ ${fmt(10**(st.mean_log-st.sd_log))}–${fmt(10**(st.mean_log+st.sd_log))} · max ${fmt(st.max)}. Token use is right-skewed, so the normal curve is fitted to log10(tokens); shaded bands are ±1σ and ±2σ.`;
}
const VC={"necessary":"applied","partly avoidable":"likely","avoidable":"open","no verdict":"skipped"},VCOL={"necessary":"var(--ok)","partly avoidable":"var(--warn)","avoidable":"var(--bad)","no verdict":"var(--muted)"};
function worst(metric){
  const other=metric==="fresh"?"total":"fresh", top=[...R.turns].filter(t=>t[metric]>0).sort((a,b)=>b[metric]-a[metric]).slice(0,10), svg=document.getElementById("worstbars");
  if(!top.length){svg.innerHTML='<text x="20" y="40">No turn data yet.</text>'}else{const max=top[0][metric],rowH=31;let g="";
    top.forEach((t,i)=>{const y=10+i*rowH,w=Math.max(2,t[metric]/max*560);
      g+=`<text x="0" y="${y+18}">${esc(t.session+" "+t.turn)}</text><rect x="120" y="${y+4}" width="${w}" height="20" rx="3" fill="${VCOL[t.verdict]}" opacity=".85"><title>${esc(t.title+"\n"+t.category+" · "+t.tools+" tool calls\n"+t.verdict+(t.note?": "+t.note:""))}</title></rect>`+
        `<text x="${126+w}" y="${y+18}">${fmt(t[metric])} · ${esc(t.category)}</text>`});svg.innerHTML=g}
  document.getElementById("worstturns").innerHTML='<table><tr><th>#</th><th>Session · turn</th><th>Category</th><th>'+metric+'</th><th>'+other+'</th><th>Tool calls</th><th>'+metric+' / call</th><th>Verdict</th><th>Retro note</th></tr>'+
    top.map((t,i)=>`<tr><td>${i+1}</td><td>${esc(t.date)} · ${esc(t.lane)}<br><b>${t.session} ${t.turn}</b> <span class="muted">${esc(t.title)}</span></td><td>${esc(t.category)}</td><td>${fmt(t[metric])}</td><td class="muted">${fmt(t[other])}</td><td>${t.tools}</td><td>${t.tools?fmt(Math.round(t[metric]/t.tools)):"–"}</td><td><span class="pill ${VC[t.verdict]}">${t.verdict}</span></td><td class="muted note">${esc(t.note)}</td></tr>`).join("")+'</table>';
  const ss=[...R.worst.sessions].sort((a,b)=>b[metric]-a[metric]);
  document.getElementById("worstsessions").innerHTML='<table><tr><th>#</th><th>Session</th><th>Lane · work type</th><th>Turns</th><th>'+metric+'</th><th>'+metric+' / turn</th><th>Flagged avoidable (fresh)</th><th>Subagents</th><th>Inacc. / iter.</th></tr>'+
    ss.map((s,i)=>`<tr><td>${i+1}</td><td>${esc(s.date)} <b>${s.id}</b><br><span class="muted">${esc(s.title)}</span></td><td>${esc(s.lane)}<br><span class="muted">${esc(s.work_type)}</span></td><td>${s.turns}</td><td>${fmt(s[metric])}</td><td>${fmt(Math.round(s[metric]/s.turns))}</td><td>${s.avoidable?fmt(s.avoidable)+" ("+Math.round(100*s.avoidable/(s.fresh||1))+"%)":"–"}</td><td>${s.subagents??"–"}</td><td>${s.inaccuracies} / ${s.iterations}</td></tr>`).join("")+'</table>';
  const grp=list=>'<table><tr><th>Name</th><th>Turns</th><th>'+metric+'</th><th>Mean / turn</th><th>Heaviest turn (fresh)</th><th>Share of fresh</th></tr>'+
    [...list].sort((a,b)=>b[metric]-a[metric]).map(g=>`<tr><td>${esc(g.name)}</td><td>${g.turns}</td><td>${fmt(g[metric])}</td><td>${fmt(Math.round(g[metric]/g.turns))}</td><td>${fmt(g.max)}</td><td><span style="display:inline-block;height:10px;width:${g.share*2}px;background:var(--accent);border-radius:2px;vertical-align:middle"></span> ${g.share}%</td></tr>`).join("")+'</table>';
  document.getElementById("worstcats").innerHTML=grp(R.worst.categories);
  document.getElementById("worstlanes").innerHTML=grp(R.worst.lanes);
  document.getElementById("worstworktypes").innerHTML=grp(R.worst.work_types);
  document.getElementById("worstfeatures").innerHTML=R.worst.features.length?grp(R.worst.features):'<p class="muted">No feature sessions.</p>';
  document.getElementById("worstfeaturephases").innerHTML=R.worst.feature_phases.length?grp(R.worst.feature_phases):'<p class="muted">No feature sessions.</p>';
}
document.querySelectorAll("button[data-m]").forEach(b=>b.onclick=()=>{document.querySelectorAll("button[data-m]").forEach(x=>x.classList.toggle("on",x===b));bell(b.dataset.m);worst(b.dataset.m)});
bell("fresh");worst("fresh");
(function saved(){const V=R.saved,E=V.elements,B=V.baselines,est=E.filter(e=>e.tokens>0),svg=document.getElementById("savedbars");
  document.getElementById("savednote").textContent=`Estimated ${fmt(V.total)} fresh tokens (≈${(V.total/(B.fresh_per_turn||1)).toFixed(0)} turns at the median ${fmt(B.fresh_per_turn)} per turn) saved by the elements below. These are estimates from the model at the bottom of this section, not measurements; subagents themselves spent ${fmt(V.subagent_spend)} fresh tokens.`;
  if(!est.length){svg.innerHTML='<text x="20" y="40">No estimated savings yet.</text>'}else{const top=est.slice(0,9),max=top[0].tokens,rowH=32;svg.setAttribute("viewBox",`0 0 900 ${20+top.length*rowH}`);
    const col={"Runnable tool":"var(--accent)","knowledge doc":"var(--ok)","skill / command":"var(--warn)","routing / process":"var(--muted)","rule":"var(--muted)","delegation":"var(--curve)"};
    svg.innerHTML=top.map((e,i)=>{const y=10+i*rowH,w=Math.max(2,e.tokens/max*540);return`<text x="0" y="${y+18}">${esc(e.name.length>28?"…"+e.name.slice(-27):e.name)}</text><rect x="200" y="${y+4}" width="${w}" height="20" rx="3" fill="${col[e.kind]||"var(--accent)"}" opacity=".85"><title>${esc(e.kind+" · "+e.uses+" uses · "+e.basis)}</title></rect><text x="${206+w}" y="${y+18}">${fmt(e.tokens)} · ≈${e.turns_saved} turns</text>`}).join("")}
  document.getElementById("savedtable").innerHTML='<table><tr><th>Element</th><th>Kind</th><th>Uses</th><th>Sessions</th><th>Est. fresh saved</th><th>≈ Turns</th><th>Evidence</th></tr>'+
    E.map(e=>`<tr><td><code>${esc(e.name)}</code>${e.misses?` <span class="pill open">${e.misses}× insufficient</span>`:""}${e.failed?` <span class="pill likely">caught errors ${e.failed}×</span>`:""}</td><td>${esc(e.kind)}<br><span class="muted note">${esc(Object.entries(e.verdicts).filter(([k])=>e.kind==="knowledge doc"||k!=="helped").map(([k,n])=>n+"× "+k).join(", "))}</span></td><td>${e.uses}</td><td>${e.sessions.length}</td><td>${e.tokens?fmt(e.tokens):"–"}</td><td>${e.tokens?e.turns_saved:"–"}</td><td class="muted note">${esc(e.evidence.join(" · ")||e.basis)}</td></tr>`).join("")+'</table>';
  const A=V.assumptions;document.getElementById("savedmodel").innerHTML='<table><tr><th>Baseline (measured)</th><th>Value</th></tr>'+
    [["Median fresh tokens per tool call",B.fresh_per_tool_call],["Median fresh tokens per turn",B.fresh_per_turn],["Median fresh tokens per subagent survey ("+B.measured_subagents+" measured)",B.fresh_per_subagent]].map(([k,v])=>`<tr><td>${k}</td><td>${fmt(v)}</td></tr>`).join("")+
    '<tr><th>Assumption (override with --assumptions)</th><th>Value</th></tr>'+Object.entries(A).map(([k,v])=>`<tr><td><code>${k}</code></td><td>${v}</td></tr>`).join("")+'</table>'+
    '<p class="muted note">Knowledge docs earn full credit when a retro’s Outcome, Router check, Cost or Corrections credits them; half credit when loaded with no evidence either way or with both praise and gaps; none when the retro says they fell short (a Router check note, a Discovery gap or a Proposed change naming them). Reads in sessions whose edits were mostly to metadata files, or of a doc the same session edited, are maintenance and not credited. typecheck.py earns credit only for runs that caught compile errors. Routing and rule files are counted but not token-estimated.</p>'})();

(function dots(){const svg=document.getElementById("dots"),v=withTok.map(s=>s.tokens);if(!v.length){svg.innerHTML='<text x="20" y="40">No session totals yet.</text>';return}
  const lo=Math.floor(Math.log10(Math.min(...v))),hi=Math.ceil(Math.log10(Math.max(...v))),X=x=>50+(Math.log10(x)-lo)/(hi-lo||1)*830;let g=`<line x1="50" x2="880" y1="60" y2="60" stroke="var(--line)"/>`;
  for(let e=lo;e<=hi;e++)g+=`<text x="${X(10**e)}" y="85" text-anchor="middle">${fmt(10**e)}</text>`;
  withTok.forEach((s,i)=>g+=`<circle cx="${X(s.tokens)}" cy="${48-(i%3)*10}" r="7" fill="var(--curve)" opacity=".8"><title>${esc(s.id+" · "+s.lane+" · "+s.title+" · "+fmt(s.tokens)+" · "+s.turn_count+" turns")}</title></circle>`);
  svg.innerHTML=g+`<text x="465" y="104" text-anchor="middle">total tokens per session (log scale) · hover for details</text>`})();

function shade(c,max){if(!c)return"var(--h0)";const k=Math.min(4,Math.ceil(c/max*4));return`var(--h${k})`}
(function heatA(){const ids=retros.map(s=>s.id),max=Math.max(1,...R.areas.flatMap(a=>ids.map(i=>(R.heat[a][i]||[]).length)));
  if(!R.areas.length){document.getElementById("heatA").innerHTML='<p class="muted">No retro issues recorded yet.</p>';return}
  let h='<table class="heat"><tr><th>Area</th>'+retros.map(s=>`<th title="${esc(s.title)}">${esc(s.started.slice(5,10))}<br>${esc(s.lane)}<br><span class="muted">${s.id}</span></th>`).join("")+'<th>Total</th><th>Kinds</th></tr>';
  R.areas.forEach(a=>{const tot=ids.reduce((n,i)=>n+(R.heat[a][i]||[]).length,0);
    h+=`<tr><td><code>${esc(a)}</code></td>`+ids.map(i=>{const k=R.heat[a][i]||[];return`<td class="c" style="background:${shade(k.length,max)}" title="${esc(k.join(", "))}">${k.length||""}</td>`}).join("")+
    `<td class="c">${tot}</td><td class="muted">${esc(Object.entries(R.kinds[a]).map(([k,n])=>n+" "+k).join(" · "))}</td></tr>`});
  document.getElementById("heatA").innerHTML=h+'</table><div class="legend muted note">fewer<span style="background:var(--h1)"></span><span style="background:var(--h2)"></span><span style="background:var(--h3)"></span><span style="background:var(--h4)"></span>more</div>'})();

(function heatB(){const lanes=D.lanes.filter(l=>D.causes.some(c=>R.causes[c][l])||retros.some(s=>s.lane===l)),max=Math.max(1,...D.causes.flatMap(c=>lanes.map(l=>R.causes[c][l])));
  let h='<table class="heat"><tr><th>Root cause</th>'+lanes.map(l=>`<th>${l}</th>`).join("")+'<th>Total</th></tr>';
  D.causes.forEach(c=>{const t=lanes.reduce((n,l)=>n+R.causes[c][l],0);h+=`<tr><td>${c}</td>`+lanes.map(l=>`<td class="c" style="background:${shade(R.causes[c][l],max)}">${R.causes[c][l]||""}</td>`).join("")+`<td class="c">${t}</td></tr>`});
  document.getElementById("heatB").innerHTML=h+'</table>'})();

(function undecided(){const U=R.undecided,el=document.getElementById("undecided");
  if(!U.length){el.innerHTML='<p class="muted">Every retro proposal has a decision.</p>';return}
  el.innerHTML='<table><tr><th>Session</th><th>Title</th><th>Pending</th><th>Undecided</th></tr>'+
  U.map(u=>`<tr><td>${esc(u.date)}<br><span class="muted">${esc(u.lane)} · ${u.session}</span></td><td>${esc(u.title)}</td><td>${u.pending.map(n=>"#"+n).join(", ")||"–"}</td><td>${u.undecided.map(n=>"#"+n).join(", ")||"–"}</td></tr>`).join("")+'</table>'})();

(function props(){if(!P.length){document.getElementById("props").innerHTML='<p class="muted">No proposals yet.</p>';return}
  const cls=s=>s==="applied"?"applied":s==="skipped"?"skipped":s==="pending"?"pending":s==="likely applied"?"likely":"open";
  document.getElementById("props").innerHTML='<table><tr><th>Session</th><th>#</th><th>Area</th><th>Change</th><th>Status</th><th>Evidence</th></tr>'+
  P.map(p=>`<tr><td>${esc(p.date)}<br><span class="muted">${esc(p.lane)} · ${p.session}</span></td><td>${p.n}</td><td><code>${esc(p.area)}</code></td><td>${esc(p.change)}</td><td><span class="pill ${cls(p.status)}">${esc(p.status)}</span></td><td class="muted note">${esc(p.evidence)}</td></tr>`).join("")+'</table>'})();

document.getElementById("improve").innerHTML=R.improve.map(i=>`<li><b>${esc(i.kind)}:</b> ${esc(i.text)}</li>`).join("")||"<li>Nothing flagged.</li>";
document.getElementById("src").textContent="Sources: "+D.sources.sessions+" · repos: "+D.sources.repos.join(", ");
</script></body></html>
"""


def in_window(sessions, since, until):
    """Sessions whose start date falls in [since, until]; either bound may be None. Sessions with
    no recorded start are dropped only when a window is given."""
    if not since and not until:
        return sessions
    kept = []
    for s in sessions:
        try:
            started = datetime.date.fromisoformat(s["started"][:10])
        except ValueError:
            continue
        if (since and started < since) or (until and started > until):
            continue
        kept.append(s)
    return kept


def window_label(since, until):
    return "%s → %s" % (since.isoformat() if since else "start", until.isoformat() if until else "today")


def default_out(sessions_dir, since, until):
    """All history: <reports>/SessionAnalysis.html. A window (MetaReview): next to that review's
    tickets, <reports>/MetaReviews/<end date>_SessionAnalysis.html."""
    reports = os.path.dirname(sessions_dir)
    if not since and not until:
        return os.path.join(reports, "SessionAnalysis.html")
    end = (until or datetime.date.today()).isoformat()
    return os.path.join(reports, "MetaReviews", "%s_SessionAnalysis.html" % end)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions", default=os.path.join(os.getcwd(), "GitIgnoreReports", "Sessions"))
    parser.add_argument("--repo", action="append", help="repository to search for proposal evidence (repeatable)")
    parser.add_argument("--out")
    parser.add_argument("--assumptions", help="JSON file overriding savings-model assumptions")
    parser.add_argument("--since", type=datetime.date.fromisoformat,
                        help="only sessions started on or after this date (YYYY-MM-DD)")
    parser.add_argument("--until", type=datetime.date.fromisoformat,
                        help="only sessions started on or before this date (YYYY-MM-DD)")
    args = parser.parse_args()
    if args.assumptions:
        ASSUMPTIONS_OVERRIDE.update(json.load(open(args.assumptions, encoding="utf-8")))
    sessions_dir = os.path.abspath(args.sessions)
    if not os.path.isdir(sessions_dir):
        print("No sessions folder at %s" % sessions_dir)
        return 1
    repos = [os.path.realpath(r) for r in (args.repo or sorted(glob.glob(os.path.join(os.getcwd(), "GitIgnoredExternals", "*"))))
             if os.path.isdir(os.path.join(os.path.realpath(r), ".git"))]
    out = os.path.abspath(args.out or default_out(sessions_dir, args.since, args.until))
    sessions = in_window(load(sessions_dir, repos), args.since, args.until)
    if not sessions:
        print("No sessions started in the window %s." % window_label(args.since, args.until))
        return 1
    result = analyse(sessions)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    source_label = sessions_dir + ("" if not (args.since or args.until) else " · window " + window_label(args.since, args.until))
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(render(sessions, result, {"sessions": source_label, "repos": [os.path.basename(r) for r in repos]}))
    counts = {}
    for p in result["proposals"]:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    print("%d sessions, %d turns, %d proposals %s -> %s" % (len(sessions), len(result["turns"]), len(result["proposals"]), counts, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
