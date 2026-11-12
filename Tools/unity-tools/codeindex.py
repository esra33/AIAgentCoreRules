#!/usr/bin/env python3
"""
Declaration index for the Unity C# codebase, backed by SQLite.

The project is ~5,600 compiled files / ~7,200 type declarations / ~24 MB of source —
several times what fits in an agent's context. This indexes every type and member
declaration so relationship questions ("who implements this", "what does this type
look like") can be answered without reading files.

Usage
  codeindex.py build [--force]              build or incrementally refresh
  codeindex.py status                       what is out of date
  codeindex.py schema                       tables + example queries

  codeindex.py where <Name|Type.Member>     where a type or member is declared: path:start-end  signature
  codeindex.py show <Type|Type.Member>      print just that declaration's source lines
  codeindex.py implementers <Interface>     types whose base list names it
  codeindex.py subclasses <Base> [--direct] transitive by default
  codeindex.py bases <Type>                 what it inherits / implements
  codeindex.py members <Type> [--kind method] [--inherited]
  codeindex.py attributed <Attribute>       types and members carrying [Attribute]
  codeindex.py types [--assembly A] [--namespace N] [--kind interface]
  codeindex.py sql "SELECT ..."             read-only passthrough

  --json on any query for machine-readable output.

Freshness: every query refreshes the index first if any source changed, so it can never
answer from stale data. Pass --no-auto-build to inspect a snapshot deliberately.

Scope: DECLARATIONS ONLY. This does not resolve names or index call sites. Base types
are matched by simple name, and ambiguity is reported rather than guessed at. For "who
calls this member" use usages.py; for "does it compile" use typecheck.py.
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _csparse import SourceParser  # noqa: E402
from _unityproj import Project, ProjectError, find_project_root, main_checkout_of  # noqa: E402

SCHEMA_VERSION = "3"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS assembly(
    id       INTEGER PRIMARY KEY,
    name     TEXT UNIQUE NOT NULL,
    csproj   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file(
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,
    assembly_id INTEGER REFERENCES assembly(id) ON DELETE CASCADE,
    mtime       REAL NOT NULL,
    size        INTEGER NOT NULL,
    sha1        TEXT NOT NULL,
    indexed_at  REAL NOT NULL,
    -- 1 = Unity compiles this for the current build target; 0 = the assembly was
    -- inferred from an .asmdef but no generated .csproj claims the file (platform
    -- gated, or created since the last editor refresh).
    in_csproj   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS type(
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    arity       INTEGER NOT NULL DEFAULT 0,
    namespace   TEXT NOT NULL DEFAULT '',
    container   TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL,
    file_id     INTEGER NOT NULL REFERENCES file(id) ON DELETE CASCADE,
    line        INTEGER NOT NULL,
    end_line    INTEGER NOT NULL,
    signature   TEXT NOT NULL DEFAULT '',
    access      TEXT,
    is_abstract INTEGER, is_sealed INTEGER, is_static INTEGER, is_partial INTEGER
);

CREATE TABLE IF NOT EXISTS base_ref(
    id       INTEGER PRIMARY KEY,
    type_id  INTEGER NOT NULL REFERENCES type(id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    raw      TEXT NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS member(
    id          INTEGER PRIMARY KEY,
    type_id     INTEGER NOT NULL REFERENCES type(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    signature   TEXT NOT NULL,
    line        INTEGER NOT NULL,
    end_line    INTEGER NOT NULL,
    access      TEXT,
    is_static   INTEGER, is_abstract INTEGER, is_virtual INTEGER,
    is_override INTEGER, is_async INTEGER
);

-- One row per attribute on a type (member_id NULL) or a member. name is as written,
-- so [Serializable] and [SerializableAttribute] differ; queries match both spellings.
CREATE TABLE IF NOT EXISTS attribute(
    id        INTEGER PRIMARY KEY,
    type_id   INTEGER NOT NULL REFERENCES type(id) ON DELETE CASCADE,
    member_id INTEGER REFERENCES member(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    raw       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_attr_name     ON attribute(name);
CREATE INDEX IF NOT EXISTS ix_type_name     ON type(name);
CREATE INDEX IF NOT EXISTS ix_type_file     ON type(file_id);
CREATE INDEX IF NOT EXISTS ix_base_name     ON base_ref(name);
CREATE INDEX IF NOT EXISTS ix_base_type     ON base_ref(type_id);
CREATE INDEX IF NOT EXISTS ix_member_type   ON member(type_id);
CREATE INDEX IF NOT EXISTS ix_member_name   ON member(name);
CREATE INDEX IF NOT EXISTS ix_file_assembly ON file(assembly_id);
"""

