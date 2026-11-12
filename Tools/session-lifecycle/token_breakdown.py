"""Where a session's tokens went, and what saved tokens — estimated from the transcript.

Unit: the same as the token report's Total Tokens — the sum, over every model call, of the
context it read (uncached + cache read + cache write) plus its output. Something added to the
context at call k is re-read by every later call until a compaction, so its cost is

    carried(size, k) = size × (calls from k to the end of its segment)

Sizes are characters / 4, which is close enough for proportions. Every number here is an
estimate; the page and metrics.md label it so.

Standardized operations are the framework's own mechanisms: Runnable tools, the session
lifecycle script, skills, rule/process loads and subagents. Everything else a tool did is
ad-hoc; the rest of the total is conversation and base context (system prompt, CLAUDE.md,
replies, reasoning).

Dependency-free: imported by session_lifecycle.py.
"""

import glob
import json
import os
import re
import statistics

CHARS_PER_TOKEN = 4.0
STANDARDIZED = ["Runnable tools", "Session lifecycle", "Skills", "Rule & process loads", "Subagents"]
AD_HOC = "Ad-hoc tool calls"
BASE = "Conversation & base context"
RUNNABLE_TOOLS = ["typecheck.py", "codeindex.py", "usages.py"]
LIFECYCLE = "session_lifecycle.py"
# Guesstimates of what one Runnable tool call replaces when done by hand: (context tokens, round-trips).
#   codeindex: one exploratory file read plus a grep to find it.
#   usages:    a grep over Assets/ plus two call-site reads.
#   typecheck: grepping the tail of Editor.log, after waiting for the editor to recompile.
AVOIDED_BY_TOOL = {"codeindex.py": (3000, 2), "usages.py": (6000, 3), "typecheck.py": (4000, 2)}
DOC_REVIEW_SAVING = "Doc review vs Miro/Confluence"
CODE_GRAPH_SAVING = "code-graph API"
SAVINGS = ["Parallel tool calls", "Subagent delegation", "Partial file reads",
           "codeindex.py", "usages.py", "typecheck.py", CODE_GRAPH_SAVING, DOC_REVIEW_SAVING]
# code-graph server calls (curl …/api/<route>) and the grep work each replaces: (context tokens, round-trips).
#   type:   a declaration grep, a grep for derived types and a whole-file read for the members.
#   graph:  a grep chain up or down the hierarchy, one grep per level plus a read.
#   search: one grep -rn for the name.
# /api/sources and /api/health are doc-review / launcher routes, not lookups. Only a curl at a command
# position (start, or after ; && || | $( ) counts, so a mention in a commit message or echo is silent.
CODE_GRAPH_PATTERN = re.compile(r"(?:^|[;&|]|\$\()\s*curl\b[^\n|;&]*?/api/(type|graph|search)\b", re.MULTILINE)
GREP_BY_CODE_GRAPH_ROUTE = {"type": (5000, 3), "graph": (6000, 4), "search": (2000, 1)}
# Missed index opportunities: work done by hand that code-graph, codeindex or usages answers.
#   grep:  a grep over C# for a type or member name (the hook-bash matcher, passed in by the caller).
#   chain: 2+ codeindex shape queries on one type, which one /api/type or /api/graph call covers.
#   read:  a whole-file .cs Read never followed by an edit of that file — read only for its shape.
# Each miss is charged its result minus what the index call would have returned (guessed below).
INDEX_CALL_TOKENS = 800
MISSED_GREP = "Type/member grep over C#"
MISSED_CHAIN = "codeindex chain"
MISSED_READ = "Whole-file .cs read for shape"
MISSED = [MISSED_GREP, MISSED_CHAIN, MISSED_READ]
MISSED_EXAMPLES = 5
CODEINDEX_SHAPE_PATTERN = r"python3?\s+\S*codeindex\.py\s+(?:where|members|subclasses|implementers)\s+([A-Za-z_]\w*)"
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# Doc-review preview calls (doc_review.py <command>, mermaid_preview.py = serve), and what the same
# operation would cost through the Miro / Confluence MCP tools: (context tokens, round-trips).
# Averages of real MCP calls (input + result) in this project's transcripts, measured 2026-10-27:
#   serve:    updateConfluencePage ~11.4K + Miro canvas composer skill ~1K + canvas_update_from_svg ~6K.
#   comments: getConfluencePageInlineComments ~1.8K + footer comments ~0.1K + Miro comment list (~0.5K, guessed).
#   reply:    createConfluenceInlineComment (~1.3K, guessed — no call to measure yet).
# Low side: a Confluence republish after every doc edit, which the preview's live reload avoids, is not counted.
DOC_REVIEW_PATTERN = r"python3?\s+\S*(doc_review|mermaid_preview)\.py(?:\s+([\w-]+))?"
MIRO_CONFLUENCE_BY_COMMAND = {"serve": (18400, 3), "comments": (2400, 2), "reply": (1300, 1)}
# Context-size warning: every call re-reads the whole current context ("Conversation & base context"
# was a median 80% of a session's tokens across 107 sessions, 2026-11-02), so a reset pays off most once
# a session's per-call context reaches most sessions' peak. Shared by hook-prompt and the Performance tab.
CONTEXT_WARNING_SHARE = 0.9
CONTEXT_WARNING_MIN_SESSIONS = 5


