#!/usr/bin/env python3
"""Single route and display catalog for tools.sh and Tools/README.md."""
import sys
from pathlib import Path

# domain|method|runner|target|signature|purpose
ROUTES = [line.split('|', 4)[:4] + line.split('|', 4)[4].rsplit('|', 1) for line in '''
code|code-graph|bash|code-graph/code-graph.sh|<start|status|stop> [--project DIR]|Control the code graph browser
documents|doc-review|python|doc-review/doc_review.py|<preview|servers|stop> ...|Control document review servers
documents|mermaid-graph|bash|mermaid-graph/mermaid-graph.sh|<create|generate|start|list|stop> ...|Edit class diagrams
documents|deimagify|python|deimagify/deimagify.py|<check|store|forget|list> ...|Cache image descriptions
documents|docs-export|python|docs-export/export_confluence.py|[options] SOURCE|Export docs for Confluence
project|setup|bash|setup/install.sh|<command> ...|Manage project integration
project|config|python|setup/project_config.py|[--project DIR] get KEY|Resolve project paths
project|publish|python|publish/publish.py|<check|publish|status> ...|Manage Git publication
'''.strip().splitlines()]

# domain|parent|command|signature|purpose. Children of a nested parent use "parent command".
SUBS = [line.split('|', 3)[:3] + line.split('|', 3)[3].rsplit('|', 1) for line in '''
code|code-graph|start|[--project DIR]|Start browser
code|code-graph|status|[--project DIR]|Check browser
code|code-graph|stop|[--project DIR]|Stop browser
documents|doc-review|preview|<start|stop|status|list> [--project DIR]|Manage persistent previews
documents|doc-review preview|start|[--project DIR]|Start project preview
documents|doc-review preview|stop|[TARGET]|Stop project preview
documents|doc-review preview|status|[--project DIR]|Show preview status
documents|doc-review preview|list||List active previews
documents|doc-review|servers|[--json]|List live servers
documents|doc-review|stop|[--port N]|Stop live server
documents|mermaid-graph|create|[options]|Create diagram
documents|mermaid-graph|generate|[options]|Generate diagram
documents|mermaid-graph|start|[options]|Start editor
documents|mermaid-graph|list|[options]|List editors
documents|mermaid-graph|stop|[options]|Stop editor
documents|deimagify|check|FILE|Check cache
documents|deimagify|store|FILE DESCRIPTION|Store description
documents|deimagify|forget|FILE|Remove cache entry
documents|deimagify|list||List cache entries
project|setup|install|[--agent AGENT]|Install integration
project|setup|check|[--agent AGENT]|Preview install
project|setup|prepare-worktree|DIR|Link worktree directories
project|setup|worktrees|[--project DIR]|List worktrees
project|config|get|KEY|Read configured path
project|publish|check|[options]|Check request
project|publish|publish|[options]|Publish request
project|publish|status|[options]|Show status
'''.strip().splitlines()]

DOMAINS = ('code', 'documents', 'project')

def rows():
    result = []
    for domain in DOMAINS:
        result.append(domain)
        for d, method, _, _, signature, purpose in ROUTES:
            if d != domain:
                continue
            result.append(f'  {method}{" " + signature if signature else ""} — {purpose}')
            for sd, parent, command, signature, purpose in SUBS:
                if (sd, parent) != (domain, method):
                    continue
                result.append(f'    {command}{" " + signature if signature else ""} — {purpose}')
                for cd, cp, child, cs, desc in SUBS:
                    if (cd, cp) == (domain, method + ' ' + command):
                        result.append(f'      {child}{" " + cs if cs else ""} — {desc}')
    return result

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if action == 'route':
        _, _, domain, method, *arguments = sys.argv
        matches = [r for r in ROUTES if r[1] == method and (not domain or r[0] == domain)]
        if len(matches) != 1:
            return 2
        if method == 'doc-review' and (not arguments or arguments[0] not in {'preview', 'servers', 'stop'}):
            return 2
        print(matches[0][2] + '\t' + matches[0][3])
    elif action == 'method-help':
        if len(sys.argv) != 4:
            return 2
        domain, method = sys.argv[2:]
        matches = [r for r in ROUTES if r[0] == domain and r[1] == method]
        if len(matches) != 1:
            return 2
        print(f'Usage: Tools/tools.sh {domain} {method} <command> [arguments]\n')
        _, _, _, _, signature, purpose = matches[0]
        print(f'{method} {signature} — {purpose}')
        for sd, parent, command, signature, purpose in SUBS:
            if (sd, parent) != (domain, method):
                continue
            print(f'  {command}{" " + signature if signature else ""} — {purpose}')
            for cd, child_parent, child, child_signature, description in SUBS:
                if (cd, child_parent) == (domain, method + ' ' + command):
                    print(f'    {child}{" " + child_signature if child_signature else ""} — {description}')
    elif action == 'help':
        print('Usage: Tools/tools.sh [domain] <method> [tool arguments]')
        print('       Tools/tools.sh -h\n')
        print('Run a method with -h for full options. Paths resolve from the current directory.\n')
        print('\n'.join(rows()))
    elif action == 'readme':
        print('```text\n' + '\n'.join(rows()) + '\n```')
    elif action == 'verify':
        assert len({(r[0], r[1]) for r in ROUTES}) == len(ROUTES)
        assert len({r[1] for r in ROUTES}) == len(ROUTES)
        assert all((Path(__file__).parent / r[3]).is_file() for r in ROUTES)
        parents = {(r[0], r[1]) for r in ROUTES}
        parents.update((s[0], s[1] + ' ' + s[2]) for s in SUBS if (s[0], s[1]) in parents)
        assert all((s[0], s[1]) in parents for s in SUBS)
        assert not {'unity', 'unitysource', 'cslint', 'feature-state', 'mermaid-preview',
                    'migrate-phase-reports', 'backfill-diagrams'} & {r[1] for r in ROUTES}
        print('Catalog routes and targets verified')
    else:
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