EXAMPLES = """
-- Types in an assembly, with their file
SELECT t.name, t.kind, f.path
  FROM type t JOIN file f ON f.id = t.file_id
  JOIN assembly a ON a.id = f.assembly_id
 WHERE a.name = 'Assembly-CSharp' AND t.kind = 'interface';

-- Every type naming IEventManager in its base list
SELECT t.name, f.path FROM base_ref b
  JOIN type t ON t.id = b.type_id
  JOIN file f ON f.id = t.file_id
 WHERE b.name = 'IEventManager';

-- Interfaces with the most implementers
SELECT b.name, COUNT(*) n FROM base_ref b GROUP BY b.name ORDER BY n DESC LIMIT 20;

-- Types and members carrying [RootPlayerData]
SELECT t.name, m.name AS member, x.raw, f.path, COALESCE(m.line, t.line) AS line
  FROM attribute x JOIN type t ON t.id = x.type_id
  LEFT JOIN member m ON m.id = x.member_id
  JOIN file f ON f.id = t.file_id
 WHERE x.name IN ('RootPlayerData', 'RootPlayerDataAttribute');

-- Async methods that return void (a common bug source)
SELECT t.name, m.name, m.signature FROM member m JOIN type t ON t.id = m.type_id
 WHERE m.is_async = 1 AND m.signature LIKE '%async void%';
"""

TYPE_SELECT = """
SELECT t.id, t.name, t.arity, t.namespace, t.container, t.kind, t.line, t.end_line,
       t.signature, t.access, t.is_abstract, t.is_sealed, t.is_static, t.is_partial,
       f.path AS file, a.name AS assembly
  FROM type t
  JOIN file f ON f.id = t.file_id
  LEFT JOIN assembly a ON a.id = f.assembly_id
"""


MEMBER_SELECT = """
SELECT m.name, m.kind, m.signature, m.line, m.end_line, m.access, m.is_static,
       m.is_abstract, m.is_virtual, m.is_override, m.is_async,
       t.name AS type, t.kind AS type_kind, t.namespace, f.path AS file, a.name AS assembly
  FROM member m
  JOIN type t ON t.id = m.type_id
  JOIN file f ON f.id = t.file_id
  LEFT JOIN assembly a ON a.id = f.assembly_id
"""


class StaleIndexError(RuntimeError):
    pass


class BuildReport:
    def __init__(self):
        self.added = self.modified = self.removed = self.unchanged = 0
        self.types = self.members = 0
        self.seconds = 0.0

    def changed(self):
        return self.added + self.modified + self.removed

    def __str__(self):
        return ("%d added, %d modified, %d removed, %d unchanged -> "
                "%d types, %d members in %.1fs"
                % (self.added, self.modified, self.removed, self.unchanged,
                   self.types, self.members, self.seconds))


