"""Persistent, request-scoped feature previews; selection is never server-global."""
import functools
import html
import json
import os
import sys
import hashlib
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import review_server as view
from sidecar_store import SidecarStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'feature-state'))
import feature_state

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'setup'))
import project_config

TITLES = ('Home', 'Plan', 'TDD', 'GDD', 'Class Diagram', 'Flow Diagram', 'LLM Performance')
ROLES = ('plan', 'tdd', 'gdd', 'class_diagram', 'flow_diagram', 'performance')


def feature_path(root, name):
    path = (root / name).resolve()
    if not name or path.parent != root.resolve() or not path.is_dir():
        raise ValueError('Unknown feature')
    return path


def artifact_path(directory, value):
    if not isinstance(value, str):
        return None
    path = (directory / value).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError('Artifact path escapes feature directory')
    return path


def project_tabs(root, directory=None):
    entries = feature_state.list_features(root)
    rows = ['# Active features', '']
    for entry in entries:
        name = Path(entry.get('feature_dir', root / entry['feature'])).name
        suffix = ' — migration required' if not (root / name / 'state.json').exists() else ''
        selected = ' — selected' if directory and directory.resolve().name == name else ''
        label = html.escape(name)
        target = '?feature=' + quote(name, safe='')
        rows.append(f'<p><a href="{target}">{label}</a>{suffix}{selected}</p>')
    if not entries:
        rows.append('No active features found.')
    tabs = [{'title': 'Home', 'kind': 'md', 'file': '#home', 'path': root, 'content': '\n'.join(rows)}]
    state = feature_state.load_state(directory) if directory and (directory / 'state.json').exists() else None

    # Add Plan tab
    if directory and state is None:
        tab = {'title': 'Plan', 'kind': 'md', 'file': '#plan', 'path': root, 'content': 'Migration required. Run the feature-state migration command explicitly.'}
    elif state:
        path = directory / (state['feature'] + '_Progress.md')
        tab = {'title': 'Plan', 'kind': 'progress', 'file': '#progress', 'path': path}
    else:
        tab = {'title': 'Plan', 'kind': 'md', 'file': '#plan', 'path': root, 'content': 'Pending generation or data not found yet.'}
    tabs.append(tab)

    # Add phase-report tabs (after Plan, before TDD/GDD)
    if state:
        phase_reports = state.get('phase_reports', {})
        phase_order = [f"{i}_{name}" for i, name in enumerate(
            ["intake", "discovery", "design", "implementation", "unit_tests", "integration", "verification", "retrospective"], 1)]
        for phase_key in sorted(phase_reports.keys(), key=lambda k: phase_order.index(k) if k in phase_order else 999):
            report_path = phase_reports[phase_key]
            path = artifact_path(directory, report_path)
            if path and path.is_file():
                phase_number = int(phase_key.split("_", 1)[0])
                phase_label = phase_key.split("_", 1)[1].replace("_", " ").title()
                title = f"Phase {phase_number}: {phase_label} Report"
                tab = {'title': title, 'kind': 'md', 'file': str(path.relative_to(directory.resolve())),
                       'path': path}
                tabs.append(tab)

        # Add milestone-report tabs (ad hoc summaries within a phase, e.g. a V-stage) in registration order
        for report in state.get('milestone_reports', []):
            path = artifact_path(directory, report.get('path'))
            if path and path.is_file():
                tab = {'title': report['label'], 'kind': 'md', 'file': str(path.relative_to(directory.resolve())),
                       'path': path}
                tabs.append(tab)

    # Add remaining fixed tabs (TDD, GDD, diagrams, performance)
    for title, role in zip(TITLES[2:], ROLES[1:]):
        tab = {'title': title, 'kind': 'md', 'file': '#' + role, 'path': root, 'content': 'Pending generation or data not found yet.'}
        if directory and state is None:
            tab['content'] = 'Migration required. Run the feature-state migration command explicitly.'
        if state:
            roles = state.get('artifact_roles', {})
            value = roles.get(role)
            if isinstance(value, list):
                value = value[0] if len(value) == 1 else None
            path = artifact_path(directory, value)
            if role == 'performance':
                reports = view.perf_view.find_reports_root(directory / 'state.json')
                if reports:
                    tab.update(kind='perf', path=reports, progress=directory / (state['feature'] + '_Progress.md'))
                    tab.pop('content')
            elif path and path.is_file():
                tab.update(kind='mmd' if path.suffix == '.mmd' else 'md', path=path, file=str(path.relative_to(directory.resolve())))
                tab.pop('content')
        tabs.append(tab)
    for index, tab in enumerate(tabs):
        tab['id'] = 'd' + str(index)
    return tabs


