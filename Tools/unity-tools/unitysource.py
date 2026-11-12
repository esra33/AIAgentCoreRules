#!/usr/bin/env python3
"""
Read the Unity engine's managed source (UnityEngine.* / UnityEditor.* modules) for the
Unity version this project uses, decompiled with ilspycmd and cached as it is asked for.

Use it for questions the project code cannot answer: what an engine getter really returns,
whether a value is copied or wraps native memory, which overloads exist. Example: DT-20157,
where ParticleSystem gradients turned out to be non-owning views over native memory.

Usage
  unitysource.py where <Type>                   module(s) that declare the type
  unitysource.py show <Type>                    outline: one line per member
  unitysource.py show <Type> --member Name      full declarations of the named member(s)
  unitysource.py show <Type> --full             the whole decompiled type
  unitysource.py module <Module>                decompile a whole module into the cache
  unitysource.py grep <regex> [-C N]            search everything cached so far
  unitysource.py cached                         what the cache holds for this version
  unitysource.py status                         Unity version, paths, ilspycmd

  <Type> may be a simple name (Gradient), a dotted path (ParticleSystem.MinMaxGradient) or
  a full name (UnityEngine.ParticleSystem+MinMaxGradient).

Cache: grows lazily, per Unity version — nothing is decompiled up front.
  - `where` lists module type tables one module at a time until the type is found
    (modules whose name matches the type first, then CoreModule), and keeps each table.
  - `show` decompiles one top-level type (nested types come with their parent).
  - `module` decompiles a whole module, for grepping widely.
  Location: ~/Library/Caches/UnityDecompiled/<version>/ on macOS ($XDG_CACHE_HOME or
  ~/.cache elsewhere); override with UNITY_SOURCE_CACHE. The DLLs only change with the
  Unity version, so entries never go stale.

Requirements: ilspycmd (dotnet tool install -g ilspycmd) and a .NET runtime. DOTNET_ROOT
defaults to ~/.dotnet when that folder exists — without it ilspycmd silently writes nothing.

Limits: this is the MANAGED side only. Native behaviour (what a setter does in C++) is not
visible here; confirm on the real object in the Editor.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _unityproj import ProjectError, editor_version, find_project_root  # noqa: E402

UNITY_APP_ROOTS = [
    "/Applications/Unity/Hub/Editor/{version}/Unity.app",
    "~/Applications/Unity/Hub/Editor/{version}/Unity.app",
]
MANAGED_SUBDIRS = [
    os.path.join("Contents", "Resources", "Scripting", "Managed", "UnityEngine"),  # Unity 6
    os.path.join("Contents", "Managed", "UnityEngine"),                            # older
]
LISTING_KINDS = "csied"   # class, struct, interface, enum, delegate
DEFAULT_MAX_LINES = 400
DECLARATION_KINDS = ("class", "struct", "interface", "enum", "delegate")


class SourceError(Exception):
    pass


# ---------------------------------------------------------------- environment

def cache_root():
    override = os.environ.get("UNITY_SOURCE_CACHE")
    if override:
        return os.path.expanduser(override)
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Caches/UnityDecompiled")
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "UnityDecompiled")


def find_managed_dir(version):
    candidates = []
    env = os.environ.get("UNITY_PATH")
    if env:
        candidates.append(os.path.expanduser(env))
    candidates += [os.path.expanduser(p.format(version=version)) for p in UNITY_APP_ROOTS]
    for app in candidates:
        for sub in MANAGED_SUBDIRS:
            path = os.path.join(app, sub)
            if os.path.exists(os.path.join(path, "UnityEngine.CoreModule.dll")):
                return path
    raise SourceError(
        "No Unity %s install with managed modules found.\nLooked in:\n  %s\n"
        "Set UNITY_PATH to the .app if it lives somewhere else."
        % (version, "\n  ".join(candidates)))


def ilspy_env():
    env = dict(os.environ)
    dotnet_home = os.path.expanduser("~/.dotnet")
    if "DOTNET_ROOT" not in env and os.path.isdir(dotnet_home):
        env["DOTNET_ROOT"] = dotnet_home
    tools = os.path.join(dotnet_home, "tools")
    env["PATH"] = os.pathsep.join([env.get("PATH", ""), tools, dotnet_home])
    return env


def find_ilspy(env):
    exe = shutil.which("ilspycmd", path=env["PATH"])
    if not exe:
        raise SourceError(
            "ilspycmd not found. Install it once (run outside a Unity project folder):\n"
            "  dotnet tool install -g ilspycmd")
    return exe


class Context:
    def __init__(self, project):
        self.root = find_project_root(project)
        self.version = editor_version(self.root)
        self.managed = find_managed_dir(self.version)
        self.cache = os.path.join(cache_root(), self.version)
        self.env = ilspy_env()
        self._ilspy = None

    @property
    def ilspy(self):
        if self._ilspy is None:
            self._ilspy = find_ilspy(self.env)
        return self._ilspy

    def run_ilspy(self, args):
        result = subprocess.run([self.ilspy] + args, env=self.env, cwd=self.cache,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        if result.returncode != 0 or not result.stdout.strip():
            detail = (result.stderr or "").strip().splitlines()[-3:]
            raise SourceError("ilspycmd %s produced no output.\n  %s"
                              % (" ".join(args[:3]), "\n  ".join(detail) or "(no stderr)"))
        return result.stdout

    def modules(self):
        return sorted(f[:-4] for f in os.listdir(self.managed)
                      if f.endswith(".dll") and f.startswith(("UnityEngine", "UnityEditor")))

    def dll(self, module):
        return os.path.join(self.managed, module + ".dll")

    def path(self, *parts):
        path = os.path.join(self.cache, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path


# ---------------------------------------------------------------- type tables

def listing(ctx, module):
    """Type table of one module: list of (kind, full_name). Cached forever."""
    path = ctx.path("listings", module + ".txt")
    if not os.path.exists(path):
        text = ctx.run_ilspy(["-l", LISTING_KINDS, ctx.dll(module)])
        with open(path, "w") as f:
            f.write(text)
    rows = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split(" ", 1)
            if len(parts) == 2 and parts[1] != "<Module>":
                rows.append((parts[0].lower(), parts[1]))
    return rows


def listed_modules(ctx):
    folder = os.path.join(ctx.cache, "listings")
    if not os.path.isdir(folder):
        return []
    return sorted(f[:-4] for f in os.listdir(folder) if f.endswith(".txt"))


def type_matches(query, full_name):
    """Simple name, dotted suffix or full name; nested '+' is treated like '.'."""
    wanted = query.replace("+", ".")
    name = full_name.replace("+", ".")
    return name == wanted or name.endswith("." + wanted)


def search_order(ctx, query):
    """Unlisted modules, the likeliest first: name contains a token of the query,
    then the core modules, then UnityEngine.*, then UnityEditor.*."""
    tokens = [t.lower() for t in re.split(r"[.+]", query) if len(t) > 2]
    done = set(listed_modules(ctx))

    def rank(module):
        low = module.lower()
        if any(t in low for t in tokens):
            return 0
        if module in ("UnityEngine.CoreModule", "UnityEditor.CoreModule"):
            return 1
        return 2 if module.startswith("UnityEngine.") else 3

    return sorted((m for m in ctx.modules() if m not in done), key=lambda m: (rank(m), m))


def where(ctx, query, scan_all=False, quiet=False):
    """Return [(module, kind, full_name)]. Cached tables first, then lists more as needed."""
    hits = []
    for module in listed_modules(ctx):
        hits += [(module, k, n) for k, n in listing(ctx, module) if type_matches(query, n)]
    if hits and not scan_all:
        return hits

    pending = search_order(ctx, query)
    quiet = quiet or not sys.stderr.isatty()
    for index, module in enumerate(pending, 1):
        if not quiet:
            sys.stderr.write("\r[listing %d/%d] %-60s" % (index, len(pending), module))
            sys.stderr.flush()
        found = [(module, k, n) for k, n in listing(ctx, module) if type_matches(query, n)]
        hits += found
        if found and not scan_all:
            break
    if not quiet and pending:
        sys.stderr.write("\r" + " " * 80 + "\r")
    return hits


def resolve(ctx, query):
    hits = where(ctx, query)
    exact = [h for h in hits if h[2].replace("+", ".") == query.replace("+", ".")]
    hits = exact or hits
    if not hits:
        raise SourceError("No type matching '%s' in the Unity %s modules." % (query, ctx.version))
    if len({h[2] for h in hits}) > 1:
        raise SourceError("'%s' is ambiguous — pass a fuller name:\n  %s" % (
            query, "\n  ".join("%s  (%s)" % (h[2], h[0]) for h in hits)))
    return hits[0]


# ---------------------------------------------------------------- decompiling

def decompiled_type(ctx, module, full_name):
    """Decompile the top-level type that holds full_name (nested types come with it)."""
    outer = full_name.split("+", 1)[0]
    path = ctx.path("types", module, outer + ".cs")
    if not os.path.exists(path):
        text = ctx.run_ilspy(["-t", outer, ctx.dll(module), "-r", ctx.managed])
        with open(path, "w") as f:
            f.write(text)
    return path


def decompiled_module(ctx, module):
    if not os.path.exists(ctx.dll(module)):
        raise SourceError("No module %s in %s" % (module, ctx.managed))
    path = ctx.path("modules", module + ".cs")
    if not os.path.exists(path):
        text = ctx.run_ilspy([ctx.dll(module), "-r", ctx.managed])
        with open(path, "w") as f:
            f.write(text)
    return path


def block_end(lines, start):
    """Index of the last line of the declaration starting at `start` (brace matched)."""
    depth = 0
    opened = False
    for index in range(start, len(lines)):
        code = lines[index].split("//", 1)[0]
        if not opened and code.rstrip().endswith(";") and "{" not in code:
            return index
        depth += code.count("{") - code.count("}")
        if "{" in code:
            opened = True
        if opened and depth <= 0:
            return index
    return len(lines) - 1


def with_leading_attributes(lines, start):
    """Pull in attribute and XML-doc lines directly above a declaration."""
    while start > 0:
        prev = lines[start - 1].strip()
        if prev.startswith("[") or prev.startswith("///"):
            start -= 1
        else:
            break
    return start


def nested_type_block(lines, full_name):
    """Lines of the innermost type named in full_name (UnityEngine.A+B → B inside A)."""
    names = full_name.split(".")[-1].split("+")
    start, end = 0, len(lines) - 1
    for name in names:
        pattern = re.compile(r"\b(%s)\s+%s\b" % ("|".join(DECLARATION_KINDS), re.escape(name)))
        for index in range(start, end + 1):
            if pattern.search(lines[index].split("//", 1)[0]):
                start, end = index, block_end(lines, index)
                break
        else:
            return None
    return with_leading_attributes(lines, start), end


def member_blocks(lines, member):
    """Every declaration (method, property, field, nested type) named `member`."""
    pattern = re.compile(r"^\s*(?:\[[^\]]*\]\s*)*(?:[\w<>\[\],.?]+\s+)+%s\s*(?:[({<]|$|=|;)"
                         % re.escape(member))
    blocks = []
    index = 0
    while index < len(lines):
        if pattern.search(lines[index]) and not lines[index].strip().startswith(("return", "//")):
            end = block_end(lines, index)
            blocks.append((with_leading_attributes(lines, index), end))
            index = end + 1
        else:
            index += 1
    return blocks


def outline(lines, start, end):
    """Member declaration lines one level inside the type block [start, end]."""
    header = start
    while header <= end and "{" not in lines[header]:
        header += 1
    indent = len(lines[header]) - len(lines[header].lstrip("\t")) + 1
    rows = []
    for index in range(header + 1, end):
        line = lines[index]
        depth = len(line) - len(line.lstrip("\t"))
        text = line.strip()
        if depth != indent or not text or text in ("{", "}") or text.startswith(("[", "//", "/*", "*")):
            continue
        if "_Injected(" in text:   # generated native-binding stubs: noise in an outline
            continue
        rows.append(index)
    return rows


def print_lines(lines, ranges, path, max_lines):
    printed = 0
    for start, end in ranges:
        if printed:
            print("\t// ...")
        for index in range(start, end + 1):
            if printed >= max_lines:
                print("// ... truncated at %d lines (--max-lines). Full file: %s" % (max_lines, path))
                return
            print("%6d  %s" % (index + 1, lines[index]))
            printed += 1


# ---------------------------------------------------------------- commands

def cmd_where(ctx, args):
    hits = where(ctx, args.type, scan_all=args.all)
    if args.json:
        print(json.dumps([{"module": m, "kind": k, "type": n} for m, k, n in hits], indent=2))
        return 0 if hits else 1
    if not hits:
        print("No type matching '%s'%s." % (
            args.type, "" if args.all else " (searched until the first hit; --all scans every module)"))
        return 1
    for module, kind, name in hits:
        print("%-10s %-60s %s" % (kind, name, module))
    return 0


def cmd_show(ctx, args):
    module, _, full_name = resolve(ctx, args.type)
    path = decompiled_type(ctx, module, full_name)
    with open(path) as f:
        lines = f.read().splitlines()

    if args.path:
        print(path)
        return 0

    block = nested_type_block(lines, full_name) or (0, len(lines) - 1)
    if args.member:
        inner = lines[block[0]:block[1] + 1]
        ranges = [(s + block[0], e + block[0]) for s, e in member_blocks(inner, args.member)]
        if not ranges:
            print("No member '%s' in %s. Full file: %s" % (args.member, full_name, path))
            return 1
    elif args.full:
        ranges = [block]
    else:
        print("// %s  ·  %s  ·  Unity %s  ·  outline (--member <Name> for bodies, --full for all)"
              % (full_name, module, ctx.version))
        rows = outline(lines, block[0], block[1])
        for index in rows[:args.max_lines]:
            print("%6d  %s" % (index + 1, lines[index]))
        if len(rows) > args.max_lines:
            print("// ... %d more members. Full file: %s" % (len(rows) - args.max_lines, path))
        return 0

    print("// %s  ·  %s  ·  Unity %s" % (full_name, module, ctx.version))
    print_lines(lines, ranges, path, args.max_lines)
    return 0


def cmd_module(ctx, args):
    path = decompiled_module(ctx, args.module)
    with open(path) as f:
        count = sum(1 for _ in f)
    print("%s  (%d lines)" % (path, count))
    return 0


def cached_files(ctx):
    files = []
    for folder in ("types", "modules"):
        base = os.path.join(ctx.cache, folder)
        for dirpath, _, names in os.walk(base):
            files += [os.path.join(dirpath, n) for n in sorted(names) if n.endswith(".cs")]
    return files


def cmd_grep(ctx, args):
    regex = re.compile(args.pattern, 0 if args.case_sensitive else re.IGNORECASE)
    total = 0
    for path in cached_files(ctx):
        with open(path) as f:
            lines = f.read().splitlines()
        hits = [i for i, line in enumerate(lines) if regex.search(line)]
        if not hits:
            continue
        rel = os.path.relpath(path, ctx.cache)
        shown = set()
        for hit in hits:
            if total >= args.max_hits:
                print("... stopped at %d hits (--max-hits)" % args.max_hits)
                return 0
            total += 1
            for index in range(max(0, hit - args.context), min(len(lines), hit + args.context + 1)):
                if index not in shown:
                    shown.add(index)
                    marker = ":" if index == hit else "-"
                    print("%s%s%d%s %s" % (rel, marker, index + 1, marker, lines[index]))
        if args.context:
            print("--")
    if not total:
        print("No hits in the cache (%d files). Pull more in with `show <Type>` or `module <Module>`."
              % len(cached_files(ctx)))
        return 1
    return 0


def cmd_cached(ctx, args):
    print("Unity %s cache: %s" % (ctx.version, ctx.cache))
    listed = listed_modules(ctx)
    print("  type tables: %d / %d modules" % (len(listed), len(ctx.modules())))
    for path in cached_files(ctx):
        print("  " + os.path.relpath(path, ctx.cache))
    return 0


def cmd_status(ctx, args):
    print("project   %s" % ctx.root)
    print("unity     %s" % ctx.version)
    print("managed   %s  (%d modules)" % (ctx.managed, len(ctx.modules())))
    print("cache     %s" % ctx.cache)
    print("DOTNET_ROOT %s" % ctx.env.get("DOTNET_ROOT", "(unset)"))
    try:
        print("ilspycmd  %s" % ctx.ilspy)
    except SourceError as e:
        print("ilspycmd  MISSING — %s" % e)
        return 1
    return 0


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=None, help="Unity project root (default: walk up from cwd)")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("where", parents=[common], help="module(s) that declare a type")
    p.add_argument("type")
    p.add_argument("--all", action="store_true", help="list every module instead of stopping at the first hit")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_where)

    p = sub.add_parser("show", parents=[common], help="decompiled source of a type")
    p.add_argument("type")
    p.add_argument("--member", help="only declarations with this name")
    p.add_argument("--full", action="store_true", help="the whole type instead of an outline")
    p.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    p.add_argument("--path", action="store_true", help="print the cached file path only")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("module", parents=[common], help="decompile a whole module into the cache")
    p.add_argument("module", help="e.g. UnityEngine.ParticleSystemModule")
    p.set_defaults(func=cmd_module)

    p = sub.add_parser("grep", parents=[common], help="search everything cached so far")
    p.add_argument("pattern")
    p.add_argument("-C", "--context", type=int, default=0)
    p.add_argument("--case-sensitive", action="store_true")
    p.add_argument("--max-hits", type=int, default=100)
    p.set_defaults(func=cmd_grep)

    p = sub.add_parser("cached", parents=[common], help="what the cache holds")
    p.set_defaults(func=cmd_cached)

    p = sub.add_parser("status", parents=[common], help="paths and prerequisites")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    try:
        ctx = Context(args.project)
        return args.func(ctx, args)
    except (ProjectError, SourceError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
