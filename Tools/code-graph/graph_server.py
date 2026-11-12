#!/usr/bin/env python3
"""Code Graph server: a read-only browser view and JSON API over a codeindex SQLite DB.

Run it through code-graph.sh (start / status / stop). Foreground use:
  python3 graph_server.py serve --db <codeindex.sqlite> --project <root> [--port N] [--refresh-cmd "<cmd>"]

Binds 127.0.0.1 only. The first stdout line is the URL (the launcher waits for it).
"""
import argparse
import functools
import http.server
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from graph_db import DEFAULT_GRAPH_DEPTH, DEFAULT_NODE_LIMIT, DEFAULT_SEARCH_LIMIT, GraphDb, GraphDbError
from refresh_job import RefreshJob

WEB_DIR = Path(__file__).resolve().parent / 'web'
WEB_CONTENT_TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                     '.css': 'text/css; charset=utf-8'}
# A custom header forces a CORS preflight, which this server never answers, so a page on another
# origin cannot trigger a rebuild with a plain form POST to 127.0.0.1.
REFRESH_HEADER = 'X-Code-Graph'


class GraphHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, db, project, refresh_job, web_dir=WEB_DIR, **kwargs):
        # Set before super().__init__: BaseHTTPRequestHandler handles the request inside __init__.
        self._db = db
        self._project = str(project)
        self._refresh = refresh_job
        self._web_files = {path.name: path for path in Path(web_dir).iterdir()
                           if path.suffix in WEB_CONTENT_TYPES} if Path(web_dir).is_dir() else {}
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        return

    # -- routing ---------------------------------------------------------

    def do_GET(self):
        url = urlsplit(self.path)
        query = {key: values[-1] for key, values in parse_qs(url.query).items()}
        routes = {
            '/api/health': lambda: {'project': self._project, 'pid': os.getpid(), 'db': self._db.db_path},
            '/api/status': self._status,
            '/api/search': lambda: {'query': query.get('q', ''), 'results': self._db.search(
                query.get('q', ''), limit=_int(query, 'limit', DEFAULT_SEARCH_LIMIT), kind=query.get('kind'))},
            '/api/type': lambda: self._db.type_detail(
                name=query.get('name'), type_id=query.get('id'), members=query.get('members') != '0',
                member_kind=query.get('kind')),
            '/api/graph': lambda: self._db.graph(
                name=query.get('name'), type_id=query.get('id'),
                depth=_int(query, 'depth', DEFAULT_GRAPH_DEPTH), direction=query.get('direction', 'both'),
                limit=_int(query, 'limit', DEFAULT_NODE_LIMIT)),
            '/api/tree': lambda: self._db.tree(query.get('assembly')),
            '/api/refresh': self._refresh.state,
        }
        if url.path in ('/', '/index.html'):
            self._send_file('index.html')
        elif url.path.startswith('/web/'):
            self._send_file(url.path[len('/web/'):])
        elif url.path in routes:
            if url.path in ('/api/type', '/api/graph') and not (query.get('name') or query.get('id')):
                self._send_json({'error': 'name or id is required'}, 400)
                return
            self._answer(routes[url.path])
        else:
            self._send_json({'error': 'not found'}, 404)

    def do_POST(self):
        if urlsplit(self.path).path != '/api/refresh':
            self._send_json({'error': 'not found'}, 404)
            return
        if self.headers.get(REFRESH_HEADER) != '1':
            self._send_json({'error': 'missing %s: 1 header' % REFRESH_HEADER}, 403)
            return
        if not self._refresh.available:
            self._send_json({'error': 'no refresh command configured (started with --refresh-cmd "", or unity-tools/codeindex.py not found)'}, 409)
            return
        if not self._refresh.start():
            self._send_json(dict(self._refresh.state(), error='a refresh is already running'), 409)
            return
        self._send_json(self._refresh.state(), 202)

    # -- helpers ---------------------------------------------------------

    def _status(self):
        status = self._db.status()
        status['project'] = self._project
        status['refresh_available'] = self._refresh.available
        status['refresh'] = self._refresh.state()['state']
        return status

    def _answer(self, produce):
        try:
            self._send_json(produce())
        except GraphDbError as error:
            self._send_json({'error': str(error)}, 503)
        except ValueError as error:
            self._send_json({'error': str(error)}, 400)

    def _send_file(self, name):
        path = self._web_files.get(name)
        if path is None:
            self._send_json({'error': 'not found'}, 404)
            return
        self._send_bytes(path.read_bytes(), WEB_CONTENT_TYPES[path.suffix], 200)

    def _send_json(self, data, status=200):
        self._send_bytes(json.dumps(data).encode('utf-8'), 'application/json', status)

    def _send_bytes(self, payload, content_type, status):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)


def _int(query, key, default):
    try:
        return int(query.get(key, default))
    except (TypeError, ValueError):
        raise ValueError('%s must be an integer' % key)


def bind_server(handler_factory, port):
    """127.0.0.1 only; a busy requested port falls back to a free one (as doc-review's _bind_server)."""
    if port is not None:
        try:
            return http.server.ThreadingHTTPServer(('127.0.0.1', port), handler_factory)
        except OSError:
            print('Port %d is in use -- picking a free one instead.' % port, file=sys.stderr)
    return http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler_factory)


def make_handler(db_path, project, refresh_cmd=None, refresh_log=None, web_dir=WEB_DIR):
    project = Path(project).resolve()
    refresh_log = refresh_log or (project / '.code-graph' / 'refresh.log')
    Path(refresh_log).parent.mkdir(parents=True, exist_ok=True)
    job = RefreshJob(refresh_cmd, project, refresh_log)
    return functools.partial(GraphHandler, db=GraphDb(db_path), project=project, refresh_job=job,
                             web_dir=web_dir)


def serve(db_path, project, port=None, refresh_cmd=None, refresh_log=None):
    httpd = bind_server(make_handler(db_path, project, refresh_cmd, refresh_log), port)
    print('http://127.0.0.1:%d/' % httpd.server_address[1], flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    serve_parser = sub.add_parser('serve', help='run the server in the foreground')
    serve_parser.add_argument('--project', default='.')
    serve_parser.add_argument('--db', help='default: <project>/Library/codeindex.sqlite')
    serve_parser.add_argument('--port', type=int)
    serve_parser.add_argument('--refresh-cmd', help='command the "Force refresh index" button runs')
    serve_parser.add_argument('--refresh-log', help='default: <project>/.code-graph/refresh.log')
    args = parser.parse_args()
    project = Path(args.project).resolve()
    serve(args.db or project / 'Library' / 'codeindex.sqlite', project, args.port, args.refresh_cmd,
          args.refresh_log)


if __name__ == '__main__':
    main()
