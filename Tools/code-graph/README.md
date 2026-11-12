# code-graph

Local, read-only browser view and JSON API over a **codeindex** SQLite database
(`schema_version` 3: assemblies → files → types → members, plus `base_ref` inheritance edges).
For the engineer: search, an assembly → namespace → type tree, a pannable inheritance graph and a
member list with `file:line`. For the agent: one `curl` returns a type's bases, derived types,
members and location — instead of several greps or `codeindex.py` calls.

Plain Python 3 (standard library only). The page loads Cytoscape 3.30.2 from cdnjs.

## Usage

```bash
# from the project root (or pass --project); start prints the URL and reuses a healthy server
Tools/code-graph/code-graph.sh start [--db PATH] [--refresh-cmd "<cmd>"]
Tools/code-graph/code-graph.sh status
Tools/code-graph/code-graph.sh stop
```

- `--db` defaults to `<project>/Library/codeindex.sqlite`.
- `--refresh-cmd "<cmd>"` (optional) overrides the command the page's **Force refresh index**
  button runs. Default: `unity-tools/codeindex.py build --force --project <project> --db <db>`
  (the sibling tool in this repo), so plain `start` already shows the button; `--refresh-cmd ""`
  hides it. Pass a real command line, e.g. `--refresh-cmd "python3 path/to/codeindex.py build --force"`.
  How it runs: from the project root, split with `shlex` (no shell), 15-minute timeout, output in
  `.code-graph/refresh.log`. The command is fixed at start; a request can only trigger it.
- `start` warns when the DB is missing — usually a sign it was run from the wrong folder (e.g.
  from `Tools/code-graph/` itself, which then becomes the project).
- Runtime state: `<project>/.code-graph/` (self-ignoring): `server.json`, `server.log`,
  `refresh.log`, `launcher.lock`.
- `start` restarts the server when this tool's code (`*.py`, `web/*`) is newer than the running
  process, or when `--db` / `--refresh-cmd` differ. The server outlives agent sessions.
- Binds 127.0.0.1 only.

## API

| Route | Returns |
|---|---|
| `GET /api/status` | `built_at`, row counts, db path, `refresh_available`, refresh state |
| `GET /api/search?q=&kind=&limit=` | types whose name contains `q` (exact, then prefix, then substring) |
| `GET /api/type?name=` or `?id=` `[&members=0][&kind=method]` | every declaration of the name: kind, namespace, assembly, `file`, `line`, `bases` (`external` / `ambiguous` flags), direct `derived`, `members` |
| `GET /api/graph?name=\|id=&depth=2&direction=both\|up\|down&limit=150` | `nodes` (keyed by type id, `ext:<Name>` for external bases) and `edges` (derived → base), `truncated` |
| `GET /api/tree[?assembly=]` | assemblies with type counts; or one assembly's namespaces and types |
| `GET /api/refresh` · `POST /api/refresh` (header `X-Code-Graph: 1`) | refresh state + log tail · start a rebuild (`202`; `409` when running or unconfigured; `403` without the header) |
| `GET /api/health` | `{project, pid, db}` (launcher health check) |

```bash
curl -s "$URL/api/type?name=IEventManager&members=0"
curl -s "$URL/api/graph?name=Screen&direction=down&depth=1"
```

## Behaviour notes

- Every request opens a fresh read-only connection (`mode=ro`, `query_only`). codeindex writes a
  build in one transaction on a WAL database, so a rebuild never shows a half-built index and the
  server needs no restart afterwards. A forced build of the TripleMatch3D index (~5.3K files,
  ~7K types, ~70K members) took about 6 s.
- Inheritance is resolved by **simple name**, exactly as codeindex does: a base name declared in
  more than one namespace fans out to every declaration (flagged `ambiguous`, dashed amber in
  the graph); a name not declared in the sources (Unity, BCL) is an `external` node.
- Usage edges (who calls X) are not in codeindex, so not here.

## Tests

```bash
python3 -m unittest discover -s Tools/code-graph/tests -p 'test_*.py'
```
