"""Generate an editable Mermaid class diagram from C# declarations."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unity-tools"))
from _csparse import (
    PRIMITIVE_TYPES, SourceParser, _find_close_paren, _split_top_level, blank_literals,
)


ANNOTATIONS = {"interface": "interface", "struct": "struct", "enum": "enumeration"}
TYPE_PART = re.compile(r"@?([A-Za-z_]\w*)\s*(?:<(.*)>)?", re.DOTALL)


def declaration_lines(source, line_map=None):
    """Give the line-oriented parser boundaries for compact C# declarations."""
    clean = blank_literals(source)
    boundaries = {0, len(source)}
    paren = square = 0
    for index, char in enumerate(clean):
        if char == "(":
            paren += 1
        elif char == ")":
            paren -= 1
        elif char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif not (paren or square):
            if char in "{};":
                boundaries.add(index + 1)
            if char == "}":
                boundaries.add(index)
    # Split the masked source so an inserted newline cannot extend a line comment
    # or alter how a second pass handles literals.
    positions = sorted(boundaries)
    parts = [clean[start:end] for start, end in zip(positions, positions[1:])]
    if line_map is not None:
        line = 1
        for part in parts:
            count = part.count("\n")
            line_map.extend(range(line, line + count + 1))
            line += count
    return "\n".join(parts)


def scan(source, *, allow_empty=False, paths=None):
    def fail(error):
        raise error

    declarations = defaultdict(list)
    parser = SourceParser()
    for folder, dirs, files in os.walk(source, onerror=fail):
        dirs.sort()
        for name in sorted(files):
            if not name.endswith(".cs"):
                continue
            path = Path(folder) / name
            try:
                if not path.is_file():
                    raise ValueError("Expected a regular file.")
                contents = path.read_text(encoding="utf-8-sig")
            except (OSError, ValueError) as error:
                raise ValueError(f"Cannot read C# source {path}: {error}") from error
            line_map = [] if paths is not None else None
            for decl in parser.parse(path, declaration_lines(contents, line_map)):
                namespace = tuple((part, 0) for part in decl.namespace.split(".") if part)
                key = namespace + decl.containing_types + ((decl.name, decl.arity),)
                declarations[key].append(decl)
                if paths is not None:
                    paths[decl] = (path, line_map[decl.line - 1])
    if not declarations and not allow_empty:
        raise ValueError(f"No supported C# type declarations in {source}")
    return declarations


def class_ids(declarations):
    counts = Counter(key[-1][0] for key in declarations)
    ids, used = {}, set()
    for key in sorted(declarations, key=lambda key: (counts[key[-1][0]] != 1, key)):
        parts = key if counts[key[-1][0]] > 1 else key[-1:]
        name = "_".join(f"{part}_{arity}" if arity else part for part, arity in parts)
        name = re.sub(r"[^A-Za-z0-9_]", "_", name)
        candidate, suffix = name, 2
        while candidate in used:
            candidate = f"{name}_{suffix}"
            suffix += 1
        ids[key] = candidate
        used.add(candidate)
    return ids


def type_references(raw):
    """Yield qualified type paths and the types inside generic arguments or tuples."""
    raw = re.sub(r"^(?:(?:ref|readonly|scoped)\s+)+", "", raw.strip())
    raw = re.sub(r"(?:\s*(?:\?|\*|\[[,\s]*\]))+$", "", raw)
    if raw.startswith("("):
        close = _find_close_paren(raw, 0)
        if close > 0:
            for element in _split_top_level(raw[1:close]):
                element = re.sub(r"\s+@?[A-Za-z_]\w*$", "", element)
                yield from type_references(element)
        return
    # A primary constructor can supply arguments to its base class.
    raw = re.sub(r"\s*\(.*\)$", "", raw)
    absolute = raw.startswith("global::")
    if absolute:
        raw = raw[len("global::"):]
    if raw in PRIMITIVE_TYPES:
        return
    path, arguments = [], []
    for part in _split_top_level(raw, sep="."):
        match = TYPE_PART.fullmatch(part)
        if not match:
            return
        args = _split_top_level(match[2] or "")
        path.append((match[1], len(args)))
        arguments.extend(args)
    if path:
        yield tuple(path), absolute
    for argument in arguments:
        yield from type_references(argument)


def render(declarations):
    ids = class_ids(declarations)
    simple = defaultdict(list)
    for key in ids:
        simple[key[-1]].append(key)

    def resolve(owner, reference, absolute, parameters):
        if absolute:
            return reference if reference in ids else None
        if len(reference) == 1 and reference[0][0] in parameters:
            return None
        for length in range(len(owner), -1, -1):
            candidate = owner[:length] + reference
            if candidate in ids:
                return candidate
        matches = simple[reference[0]] if len(reference) == 1 else []
        if len(matches) == 1:
            return matches[0]
        return None

    lines, edges = ["classDiagram"], set()
    for key in sorted(ids):
        name, members = ids[key], set()
        kind = declarations[key][0].kind
        for decl in declarations[key]:
            parameters = {
                parameter
                for length in range(1, len(key) + 1)
                for scope in declarations.get(key[:length], ())
                for parameter in scope.generic_parameters
            }
            for _, raw in decl.bases:
                for index, (reference, absolute) in enumerate(type_references(raw)):
                    target = resolve(key, reference, absolute, parameters)
                    if target is None:
                        continue
                    target_kind = declarations[target][0].kind
                    arrow = "..>" if index else "--|>"
                    if index == 0 and target_kind == "interface" and kind != "interface":
                        arrow = "..|>"
                    if kind != "enum":
                        edges.add((name, arrow, ids[target]))
            for member in decl.members:
                # Mermaid's editor reserves braces, semicolons and comment markers.
                signature = re.sub(r"[{};]", "", member.header).replace("%%", "% %").strip()
                if signature:
                    members.add(signature)
                arrow = "o--" if member.kind in ("field", "property") else "..>"
                for raw in member.declared_types or ():
                    for reference, absolute in type_references(raw):
                        target = resolve(key, reference, absolute,
                                         parameters.union(member.generic_parameters))
                        if target is not None:
                            edges.add((name, arrow, ids[target]))
        annotation = ANNOTATIONS.get(kind)
        if members or annotation:
            lines.append(f"    class {name} {{")
            if annotation:
                lines.append(f"        <<{annotation}>>")
            lines.extend(f"        {member}" for member in sorted(members))
            lines.append("    }")
        else:
            lines.append(f"    class {name}")
    lines.extend(f"    {left} {arrow} {right}" for left, arrow, right in sorted(edges))
    return "\n".join(lines) + "\n"


def dated_output(directory, name):
    date = datetime.now(timezone.utc).strftime("%d_%m_%y")
    return directory / f"{name}_{date}.mmd"


def write_diagram(output, diagram):
    try:
        with output.open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(diagram)
    except FileExistsError:
        raise ValueError(f"Output already exists: {output}") from None
    return output


def create(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"Expected an existing destination directory: {directory}")
    name = Path(os.path.abspath(directory)).name or "ClassDiagram"
    return write_diagram(dated_output(directory, name), "classDiagram\n")


def generate(source, output):
    source = Path(source)
    if not source.is_dir():
        raise ValueError(f"Expected a C# source directory: {source}")
    output = Path(output)
    if output.is_dir():
        output = dated_output(output, Path(os.path.abspath(source)).name)
    if not output.parent.is_dir():
        raise ValueError(f"Output parent directory does not exist: {output.parent}")
    if os.path.lexists(output):
        raise ValueError(f"Output already exists: {output}")
    return write_diagram(output, render(scan(source)))
