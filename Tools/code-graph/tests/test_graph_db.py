import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR))

from graph_db import GraphDb, GraphDbError  # noqa: E402

# Subset of codeindex.py's SCHEMA (schema_version 3) -- the tables and columns this tool reads.
SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE assembly(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, csproj TEXT NOT NULL);
CREATE TABLE file(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, assembly_id INTEGER,
    mtime REAL NOT NULL, size INTEGER NOT NULL, sha1 TEXT NOT NULL, indexed_at REAL NOT NULL,
    in_csproj INTEGER NOT NULL DEFAULT 1);
CREATE TABLE type(id INTEGER PRIMARY KEY, name TEXT NOT NULL, arity INTEGER NOT NULL DEFAULT 0,
    namespace TEXT NOT NULL DEFAULT '', container TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL,
    file_id INTEGER NOT NULL, line INTEGER NOT NULL, access TEXT,
    is_abstract INTEGER, is_sealed INTEGER, is_static INTEGER, is_partial INTEGER);
CREATE TABLE base_ref(id INTEGER PRIMARY KEY, type_id INTEGER NOT NULL, name TEXT NOT NULL,
    raw TEXT NOT NULL, position INTEGER NOT NULL);
CREATE TABLE member(id INTEGER PRIMARY KEY, type_id INTEGER NOT NULL, name TEXT NOT NULL,
    kind TEXT NOT NULL, signature TEXT NOT NULL, line INTEGER NOT NULL, access TEXT,
    is_static INTEGER, is_abstract INTEGER, is_virtual INTEGER, is_override INTEGER, is_async INTEGER);
