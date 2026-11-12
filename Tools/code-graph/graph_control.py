#!/usr/bin/env python3
"""start / status / stop for the Code Graph server (wrapper: code-graph.sh).

Modelled on doc-review's preview_control.py. Runtime state lives in <project>/.code-graph/
(self-ignoring .gitignore): server.json {pid, url, project, db, refresh_cmd, started}, server.log,
refresh.log and launcher.lock (serialises concurrent start/stop calls). `start` reuses a healthy
server and prints its URL; it restarts the server when the tool code is newer than the running
process, or when --db / --refresh-cmd differ from what it was started with. The server outlives
the agent session -- do not stop it at session end. Without --refresh-cmd the "Force refresh index"
button runs the sibling unity-tools/codeindex.py build --force on the same project and DB;
--refresh-cmd "" hides the button.
"""
import argparse
import fcntl
import json
import os
import shlex
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

TOOL_DIR = Path(__file__).resolve().parent
RUNTIME_DIR_NAME = '.code-graph'
# Python never reloads modules, so a long-running server keeps serving the code it started with.
TOOL_FILES = ('*.py', 'web/*')
CODEINDEX_SCRIPT = TOOL_DIR.parent / 'unity-tools' / 'codeindex.py'


def default_refresh_cmd(project, db, codeindex=CODEINDEX_SCRIPT):
    """Rebuild the exact DB the server reads; None when codeindex.py is not shipped alongside."""
    if not Path(codeindex).is_file():
        return None
    return shlex.join([sys.executable, str(codeindex), 'build', '--force', '--project', str(project),
                       '--db', str(db)])


def healthy(state, project):
    try:
        with urlopen(state['url'] + 'api/health', timeout=1) as response:
            data = json.load(response)
        return data.get('project') == str(project) and data.get('pid') == state['pid']
    except (OSError, ValueError, KeyError):
        return False


def tool_code_mtime(tool_dir=TOOL_DIR):
    return max((path.stat().st_mtime for pattern in TOOL_FILES for path in Path(tool_dir).glob(pattern)), default=0.0)


def stale(state, tool_dir=TOOL_DIR):
    return tool_code_mtime(tool_dir) > state.get('started', 0)


def stop(state, project, state_path):
    os.kill(state['pid'], signal.SIGTERM)
    for _ in range(40):
        if not healthy(state, project):
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Code Graph server did not stop; runtime metadata retained')
    state_path.unlink(missing_ok=True)


def launch(project, db, refresh_cmd, runtime, state_path):
    log_path = runtime / 'server.log'
    started = time.time()
    command = [sys.executable, str(TOOL_DIR / 'graph_server.py'), 'serve', '--project', str(project), '--db', str(db),
               '--refresh-log', str(runtime / 'refresh.log')]
    if refresh_cmd:
        command += ['--refresh-cmd', refresh_cmd]
    with log_path.open('w') as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    for _ in range(60):
        lines = log_path.read_text().splitlines()
        if lines and lines[0].startswith('http://127.0.0.1:'):
            state = {'pid': process.pid, 'url': lines[0], 'project': str(project), 'db': str(db),
                     'refresh_cmd': refresh_cmd, 'started': started}
            if healthy(state, project):
                temporary = state_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(state))
                temporary.replace(state_path)
                return state
        if process.poll() is not None:
            break
        time.sleep(.1)
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)
    raise RuntimeError('Code Graph startup failed; see ' + str(log_path))


def control(action, project, db=None, refresh_cmd=None, out=print,
            warn=lambda message: print(message, file=sys.stderr)):
    project = Path(project).resolve()
    db = Path(db).resolve() if db else project / 'Library' / 'codeindex.sqlite'
    if refresh_cmd is None:
        refresh_cmd = default_refresh_cmd(project, db)
    runtime = project / RUNTIME_DIR_NAME
    os.umask(0o077)
    runtime.mkdir(exist_ok=True)
    (runtime / '.gitignore').write_text('*\n')
    with (runtime / 'launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = runtime / 'server.json'
        try:
            state = json.loads(state_path.read_text())
        except (OSError, ValueError):
            state = {}
        running = healthy(state, project)
        if action == 'status':
            if running:
                out('Running: %s\n  db: %s\n  refresh: %s' % (state['url'], state.get('db'),
                                                             state.get('refresh_cmd') or '(not configured)'))
            else:
                out('Stopped')
            return state if running else None
        if action == 'stop':
            if running:
                stop(state, project, state_path)
            out('Stopped' if running else 'No Code Graph server running')
            return None
        if not db.is_file():
            warn('warning: no codeindex DB at %s -- run from the project root or pass --project '
                 '(the page\'s Force refresh index button builds it)' % db)
        reasons = []
        if running and stale(state):
            reasons.append('tool code changed')
        if running and (state.get('db') != str(db) or state.get('refresh_cmd') != refresh_cmd):
            reasons.append('--db / --refresh-cmd changed')
        if running and not reasons:
            out(state['url'])
            return state
        if running:
            stop(state, project, state_path)
            out('restarted (%s)' % ', '.join(reasons))
        state = launch(project, db, refresh_cmd, runtime, state_path)
        out(state['url'])
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=('start', 'stop', 'status'))
    parser.add_argument('--project', default='.')
    parser.add_argument('--db', help='codeindex SQLite DB (default: <project>/Library/codeindex.sqlite)')
    parser.add_argument('--refresh-cmd', help='command the "Force refresh index" button runs, run from the project '
                        'root (default: unity-tools/codeindex.py build --force for this project and DB; "" hides '
                        'the button)')
    args = parser.parse_args()
    try:
        control(args.action, args.project, args.db, args.refresh_cmd)
    except (OSError, RuntimeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