def size(value):
    """Tokens in a tool input, tool result or text block (chars / 4)."""
    if value is None:
        return 0
    if isinstance(value, list):
        return sum(size(item.get("text") if isinstance(item, dict) and "text" in item else item) for item in value)
    if not isinstance(value, str):
        value = json.dumps(value)
    return int(len(value) / CHARS_PER_TOKEN)


def read_calls(path):
    """[(message_id, context, output)] in order, one per model call (usage is repeated on every
    content block of a message; keep the largest)."""
    calls, index = [], {}
    try:
        handle = open(path, errors="replace")
    except OSError:
        return calls
    with handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") or {}
            usage = message.get("usage")
            if entry.get("type") != "assistant" or not usage:
                continue
            context = (usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0) \
                + (usage.get("cache_creation_input_tokens") or 0)
            output = usage.get("output_tokens") or 0
            key = message.get("id") or entry.get("uuid")
            if key in index:
                old = calls[index[key]]
                calls[index[key]] = (key, max(old[1], context), max(old[2], output))
            else:
                index[key] = len(calls)
                calls.append((key, context, output))
    return calls


def context_warning_threshold(peaks):
    """CONTEXT_WARNING_SHARE x the median peak per-call context of other sessions, or None with too few."""
    peaks = [peak for peak in peaks if peak]
    if len(peaks) < CONTEXT_WARNING_MIN_SESSIONS:
        return None
    return int(CONTEXT_WARNING_SHARE * statistics.median(peaks))


def subagent_runs(transcript_path, session_id):
    """{tool_use_id or file: {total, calls, peak, first}} for each subagent transcript."""
    runs = {}
    folder = os.path.join(os.path.dirname(transcript_path), session_id, "subagents")
    for path in sorted(glob.glob(os.path.join(folder, "*.jsonl"))):
        calls = [c for c in read_calls(path) if c[1] or c[2]]
        if not calls:
            continue
        key = os.path.basename(path)
        try:
            with open(path[:-len(".jsonl")] + ".meta.json") as handle:
                key = json.load(handle).get("toolUseId") or key
        except (OSError, ValueError):
            pass
        runs[key] = {"total": sum(c[1] + c[2] for c in calls), "calls": len(calls),
                     "peak": max(c[1] for c in calls), "first": calls[0][1]}
    return runs


def classify(name, tool_input, roots):
    if name == "Bash":
        command = tool_input.get("command", "")
        if any(re.search(r"python3?\s+\S*" + re.escape(tool), command) for tool in RUNNABLE_TOOLS):
            return "Runnable tools"
        if LIFECYCLE in command:
            return "Session lifecycle"
    elif name == "Skill":
        return "Skills"
    elif name in ("Agent", "Task"):
        return "Subagents"
    elif name == "Read":
        real = os.path.realpath(os.path.expanduser(tool_input.get("file_path", "")))
        if real.endswith(".md") and any(real.startswith(root + os.sep) for root in roots):
            return "Rule & process loads"
    return AD_HOC


