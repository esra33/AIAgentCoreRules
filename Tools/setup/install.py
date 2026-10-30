#!/usr/bin/env python3
"""Install AIAgentCoreRules into a host project, and prepare and list agent worktrees.

Run from anywhere inside the host project (or one of its worktrees); the project root is the
main checkout of the git repository you are in. Override with --project.

Subcommands:
    install            Configure Claude (default), Codex, or both with --agent.
                       Codex links skills into .agents/skills/ and creates AGENTS.md if missing.
                       Safe to re-run: only adds or updates what the fragments define.
    check              Same as `install --dry-run`; accepts --agent too.
    prepare-worktree   Symlink worktree.symlinkDirectories into a worktree Claude Code did not
                       create (for example one made by hand with `git worktree add`).
    worktrees          List the project's linked worktrees with branch, dirty state, and commits
                       ahead of the current branch (used by /land-worktree).

The core layer lives in <project>/GitIgnoredExternals/ (or GitIgnoreExternals/).
Host layers may live there or in <project>/AIMetaData/. Each layer may ship:
    Skills/<name>/SKILL.md          linked to the selected agent's skills directory
    Setup/settings.host.json        merged after this layer's Tools/setup/settings.core.json

Merge rules: objects merge key by key, lists of plain values are unioned, other values are set.
Hooks are matched by command string — a hook whose command is already present in that event is
left as it is. A changed settings.json is backed up to settings.json.bak before it is written.
Nothing is ever deleted.
"""

import argparse
import json
import os
import subprocess
import sys

import project_root

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_ROOT = os.path.realpath(os.path.join(SCRIPT_DIR, "..", ".."))
CORE_FRAGMENT = os.path.join(SCRIPT_DIR, "settings.core.json")
HOST_FRAGMENT = os.path.join("Setup", "settings.host.json")
EXTERNALS = "GitIgnoredExternals"
CORE_NAME = "AIAgentCoreRules"
HOST_NAME = "AIMetaData"
CORE_IMPORTS = [
    "@GitIgnoredExternals/AIAgentCoreRules/Rules/MetaRouter.md",
    "@GitIgnoredExternals/AIAgentCoreRules/Rules/StopAndVerify.md",
    "@GitIgnoredExternals/AIAgentCoreRules/Rules/CoreTags.md",
]


# ---------------------------------------------------------------------------------------------
# Project and layers

def git(args, cwd):
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip()}")
    return result.stdout.strip()


def find_project_root(start):
    root = project_root.find_project_root(start)
    if not root:
        raise RuntimeError(f"no git repository or CLAUDE.md above {start}; pass --project")
    return root


def find_layers(root):
    """Return [(name, path)] with the core layer first."""
    candidates = [os.path.join(root, name) for name in (EXTERNALS, "GitIgnoreExternals")]
    present = [path for path in candidates if os.path.isdir(path)]
    if len(present) > 1:
        raise RuntimeError("both GitIgnoredExternals and GitIgnoreExternals exist — keep one layer directory")
    if not present:
        raise RuntimeError(f"{candidates[0]} or {candidates[1]} not found — link AIAgentCoreRules first (Documentation/01_Setup.md)")
    externals = present[0]
    layers = []
    for name in sorted(os.listdir(externals)):
        path = os.path.join(externals, name)
        if os.path.isdir(path):
            layers.append((name, path))
    host_path = os.path.join(root, HOST_NAME)
    if os.path.isdir(host_path):
        if host_layers(layers):
            raise RuntimeError(f"host metadata exists in both {externals} and {host_path}")
        layers.append((HOST_NAME, host_path))
    is_core = lambda layer: os.path.realpath(layer[1]) == CORE_ROOT or layer[0] == CORE_NAME
    layers.sort(key=lambda layer: not is_core(layer))
    if not layers or not is_core(layers[0]):
        raise RuntimeError(f"{CORE_NAME} is not linked under {externals}")
    return layers


