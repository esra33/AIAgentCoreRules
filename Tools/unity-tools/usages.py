#!/usr/bin/env python3
"""
Map every use of a type or member across the project, one `path:line: code` per site,
partitioned by what each site actually does.

Built for interface-segregation work: before splitting an interface you need to know
which call sites only read and which call the members you intend to move out. Answering
that with raw grep takes many passes and returns a lot of lines you have to classify by
hand; this does the classification and prints each site's line.

Usage
  usages.py IEventManager                       a type
  usages.py FetchEvents                         a member name, in any type
  usages.py GemEventManager.FetchEvents         a member, declared in that type
  usages.py IEventManager --members FetchEvents,FetchEvent,RefreshEventStatus
  usages.py IPrizeManager --assembly Assembly-CSharp

Options
  --members a,b,c  Split the symbol's sites into those that invoke one of these members
                   and those that do not.
  --limit N        Print at most N lines per section (default 60); the rest are summarised
                   per assembly.
  --full           No limit.
  --assembly NAME  Restrict to one assembly.
  --project PATH   Unity project root (default: walk up from cwd).
  --db PATH        codeindex database (default: <project>/Library/codeindex.sqlite).

Only files that belong to a generated .csproj are searched, so results are limited to
code that actually compiles. Orphaned project files are ignored.

Declarations come from codeindex (it is refreshed first, as every codeindex query is). The
other buckets are lexical, not semantic: IMPLEMENTS matches a base list naming the type,
CALLS matches `Member(` on a line of a file that mentions the symbol, and a member's
references are every `\\bName\\b` outside its declarations — `Type.Member` narrows the
declarations, not the call sites. Treat it as a fast triage pass, not a compiler-grade
reference index.
"""

import argparse
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _unityproj import Project, ProjectError, find_project_root  # noqa: E402
from codeindex import CodeIndex  # noqa: E402

CODE_WIDTH = 160


def declarations(root, db, symbol):
    """(path, line) -> signature for the symbol's declarations, and for other same-named
    members that `Type.Member` excludes. Empty when the index cannot be opened."""
    try:
        with CodeIndex(root, db) as index:
            index.ensure_fresh()
            types, members = index.lookup(symbol)
            own = {(r["file"], r["line"]): r["signature"] for r in types + members}
            other = {}
            if "." in symbol:
                _, members_all = index.lookup(symbol.rsplit(".", 1)[1])
                other = {(r["file"], r["line"]): r["signature"]
                         for r in members_all if (r["file"], r["line"]) not in own}
            return own, other, bool(types)
    except Exception as exc:   # the line scan still works without declarations
        print("[codeindex unavailable: %s]" % exc, file=sys.stderr)
        return {}, {}, False


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("symbol")
    parser.add_argument("--members", default="")
    parser.add_argument("--assembly", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    try:
        root = os.path.abspath(args.project) if args.project else find_project_root()
        project = Project(root)
    except ProjectError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    symbol = args.symbol
    name = symbol.rsplit(".", 1)[-1]
    members = [m.strip() for m in args.members.split(",") if m.strip()]
    limit = None if args.full or args.limit <= 0 else args.limit

    declared, excluded, is_type = declarations(root, args.db, symbol)

    sym_re = re.compile(r"\b%s\b" % re.escape(name))
    base_re = re.compile(r":\s*[^{;=()\n]*\b%s\b" % re.escape(name))
    member_res = [re.compile(r"\b%s\s*\(" % re.escape(m)) for m in members]

    buckets = {"DECLARES": [], "IMPLEMENTS": [], "CALLS": [], "REFERENCES": []}
    seen_declared = set()

    for path, asms in project.file_to_assemblies().items():
        asm = asms[0]
        if args.assembly and asm != args.assembly:
            continue
        try:
            with open(path, "r", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        if not sym_re.search(text):
            continue

        rel = os.path.relpath(path, root)
        for number, line in enumerate(text.splitlines(), 1):
            key = (rel, number)
            if key in excluded:
                continue
            if key in declared:
                buckets["DECLARES"].append((asm, rel, number, line))
                seen_declared.add(key)
            elif member_res and any(p.search(line) for p in member_res):
                buckets["CALLS"].append((asm, rel, number, line))
            elif not sym_re.search(line):
                continue
            elif is_type and base_re.search(line) and not line.lstrip().startswith(("//", "*")):
                buckets["IMPLEMENTS"].append((asm, rel, number, line))
            else:
                buckets["REFERENCES"].append((asm, rel, number, line))

    # Declarations outside the .csproj set (or in another assembly filter) still show.
    for (rel, number), signature in sorted(declared.items()):
        if (rel, number) not in seen_declared and not args.assembly:
            buckets["DECLARES"].append(("(not in a .csproj)", rel, number, signature))

    files = {rel for rows in buckets.values() for _, rel, _, _ in rows}
    asms_seen = {asm for rows in buckets.values() for asm, _, _, _ in rows}
    print("%s — %d line(s) in %d file(s) across %d assembl%s"
          % (symbol, sum(len(r) for r in buckets.values()), len(files), len(asms_seen),
             "y" if len(asms_seen) == 1 else "ies"))
    if "." in symbol and declared:
        print("note: references are lexical matches of `%s`; only the declarations are "
              "narrowed to %s." % (name, symbol.rsplit(".", 1)[0]))
    elif not declared:
        print("note: codeindex has no declaration of %s; lines below are lexical matches "
              "of `%s` (try `codeindex.py where %s`)." % (symbol, name, name))

    titles = {"DECLARES": "DECLARES", "IMPLEMENTS": "IMPLEMENTS / EXTENDS",
              "CALLS": "CALLS %s" % "/".join(members),
              "REFERENCES": "OTHER REFERENCES" if members else "REFERENCES"}
    for bucket, rows in buckets.items():
        if not rows and not (bucket == "CALLS" and members):
            continue
        rows.sort(key=lambda r: (r[1], r[2]))
        print("\n%s (%d)" % (titles[bucket], len(rows)))
        shown = rows if limit is None else rows[:limit]
        for _, rel, number, line in shown:
            code = " ".join(line.split())
            if len(code) > CODE_WIDTH:
                code = code[:CODE_WIDTH - 1] + "…"
            print("%s:%d: %s" % (rel, number, code))
        if not rows:
            print("  (none)")
        rest = rows[len(shown):]
        if rest:
            per_asm = defaultdict(set)
            for asm, rel, _, _ in rest:
                per_asm[asm].add(rel)
            print("  … %d more line(s) in %d file(s) — --full, --limit N or --assembly NAME:"
                  % (len(rest), len({r for _, r, _, _ in rest})))
            for asm, rels in sorted(per_asm.items()):
                print("    %-55s %d file(s)" % (asm, len(rels)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
