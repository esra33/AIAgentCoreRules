#!/usr/bin/env python3
"""Read-only graph queries over a codeindex SQLite database (schema_version 3).

The DB is written by the host's codeindex.py; this module never writes it. Each call opens a
fresh read-only connection, so a rebuild committed while the server runs is picked up by the
next request (the DB is in WAL mode: readers see the last committed snapshot).

Inheritance edges are resolved the way codeindex.py resolves them: base_ref.name is the base's
simple name (generic arguments and namespace stripped), matched against type.name only. A name
declared in more than one namespace fans out to every declaration and is flagged 'ambiguous';
a name with no declaration (Unity / BCL types) becomes an 'external' node.
"""
import os
import sqlite3
from contextlib import closing

SCHEMA_VERSION = '4'
DEFAULT_GRAPH_DEPTH = 2
MAX_GRAPH_DEPTH = 6
DEFAULT_NODE_LIMIT = 150
DEFAULT_SEARCH_LIMIT = 50

TYPE_COLUMNS = (
    't.id, t.name, t.arity, t.namespace, t.container, t.kind, t.line, t.access, '
    't.is_abstract, t.is_sealed, t.is_static, t.is_partial, f.path AS file, a.name AS assembly')
TYPE_FROM = (
    ' FROM type t JOIN file f ON f.id = t.file_id'
    ' LEFT JOIN assembly a ON a.id = f.assembly_id')
FLAG_COLUMNS = ('is_abstract', 'is_sealed', 'is_static', 'is_partial')
MEMBER_FLAG_COLUMNS = ('is_static', 'is_abstract', 'is_virtual', 'is_override', 'is_async')


class GraphDbError(Exception):
    """The database is missing, unreadable, or not a codeindex schema this tool understands."""