def host_layers(layers):
    return [
        (name, path) for name, path in layers
        if os.path.realpath(path) != CORE_ROOT and name != CORE_NAME
        and (name == HOST_NAME or os.path.isfile(os.path.join(path, "SystemIndex.md"))
             or os.path.isfile(os.path.join(path, HOST_FRAGMENT)))
    ]


def choose_host_location(args, root, layers):
    """Select a location only for an unconfigured host project."""
    existing = host_layers(layers)
    if existing:
        if args.metadata_location:
            selected = "project" if os.path.dirname(existing[0][1]) == root else "externals"
            if selected != args.metadata_location:
                raise RuntimeError(f"host metadata already lives at {existing[0][1]}")
        return None
    if args.metadata_location:
        return args.metadata_location
    if args.dry_run:
        return None
    if not sys.stdin.isatty():
        raise RuntimeError("new install needs a metadata location; pass --metadata-location externals or project")
    print("Where should this project's AI metadata live?")
    externals_name = os.path.basename(os.path.dirname(layers[0][1]))
    print(f"  1. {externals_name}/{HOST_NAME}/ (local, excluded from the project repository)")
    print("  2. Project root (AIMetaData/, files can be committed)")
    while True:
        try:
            answer = input("Choose 1 or 2: ").strip()
        except (EOFError, KeyboardInterrupt) as error:
            raise RuntimeError("metadata location selection cancelled") from error
        if answer in ("1", "2"):
            return "externals" if answer == "1" else "project"
        print("Enter 1 or 2.")


def scaffold_host(root, layers, location, dry_run, log):
    if location is None:
        if not host_layers(layers):
            log.append("host metadata: choose a location with --metadata-location externals or project")
        return layers
    externals = os.path.dirname(layers[0][1])
    path = os.path.join(externals if location == "externals" else root, HOST_NAME)
    if os.path.lexists(path):
        raise RuntimeError(f"{path} exists but is not a host metadata directory")
    if location == "project":
        relative = os.path.join(HOST_NAME, "SystemIndex.md")
        result = subprocess.run(["git", "check-ignore", "-q", relative], cwd=root)
        if result.returncode == 0:
            raise RuntimeError(f"{relative} is ignored by git; adjust ignore rules before choosing project")
    files = {
        "Rules/ProjectRules.md": "# Project rules\n\nAdd project-wide AI instructions here.\n",
        "SystemIndex.md": "# System index\n\nMap project systems to their documentation here.\n",
        "Setup/settings.host.json": "{}\n",
    }
    for relative, content in files.items():
        target = os.path.join(path, relative)
        log.append(f"host metadata: create {os.path.relpath(target, root)}")
        if not dry_run:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(content)
    return layers + [(HOST_NAME, path)]


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------------------------
# Settings merge

def merge_hooks(target, fragment, source, log):
    hooks = target.setdefault("hooks", {})
    for event, groups in fragment.items():
        existing = hooks.setdefault(event, [])
        commands = {hook.get("command") for group in existing for hook in group.get("hooks", [])}
        for group in groups:
            missing = [hook for hook in group.get("hooks", []) if hook.get("command") not in commands]
            if not missing:
                continue
            existing.append(dict(group, hooks=missing))
            for hook in missing:
                log.append(f"settings: add {event} hook from {source}: {hook.get('command')}")
                commands.add(hook.get("command"))


def merge_value(target, fragment, source, log, path=""):
    for key, value in fragment.items():
        key_path = f"{path}.{key}" if path else key
        if key_path == "hooks":
            merge_hooks(target, value, source, log)
        elif isinstance(value, dict):
            child = target.setdefault(key, {})
            if not isinstance(child, dict):
                log.append(f"settings: SKIP {key_path} from {source} — existing value is not an object")
                continue
            merge_value(child, value, source, log, key_path)
        elif isinstance(value, list):
            current = target.setdefault(key, [])
            for item in value:
                if item not in current:
                    current.append(item)
                    log.append(f"settings: add {item!r} to {key_path} ({source})")
        elif target.get(key) != value:
            if key in target:
                log.append(f"settings: change {key_path} {target[key]!r} -> {value!r} ({source})")
            else:
                log.append(f"settings: set {key_path} = {value!r} ({source})")
            target[key] = value


