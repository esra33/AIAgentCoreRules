"""
Shared Unity project model for the Runnable scripts.

Parses the .csproj files Unity generates at the project root and exposes:
  - which source files belong to which assembly
  - the reference graph between assemblies (and its inverse)
  - the path to the Unity editor's bundled Roslyn compiler

Nothing here touches the Unity editor or the Library folder cache beyond reading
prebuilt DLLs, so it is safe to run while the editor is open.
"""

import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from functools import lru_cache

NS = "{http://schemas.microsoft.com/developer/msbuild/2003}"

# Roots searched for an installed Unity editor, in order. UNITY_PATH wins if set.
UNITY_SEARCH_ROOTS = [
    "/Applications/Unity/Hub/Editor/{version}/Unity.app",
    "~/Documents/UnityInstalls/{version}/Unity.app",
    "/Applications/Unity/{version}/Unity.app",
]


class ProjectError(Exception):
    pass


def find_project_root(start=None):
    """Walk up from `start` (default cwd) until a Unity project root is found."""
    path = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(path, "ProjectSettings", "ProjectVersion.txt")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            raise ProjectError(
                "No Unity project root found (looked for ProjectSettings/ProjectVersion.txt "
                "in every parent of %s). Pass --project explicitly." % (start or os.getcwd())
            )
        path = parent


def main_checkout_of(root):
    """If `root` is a linked git worktree, return the main checkout's root, else None.

    A worktree holds only tracked files, so Unity's generated .csproj files, Library/
    and every git-ignored folder exist only in the main checkout."""

    def git(*args):
        result = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else ""

    git_dir = git("rev-parse", "--absolute-git-dir")
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if not git_dir or not common or os.path.realpath(git_dir) == os.path.realpath(common):
        return None
    main = os.path.dirname(os.path.realpath(common))
    return main if os.path.isdir(main) else None


def git_ignored(root, paths):
    """The subset of `paths` that git ignores in the checkout at `root`."""
    if not paths:
        return set()
    result = subprocess.run(
        ["git", "-C", root, "check-ignore", "--no-index", "--stdin"],
        input="\n".join(os.path.relpath(p, root) for p in paths),
        capture_output=True, text=True,
    )
    return {os.path.join(root, line) for line in result.stdout.splitlines() if line}


def editor_version(root):
    with open(os.path.join(root, "ProjectSettings", "ProjectVersion.txt")) as f:
        for line in f:
            if line.startswith("m_EditorVersion:"):
                return line.split(":", 1)[1].strip()
    raise ProjectError("Could not read m_EditorVersion from ProjectVersion.txt")


def _meta_guid(meta_path):
    """The `guid:` of a Unity .meta file, lower-case, or None."""
    try:
        with open(meta_path, errors="replace") as f:
            for line in f:
                if line.startswith("guid:"):
                    return line.split(":", 1)[1].strip().lower()
    except OSError:
        pass
    return None


def find_compiler(root):
    """Return (dotnet, csc.dll) from the Unity install matching this project."""
    version = editor_version(root)

    candidates = []
    env = os.environ.get("UNITY_PATH")
    if env:
        candidates.append(env)
    candidates += [os.path.expanduser(p.format(version=version)) for p in UNITY_SEARCH_ROOTS]

    for app in candidates:
        contents = os.path.join(app, "Contents")
        # Unity 6 moved both under Contents/Resources/Scripting; older layouts keep
        # them directly under Contents.
        for prefix in (contents, os.path.join(contents, "Resources", "Scripting")):
            dotnet = os.path.join(prefix, "NetCoreRuntime", "dotnet")
            csc = os.path.join(prefix, "DotNetSdkRoslyn", "csc.dll")
            if os.path.exists(dotnet) and os.path.exists(csc):
                return dotnet, csc

    raise ProjectError(
        "No Unity %s install found with a bundled Roslyn.\nLooked in:\n  %s\n"
        "Set UNITY_PATH to the .app if it lives somewhere else."
        % (version, "\n  ".join(candidates))
    )


