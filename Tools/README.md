# Tools

Run `bash Tools/tools.sh -h` to see every callable method. Use
`bash Tools/tools.sh <domain> <method> [arguments]` from the project root, or
call `Tools/tools.sh` by absolute path from another directory. The dispatcher
passes arguments unchanged and does not alter the working directory. A method's
`-h` shows its detailed CLI. `TOOLS_PYTHON` selects the interpreter for methods
that invoke Python directly; existing Bash wrappers retain their own interpreter
settings.

The dispatcher lists engineer-facing commands. Skills and local servers continue
to call their underlying tools through direct paths. `by-domain/` provides links
to those tool directories and their detailed documentation.

| Domain | Tool directories | Primary use |
| --- | --- | --- |
| [code](by-domain/code/) | `code-graph` | Graph browser and index refresh |
| [documents](by-domain/documents/) | `doc-review`, `mermaid-graph`, `deimagify`, `docs-export` | Review, diagrams, image description cache, export |
| [project](by-domain/project/) | `setup`, `publish` | Project integration and publishing |

Examples:

```bash
bash Tools/tools.sh code code-graph start --project .
bash Tools/tools.sh documents doc-review preview status --project .
bash Tools/tools.sh documents doc-review servers --json
bash Tools/tools.sh project setup check --agent codex
```

The full command map below is generated from `command_catalog.py`, which also drives
`tools.sh -h` and command routing. Regenerate it with
`python3 Tools/command_catalog.py readme`.

<!-- command-catalog:start -->
```text
code
  code-graph <start|status|stop> [--project DIR] — Control the code graph browser
    start [--project DIR] — Start browser
    status [--project DIR] — Check browser
    stop [--project DIR] — Stop browser
documents
  doc-review <preview|servers|stop> ... — Control document review servers
    preview <start|stop|status|list> [--project DIR] — Manage persistent previews
      start [--project DIR] — Start project preview
      stop [TARGET] — Stop project preview
      status [--project DIR] — Show preview status
      list — List active previews
    servers [--json] — List live servers
    stop [--port N] — Stop live server
  mermaid-graph <create|generate|start|list|stop> ... — Edit class diagrams
    create [options] — Create diagram
    generate [options] — Generate diagram
    start [options] — Start editor
    list [options] — List editors
    stop [options] — Stop editor
  deimagify <check|store|forget|list> ... — Cache image descriptions
    check FILE — Check cache
    store FILE DESCRIPTION — Store description
    forget FILE — Remove cache entry
    list — List cache entries
  docs-export [options] SOURCE — Export docs for Confluence
project
  setup <command> ... — Manage project integration
    install [--agent AGENT] — Install integration
    check [--agent AGENT] — Preview install
    prepare-worktree DIR — Link worktree directories
    worktrees [--project DIR] — List worktrees
  config [--project DIR] get KEY — Resolve project paths
    get KEY — Read configured path
  publish <check|publish|status> ... — Manage Git publication
    check [options] — Check request
    publish [options] — Publish request
    status [options] — Show status
```
<!-- command-catalog:end -->

Commands that write files or start servers keep the behavior and safety checks
described in their individual READMEs. The `-h` listing is safe to run; it
does not launch a tool.