def fragments(layers):
    found = [(f"{CORE_NAME} core", CORE_FRAGMENT)]
    for name, path in layers:
        host = os.path.join(path, HOST_FRAGMENT)
        if os.path.isfile(host):
            found.append((name, host))
    return found


def install_settings(root, layers, dry_run, log):
    settings_path = os.path.join(root, ".claude", "settings.json")
    settings = load_json(settings_path) if os.path.isfile(settings_path) else {}
    before = json.dumps(settings, sort_keys=True)
    for source, path in fragments(layers):
        fragment = load_json(path)
        if path == CORE_FRAGMENT:
            externals_name = os.path.basename(os.path.dirname(layers[0][1]))
            fragment = json.loads(json.dumps(fragment).replace(EXTERNALS, externals_name))
        merge_value(settings, fragment, source, log)
    if json.dumps(settings, sort_keys=True) == before or dry_run:
        return
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    if os.path.isfile(settings_path):
        with open(settings_path, encoding="utf-8") as src, open(settings_path + ".bak", "w", encoding="utf-8") as dst:
            dst.write(src.read())
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")


# ---------------------------------------------------------------------------------------------
# Skills and CLAUDE.md

def install_skills(root, layers, dry_run, log, agent="claude"):
    skills_dir = os.path.join(root, ".agents" if agent == "codex" else ".claude", "skills")
    claimed = {}
    for layer_name, layer_path in layers:
        layer_skills = os.path.join(layer_path, "Skills")
        if not os.path.isdir(layer_skills):
            continue
        for skill in sorted(os.listdir(layer_skills)):
            if not os.path.isfile(os.path.join(layer_skills, skill, "SKILL.md")):
                continue
            if skill in claimed:
                log.append(f"skills: SKIP {skill} from {layer_name} — already provided by {claimed[skill]}")
                continue
            claimed[skill] = layer_name
            link = os.path.join(skills_dir, skill)
            target = os.path.relpath(os.path.join(layer_skills, skill), skills_dir)
            if os.path.lexists(link):
                if os.path.realpath(link) != os.path.realpath(os.path.join(layer_skills, skill)):
                    log.append(f"skills: CONFLICT {link} exists and does not point at {layer_name} — left as is")
                continue
            log.append(f"skills: link {skill} -> {target}")
            if not dry_run:
                os.makedirs(skills_dir, exist_ok=True)
                os.symlink(target, link)
    prune_stale_skills(skills_dir, layers, dry_run, log)


def prune_stale_skills(skills_dir, layers, dry_run, log):
    """Remove dangling links into a layer's Skills/ folder, left behind by a renamed or deleted skill."""
    if not os.path.isdir(skills_dir):
        return
    layer_skill_dirs = {os.path.normpath(os.path.join(path, "Skills")) for _, path in layers}
    for name in sorted(os.listdir(skills_dir)):
        link = os.path.join(skills_dir, name)
        if not os.path.islink(link) or os.path.exists(link):
            continue
        target = os.path.normpath(os.path.join(skills_dir, os.readlink(link)))
        if os.path.dirname(target) not in layer_skill_dirs:
            continue
        log.append(f"skills: prune stale {name} (target {os.readlink(link)} is gone)")
        if not dry_run:
            os.unlink(link)


def install_claude_md(root, dry_run, log, imports=CORE_IMPORTS):
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(path):
        log.append("CLAUDE.md: create with the core imports — add the host layer's always-on files below them")
        if not dry_run:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(imports) + "\n")
        return
    with open(path, encoding="utf-8") as handle:
        lines = {line.strip() for line in handle}
    for line in imports:
        if line not in lines:
            log.append(f"CLAUDE.md: MISSING {line} — add it by hand")


