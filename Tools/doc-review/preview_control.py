#!/usr/bin/env python3
"""Project-owned preview process management. No shell utilities or external flock required."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

# Python never reloads modules, so a long-running server keeps serving the code it started with.
TOOL_DIRS = (Path(__file__).parent, Path(__file__).parent.parent / 'feature-state')


def server_identity(url):
    try:
        with urlopen(url + 'api/health', timeout=1) as response:
            identity = json.load(response)
        return identity if isinstance(identity, dict) else {}
    except (OSError, ValueError):
        return {}


def healthy(state, project):
    if not state.get('url'):
        return False
    identity = server_identity(state['url'])
    return identity.get('project') == str(project) and identity.get('pid') == state.get('pid')


def list_previews():
    from doc_review import running_servers

    found = False
    for server in running_servers('serve-project'):
        if not server['port']:
            continue
        url = f"http://127.0.0.1:{server['port']}/"
        identity = server_identity(url)
        if identity.get('pid') == server['pid'] and identity.get('project'):
            print(f"pid {server['pid']}  {url}  {identity['project']}")
            found = True
    if not found:
        print('No active project previews')


def tool_code_mtime(tool_dirs=None):
    return max((path.stat().st_mtime for directory in tool_dirs or TOOL_DIRS for path in directory.glob('*.py')), default=0.0)


def stale(state, state_path, tool_dirs=None):
    # Servers started before 'started' was recorded fall back to when server.json was written.
    try:
        started = state.get('started') or state_path.stat().st_mtime
    except OSError:
        return False
    return tool_code_mtime(tool_dirs) > started


def stop(state, project, state_path):
    os.kill(state['pid'], signal.SIGTERM)
    for _ in range(40):
        if not healthy(state, project):
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Preview did not stop; runtime metadata retained')
    state_path.unlink(missing_ok=True)


def control(action, project):
    project = project.resolve()
    runtime = project / '.doc-review'
    os.umask(0o077)
    runtime.mkdir(exist_ok=True)
    (runtime / ".gitignore").write_text("*\n")
    with (runtime / 'launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = runtime / 'server.json'
        try:
            state = json.loads(state_path.read_text())
        except (OSError, ValueError):
            state = {}
        running = healthy(state, project)
        if action == 'status':
            print('Running: ' + state['url'] if running else 'Stopped')
            return
        if action == 'stop':
            if running:
                stop(state, project, state_path)
            print('Stopped' if running else 'No managed preview running')
            return
        if running and not stale(state, state_path):
            print(state['url'])
            return
        if running:
            stop(state, project, state_path)
            print('restarted (tool code changed)')
        log_path = runtime / 'server.log'
        started = time.time()
        with log_path.open('w') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('doc_review.py')), 'serve-project', str(project)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(60):
            lines = log_path.read_text().splitlines()
            if lines and lines[0].startswith('http://127.0.0.1:'):
                state = {'pid': process.pid, 'url': lines[0], 'project': str(project), 'started': started}
                if healthy(state, project):
                    temporary = state_path.with_suffix('.tmp')
                    temporary.write_text(json.dumps(state))
                    temporary.replace(state_path)
                    print(state['url'])
                    return
            if process.poll() is not None:
                break
            time.sleep(.1)
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        raise RuntimeError('Preview startup failed; see ' + str(log_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'stop', 'status', 'list'))
    parser.add_argument('--project', default='.')
    args = parser.parse_args()
    try:
        if args.action == 'list':
            list_previews()
        else:
            control(args.action, Path(args.project))
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