def doc_review_commands(name, tool_input):
    """The doc-review preview commands a Bash call runs, e.g. ["serve"]; mermaid_preview.py is a serve."""
    if name != "Bash":
        return []
    return ["serve" if script == "mermaid_preview" else (command or "?")
            for script, command in re.findall(DOC_REVIEW_PATTERN, tool_input.get("command", ""))]


def is_miro_or_confluence(name):
    """A Miro or Confluence MCP tool (Jira calls on the Atlassian server are not doc operations)."""
    if not name or not name.startswith("mcp__"):
        return False
    return "miro" in name.split("__")[1] or "Confluence" in name or name.endswith("getContentFormatGuide")


def partial_read_unread(tool_input):
    """Tokens of a file left unread by a Read with limit/offset, judged from the file as it is now."""
    if not tool_input.get("limit") and not tool_input.get("offset"):
        return 0
    path = tool_input.get("file_path", "")
    try:
        with open(path, errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return 0
    if not lines:
        return 0
    start = max(int(tool_input.get("offset") or 1) - 1, 0)
    read = min(int(tool_input.get("limit") or len(lines)), max(len(lines) - start, 0))
    unread_lines = len(lines) - read
    return int(sum(len(line) for line in lines) / CHARS_PER_TOKEN * unread_lines / len(lines))


def suggested_tool(suggestion):
    """The index call to show for a hook-bash suggestion: a declaration lookup is one code-graph call."""
    command = suggestion[0]
    if command.startswith("codeindex.py where "):
        return 'curl -s "$URL/api/type?name=%s&members=0"' % command.split()[-1]
    return command


def missed_opportunities(order, carried, grep_suggestions):
    """{kind: {count, tokens, round_trips, examples}} for the MISSED kinds (see MISSED_GREP above)."""
    missed = {kind: {"count": 0, "tokens": 0, "round_trips": 0, "examples": []} for kind in MISSED}

    def add(kind, tokens, round_trips, example):
        entry = missed[kind]
        entry["count"] += 1
        entry["tokens"] += tokens
        entry["round_trips"] += round_trips
        if len(entry["examples"]) < MISSED_EXAMPLES:
            entry["examples"].append(example)

    chains = {}                              # type name -> [op], in order
    edited = {}                              # real path -> last call that edited it
    for op in order:
        if op["name"] in EDIT_TOOLS:
            path = os.path.realpath(op["input"].get("file_path") or op["input"].get("notebook_path") or "")
            edited[path] = max(edited.get(path, -1), op["call"])
    for op in order:
        if op["name"] == "Bash":
            command = op["input"].get("command", "")
            suggestions = grep_suggestions(command) if grep_suggestions else []
            if suggestions:
                add(MISSED_GREP, carried(max(op.get("result", 0) - INDEX_CALL_TOKENS, 0), op["at"]), 1,
                    "`%s` → `%s`" % (command.strip().splitlines()[0][:100].replace("`", "'"),
                                     suggested_tool(suggestions[0])))
            for name in re.findall(CODEINDEX_SHAPE_PATTERN, command):
                chains.setdefault(name.split(".")[0], []).append(op)
        elif op["name"] == "Read":
            path = os.path.realpath(op["input"].get("file_path", ""))
            if path.endswith(".cs") and not op["input"].get("limit") and not op["input"].get("offset") \
                    and edited.get(path, -1) < op["call"]:
                unneeded = max(op.get("result", 0) - INDEX_CALL_TOKENS, 0)
                if unneeded:
                    add(MISSED_READ, carried(unneeded, op["at"]), 0,
                        "`%s` → `curl -s \"$URL/api/type?name=%s\"`"
                        % (os.path.basename(path), os.path.splitext(os.path.basename(path))[0]))
    for name, ops in chains.items():
        messages = sorted({op["call"] for op in ops})
        if len(ops) < 2:
            continue
        add(MISSED_CHAIN, sum(carried(op["tokens"], op["at"]) for op in ops[1:]), len(messages) - 1,
            "%d codeindex calls on `%s` → `curl -s \"$URL/api/type?name=%s\"`" % (len(ops), name, name))
    return missed


def analyse(transcript_path, session_id, roots, grep_suggestions=None):
    """{"total", "categories": {name: tokens}, "standardized", "savings": {name: {tokens, round_trips,
    count}}, "missed": {kind: {count, tokens, round_trips, examples}}, "estimated": True} — or None when
    the transcript is missing. grep_suggestions(command) -> [suggestion tuple] flags a grep over C# for a
    type or member name (session_lifecycle.type_grep_suggestions); without it no grep counts as missed."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    roots = [os.path.realpath(root) for root in roots]
    calls = read_calls(transcript_path)
    position = {key: i for i, (key, _context, _output) in enumerate(calls)}
    boundaries = []                         # call indexes where a compaction started a new segment
    ops = {}                                # tool_use id -> op
    order = []
    extra = []                              # (category, tokens, at) not tied to a tool_use block
    tool_uses_per_call = {}
    last_skill = None
    seen_calls = 0

    with open(transcript_path, errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") or {}
            content = message.get("content")
            if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
                boundaries.append(seen_calls)
            if entry.get("type") == "assistant":
                key = message.get("id") or entry.get("uuid")
                call = position.get(key, seen_calls)
                seen_calls = max(seen_calls, call + 1)
                for block in content if isinstance(content, list) else []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    tool_input = block.get("input") or {}
                    op = {"id": block.get("id"), "name": block.get("name"), "input": tool_input, "call": call, "at": call + 1,
                          "tokens": size(tool_input),
                          "category": classify(block.get("name"), tool_input, roots)}
                    ops[block.get("id")] = op
                    order.append(op)
                    tool_uses_per_call[call] = tool_uses_per_call.get(call, 0) + 1
                    if op["name"] == "Skill":
                        last_skill = op
            elif entry.get("type") == "user":
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id") in ops:
                            op = ops[block["tool_use_id"]]
                            op["result"] = size(block.get("content"))
                            op["tokens"] += op["result"]
                            op["at"] = seen_calls
                text = content if isinstance(content, str) else " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text") \
                    if isinstance(content, list) else ""
                if entry.get("isMeta") and text.startswith("Base directory for this skill") and last_skill:
                    last_skill["tokens"] += size(text)     # the skill body is injected after the Skill call
                elif "<task-notification>" in text:
                    extra.append(("Subagents", size(text), seen_calls))

    def remaining(at):
        """Calls from index `at` to the end of its compaction segment."""
        end = next((b for b in boundaries if b > at), len(calls))
        return max(end - at, 0)

    def carried(tokens, at):
        return tokens * remaining(at)

    categories = dict.fromkeys(STANDARDIZED + [AD_HOC], 0)
    for op in order:
        categories[op["category"]] += carried(op["tokens"], op["at"])
    for category, tokens, at in extra:
        categories[category] += carried(tokens, at)
    runs = subagent_runs(transcript_path, session_id)
    categories["Subagents"] += sum(run["total"] for run in runs.values())

    total = sum(context + output for _key, context, output in calls) + sum(run["total"] for run in runs.values())
    categories[BASE] = max(total - sum(categories.values()), 0)

    savings = {name: {"tokens": 0, "round_trips": 0, "count": 0} for name in SAVINGS}
    for call, count in tool_uses_per_call.items():
        if count > 1:
            saving = savings["Parallel tool calls"]
            saving["count"] += 1
            saving["round_trips"] += count - 1
            saving["tokens"] += (count - 1) * (calls[call][1] if call < len(calls) else 0)
    for op in order:
        if op["category"] == "Subagents":
            run = runs.get(op["id"])
            if run:
                saving = savings["Subagent delegation"]
                saving["count"] += 1
                saving["round_trips"] += run["calls"]
                kept_out = max(run["peak"] - run["first"] - op.get("result", 0), 0)
                saving["tokens"] += carried(kept_out, op["at"])
        elif op["name"] == "Read":
            unread = partial_read_unread(op["input"])
            if unread:
                saving = savings["Partial file reads"]
                saving["count"] += 1
                saving["tokens"] += carried(unread, op["at"])
        elif op["category"] == "Runnable tools":
            command = op["input"].get("command", "")
            hits = [tool for tool in RUNNABLE_TOOLS
                    for _ in re.findall(r"python3?\s+\S*" + re.escape(tool), command)]
            for tool in hits:
                avoided, round_trips = AVOIDED_BY_TOOL[tool]
                saving = savings[tool]
                saving["count"] += 1
                saving["round_trips"] += round_trips
                saving["tokens"] += carried(max(avoided - op["tokens"] // len(hits), 0), op["at"])
        if op["name"] == "Bash":
            routes = re.findall(CODE_GRAPH_PATTERN, op["input"].get("command", ""))
            for route in routes:
                avoided, round_trips = GREP_BY_CODE_GRAPH_ROUTE[route]
                saving = savings[CODE_GRAPH_SAVING]
                saving["count"] += 1
                saving["round_trips"] += round_trips
                saving["tokens"] += carried(max(avoided - op["tokens"] // len(routes), 0), op["at"])

    doc_review ={"count": 0, "tokens": 0, "equivalent": 0, "round_trips": 0, "commands": {},
                  "miro_confluence": {"count": 0, "tokens": 0}}
    for op in order:
        commands = doc_review_commands(op["name"], op["input"])
        if commands:
            actual = carried(op["tokens"], op["at"])
            equivalent = sum(carried(MIRO_CONFLUENCE_BY_COMMAND.get(command, (0, 0))[0], op["at"]) for command in commands)
            round_trips = sum(MIRO_CONFLUENCE_BY_COMMAND.get(command, (0, 0))[1] for command in commands)
            doc_review["count"] += 1
            doc_review["tokens"] += actual
            doc_review["equivalent"] += equivalent
            doc_review["round_trips"] += round_trips
            for command in commands:
                doc_review["commands"][command] = doc_review["commands"].get(command, 0) + 1
            if equivalent:
                saving = savings[DOC_REVIEW_SAVING]
                saving["count"] += 1
                saving["round_trips"] += round_trips
                saving["tokens"] += max(equivalent - actual, 0)
        elif is_miro_or_confluence(op["name"]):
            doc_review["miro_confluence"]["count"] += 1
            doc_review["miro_confluence"]["tokens"] += carried(op["tokens"], op["at"])

    assumptions = {tool: {"tokens": t, "round_trips": r} for tool, (t, r) in AVOIDED_BY_TOOL.items()}
    assumptions.update({"doc_review.py " + command: {"tokens": t, "round_trips": r}
                        for command, (t, r) in MIRO_CONFLUENCE_BY_COMMAND.items()})
    assumptions.update({"code-graph /api/" + route: {"tokens": t, "round_trips": r}
                        for route, (t, r) in GREP_BY_CODE_GRAPH_ROUTE.items()})
    return {"estimated": True, "total": total, "calls": len(calls), "categories": categories,
            "standardized": sum(categories[name] for name in STANDARDIZED), "savings": savings,
            "missed": missed_opportunities(order, carried, grep_suggestions),
            "doc_review": doc_review, "assumptions": assumptions,
            "peak_context": max((context for _key, context, _output in calls), default=0),
            "last_context": calls[-1][1] if calls else 0}


def session_total(transcript_path, session_id):
    """(tokens, model calls) for a session, main thread plus subagents, each call counted once."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    calls = read_calls(transcript_path)
    runs = subagent_runs(transcript_path, session_id)
    return (sum(context + output for _key, context, output in calls) + sum(run["total"] for run in runs.values()),
            len(calls))