def install_agents_md(root, layers, dry_run, log):
    path = os.path.join(root, "AGENTS.md")
    if os.path.lexists(path):
        return
    core_path = os.path.relpath(layers[0][1], root).replace(os.sep, "/")
    host_paths = [os.path.relpath(path, root).replace(os.sep, "/") for _, path in host_layers(layers)]
    host_instructions = "".join(
        f"Read `{path}/Rules/ProjectRules.md` and `{path}/SystemIndex.md` when present.\n"
        for path in host_paths
    )
    log.append("AGENTS.md: create with the core rule entry points")
    if not dry_run:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "# Agent instructions\n\n"
                "Before substantive work, read these source files in order:\n\n"
                f"1. `{core_path}/Rules/MetaRouter.md`\n"
                f"2. `{core_path}/Rules/StopAndVerify.md`\n"
                f"3. `{core_path}/Rules/CoreTags.md`\n\n"
                f"{host_instructions}\n"
                "Follow the router and resolve its relative paths against its Rules directory.\n"
                "Use available filesystem reading tools when a dedicated Read tool is absent.\n"
                "Invoke discovered skills with `$skill-name`; interpret Claude-specific tool names\n"
                "using available equivalents. Do not assume Claude hooks, launch commands, or\n"
                "session metrics work in Codex. Report unavailable tooling without inventing results.\n"
            )


# ---------------------------------------------------------------------------------------------
# Worktrees

def list_worktrees(root):
    entries, current = [], {}
    for line in git(["worktree", "list", "--porcelain"], root).splitlines() + [""]:
        if not line:
            if current:
                entries.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value or True
    return [entry for entry in entries if os.path.realpath(entry["worktree"]) != os.path.realpath(root)]


def symlink_directories(root):
    settings_path = os.path.join(root, ".claude", "settings.json")
    settings = load_json(settings_path) if os.path.isfile(settings_path) else {}
    return settings.get("worktree", {}).get("symlinkDirectories", [])


def cmd_prepare_worktree(args, root):
    worktree = os.path.realpath(args.path)
    known = [os.path.realpath(entry["worktree"]) for entry in list_worktrees(root)]
    if worktree not in known:
        print(f"error: {worktree} is not a linked worktree of {root}", file=sys.stderr)
        return 1
    for rel in symlink_directories(root):
        source, dest = os.path.join(root, rel), os.path.join(worktree, rel)
        if not os.path.exists(source):
            print(f"skip {rel}: not present in {root}")
        elif os.path.lexists(dest):
            print(f"ok   {rel}: already present")
        else:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.symlink(source, dest)
            print(f"link {rel} -> {source}")
    return 0


def default_remote_branch(root):
    try:
        return git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], root)
    except RuntimeError:
        return None


def describe_worktree(root, entry, upstream):
    branch = entry.get("branch", "").replace("refs/heads/", "") or "(detached)"
    info = {"path": entry["worktree"], "branch": branch, "prunable": "prunable" in entry}
    if info["prunable"] or branch == "(detached)":
        return info
    tip = entry["HEAD"]
    info["dirty"] = bool(git(["status", "--porcelain"], entry["worktree"]))
    info["ahead"] = int(git(["rev-list", "--count", f"HEAD..{tip}"], root))
    info["behind"] = int(git(["rev-list", "--count", f"{tip}..HEAD"], root))
    if upstream:
        own = int(git(["rev-list", "--count", f"HEAD..{tip}", "--not", upstream], root))
        info["from_upstream"] = info["ahead"] - own
    return info