# A generated .csproj whose HintPaths mostly point at files that no longer exist was
# left behind by an older assembly layout; Unity does not delete these. They cannot be
# compiled (their framework references are gone) and they shadow live assemblies in the
# file index, so they are detected and excluded. Live projects resolve nearly all of
# their references; orphans in practice resolve under 10%.
STALE_REF_RESOLUTION = 0.5


class Assembly:
    __slots__ = ("name", "csproj", "sources", "defines", "hint_refs", "proj_refs", "stale")

    def __init__(self, name, csproj):
        self.name = name
        self.csproj = csproj
        self.sources = []
        self.defines = ""
        self.hint_refs = []
        self.proj_refs = []
        self.stale = False


class Project:
    """The whole set of generated csproj files, parsed once.

    `root` is the checkout whose sources are compiled. `project_files_root` is where the
    .csproj files and Library/ live; it differs from `root` only for a git worktree,
    which borrows them from its main checkout (see `main_checkout_of`)."""

    def __init__(self, root, project_files_root=None):
        self.root = root
        self.project_files_root = project_files_root or root
        self.assemblies = {}
        self.borrowed_sources = 0   # git-ignored in the worktree, compiled from the main checkout
        self.dropped_sources = 0    # listed by the borrowed .csproj but deleted in the worktree
        self.added_references = []  # [(assembly, new asmdef)] wired in for a worktree
        self.unbuilt_asmdefs = []   # new worktree asmdefs with no .csproj in the main checkout
        self._file_index = None
        self._asmdefs = None
        self._parse_all()

    @property
    def is_worktree(self):
        return self.project_files_root != self.root

    def _parse_all(self):
        names = [f for f in os.listdir(self.project_files_root) if f.endswith(".csproj")]
        if not names:
            raise ProjectError(
                "No .csproj files at %s. Open the project in Unity once so it can "
                "generate them (Preferences > External Tools > Regenerate)." % self.project_files_root
            )

        for filename in names:
            name = filename[: -len(".csproj")]
            path = os.path.join(self.project_files_root, filename)
            try:
                tree = ET.parse(path)
            except ET.ParseError:
                continue

            asm = Assembly(name, path)
            node = tree.getroot()

            # Unity emits one DefineConstants per configuration; they only differ by
            # DEBUG/TRACE, so the longest is a safe superset for type checking.
            for element in node.iter(NS + "DefineConstants"):
                if len(element.text or "") > len(asm.defines):
                    asm.defines = element.text or ""

            for element in node.iter(NS + "Compile"):
                include = element.get("Include")
                if include:
                    asm.sources.append(os.path.join(self.root, include.replace("\\", "/")))

            for element in node.iter(NS + "HintPath"):
                hint = (element.text or "").replace("\\", "/")
                if not hint:
                    continue
                if not os.path.isabs(hint):
                    hint = os.path.join(self.project_files_root, hint)
                asm.hint_refs.append(hint)

            for element in node.iter(NS + "ProjectReference"):
                include = element.get("Include") or ""
                dep = include.replace("\\", "/").split("/")[-1]
                if dep.endswith(".csproj"):
                    asm.proj_refs.append(dep[: -len(".csproj")])

            if asm.hint_refs:
                resolved = sum(1 for h in asm.hint_refs if os.path.exists(h))
                asm.stale = (resolved / len(asm.hint_refs)) < STALE_REF_RESOLUTION

            self.assemblies[name] = asm

        if self.is_worktree:
            self._resolve_worktree_sources()
            self._wire_new_asmdefs()

    def _resolve_worktree_sources(self):
        """Sources missing from the worktree are either git-ignored there (symlinked
        tool folders and the like, which only exist in the main checkout: compile the
        main checkout's copy) or deleted in the worktree (drop them, never fall back,
        or a deleted file would be compiled from the main checkout)."""
        missing = {s for asm in self.assemblies.values() for s in asm.sources
                   if not os.path.exists(s)}
        ignored = git_ignored(self.root, missing)
        for asm in self.assemblies.values():
            resolved = []
            for src in asm.sources:
                if src not in missing:
                    resolved.append(src)
                elif src in ignored:
                    resolved.append(os.path.join(self.project_files_root,
                                                 os.path.relpath(src, self.root)))
                    self.borrowed_sources += 1
                else:
                    self.dropped_sources += 1
            asm.sources = resolved

    def _wire_new_asmdefs(self):
        """An .asmdef added in the worktree is missing from the borrowed predefined
        .csproj files, so Assembly-CSharp would fail with false CS0246 errors for its
        types. Unity references every autoReferenced asmdef (the default) from the
        predefined assemblies; an Editor-only one only from the Editor assemblies."""
        for _, data in self._new_worktree_asmdefs():
            name = data.get("name")
            if not name:
                continue
            if name not in self.assemblies:
                self.unbuilt_asmdefs.append(name)
                continue
            if not data.get("autoReferenced", True) or data.get("overrideReferences", False):
                continue
            targets = ["Assembly-CSharp-Editor"]
            if data.get("includePlatforms") != ["Editor"]:
                targets.insert(0, "Assembly-CSharp")
            for target in targets:
                asm = self.assemblies.get(target)
                if asm is not None and name not in asm.proj_refs:
                    asm.proj_refs.append(name)
                    self.added_references.append((target, name))

    def _new_worktree_asmdefs(self):
        """[(path, parsed json)] for .asmdef files in the worktree that the main
        checkout does not have at the same path."""
        found = []
        for dirpath, dirnames, filenames in os.walk(os.path.join(self.root, "Assets")):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for filename in filenames:
                if not filename.endswith(".asmdef"):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, self.root)
                if os.path.exists(os.path.join(self.project_files_root, rel)):
                    continue
                try:
                    with open(path, errors="replace") as fh:
                        found.append((path, json.load(fh)))
                except (OSError, ValueError):
                    continue
        return found

    def missing_asmdef_references(self):
        """[(assembly, referenced assembly)] for every `references` entry of an .asmdef
        changed since Unity last regenerated the project files that its .csproj does not
        list yet. Until Unity regenerates them, the referenced types fail with false
        CS0246 / CS0234 errors. Only changed .asmdef files count: Unity leaves orphaned
        .csproj files (platform-gated assemblies) whose references are never filled in."""
        newest_sync = max(os.path.getmtime(a.csproj) for a in self.assemblies.values())

        def unsynced(path):
            if self.is_worktree:
                synced = os.path.join(self.project_files_root, os.path.relpath(path, self.root))
                try:
                    with open(path, "rb") as mine, open(synced, "rb") as theirs:
                        if mine.read() != theirs.read():
                            return True
                except OSError:
                    return True
                path = synced
            return os.path.getmtime(path) > newest_sync

        asmdefs = []
        by_guid = {}
        for top in ("Assets", "Packages"):
            for dirpath, dirnames, filenames in os.walk(os.path.join(self.root, top)):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for filename in filenames:
                    if not filename.endswith(".asmdef"):
                        continue
                    path = os.path.join(dirpath, filename)
                    try:
                        with open(path, errors="replace") as fh:
                            data = json.load(fh)
                    except (OSError, ValueError):
                        continue
                    asmdefs.append((path, data))
                    guid = _meta_guid(path + ".meta")
                    if guid and data.get("name"):
                        by_guid[guid] = data["name"]

        live = self.live()
        missing = []
        for path, data in asmdefs:
            name = data.get("name")
            if name not in live or not unsynced(path):
                continue
            asm = self.assemblies[name]
            for ref in data.get("references") or []:
                dep = by_guid.get(ref[len("GUID:"):].lower()) if ref.startswith("GUID:") else ref
                if dep in live and dep not in asm.proj_refs:
                    missing.append((name, dep))
        return sorted(set(missing))

    # -- lookups ---------------------------------------------------------

    # -- assembly inference ----------------------------------------------
    #
    # The generated .csproj files only describe what Unity compiles for the *current*
    # build target, and they are only rewritten on refresh — so a file created since
    # the last refresh, or one behind a platform-gated .asmdef, belongs to no project
    # file. Reproducing Unity's own attribution rule covers both cases without needing
    # the editor: nearest ancestor .asmdef wins, otherwise the predefined assemblies.

    def asmdef_dirs(self):
        """realpath(directory) -> assembly name, for every .asmdef under Assets/."""
        if self._asmdefs is None:
            found = {}
            for dirpath, dirnames, filenames in os.walk(os.path.join(self.root, "Assets")):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for filename in filenames:
                    if not filename.endswith(".asmdef"):
                        continue
                    try:
                        with open(os.path.join(dirpath, filename), errors="replace") as fh:
                            name = json.load(fh).get("name")
                    except (OSError, ValueError):
                        continue
                    if name:
                        found[os.path.realpath(dirpath)] = name
            self._asmdefs = found
        return self._asmdefs

    def infer_assembly(self, path):
        """Which assembly Unity would put this file in."""
        mapping = self.asmdef_dirs()
        root = os.path.realpath(self.root)
        current = os.path.dirname(os.path.realpath(path))
        while current.startswith(root):
            if current in mapping:
                return mapping[current]
            if current == root:
                break
            current = os.path.dirname(current)

        rel = os.path.relpath(os.path.realpath(path), root).replace(os.sep, "/")
        segments = rel.split("/")[:-1]
        is_editor = "Editor" in segments
        first_pass = any(rel.startswith("Assets/" + p + "/")
                         for p in ("Plugins", "Standard Assets", "Pro Standard Assets"))
        if first_pass:
            return "Assembly-CSharp-Editor-firstpass" if is_editor else "Assembly-CSharp-firstpass"
        return "Assembly-CSharp-Editor" if is_editor else "Assembly-CSharp"

    def live(self):
        """Assembly names excluding orphaned project files."""
        return {n for n, a in self.assemblies.items() if not a.stale}

    def stale_names(self):
        return sorted(n for n, a in self.assemblies.items() if a.stale)

    def file_to_assemblies(self):
        """Map absolute source path -> [live assembly names]. Built lazily, cached."""
        if self._file_index is None:
            index = {}
            for asm in self.assemblies.values():
                if asm.stale:
                    continue
                for src in asm.sources:
                    index.setdefault(os.path.realpath(src), []).append(asm.name)
            self._file_index = index
        return self._file_index

    def assembly_for(self, path):
        names = self.file_to_assemblies().get(os.path.realpath(path))
        return names[0] if names else None

    def dependents_of(self, names):
        """All assemblies that transitively reference any of `names` (inclusive)."""
        reverse = {}
        for asm in self.assemblies.values():
            if asm.stale:
                continue
            for dep in asm.proj_refs:
                reverse.setdefault(dep, set()).add(asm.name)

        seen = set()
        stack = list(names)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(reverse.get(current, ()))
        return seen

    def build_order(self, names):
        """Topologically sort `names` plus their in-set dependencies."""
        wanted = set(names)
        ordered, visiting, done = [], set(), set()

        def visit(name):
            if name in done or name not in self.assemblies:
                return
            if name in visiting:
                return  # cycle; Unity forbids these, but do not hang on one
            visiting.add(name)
            for dep in self.assemblies[name].proj_refs:
                if dep in wanted:
                    visit(dep)
            visiting.discard(name)
            done.add(name)
            ordered.append(name)

        for name in sorted(wanted):
            visit(name)
        return ordered


def changed_files(root, base=None):
    """Source files changed vs `base` (default: working tree + staged + untracked)."""

    def run(args):
        result = subprocess.run(
            ["git", "-C", root] + args, capture_output=True, text=True
        )
        return result.stdout.splitlines() if result.returncode == 0 else []

    paths = set()
    if base:
        paths.update(run(["diff", "--name-only", base]))
    else:
        paths.update(run(["diff", "--name-only", "HEAD"]))
        paths.update(run(["ls-files", "--others", "--exclude-standard"]))

    return [
        os.path.join(root, p)
        for p in paths
        if p.endswith(".cs") and os.path.exists(os.path.join(root, p))
    ]