class GraphDb:
    def __init__(self, db_path):
        self.db_path = os.path.abspath(db_path)

    # -- connection ------------------------------------------------------

    def _connect(self):
        if not os.path.exists(self.db_path):
            raise GraphDbError('codeindex database not found: %s (run codeindex.py build)' % self.db_path)
        try:
            conn = sqlite3.connect('file:%s?mode=ro' % self.db_path, uri=True)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA query_only = ON')
            version = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        except sqlite3.Error as error:
            raise GraphDbError('cannot read %s: %s' % (self.db_path, error))
        if version is None or version[0] != SCHEMA_VERSION:
            conn.close()
            raise GraphDbError('unsupported codeindex schema_version %r (expected %s)'
                               % (version[0] if version else None, SCHEMA_VERSION))
        return conn

    @staticmethod
    def _rows(conn, sql, params=()):
        return [dict(row) for row in conn.execute(sql, params)]

    @staticmethod
    def _clean(row, flags=FLAG_COLUMNS):
        """Turn 0/1/NULL flag columns into a compact list of set flag names."""
        row = dict(row)
        row['flags'] = [flag[3:] for flag in flags if row.pop(flag, None)]
        return row

    # -- status ----------------------------------------------------------

    def status(self):
        with closing(self._connect()) as conn:
            meta = {row['key']: row['value'] for row in conn.execute('SELECT key, value FROM meta')}
            counts = {table: conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
                      for table in ('assembly', 'file', 'type', 'base_ref', 'member')}
        return {
            'db': self.db_path,
            'schema_version': meta.get('schema_version'),
            'built_at': meta.get('built_at'),
            'project_root': meta.get('project_root'),
            'counts': counts,
        }

    # -- search ----------------------------------------------------------

    def search(self, query, limit=DEFAULT_SEARCH_LIMIT, kind=None):
        """Types whose name contains query: exact first, then prefix, then substring."""
        query = (query or '').strip()
        if not query:
            return []
        params = ['%' + query + '%']
        where = ' WHERE t.name LIKE ?'
        if kind:
            where += ' AND t.kind = ?'
            params.append(kind)
        sql = ('SELECT ' + TYPE_COLUMNS + TYPE_FROM + where +
               ' ORDER BY CASE WHEN t.name = ? THEN 0 WHEN t.name LIKE ? THEN 1 ELSE 2 END,'
               ' length(t.name), t.name, t.namespace LIMIT ?')
        params += [query, query + '%', int(limit)]
        with closing(self._connect()) as conn:
            return [self._clean(row) for row in self._rows(conn, sql, params)]

    # -- type detail -----------------------------------------------------

    def types_named(self, conn, name):
        return [self._clean(row) for row in self._rows(
            conn, 'SELECT ' + TYPE_COLUMNS + TYPE_FROM + ' WHERE t.name = ? ORDER BY t.namespace, f.path', (name,))]

    def _declaration_counts(self, conn, names):
        names = sorted(set(names))
        if not names:
            return {}
        marks = ','.join('?' * len(names))
        rows = conn.execute('SELECT name, COUNT(*) FROM type WHERE name IN (%s) GROUP BY name' % marks, names)
        return {row[0]: row[1] for row in rows}

    def _bases(self, conn, type_id):
        bases = self._rows(conn, 'SELECT name, raw, position FROM base_ref WHERE type_id = ? ORDER BY position',
                           (type_id,))
        counts = self._declaration_counts(conn, [base['name'] for base in bases])
        for base in bases:
            declared = counts.get(base['name'], 0)
            base['external'] = declared == 0
            base['ambiguous'] = declared > 1
        return bases

    def _derived(self, conn, name):
        """Direct derived types / implementers: codeindex.py implementers_of(direct=True)."""
        return [self._clean(row) for row in self._rows(
            conn, 'SELECT ' + TYPE_COLUMNS + TYPE_FROM + ' JOIN base_ref b ON b.type_id = t.id'
            ' WHERE b.name = ? ORDER BY a.name, t.name', (name,))]

    def _type_row(self, conn, type_id):
        rows = self._rows(conn, 'SELECT ' + TYPE_COLUMNS + TYPE_FROM + ' WHERE t.id = ?', (type_id,))
        return self._clean(rows[0]) if rows else None

    def _type_refs(self, conn, type_id):
        """Outgoing type_ref edges of a single type: field/property/param/return
        dependencies, each flagged external/ambiguous like _bases()."""
        refs = self._rows(
            conn, 'SELECT member_id, member_kind, name, raw, relation, is_collection, position'
                  ' FROM type_ref WHERE owner_id = ? ORDER BY member_id, position', (type_id,))
        counts = self._declaration_counts(conn, [ref['name'] for ref in refs])
        for ref in refs:
            declared = counts.get(ref['name'], 0)
            ref['external'] = declared == 0
            ref['ambiguous'] = declared > 1
        return refs

    def _used_by(self, conn, name):
        """Other types' type_ref rows naming `name` as their referenced type, with the
        referencing type's identity."""
        return self._rows(
            conn, 'SELECT t.id AS owner_id, t.name AS owner_name, r.member_kind, r.raw,'
                  '       r.relation, r.is_collection'
                  '  FROM type_ref r JOIN type t ON t.id = r.owner_id'
                  ' WHERE r.name = ? ORDER BY t.name', (name,))

    def _edges_out(self, conn, type_id, kinds):
        """(name, raw, kind) outgoing edges of type_id restricted to `kinds` -- 'inherits'
        from base_ref, 'uses'/'aggregation' from type_ref."""
        out = [(b['name'], b['raw'], 'inherits') for b in self._bases(conn, type_id)] \
            if 'inherits' in kinds else []
        wanted = kinds & {'uses', 'aggregation'}
        if wanted:
            out.extend((row['name'], row['raw'], row['relation']) for row in self._rows(
                conn, 'SELECT name, raw, relation FROM type_ref WHERE owner_id = ?', (type_id,))
                if row['relation'] in wanted)
        return out

    def _edges_in(self, conn, name, kinds):
        """(child type row, raw, kind) incoming edges naming `name`, restricted to `kinds`."""
        out = []
        if 'inherits' in kinds:
            for child in self._derived(conn, name):
                raw = conn.execute('SELECT raw FROM base_ref WHERE type_id = ? AND name = ? LIMIT 1',
                                   (child['id'], name)).fetchone()
                out.append((child, raw[0] if raw else name, 'inherits'))
        wanted = kinds & {'uses', 'aggregation'}
        if wanted:
            seen = set()
            for row in self._rows(
                conn, 'SELECT t.id, r.raw, r.relation FROM type_ref r JOIN type t ON t.id = r.owner_id'
                      ' WHERE r.name = ?', (name,)):
                key = (row['id'], row['relation'])
                if row['relation'] not in wanted or key in seen:
                    continue
                seen.add(key)
                child = self._type_row(conn, row['id'])
                if child:
                    out.append((child, row['raw'], row['relation']))
        return out

    def _members(self, conn, type_id, kind=None):
        sql = ('SELECT name, kind, signature, line, access, ' + ', '.join(MEMBER_FLAG_COLUMNS) +
               ' FROM member WHERE type_id = ?')
        params = [type_id]
        if kind:
            sql += ' AND kind = ?'
            params.append(kind)
        return [self._clean(row, MEMBER_FLAG_COLUMNS) for row in self._rows(conn, sql + ' ORDER BY line', params)]

    def type_detail(self, name=None, type_id=None, members=True, member_kind=None):
        """Every declaration of `name` (or the one `type_id`) with bases, direct derived types and members."""
        with closing(self._connect()) as conn:
            if type_id is not None:
                declarations = [self._clean(row) for row in self._rows(
                    conn, 'SELECT ' + TYPE_COLUMNS + TYPE_FROM + ' WHERE t.id = ?', (int(type_id),))]
                name = declarations[0]['name'] if declarations else name
            else:
                declarations = self.types_named(conn, name)
            derived = self._derived(conn, name) if declarations else []
            used_by = self._used_by(conn, name) if declarations else []
            for declaration in declarations:
                declaration['bases'] = self._bases(conn, declaration['id'])
                declaration['derived'] = derived
                declaration['uses'] = self._type_refs(conn, declaration['id'])
                declaration['used_by'] = used_by
                if members:
                    declaration['members'] = self._members(conn, declaration['id'], member_kind)
        return {'name': name, 'ambiguous': len(declarations) > 1, 'types': declarations}

    # -- graph -----------------------------------------------------------

    def graph(self, name=None, type_id=None, depth=DEFAULT_GRAPH_DEPTH, direction='both',
              limit=DEFAULT_NODE_LIMIT, edge_kinds='inherits'):
        """Structural neighbourhood: nodes keyed by type id ('ext:<Name>' for external bases).

        Edges point from the dependent/derived type to what it depends on/derives from.
        'up' follows them outward (bases; or what this type uses/aggregates), 'down'
        follows them inward (derived types; or types that use/aggregate this one), 'both'
        does each from the root (not siblings). `edge_kinds` is a comma list of 'inherits'
        (base_ref -- the default; omitting it reproduces the original inheritance-only
        graph), 'uses' and 'aggregation' (both from type_ref). Every edge carries a `kind`.
        """
        if direction not in ('up', 'down', 'both'):
            raise ValueError("direction must be 'up', 'down' or 'both'")
        kinds = {k.strip() for k in (edge_kinds or 'inherits').split(',') if k.strip()}
        if not kinds or not kinds <= {'inherits', 'uses', 'aggregation'}:
            raise ValueError("edge_kinds must be one or more of: inherits, uses, aggregation")
        depth = max(0, min(int(depth), MAX_GRAPH_DEPTH))
        limit = max(1, int(limit))
        nodes, edges, edge_keys = {}, [], set()
        truncated = False

        def add_node(row, level):
            key = str(row['id'])
            if key not in nodes:
                node = {key_name: row[key_name] for key_name in
                        ('id', 'name', 'kind', 'namespace', 'container', 'file', 'line', 'assembly', 'flags')}
                node['id'] = key
                node['depth'] = level
                nodes[key] = node
            return key

        def add_edge(source, target, raw, ambiguous, kind):
            edge_key = (source, target, kind)
            if edge_key in edge_keys:
                return
            edge_keys.add(edge_key)
            edges.append({'source': source, 'target': target, 'raw': raw, 'ambiguous': ambiguous,
                          'kind': kind})

        with closing(self._connect()) as conn:
            if type_id is not None:
                roots = [self._clean(row) for row in self._rows(
                    conn, 'SELECT ' + TYPE_COLUMNS + TYPE_FROM + ' WHERE t.id = ?', (int(type_id),))]
            else:
                roots = self.types_named(conn, name)
            if not roots:
                return {'root': name, 'nodes': [], 'edges': [], 'truncated': False}
            root_keys = [add_node(row, 0) for row in roots]

            if direction in ('up', 'both'):
                frontier = list(roots)
                for level in range(1, depth + 1):
                    next_frontier = []
                    for row in frontier:
                        for edge_name, raw, kind in self._edges_out(conn, row['id'], kinds):
                            targets = self.types_named(conn, edge_name)
                            if not targets:
                                key = 'ext:' + edge_name
                                if key not in nodes:
                                    if len(nodes) >= limit:
                                        truncated = True
                                        continue
                                    nodes[key] = {'id': key, 'name': edge_name, 'kind': 'external',
                                                  'namespace': '', 'container': '', 'file': None, 'line': None,
                                                  'assembly': None, 'flags': [], 'depth': -level}
                                add_edge(str(row['id']), key, raw, False, kind)
                                continue
                            for target in targets:
                                if str(target['id']) not in nodes:
                                    if len(nodes) >= limit:
                                        truncated = True
                                        continue
                                    add_node(target, -level)
                                    next_frontier.append(target)
                                add_edge(str(row['id']), str(target['id']), raw, len(targets) > 1, kind)
                    frontier = next_frontier

            if direction in ('down', 'both'):
                frontier = list(roots)
                for level in range(1, depth + 1):
                    next_frontier = []
                    for row in frontier:
                        parents = self.types_named(conn, row['name'])
                        for child, raw, kind in self._edges_in(conn, row['name'], kinds):
                            if str(child['id']) not in nodes:
                                if len(nodes) >= limit:
                                    truncated = True
                                    continue
                                add_node(child, level)
                                next_frontier.append(child)
                            add_edge(str(child['id']), str(row['id']), raw, len(parents) > 1, kind)
                    frontier = next_frontier

        return {'root': roots[0]['name'], 'roots': root_keys, 'nodes': list(nodes.values()),
                'edges': edges, 'truncated': truncated}

    # -- tree ------------------------------------------------------------

    def tree(self, assembly=None):
        """No assembly: assemblies with type counts. With one: its namespaces, each with its types."""
        with closing(self._connect()) as conn:
            if assembly is None:
                return {'assemblies': self._rows(
                    conn, 'SELECT a.name, COUNT(t.id) AS types FROM assembly a'
                          ' JOIN file f ON f.assembly_id = a.id JOIN type t ON t.file_id = f.id'
                          ' GROUP BY a.id ORDER BY a.name')}
            rows = self._rows(
                conn, 'SELECT t.id, t.name, t.kind, t.namespace, t.container FROM type t'
                      ' JOIN file f ON f.id = t.file_id JOIN assembly a ON a.id = f.assembly_id'
                      ' WHERE a.name = ? ORDER BY t.namespace, t.name', (assembly,))
        namespaces = {}
        for row in rows:
            namespaces.setdefault(row.pop('namespace') or '(global)', []).append(row)
        return {'assembly': assembly,
                'namespaces': [{'name': key, 'types': value} for key, value in namespaces.items()]}