def cmd_worktrees(args, root):
    upstream = default_remote_branch(root)
    rows = [describe_worktree(root, entry, upstream) for entry in list_worktrees(root)]
    if args.json:
        print(json.dumps({"project": root, "current_branch": git(["branch", "--show-current"], root),
                          "upstream": upstream, "worktrees": rows}, indent=2))
        return 0
    print(f"project {root} on {git(['branch', '--show-current'], root) or '(detached)'}")
    if not rows:
        print("no linked worktrees")
    for row in rows:
        if row["prunable"]:
            print(f"- {row['path']}  PRUNABLE (folder missing — run git worktree prune)")
            continue
        if "ahead" not in row:
            print(f"- {row['path']}  {row['branch']}")
            continue
        notes = ["DIRTY" if row["dirty"] else "clean", f"{row['ahead']} ahead", f"{row['behind']} behind"]
        if row.get("from_upstream"):
            notes.append(f"{row['from_upstream']} of the ahead commits come from {upstream}")
        print(f"- {row['path']}  {row['branch']}  ({', '.join(notes)})")
    return 0


# ---------------------------------------------------------------------------------------------

def cmd_install(args, root):
    layers = find_layers(root)
    log = []
    location = choose_host_location(args, root, layers)
    layers = scaffold_host(root, layers, location, args.dry_run, log)
    agents = ("claude", "codex") if args.agent == "both" else (args.agent,)
    for agent in agents:
        if agent == "claude":
            install_settings(root, layers, args.dry_run, log)
            core_path = os.path.relpath(layers[0][1], root).replace(os.sep, "/")
            imports = [f"@{core_path}/Rules/{name}.md" for name in ("MetaRouter", "StopAndVerify", "CoreTags")]
            if location is not None:
                for _, path in host_layers(layers):
                    host_path = os.path.relpath(path, root).replace(os.sep, "/")
                    imports.extend((f"@{host_path}/Rules/ProjectRules.md", f"@{host_path}/SystemIndex.md"))
            install_claude_md(root, args.dry_run, log, imports)
        else:
            install_agents_md(root, layers, args.dry_run, log)
        install_skills(root, layers, args.dry_run, log, agent)
    header = "would change" if args.dry_run else "changed"
    print(f"project {root}  layers: {', '.join(name for name, _ in layers)}")
    print(f"{header}:" if log else "up to date — nothing to change")
    for line in log:
        print(f"  {line}")
    if log and not args.dry_run:
        if "claude" in agents:
            print("Restart Claude Code sessions in this project to pick up settings and new skills.")
        if "codex" in agents:
            print("Codex skills are linked; restart Codex if they do not appear. Invoke with $skill-name.")
    if "codex" in agents:
        print("Codex: Claude hooks/settings were not installed for Codex; Claude-specific launchers and session tracking still require adaptation.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", help="host project root (default: main checkout of the current git repo)")
    sub = parser.add_subparsers(dest="command")
    install = sub.add_parser("install", help="configure Claude, Codex, or both")
    install.add_argument("--agent", choices=("claude", "codex", "both"), default="claude")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--metadata-location", choices=("externals", "project"),
                         help="location for new host metadata; prompts when omitted on an interactive install")
    install.set_defaults(func=cmd_install)
    check = sub.add_parser("check", help="install --dry-run")
    check.add_argument("--agent", choices=("claude", "codex", "both"), default="claude")
    check.add_argument("--metadata-location", choices=("externals", "project"),
                       help="preview a new host metadata location")
    check.set_defaults(func=cmd_install, dry_run=True)
    prepare = sub.add_parser("prepare-worktree", help="symlink worktree.symlinkDirectories into a worktree")
    prepare.add_argument("path")
    prepare.set_defaults(func=cmd_prepare_worktree)
    worktrees = sub.add_parser("worktrees", help="list linked worktrees and how they relate to the current branch")
    worktrees.add_argument("--json", action="store_true")
    worktrees.set_defaults(func=cmd_worktrees)
    args = parser.parse_args()
    if not args.command:
        args = parser.parse_args(sys.argv[1:] + ["install"])
    try:
        start = args.project or os.environ.get("CLAUDE_PROJECT_DIR") or project_root.logical_cwd()
        root = os.path.realpath(args.project) if args.project else find_project_root(start)
        return args.func(args, root)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