"""

# (id, name, arity, namespace, kind, file_id, line, is_abstract)
TYPES = [
    (1, 'IEventManager', 0, 'Events', 'interface', 1, 3, 0),
    (2, 'EventManagerBase', 0, 'Events', 'class', 2, 5, 1),
    (3, 'GemEventManager', 0, 'Events.Gem', 'class', 3, 7, 0),
    (4, 'Shared', 0, 'A', 'class', 4, 1, 0),
    (5, 'Shared', 0, 'B', 'class', 5, 1, 0),
    (6, 'UsesShared', 0, 'A', 'class', 4, 9, 0),
    (7, 'Repo', 1, 'Data', 'class', 6, 2, 0),
    (8, 'EditorTool', 0, 'Tools', 'class', 7, 4, 0),
]
# (type_id, name, raw, position)
BASES = [
    (2, 'IEventManager', 'IEventManager', 0),
    (3, 'EventManagerBase', 'EventManagerBase', 0),
    (3, 'MonoBehaviour', 'UnityEngine.MonoBehaviour', 1),
    (6, 'Shared', 'Shared', 0),
    (7, 'List', 'List<int>', 0),
    (8, 'GemEventManager', 'GemEventManager', 0),
]
# (type_id, name, kind, signature, line, is_static, is_abstract, is_override)
MEMBERS = [
    (1, 'FetchEvents', 'method', 'Task FetchEvents()', 4, 0, 0, 0),
    (2, 'FetchEvents', 'method', 'public abstract Task FetchEvents()', 6, 0, 1, 0),
    (2, 'Count', 'property', 'public int Count', 8, 0, 0, 0),
    (3, 'FetchEvents', 'method', 'public override Task FetchEvents()', 9, 0, 0, 1),
    (3, 'Create', 'method', 'public static GemEventManager Create()', 12, 1, 0, 0),
]


def build_fixture_db(directory, schema_version='3'):
    """Write a small codeindex-shaped DB into directory and return its path."""
    path = os.path.join(directory, 'codeindex.sqlite')
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executemany('INSERT INTO meta VALUES (?, ?)', [
        ('schema_version', schema_version), ('built_at', '2026-11-05T10:00:00'), ('project_root', '/proj')])
    conn.executemany('INSERT INTO assembly VALUES (?, ?, ?)', [
        (1, 'Game', 'Game.csproj'), (2, 'Game.Editor', 'Game.Editor.csproj')])
    files = ['Assets/IEventManager.cs', 'Assets/EventManagerBase.cs', 'Assets/GemEventManager.cs',
             'Assets/A/Shared.cs', 'Assets/B/Shared.cs', 'Assets/Repo.cs', 'Assets/Editor/EditorTool.cs']
    conn.executemany('INSERT INTO file VALUES (?, ?, ?, 0, 0, ?, 0, 1)', [
        (index + 1, path_name, 2 if 'Editor' in path_name else 1, 'sha') for index, path_name in enumerate(files)])
    conn.executemany(
        'INSERT INTO type (id, name, arity, namespace, kind, file_id, line, access, is_abstract) '
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'public', ?)", TYPES)
    conn.executemany('INSERT INTO base_ref (type_id, name, raw, position) VALUES (?, ?, ?, ?)', BASES)
    conn.executemany(
        'INSERT INTO member (type_id, name, kind, signature, line, access, is_static, is_abstract, is_override) '
        "VALUES (?, ?, ?, ?, ?, 'public', ?, ?, ?)", MEMBERS)
    conn.commit()
    conn.close()
    return path


class GraphDbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = GraphDb(build_fixture_db(self.tmp))

    def test_status_reports_meta_and_counts(self):
        status = self.db.status()
        self.assertEqual(status['built_at'], '2026-11-05T10:00:00')
        self.assertEqual(status['counts']['type'], len(TYPES))
        self.assertEqual(status['counts']['member'], len(MEMBERS))

    def test_missing_db_raises(self):
        with self.assertRaises(GraphDbError):
            GraphDb(os.path.join(self.tmp, 'nope.sqlite')).status()

    def test_wrong_schema_version_raises(self):
        other = tempfile.mkdtemp()
        with self.assertRaises(GraphDbError):
            GraphDb(build_fixture_db(other, schema_version='2')).status()

    def test_db_is_opened_read_only(self):
        conn = self.db._connect()
        try:
            with self.assertRaises(sqlite3.Error):
                conn.execute("INSERT INTO meta VALUES ('x', 'y')")
        finally:
            conn.close()

    def test_search_orders_exact_then_prefix_then_substring(self):
        names = [row['name'] for row in self.db.search('EventManager')]
        self.assertEqual(names[0], 'EventManagerBase')  # prefix (no exact match)
        self.assertIn('IEventManager', names)
        self.assertEqual([row['name'] for row in self.db.search('Shared')][:2], ['Shared', 'Shared'])
        self.assertEqual(self.db.search('   '), [])

    def test_search_kind_filter_and_limit(self):
        self.assertEqual([row['name'] for row in self.db.search('Event', kind='interface')], ['IEventManager'])
        self.assertEqual(len(self.db.search('e', limit=2)), 2)

    def test_type_detail_bases_derived_members(self):
        detail = self.db.type_detail('GemEventManager')
        self.assertFalse(detail['ambiguous'])
        gem = detail['types'][0]
        self.assertEqual(gem['file'], 'Assets/GemEventManager.cs')
        self.assertEqual(gem['assembly'], 'Game')
        self.assertEqual([(b['name'], b['external']) for b in gem['bases']],
                         [('EventManagerBase', False), ('MonoBehaviour', True)])
        self.assertEqual([d['name'] for d in gem['derived']], ['EditorTool'])
        self.assertEqual([(m['name'], m['flags']) for m in gem['members']],
                         [('FetchEvents', ['override']), ('Create', ['static'])])

    def test_type_detail_member_kind_and_no_members(self):
        base = self.db.type_detail('EventManagerBase', member_kind='property')['types'][0]
        self.assertEqual([m['name'] for m in base['members']], ['Count'])
        self.assertNotIn('members', self.db.type_detail('EventManagerBase', members=False)['types'][0])

    def test_type_detail_ambiguous_name_and_by_id(self):
        detail = self.db.type_detail('Shared')
        self.assertTrue(detail['ambiguous'])
        self.assertEqual([t['namespace'] for t in detail['types']], ['A', 'B'])
        self.assertEqual(self.db.type_detail(type_id=5)['types'][0]['namespace'], 'B')
        self.assertTrue(self.db.type_detail('UsesShared')['types'][0]['bases'][0]['ambiguous'])

    def test_type_detail_unknown(self):
        self.assertEqual(self.db.type_detail('Nope')['types'], [])

    def test_graph_up_includes_external_base(self):
        graph = self.db.graph('GemEventManager', direction='up', depth=3)
        names = {node['name'] for node in graph['nodes']}
        self.assertEqual(names, {'GemEventManager', 'EventManagerBase', 'IEventManager', 'MonoBehaviour'})
        self.assertIn({'source': '3', 'target': 'ext:MonoBehaviour', 'raw': 'UnityEngine.MonoBehaviour',
                       'ambiguous': False}, graph['edges'])

    def test_graph_down_and_depth(self):
        graph = self.db.graph('IEventManager', direction='down', depth=1)
        self.assertEqual({node['name'] for node in graph['nodes']}, {'IEventManager', 'EventManagerBase'})
        deep = self.db.graph('IEventManager', direction='down', depth=3)
        self.assertEqual({node['name'] for node in deep['nodes']},
                         {'IEventManager', 'EventManagerBase', 'GemEventManager', 'EditorTool'})
        self.assertEqual({(edge['source'], edge['target']) for edge in deep['edges']},
                         {('2', '1'), ('3', '2'), ('8', '3')})

    def test_graph_ambiguous_fan_out_and_limit(self):
        graph = self.db.graph('UsesShared', direction='up')
        self.assertEqual(len([node for node in graph['nodes'] if node['name'] == 'Shared']), 2)
        self.assertTrue(all(edge['ambiguous'] for edge in graph['edges']))
        limited = self.db.graph('IEventManager', direction='down', depth=3, limit=2)
        self.assertEqual(len(limited['nodes']), 2)
        self.assertTrue(limited['truncated'])

    def test_graph_unknown_and_bad_direction(self):
        self.assertEqual(self.db.graph('Nope')['nodes'], [])
        with self.assertRaises(ValueError):
            self.db.graph('Shared', direction='sideways')

    def test_tree_assemblies_and_namespaces(self):
        self.assertEqual(self.db.tree()['assemblies'], [{'name': 'Game', 'types': 7}, {'name': 'Game.Editor', 'types': 1}])
        namespaces = self.db.tree('Game')['namespaces']
        self.assertEqual([ns['name'] for ns in namespaces], ['A', 'B', 'Data', 'Events', 'Events.Gem'])
        self.assertEqual(self.db.tree('Nope')['namespaces'], [])


if __name__ == '__main__':
    unittest.main()