class ProjectHandler(view.ReviewRequestHandler):
    def __init__(self, *args, features_root, project, **kwargs):
        self.features_root = features_root
        self.project = project
        self.directory = None
        self.project_tabs = []
        super().__init__(*args, doc_paths=[project / '_project.md'], store=None, **kwargs)

    def _context(self):
        parsed = urlsplit(self.path)
        name = parse_qs(parsed.query).get('feature', [''])[0]
        self.directory = feature_path(self.features_root, name) if name else None
        self._doc_paths = [self.directory / '_feature.md'] if self.directory else [self.project / '_project.md']
        self._store = SidecarStore(self.directory, feature=True) if self.directory else None
        self.path = parsed.path
        self.project_tabs = project_tabs(self.features_root, self.directory)

    def do_GET(self):
        try:
            self._context()
            if self.path == '/api/health':
                self._send_json({'project': str(self.project), 'pid': os.getpid()})
            elif self.path == '/':
                page = view.build_page(self._doc_paths, live=True, tabs=self.project_tabs)
                prefix = '<script>const originalFetch=window.fetch.bind(window);const selectedFeature=new URLSearchParams(location.search).get("feature");window.fetch=(input,options)=>{if(typeof input==="string"&&input.startsWith("/api/")&&selectedFeature){input += (input.includes("?")?"&":"?")+"feature="+encodeURIComponent(selectedFeature);}return originalFetch(input,options);};</script>'
                prefix += '<script>window.projectTopology=' + json.dumps(self._topology()) + ';</script>'
                self._send_html(page.replace('<head>', '<head>' + prefix))
            elif self.path == '/api/state':
                threads = self._store.load()['threads'] if self._store else []
                for thread in threads:
                    artifact_path(self.directory, thread['anchor']['file'])
                    thread['resolution'] = view.resolve_thread(self.directory, thread)
                self._send_json({'mtimes': view._collect_mtimes(self.project_tabs), 'threads': threads, 'topology': self._topology()})
            elif self.path == '/api/sources':
                self._send_json(view._collect_sources(self.project_tabs))
            else:
                super().do_GET()
        except (ValueError, OSError, KeyError) as error:
            self._send_json({'error': str(error)}, status=400)

    def _topology(self):
        shape = [(tab['kind'], tab['file'], str(tab['path'])) for tab in self.project_tabs]
        return hashlib.sha256(json.dumps(shape).encode()).hexdigest()

    def do_POST(self):
        try:
            self._context()
            if self.directory is None or not (self.directory / 'state.json').is_file():
                raise ValueError('Select a migrated feature before commenting')
            super().do_POST()
        except (ValueError, OSError, KeyError) as error:
            self._send_json({'error': str(error)}, status=400)

    def _read_json_body(self):
        body = super()._read_json_body()
        if body and body.get('anchor'):
            anchor = body['anchor']
            path = artifact_path(self.directory, anchor.get('file'))
            if path is None or not path.is_file() or path.suffix not in ('.md', '.mmd'):
                raise ValueError('Comment target must be a feature document or diagram')
        return body


def serve_project(project, features_root=None, port=None, open_browser=False):
    project = project.resolve()
    root = project_config.resolve_path(project, 'features', override=features_root)
    factory = functools.partial(ProjectHandler, features_root=root, project=project)
    server = view._bind_server(factory, port)
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    print(url, flush=True)
    if open_browser:
        view._open_url(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
