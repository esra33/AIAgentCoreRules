import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TESTS_DIR = Path(__file__).resolve().parent
TOOL_DIR = TESTS_DIR.parent
sys.path.insert(0, str(TOOL_DIR))
sys.path.insert(0, str(TESTS_DIR))

import graph_server  # noqa: E402
from test_graph_db import build_fixture_db  # noqa: E402


class ServerCase(unittest.TestCase):
    refresh_cmd = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = build_fixture_db(self.tmp)
        self.web = os.path.join(self.tmp, 'web')
        os.mkdir(self.web)
        Path(self.web, 'index.html').write_text('<html>graph</html>')
        Path(self.web, 'secret.txt').write_text('no')
        handler = graph_server.make_handler(self.db_path, self.tmp, self.refresh_cmd,
                                            os.path.join(self.tmp, 'refresh.log'), web_dir=self.web)
        self.httpd = graph_server.bind_server(handler, None)
        self.base = 'http://127.0.0.1:%d' % self.httpd.server_address[1]
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, path):
        try:
            with urlopen(self.base + path, timeout=5) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def get_json(self, path):
        status, body = self.get(path)
        return status, json.loads(body)

    def post(self, path, header=True):
        request = Request(self.base + path, data=b'', method='POST',
                          headers={'X-Code-Graph': '1'} if header else {})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())


class GraphServerTest(ServerCase):
    def test_index_and_web_allowlist(self):
        self.assertEqual(self.get('/'), (200, b'<html>graph</html>'))
        self.assertEqual(self.get('/web/index.html')[0], 200)
        self.assertEqual(self.get('/web/secret.txt')[0], 404)

    def test_path_traversal_is_refused(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_address[1], timeout=5)
        conn.request('GET', '/web/../test_graph_db.py')
        self.assertEqual(conn.getresponse().status, 404)
        conn.close()

    def test_health_and_status(self):
        status, health = self.get_json('/api/health')
        self.assertEqual((status, health['pid']), (200, os.getpid()))
        self.assertEqual(health['project'], str(Path(self.tmp).resolve()))
        _, data = self.get_json('/api/status')
        self.assertEqual(data['built_at'], '2026-11-05T10:00:00')
        self.assertFalse(data['refresh_available'])

    def test_search_type_graph_tree(self):
        _, search = self.get_json('/api/search?q=Gem')
        self.assertEqual(search['results'][0]['name'], 'GemEventManager')
        _, detail = self.get_json('/api/type?name=GemEventManager&members=0')
        self.assertNotIn('members', detail['types'][0])
        self.assertEqual(detail['types'][0]['bases'][1]['name'], 'MonoBehaviour')
        _, by_id = self.get_json('/api/type?id=5')
        self.assertEqual(by_id['types'][0]['namespace'], 'B')
        _, graph = self.get_json('/api/graph?name=IEventManager&direction=down&depth=1')
        self.assertEqual({node['name'] for node in graph['nodes']}, {'IEventManager', 'EventManagerBase'})
        self.assertTrue(all(edge['kind'] == 'inherits' for edge in graph['edges']))
        _, uses_graph = self.get_json(
            '/api/graph?name=GemEventManager&direction=up&depth=1&edge_kinds=uses,aggregation')
        self.assertEqual({node['name'] for node in uses_graph['nodes']},
                         {'GemEventManager', 'EventLogger', 'EventOptions'})
        _, tree = self.get_json('/api/tree')
        self.assertEqual(tree['assemblies'][0]['name'], 'Game')
        _, namespaces = self.get_json('/api/tree?assembly=Game.Editor')
        self.assertEqual(namespaces['namespaces'][0]['types'][0]['name'], 'EditorTool')

    def test_bad_requests(self):
        self.assertEqual(self.get_json('/api/type')[0], 400)
        self.assertEqual(self.get_json('/api/graph?name=X&depth=deep')[0], 400)
        self.assertEqual(self.get_json('/api/graph?name=X&direction=sideways')[0], 400)
        self.assertEqual(self.get_json('/api/graph?name=X&edge_kinds=sideways')[0], 400)
        self.assertEqual(self.get_json('/api/nope')[0], 404)
        self.assertEqual(self.post('/api/nope')[0], 404)

    def test_missing_db_is_503(self):
        os.remove(self.db_path)
        for suffix in ('-wal', '-shm'):
            if os.path.exists(self.db_path + suffix):
                os.remove(self.db_path + suffix)
        status, body = self.get_json('/api/status')
        self.assertEqual(status, 503)
        self.assertIn('not found', body['error'])

    def test_refresh_unconfigured(self):
        _, state = self.get_json('/api/refresh')
        self.assertFalse(state['available'])
        self.assertEqual(self.post('/api/refresh')[0], 409)


class RefreshServerTest(ServerCase):
    refresh_cmd = [sys.executable, '-c', "import time; print('rebuilt'); time.sleep(0.5)"]

    def test_refresh_requires_header(self):
        self.assertEqual(self.post('/api/refresh', header=False)[0], 403)
        self.assertEqual(self.get_json('/api/refresh')[1]['state'], 'idle')

    def test_refresh_runs_once_then_reports_done(self):
        status, state = self.post('/api/refresh')
        self.assertEqual((status, state['state']), (202, 'running'))
        self.assertEqual(self.post('/api/refresh')[0], 409)
        self.assertTrue(self.get_json('/api/status')[1]['refresh_available'])
        for _ in range(50):
            state = self.get_json('/api/refresh')[1]
            if state['state'] != 'running':
                break
            time.sleep(0.1)
        self.assertEqual((state['state'], state['log_tail']), ('done', ['rebuilt']))


if __name__ == '__main__':
    unittest.main()
