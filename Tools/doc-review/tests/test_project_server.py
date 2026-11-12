"""Project preview contracts and request isolation."""
import functools
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import project_server
from review_server import _bind_server


class ProjectPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        self.root = self.project / 'Assets/GitIgnoreAssets/Features'
        for name in ('Alpha', 'Beta'):
            directory = self.root / name
            directory.mkdir(parents=True)
            state = project_server.feature_state.create_state(directory, name)
            (directory / 'Design.md').write_text('# Design\nFeature content')
            # Artifact registration uses the public update API in production.
            state['artifact_roles']['tdd'] = 'Design.md'
            (directory / 'state.json').write_text(json.dumps(state))

    def test_fixedTabsAndMissingPlaceholders(self):
        tabs = project_server.project_tabs(self.root, self.root / 'Alpha')
        self.assertEqual([tab['title'] for tab in tabs], list(project_server.TITLES))
        self.assertIn('Beta', tabs[0]['content'])
        self.assertEqual(tabs[2]['file'], 'Design.md')
        self.assertIn('Pending generation', tabs[3]['content'])

    def test_milestoneReportTabInsertedAfterPlanBeforeFixedTabs(self):
        directory = self.root / 'Alpha'
        (directory / 'V0Summary.md').write_text('# V0 Summary\nDone.')
        state = project_server.feature_state.load_state(directory)
        state['milestone_reports'] = [{'label': 'V0 Summary', 'path': 'V0Summary.md'}]
        (directory / 'state.json').write_text(json.dumps(state))
        tabs = project_server.project_tabs(self.root, directory)
        titles = [tab['title'] for tab in tabs]
        self.assertEqual(titles, ['Home', 'Plan', 'V0 Summary'] + list(project_server.TITLES[2:]))
        self.assertEqual(tabs[2]['file'], 'V0Summary.md')

    def test_rejectsFeatureAndArtifactTraversal(self):
        with self.assertRaises(ValueError):
            project_server.feature_path(self.root, '../Elsewhere')
        with self.assertRaises(ValueError):
            project_server.artifact_path(self.root / 'Alpha', '../../outside.md')

    def test_commentsAreRequestScopedAndSourceFilesRemainUnchanged(self):
        server = _bind_server(functools.partial(project_server.ProjectHandler, features_root=self.root, project=self.project), None)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:' + str(server.server_address[1])
        for name in ('Alpha', 'Beta'):
            payload = {'anchor': {'kind': 'text', 'file': 'Design.md', 'quote': 'Feature content'}, 'text': name}
            request = Request(url + '/api/comment?feature=' + name, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urlopen(request) as response:
                self.assertEqual(json.load(response)['id'], 't1')
        for name in ('Alpha', 'Beta'):
            with urlopen(url + '/api/state?feature=' + name) as response:
                threads = json.load(response)['threads']
            self.assertEqual(len(threads), 1)
            self.assertEqual(threads[0]['replies'][0]['text'], name)
            self.assertEqual((self.root / name / 'Design.md').read_text(), '# Design\nFeature content')
        request = Request(url + '/api/comment', data=b'{}', headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 400)


class ProjectPreviewRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()

    def served_root(self, override=None, environment=None):
        server = mock.Mock(server_address=('127.0.0.1', 12345))
        with mock.patch.dict(os.environ, environment or {}, clear=True), \
             mock.patch.object(project_server.view, '_bind_server', return_value=server) as bind:
            project_server.serve_project(self.project, features_root=override)
        server.serve_forever.assert_called_once()
        server.server_close.assert_called_once()
        return bind.call_args.args[0].keywords['features_root']

    def test_configured_feature_directory_and_override_precedence(self):
        (self.project / 'ai-agent-core.json').write_text(json.dumps({
            'schema_version': 1, 'paths': {'features': 'Assets/Documentation/Features', 'design_documents': 'Assets/Documentation/DesignDocuments'}
        }))
        self.assertEqual(self.served_root(), self.project / 'Assets/Documentation/Features')
        environment = {'SESSION_FEATURES_ROOT': str(self.project / 'EnvironmentFeatures')}
        self.assertEqual(self.served_root(environment=environment), self.project / 'EnvironmentFeatures')
        self.assertEqual(self.served_root(override=self.project / 'ExplicitFeatures', environment=environment),
                         self.project / 'ExplicitFeatures')

    def test_project_without_config_uses_legacy_directory(self):
        self.assertEqual(self.served_root(), self.project / 'Assets/GitIgnoreAssets/Features')

    def test_invalid_config_fails_before_binding(self):
        (self.project / 'ai-agent-core.json').write_text('{invalid')
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(project_server.view, '_bind_server') as bind:
            with self.assertRaises(RuntimeError):
                project_server.serve_project(self.project)
        bind.assert_not_called()


if __name__ == '__main__':
    unittest.main()