class CodeIndex:
    """Owns the SQLite database. Canned queries are thin wrappers over real SQL."""

    def __init__(self, root, db_path=None):
        self.root = root
        self.db_path = db_path or os.path.join(root, "Library", "codeindex.sqlite")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self._project = None
        self._readonly = None
        self._disk_cache = None
        self.compiled_only = False

    def _migrate(self):
        """The index is derived data, so a schema change just rebuilds from scratch."""
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        if row is None or row["value"] == SCHEMA_VERSION:
            return
        for table in ("attribute", "member", "base_ref", "type", "file", "assembly", "meta"):
            self.conn.execute("DROP TABLE IF EXISTS %s" % table)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- lifecycle -------------------------------------------------------

    @classmethod
    def open(cls, root=None, db_path=None):
        return cls(root or find_project_root(), db_path)

    def close(self):
        self.conn.commit()
        self.conn.close()
        if self._readonly:
            self._readonly.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def project(self):
        if self._project is None:
            # A git worktree has no .csproj files; borrow the main checkout's, like typecheck.py
            self._project = Project(self.root, main_checkout_of(self.root))
            if self._project.is_worktree:
                print("[worktree: indexing %s with .csproj files from %s]"
                      % (self.root, self._project.project_files_root), file=sys.stderr)
        return self._project

    # -- freshness -------------------------------------------------------

    def _source_map(self):
        """Absolute source path -> (assembly name, in_csproj).

        Two passes. The .csproj files are authoritative for what Unity compiles right
        now. Anything on disk they do not claim still gets indexed, with its assembly
        inferred the way Unity would — that is what closes the gap for a file created
        since the last editor refresh, which would otherwise be invisible.
        """
        out = {}
        for name in sorted(self.project.live()):
            for src in self.project.assemblies[name].sources:
                out.setdefault(os.path.realpath(src), (name, 1))
        for path in self._disk_sources():
            if path not in out:
                out[path] = (self.project.infer_assembly(path), 0)
        return out

    def _disk_sources(self):
        """Every .cs actually on disk under Assets/, regardless of any .csproj."""
        if self._disk_cache is None:
            found = set()
            for dirpath, dirnames, filenames in os.walk(os.path.join(self.root, "Assets")):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for filename in filenames:
                    if filename.endswith(".cs"):
                        found.add(os.path.realpath(os.path.join(dirpath, filename)))
            self._disk_cache = found
        return self._disk_cache

    def not_compiled(self):
        """Indexed files that no .csproj claims — present in source and queryable, but
        outside what Unity builds for the current target, so typecheck.py will not
        verify them."""
        return [self._abs(r["path"]) for r in
                self.conn.execute("SELECT path FROM file WHERE in_csproj = 0 ORDER BY path")]

    def _abs(self, rel):
        """Absolute path of a stored (root-relative) path. normpath folds the `..` that
        relpath writes for a file outside the root (e.g. under a symlinked Assets/ folder),
        so it matches the realpath keys of _source_map()."""
        return os.path.normpath(os.path.join(self.root, rel))

    def _meta_get(self, key):
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def status(self):
        sources = self._source_map()
        known = {
            self._abs(r["path"]): (r["mtime"], r["size"])
            for r in self.conn.execute("SELECT path, mtime, size FROM file")
        }
        added, modified = [], []
        for path in sources:
            if path not in known:
                if os.path.exists(path):
                    added.append(path)
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            if abs(st.st_mtime - known[path][0]) > 1e-6 or st.st_size != known[path][1]:
                modified.append(path)
        removed = [p for p in known if p not in sources]
        return {"added": added, "modified": modified, "removed": removed,
                "indexed": len(known), "sources": len(sources)}

    def is_fresh(self):
        s = self.status()
        return not (s["added"] or s["modified"] or s["removed"])

    def ensure_fresh(self, auto_build=True):
        if self.is_fresh():
            return None
        if not auto_build:
            raise StaleIndexError(
                "Index is stale and --no-auto-build was passed. Run `codeindex.py build`.")
        return self.build()

    # -- building --------------------------------------------------------

    def build(self, force=False):
        started = time.time()
        report = BuildReport()
        parser = SourceParser()
        sources = self._source_map()

        for name in sorted(self.project.live()):
            self.conn.execute(
                "INSERT OR IGNORE INTO assembly(name, csproj) VALUES(?,?)",
                (name, os.path.relpath(self.project.assemblies[name].csproj, self.root)))
        asm_ids = {r["name"]: r["id"] for r in self.conn.execute("SELECT id, name FROM assembly")}

        known = {
            self._abs(r["path"]): (r["mtime"], r["size"], r["sha1"])
            for r in self.conn.execute("SELECT path, mtime, size, sha1 FROM file")
        }

        for path in list(known):
            if path not in sources:
                self.conn.execute("DELETE FROM file WHERE path = ?",
                                  (os.path.relpath(path, self.root),))
                report.removed += 1

        for path, (assembly, in_csproj) in sources.items():
            try:
                st = os.stat(path)
            except OSError:
                continue

            prior = known.get(path)
            if prior and not force:
                # mtime+size first; hashing 24 MB on every run is wasteful when the
                # cheap comparison already proves nothing changed.
                if abs(st.st_mtime - prior[0]) <= 1e-6 and st.st_size == prior[1]:
                    report.unchanged += 1
                    continue

            try:
                with open(path, "r", errors="replace") as handle:
                    text = handle.read()
            except OSError:
                continue

            sha1 = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
            if prior and sha1 == prior[2] and not force:
                self.conn.execute(
                    "UPDATE file SET mtime = ?, size = ? WHERE path = ?",
                    (st.st_mtime, st.st_size, os.path.relpath(path, self.root)))
                report.unchanged += 1
                continue

            rel = os.path.relpath(path, self.root)
            if prior:
                self.conn.execute("DELETE FROM file WHERE path = ?", (rel,))
                report.modified += 1
            else:
                report.added += 1

            if assembly not in asm_ids:
                # Inferred from an .asmdef with no generated .csproj.
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO assembly(name, csproj) VALUES(?,?)",
                    (assembly, ""))
                asm_ids[assembly] = cur.lastrowid or self.conn.execute(
                    "SELECT id FROM assembly WHERE name = ?", (assembly,)).fetchone()["id"]

            cursor = self.conn.execute(
                "INSERT INTO file(path, assembly_id, mtime, size, sha1, indexed_at, in_csproj) "
                "VALUES(?,?,?,?,?,?,?)",
                (rel, asm_ids.get(assembly), st.st_mtime, st.st_size, sha1, time.time(),
                 in_csproj))
            file_id = cursor.lastrowid

            for decl in parser.parse(path, text):
                cur = self.conn.execute(
                    "INSERT INTO type(name, arity, namespace, container, kind, file_id, "
                    "line, end_line, signature, access, is_abstract, is_sealed, is_static, "
                    "is_partial) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (decl.name, decl.arity, decl.namespace or "", decl.container or "",
                     decl.kind, file_id, decl.line, decl.end_line or decl.line,
                     decl.signature or "", decl.access, decl.is_abstract,
                     decl.is_sealed, decl.is_static, decl.is_partial))
                type_id = cur.lastrowid
                report.types += 1

                self.conn.executemany(
                    "INSERT INTO base_ref(type_id, name, raw, position) VALUES(?,?,?,?)",
                    [(type_id, simple, raw, pos)
                     for pos, (simple, raw) in enumerate(decl.bases)])

                attributes = [(type_id, None, name, raw) for name, raw in decl.attributes]
                for m in decl.members:
                    member_id = self.conn.execute(
                        "INSERT INTO member(type_id, name, kind, signature, line, end_line, "
                        "access, is_static, is_abstract, is_virtual, is_override, is_async) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (type_id, m.name, m.kind, m.signature, m.line, m.end_line or m.line,
                         m.access, m.is_static, m.is_abstract, m.is_virtual, m.is_override,
                         m.is_async)).lastrowid
                    attributes.extend((type_id, member_id, name, raw)
                                      for name, raw in m.attributes)
                self.conn.executemany(
                    "INSERT INTO attribute(type_id, member_id, name, raw) VALUES(?,?,?,?)",
                    attributes)
                report.members += len(decl.members)

        for key, value in (("schema_version", SCHEMA_VERSION),
                           ("built_at", str(time.time())),
                           ("project_root", self.root)):
            self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)",
                              (key, value))
        self.conn.commit()
        report.seconds = time.time() - started
        return report

    # -- queries ---------------------------------------------------------

    def _rows(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params)]

    def _scope(self):
        """Extra predicate restricting results to what Unity compiles right now."""
        return " AND f.in_csproj = 1" if self.compiled_only else ""

    def where_declared(self, name):
        return self._rows(TYPE_SELECT + " WHERE t.name = ?" + self._scope() +
                          " ORDER BY t.namespace, f.path", (name,))

    def where_member(self, name, owner=None):
        """Members called `name`, optionally only those declared directly in type `owner`."""
        sql = MEMBER_SELECT + " WHERE m.name = ?"
        params = [name]
        if owner:
            sql += " AND t.name = ?"
            params.append(owner)
        return self._rows(sql + self._scope() + " ORDER BY f.path, m.line", tuple(params))

    def lookup(self, target):
        """`Type`, `Member` or `Type.Member` -> (types, members). A dotted name that is not a
        member of that type is retried as a nested or namespace-qualified type name."""
        if "." in target:
            owner, name = target.rsplit(".", 1)
            members = self.where_member(name, owner.rsplit(".", 1)[-1])
            if members:
                return [], members
            types = [t for t in self.where_declared(name)
                     if (t["container"] + "." + t["name"]).endswith(target)
                     or (t["namespace"] + "." + t["name"]).endswith(target)]
            return types, []
        return self.where_declared(target), self.where_member(target)

    def bases_of(self, name):
        return self._rows(
            "SELECT b.name, b.raw, b.position, t.namespace, f.path AS file "
            "  FROM base_ref b JOIN type t ON t.id = b.type_id "
            "  JOIN file f ON f.id = t.file_id "
            " WHERE t.name = ?" + self._scope() + " ORDER BY f.path, b.position", (name,))

    def implementers_of(self, name, direct=True):
        if direct:
            return self._rows(
                TYPE_SELECT +
                " JOIN base_ref b ON b.type_id = t.id WHERE b.name = ?" + self._scope() +
                " ORDER BY a.name, t.name", (name,))
        return self.subclasses_of(name, transitive=True)

    def subclasses_of(self, name, transitive=True):
        if not transitive:
            return self.implementers_of(name, direct=True)
        # Recursive CTE walks base_ref edges by simple name. The depth cap matters:
        # simple-name matching can create a false cycle when two namespaces reuse a
        # name, and UNION alone will not terminate one at differing depths.
        return self._rows("""
            WITH RECURSIVE descendants(name, depth) AS (
                SELECT ?, 0
              UNION
                SELECT t.name, d.depth + 1
                  FROM type t
                  JOIN base_ref b ON b.type_id = t.id
                  JOIN descendants d ON b.name = d.name
                 WHERE d.depth < 16
            )
            SELECT DISTINCT t.name, t.kind, t.namespace, t.line, d.depth,
                   f.path AS file, a.name AS assembly
              FROM descendants d
              JOIN type t ON t.name = d.name
              JOIN file f ON f.id = t.file_id
              LEFT JOIN assembly a ON a.id = f.assembly_id
             WHERE d.depth > 0 %s
             ORDER BY d.depth, t.name
        """ % self._scope(), (name,))

    def members_of(self, name, kind=None):
        sql = MEMBER_SELECT + " WHERE t.name = ?"
        params = [name]
        if kind:
            sql += " AND m.kind = ?"
            params.append(kind)
        return self._rows(sql + self._scope() + " ORDER BY f.path, m.line", tuple(params))

    def ancestors_of(self, name, max_depth=16):
        """Base types and interfaces of `name`, nearest first, by simple name (like
        subclasses_of). Returns (indexed, external): indexed is [(depth, type row)], external
        the base names with no declaration in the index (engine and BCL types)."""
        indexed, external, seen = [], [], {name}
        frontier = [name]
        for depth in range(1, max_depth + 1):
            following = []
            for current in frontier:
                for base in self.bases_of(current):
                    if base["name"] in seen:
                        continue
                    seen.add(base["name"])
                    rows = self.where_declared(base["name"])
                    if not rows:
                        external.append(base["name"])
                        continue
                    indexed.extend((depth, row) for row in rows)
                    following.append(base["name"])
            if not following:
                break
            frontier = following
        return indexed, external

    def attributed(self, name):
        """Types and members carrying [name]; `Foo` and `FooAttribute` are the same attribute."""
        base = name[:-len("Attribute")] if name.endswith("Attribute") and name != "Attribute" else name
        return self._rows(
            "SELECT x.name AS attribute, x.raw, t.name AS type, t.kind AS type_kind, "
            "       m.name AS member, m.kind AS member_kind, "
            "       COALESCE(m.line, t.line) AS line, COALESCE(m.end_line, t.end_line) AS end_line, "
            "       COALESCE(m.signature, t.signature) AS signature, f.path AS file "
            "  FROM attribute x JOIN type t ON t.id = x.type_id "
            "  LEFT JOIN member m ON m.id = x.member_id "
            "  JOIN file f ON f.id = t.file_id "
            " WHERE x.name IN (?, ?)" + self._scope() + " ORDER BY f.path, line",
            (base, base + "Attribute"))

    def source_lines(self, rel_path):
        try:
            with open(self._abs(rel_path), "r", errors="replace") as handle:
                return handle.read().split("\n")
        except OSError:
            return None

    def types_in(self, assembly=None, namespace=None, kind=None):
        sql, params, where = TYPE_SELECT, [], []
        if assembly:
            where.append("a.name = ?")
            params.append(assembly)
        if namespace:
            where.append("t.namespace LIKE ?")
            params.append(namespace + "%")
        if kind:
            where.append("t.kind = ?")
            params.append(kind)
        if self.compiled_only:
            where.append("f.in_csproj = 1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        return self._rows(sql + " ORDER BY t.namespace, t.name", tuple(params))

    def sql(self, query, params=()):
        """Read-only passthrough on a separate query_only connection."""
        if self._readonly is None:
            self._readonly = sqlite3.connect("file:%s?mode=ro" % self.db_path, uri=True)
            self._readonly.row_factory = sqlite3.Row
            self._readonly.execute("PRAGMA query_only = ON")
        return [dict(r) for r in self._readonly.execute(query, params)]

    def schema(self):
        return SCHEMA.strip() + "\n\n-- Example queries\n" + EXAMPLES.strip()


# -- CLI ------------------------------------------------------------------

def emit(rows, as_json, columns=None, empty="(none)"):
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print(empty)
        return
    columns = columns or list(rows[0].keys())
    widths = {c: min(max(len(c), *(len(str(r.get(c, ""))) for r in rows)), 78) for c in columns}

    # The last column is printed whole: it is usually a signature or path, and a cut one
    # sends the reader back to grep for the rest.
    def cells(values):
        head = [str(v)[: widths[c]].ljust(widths[c]) for c, v in zip(columns[:-1], values[:-1])]
        return "  ".join(head + [str(values[-1])]).rstrip()

    print(cells(columns))
    print(cells(["-" * widths[c] for c in columns]))
    for row in rows:
        print(cells([row.get(c, "") for c in columns]))
    print("\n%d row(s)" % len(rows))


def span(row):
    """`path:start-end` — paste-ready for Read's offset (start) and limit (end - start + 1)."""
    return "%s:%d-%d" % (row["file"], row["line"], row.get("end_line") or row["line"])


def emit_declarations(types, members, as_json, empty="(none)"):
    """One line per declaration: path:start-end  kind  Owner.Name  full signature."""
    if as_json:
        print(json.dumps({"types": types, "members": members}, indent=2))
        return
    if not types and not members:
        print(empty)
        return
    for t in types:
        owner = (t["container"] + ".") if t["container"] else ""
        print("%s  %s %s%s  %s  [%s%s]" % (
            span(t), t["kind"], owner, t["name"], t["signature"],
            (t["namespace"] + ", ") if t["namespace"] else "", t["assembly"] or "?"))
    for m in members:
        print("%s  %s %s.%s  %s" % (span(m), m["kind"], m["type"], m["name"], m["signature"]))


def emit_members(rows, as_json, heading=None):
    """Members grouped by file: `start-end  kind  signature`, signatures in full."""
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    current = None
    for row in rows:
        if row["file"] != current:
            current = row["file"]
            print("%s%s" % (heading + " — " if heading else "", current))
        print("  %5d-%-5d %-11s %s" % (row["line"], row["end_line"], row["kind"], row["signature"]))


def show_slices(index, types, members, max_lines):
    """Print each declaration's source, with leading attributes and /// docs, numbered."""
    total = 0
    for row in types + members:
        lines = index.source_lines(row["file"])
        if lines is None:
            print("%s  (file unreadable)" % span(row))
            continue
        start, end = row["line"], row.get("end_line") or row["line"]
        while start > 1 and re.match(r"\s*(\[|///)", lines[start - 2]):
            start -= 1
        owner = row.get("type") or row.get("container") or ""
        print("== %s:%d-%d  %s%s" % (row["file"], start, end,
                                      owner + "." if owner else "", row["name"]))
        stop = min(end, start + max_lines - 1) if max_lines else end
        for number in range(start, stop + 1):
            print("%5d  %s" % (number, lines[number - 1] if number <= len(lines) else ""))
        if stop < end:
            print("  … %d more line(s): Read %s offset=%d limit=%d"
                  % (end - stop, row["file"], stop + 1, end - stop))
        total += 1
    return total


def main():
    # Shared flags live on a parent parser so they are accepted both before and after
    # the subcommand — `codeindex.py bases Foo --json` is the natural way to type it.
    # SUPPRESS is required, not stylistic: with a normal default the subparser writes
    # its own default over a value the top-level parser already set, so a leading
    # `--json` would be silently discarded.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=argparse.SUPPRESS)
    common.add_argument("--db", default=argparse.SUPPRESS)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--no-auto-build", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--compiled-only", action="store_true", default=argparse.SUPPRESS,
                        help="restrict to files Unity compiles for the current build target")

    parser = argparse.ArgumentParser(
        parents=[common], description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    add("build").add_argument("--force", action="store_true")
    add("status")
    add("schema")
    add("where").add_argument("name")

    show = add("show")
    show.add_argument("name")
    show.add_argument("--max-lines", type=int, default=200,
                      help="per declaration; 0 = no limit (default 200)")

    add("attributed").add_argument("name")
    add("bases").add_argument("name")

    impl = add("implementers")
    impl.add_argument("name")
    impl.add_argument("--transitive", action="store_true")

    subc = add("subclasses")
    subc.add_argument("name")
    subc.add_argument("--direct", action="store_true")

    mem = add("members")
    mem.add_argument("name")
    mem.add_argument("--kind", default=None)
    mem.add_argument("--inherited", action="store_true",
                     help="also list members of indexed base types and interfaces")

    typ = add("types")
    typ.add_argument("--assembly", default=None)
    typ.add_argument("--namespace", default=None)
    typ.add_argument("--kind", default=None)

    add("sql").add_argument("query")

    args = parser.parse_args()
    as_json = getattr(args, "json", False)
    project = getattr(args, "project", None)
    db = getattr(args, "db", None)
    auto_build = not getattr(args, "no_auto_build", False)
    compiled_only = getattr(args, "compiled_only", False)

    try:
        root = os.path.abspath(project) if project else find_project_root()
    except ProjectError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    with CodeIndex(root, db) as index:
        index.compiled_only = compiled_only
        if args.cmd == "schema":
            print(index.schema())
            return 0

        if args.cmd == "build":
            print(index.build(force=args.force))
            loose = index.not_compiled()
            if loose:
                print("note: %d indexed file(s) are outside the current build target's "
                      ".csproj set (platform-gated .asmdef, or Unity has not refreshed). "
                      "They are queryable; typecheck.py will not verify them. "
                      "Use --compiled-only to exclude." % len(loose))
            return 0

        if args.cmd == "status":
            s = index.status()
            print("indexed files: %d   project sources: %d" % (s["indexed"], s["sources"]))
            print("added: %d   modified: %d   removed: %d"
                  % (len(s["added"]), len(s["modified"]), len(s["removed"])))
            for label in ("added", "modified", "removed"):
                for path in s[label][:10]:
                    print("  %-9s %s" % (label, os.path.relpath(path, root)))
            loose = index.not_compiled()
            if loose:
                print("indexed but not in the current build target's .csproj set: %d"
                      % len(loose))
                for path in loose[:10]:
                    print("  not-compiled %s" % os.path.relpath(path, root))
            print("FRESH" if index.is_fresh() else "STALE — run `codeindex.py build`")
            return 0

        try:
            rebuilt = index.ensure_fresh(auto_build=auto_build)
        except StaleIndexError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        if rebuilt and rebuilt.changed():
            print("[index refreshed: %s]\n" % rebuilt, file=sys.stderr)

        if args.cmd == "where":
            types, members = index.lookup(args.name)
            emit_declarations(types, members, as_json)
        elif args.cmd == "show":
            types, members = index.lookup(args.name)
            if as_json:
                emit_declarations(types, members, True)
            elif not show_slices(index, types, members, args.max_lines):
                print("(none)")
        elif args.cmd == "attributed":
            rows = index.attributed(args.name)
            if as_json:
                print(json.dumps(rows, indent=2))
            elif not rows:
                print("(none)")
            for row in ([] if as_json else rows):
                owner = row["type"] + ("." + row["member"] if row["member"] else "")
                print("%s  %s %s  [%s]  %s" % (span(row), row["member_kind"] or row["type_kind"],
                                               owner, row["raw"], row["signature"]))
        elif args.cmd == "bases":
            emit(index.bases_of(args.name), as_json, ["name", "raw", "position", "file"])
        elif args.cmd == "implementers":
            emit(index.implementers_of(args.name, direct=not args.transitive), as_json,
                 ["name", "kind", "namespace", "assembly", "file", "line"])
        elif args.cmd == "subclasses":
            emit(index.subclasses_of(args.name, transitive=not args.direct), as_json,
                 ["name", "kind", "depth", "namespace", "assembly", "file"])
        elif args.cmd == "members":
            rows = index.members_of(args.name, args.kind)
            if not args.inherited:
                if not rows and not as_json:
                    print("(none)")
                emit_members(rows, as_json)
            else:
                indexed, external = index.ancestors_of(args.name)
                groups = [(0, args.name, rows)] + [
                    (depth, "from %s (%s)" % (t["name"], t["kind"]),
                     [r for r in index.members_of(t["name"], args.kind) if r["file"] == t["file"]])
                    for depth, t in indexed]
                if as_json:
                    print(json.dumps({"declared": rows,
                                      "inherited": [{"depth": d, "from": label[5:].split(" ")[0],
                                                     "members": r} for d, label, r in groups[1:]],
                                      "not_indexed": external}, indent=2))
                else:
                    for depth, label, members in groups:
                        if depth == 0:
                            emit_members(members, False, args.name)
                        elif members:
                            emit_members(members, False, label)
                    if external:
                        print("not indexed: %s" % ", ".join(external))
        elif args.cmd == "types":
            emit(index.types_in(args.assembly, args.namespace, args.kind), as_json,
                 ["name", "kind", "namespace", "assembly", "file"])
        elif args.cmd == "sql":
            try:
                emit(index.sql(args.query), as_json)
            except sqlite3.OperationalError as exc:
                print("error: %s" % exc, file=sys.stderr)
                if "readonly" in str(exc):
                    print("The sql passthrough is read-only by design; use `build` to "
                          "change the index.", file=sys.stderr)
                return 2
            except sqlite3.Error as exc:
                print("error: %s" % exc, file=sys.stderr)
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
