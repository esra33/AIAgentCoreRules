#!/usr/bin/env python3
"""
Type check Unity assemblies without opening the editor.

Compiles from the generated .csproj files using the Roslyn that ships inside the
matching Unity install, and prints only errors plus a one-line result per assembly.

Why this exists: verifying a cross-assembly refactor otherwise means launching Unity
and reading a multi-megabyte Editor.log. This turns that into a few seconds and a
handful of lines.

Usage
  typecheck.py --changed              # assemblies touched by your working tree, plus
                                      # everything that references them  (default)
  typecheck.py Assembly-CSharp        # named assemblies and their dependencies
  typecheck.py --all                  # every assembly in the project
  typecheck.py --changed --base develop
  typecheck.py --list                 # show what would be compiled, compile nothing
  typecheck.py --files Assets/Scripts/Foo.cs   # the assemblies these files belong to, plus
                                      # their dependents, whether or not the files changed
  typecheck.py --include-new          # also compile new .cs files Unity has not added to a .csproj yet
  typecheck.py Assembly-CSharp-Editor --define USING_TOOLS   # code behind a define that is off

Options
  --project PATH   Unity project root (default: walk up from cwd)
  --verbose        Show warnings and the full compiler output
  --jobs N         Parallel compiles within a dependency level (default 4)
  --define SYMBOL  Extra preprocessor symbol for every compiled assembly (repeatable)
  --include-new    Attach changed .cs files that no .csproj lists yet to the assembly
                   Unity would put them in (nearest .asmdef, else the predefined ones)

Exit code is the number of assemblies that failed, so it works in a hook or CI step.

Notes
  - Reads Library/ScriptAssemblies for dependencies that are not being rebuilt, so a
    stale Library only matters for assemblies you did not ask for.
  - Safe to run while the Unity editor is open; nothing is written into the project.
  - Requires the .csproj files to exist. If you added or deleted a .cs file, let Unity
    refresh once first or the new file will not be compiled — or pass --include-new.
  - Code inside #if SYMBOL is compiled out unless the .csproj defines SYMBOL, and the
    check still reports clean. Pass --define SYMBOL for code behind a define that is off.
  - In a git worktree, run it from inside the worktree without --project. It compiles the
    worktree's sources against the main checkout's .csproj files and Library/, and
    implies --include-new. --project naming another checkout compiles that checkout's
    files, not yours; the script warns when it does.
  - An .asmdef added in a worktree is wired into Assembly-CSharp(-Editor) when it is
    autoReferenced and the main checkout has its .csproj; with no .csproj it cannot be
    compiled, and the script warns so its CS0246 errors are not taken for real ones.
  - A references entry added to an existing .asmdef is not in its .csproj until Unity
    regenerates the project files (worktree or main checkout). The script warns naming
    the pair; CS0246/CS0234 errors for the referenced types are false until then.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _unityproj import (  # noqa: E402
    Project, ProjectError, changed_files, find_compiler, find_project_root, main_checkout_of,
)

BASE_FLAGS = [
    "-target:library",
    "-nostdlib+",
    "-noconfig",
    "-langversion:9.0",
    "-deterministic",
    "-nowarn:0169,0649,CS1701,CS1702",
]


def compile_assembly(asm, project, outdir, dotnet, csc, verbose):
    """Compile one assembly. Returns (name, ok, [diagnostic lines])."""
    refs = []
    for hint in asm.hint_refs:
        if os.path.exists(hint):
            refs.append(hint)

    prebuilt_dir = os.path.join(project.project_files_root, "Library", "ScriptAssemblies")
    missing = []
    for dep in asm.proj_refs:
        fresh = os.path.join(outdir, dep + ".dll")
        stale = os.path.join(prebuilt_dir, dep + ".dll")
        if os.path.exists(fresh):
            refs.append(fresh)
        elif os.path.exists(stale):
            refs.append(stale)
        else:
            missing.append(dep)

    rsp_path = os.path.join(outdir, asm.name + ".rsp")
    with open(rsp_path, "w") as rsp:
        rsp.write(" ".join(BASE_FLAGS) + "\n")
        rsp.write('-out:"%s"\n' % os.path.join(outdir, asm.name + ".dll"))
        if asm.defines:
            rsp.write("-define:%s\n" % asm.defines)
        for ref in sorted(set(refs)):
            rsp.write('-r:"%s"\n' % ref)
        for src in asm.sources:
            rsp.write('"%s"\n' % src)

    result = subprocess.run(
        [dotnet, csc, "@" + rsp_path], capture_output=True, text=True, cwd=project.root
    )
    output = result.stdout + result.stderr

    keep = ": error " if not verbose else ": error "
    lines = sorted({l.strip() for l in output.splitlines() if keep in l})
    if verbose:
        lines += sorted({l.strip() for l in output.splitlines() if ": warning " in l})

    notes = []
    if missing and (lines or verbose):
        notes.append(
            "unresolved references (not built, not in Library/ScriptAssemblies): "
            + ", ".join(sorted(missing))
        )

    errors = [l for l in lines if ": error " in l]
    return asm.name, not errors, notes + lines


def warn_if_other_checkout(root):
    """--project pointing at a different checkout than the cwd compiles that checkout's
    files, not the ones being edited, and still reports clean. Say so up front."""
    try:
        here = find_project_root()
    except ProjectError:
        return
    if os.path.realpath(here) != os.path.realpath(root):
        print("warning: --project is %s, but you are in %s.\n"
              "         Compiling %s's files, NOT the working copy you are in. Run without\n"
              "         --project from inside the checkout you edited."
              % (root, here, os.path.basename(root)), file=sys.stderr)


def attach_new_files(project, files):
    """Add changed .cs files that no .csproj lists yet to the assembly Unity would put
    them in. Returns [(path, assembly name)] for every file attached."""
    known = project.file_to_assemblies()
    added = []
    for path in files:
        real = os.path.realpath(path)
        if real in known:
            continue
        name = project.infer_assembly(path)
        asm = project.assemblies.get(name)
        if asm is None:
            continue
        asm.sources.append(real)
        known[real] = [name]  # keeps the --changed lookup below consistent
        added.append((path, name))
    return added


def main():
    parser = argparse.ArgumentParser(add_help=True, description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("assemblies", nargs="*", help="assembly names to check")
    parser.add_argument("--project", default=None)
    parser.add_argument("--changed", action="store_true",
                        help="derive assemblies from git changes plus their dependents")
    parser.add_argument("--base", default=None, help="git ref to diff against")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--define", action="append", default=[],
                        help="extra preprocessor symbol for every compiled assembly (repeatable)")
    parser.add_argument("--include-new", action="store_true",
                        help="compile changed .cs files that no .csproj lists yet")
    parser.add_argument("--files", nargs="+", default=[], metavar="PATH",
                        help="check the assemblies these .cs files belong to (inferred for a file no "
                             ".csproj lists) plus their dependents; the session baseline hook uses it")
    args = parser.parse_args()

    try:
        root = os.path.abspath(args.project) if args.project else find_project_root()
        warn_if_other_checkout(root)
        main_checkout = main_checkout_of(root)
        project = Project(root, main_checkout)
        dotnet, csc = find_compiler(root)
    except ProjectError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if project.is_worktree:
        print("Worktree: compiling sources from %s\n"
              "          with .csproj files and Library/ from the main checkout %s"
              % (root, main_checkout))
        if project.borrowed_sources or project.dropped_sources:
            print("          %d git-ignored source(s) taken from the main checkout, "
                  "%d deleted in this worktree skipped"
                  % (project.borrowed_sources, project.dropped_sources))
        for target, name in project.added_references:
            print("          new asmdef %s referenced from %s (missing from the borrowed .csproj)"
                  % (name, target))
        if project.unbuilt_asmdefs:
            print("warning: new asmdef(s) with no .csproj in the main checkout: %s\n"
                  "         Their sources are not compiled, so CS0246 errors for their types\n"
                  "         are not real. Let Unity refresh the main checkout on this branch to verify."
                  % ", ".join(sorted(project.unbuilt_asmdefs)), file=sys.stderr)
        # The borrowed .csproj files cannot list files added in this worktree.
        args.include_new = True

    stale_refs = project.missing_asmdef_references()
    if stale_refs:
        print("warning: .asmdef reference(s) not in the .csproj yet: %s\n"
              "         CS0246/CS0234 errors in those assemblies for the referenced types are\n"
              "         not real. Let Unity regenerate the project files to verify."
              % ", ".join("%s -> %s" % pair for pair in stale_refs), file=sys.stderr)

    if args.define:
        for asm in project.assemblies.values():
            asm.defines = ";".join([d for d in [asm.defines] if d] + args.define)
        print("Extra defines: %s" % ", ".join(args.define))

    if args.include_new:
        for path, name in attach_new_files(project, changed_files(root, args.base)):
            print("Including new file %s -> %s" % (os.path.relpath(path, root), name))

    # Decide what to check. Default to --changed when nothing else is asked for.
    if args.all:
        targets = project.live()
        why = "all assemblies"
    elif args.assemblies:
        unknown = [a for a in args.assemblies if a not in project.assemblies]
        if unknown:
            print("error: unknown assembly: %s" % ", ".join(unknown), file=sys.stderr)
            print("hint: run with --list to see the available names", file=sys.stderr)
            return 2
        targets = project.dependents_of(args.assemblies)
        why = "%s + %d dependents" % (", ".join(args.assemblies), len(targets) - len(args.assemblies))
    elif args.files:
        named = {project.assembly_for(os.path.abspath(f)) or project.infer_assembly(os.path.abspath(f))
                 for f in args.files}
        named = {n for n in named if n in project.assemblies}
        if not named:
            print("None of the %d file(s) belong to a known assembly. Nothing to check." % len(args.files))
            return 0
        targets = project.dependents_of(named)
        why = "%d file(s) -> %s + dependents" % (len(args.files), ", ".join(sorted(named)))
    else:
        files = changed_files(root, args.base)
        if not files:
            print("No changed .cs files%s. Nothing to check." %
                  (" vs %s" % args.base if args.base else ""))
            return 0
        direct = {a for f in files for a in project.file_to_assemblies().get(os.path.realpath(f), [])}
        orphans = [f for f in files
                   if not project.file_to_assemblies().get(os.path.realpath(f))]
        if not direct:
            print("%d changed .cs file(s) but none belong to a generated .csproj.\n"
                  "Let Unity refresh so it regenerates the project files, then retry."
                  % len(files))
            return 0
        targets = project.dependents_of(direct)
        why = "%d changed file(s) -> %d assembl%s + dependents" % (
            len(files), len(direct), "y" if len(direct) == 1 else "ies")
        if orphans:
            why += " (%d file(s) not in any .csproj — Unity refresh needed)" % len(orphans)

    targets &= project.live()
    order = project.build_order(targets)

    orphaned = project.stale_names()
    if orphaned and args.verbose:
        print("Ignoring %d orphaned .csproj left over from an older assembly layout: %s"
              % (len(orphaned), ", ".join(orphaned)))

    if args.list:
        print("Would check %d assembl%s (%s):" %
              (len(order), "y" if len(order) == 1 else "ies", why))
        for name in order:
            print("  %-55s %d sources" % (name, len(project.assemblies[name].sources)))
        return 0

    print("Checking %d assembl%s (%s)" %
          (len(order), "y" if len(order) == 1 else "ies", why))

    outdir = tempfile.mkdtemp(prefix="unity-typecheck-")
    failed, checked = [], 0
    try:
        # Assemblies at the same depth have no ordering constraint between them, but
        # a dependency must exist on disk before its dependents compile. Walking the
        # topological order in levels keeps that guarantee while still parallelising.
        remaining = list(order)
        done, broken, skipped = set(), set(), []
        while remaining:
            level = [n for n in remaining
                     if all(d in done or d not in targets
                            for d in project.assemblies[n].proj_refs)]
            if not level:
                level = remaining[:1]  # cycle guard

            # If a dependency we were asked to check failed, its DLL was never produced
            # and this assembly would silently compile against the stale copy in
            # Library/ScriptAssemblies — reporting a pass that means nothing. Skip it.
            blocked = [n for n in level
                       if any(d in broken for d in project.assemblies[n].proj_refs)]
            for name in blocked:
                cause = sorted(set(project.assemblies[name].proj_refs) & broken)
                print("  skip  %-50s depends on failed %s" % (name, ", ".join(cause)))
                skipped.append(name)
                broken.add(name)
                done.add(name)
            level = [n for n in level if n not in blocked]
            if not level:
                remaining = [n for n in remaining if n not in done]
                continue

            with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
                results = list(pool.map(
                    lambda n: compile_assembly(project.assemblies[n], project, outdir,
                                               dotnet, csc, args.verbose),
                    level))

            for name, ok, lines in results:
                checked += 1
                count = len(project.assemblies[name].sources)
                if ok and not lines:
                    print("  ok    %-50s %5d sources" % (name, count))
                elif ok:
                    print("  ok    %-50s %5d sources" % (name, count))
                    for line in lines:
                        print("          %s" % line)
                else:
                    errs = [l for l in lines if ": error " in l]
                    print("  FAIL  %-50s %5d sources  %d error(s)" % (name, count, len(errs)))
                    for line in lines:
                        print("          %s" % line)
                    failed.append(name)
                    broken.add(name)

            done.update(level)
            remaining = [n for n in remaining if n not in done]
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    print()
    if failed:
        print("FAILED: %s" % ", ".join(failed))
        if skipped:
            print("SKIPPED (unverified, dependency failed): %s" % ", ".join(skipped))
        print("%d checked, %d failed, %d skipped." % (checked, len(failed), len(skipped)))
    else:
        print("All %d assembl%s type check clean." %
              (checked, "y" if checked == 1 else "ies"))
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
