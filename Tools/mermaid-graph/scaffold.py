"""Preview and create Unity C# scaffolds from Mermaid class diagrams."""

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re

from diagram import ANNOTATION, ID, KINDS, parse
from generator import PRIMITIVE_TYPES, scan

KEYWORDS = set("""abstract as base bool break byte case catch char checked class const
continue decimal default delegate do double else enum event explicit extern false finally
fixed float for foreach goto if implicit in int interface internal is lock long namespace
new null object operator out override params private protected public readonly ref return
sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof
uint ulong unchecked unsafe ushort using virtual void volatile while""".split())
QUALIFIED = rf"{ID}(?:\.{ID})*"
TYPE = rf"(?:global::)?{QUALIFIED}(?:\[\])?"
METHOD = re.compile(rf"(?:\+(?P<mermaid>{ID})\((?P<args>[^()]*)\)(?:\s+(?P<result>{TYPE}))?|"
                    rf"(?:public\s+)?(?P<cs_result>{TYPE})\s+(?P<cs>{ID})\((?P<cs_args>[^()]*)\))")
FIELD = re.compile(rf"(?:\+|public\s+)(?P<type>{TYPE})\s+(?P<name>{ID})")


def valid_name(name):
    return bool(re.fullmatch(ID, name)) and name not in KEYWORDS


@dataclass
class Type:
    name: str
    qualified: str
    kind: str
    declarations: list = field(default_factory=list)
    members: dict = field(default_factory=dict)
    bases: list = field(default_factory=list)

    @property
    def reference(self):
        return "global::" + self.qualified


def source_roots(root):
    yield root / "Assets"
    packages = root / "Packages"
    if packages.is_dir():
        yield from sorted(path for path in packages.iterdir() if path.is_dir())


def context(root, destination):
    destination = destination.resolve()
    candidates = (destination, *destination.parents)
    root = root.resolve() if root else next(
        (path for path in candidates
         if (path / "Assets").is_dir() and (path / "ProjectSettings").is_dir()), None)
    if root is None or not (root / "ProjectSettings").is_dir() or not (
            root / "Assets").is_dir() or not destination.is_relative_to(root / "Assets"):
        raise ValueError("Expected an output directory under a Unity project's Assets/.")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Expected an output directory: {destination}")
    return root, destination


class Scaffold:
    def __init__(self, root, destination, namespace, assembly):
        self.destination = destination
        self.namespace = namespace
        self.assembly = assembly
        self.index = defaultdict(list)
        self.paths = {}
        self.qualified = defaultdict(list)
        self.assemblies = {}
        self.dependencies = set()
        self.types = {}
        self.gaps = []
        self.status = []
        for source in source_roots(root):
            for key, declarations in scan(source, allow_empty=True, paths=self.paths).items():
                name = ".".join(part for part, _ in key)
                item = Type(key[-1][0], name, declarations[0].kind, declarations)
                self.index[item.name].append(item)
                if not any(arity for _, arity in key):
                    self.qualified[name].append(item)
            for path in sorted([*source.rglob("*.asmdef"), *source.rglob("*.asmref")]):
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if path.parent in self.assemblies:
                    raise ValueError(f"Multiple assembly assets in {path.parent}")
                self.assemblies[path.parent] = (path, data)
        self.assembly_names = {}
        for path, data in self.assemblies.values():
            if path.suffix == ".asmdef":
                name = data["name"]
                if name in self.assembly_names:
                    raise ValueError(f"Duplicate assembly name: {name}")
                self.assembly_names[name] = (path, data)

    def assembly_at(self, folder):
        for ancestor in (folder, *folder.parents):
            if ancestor in self.assemblies:
                path, data = self.assemblies[ancestor]
                if path.suffix == ".asmdef":
                    return data["name"]
                name = data.get("reference", "")
                if name.startswith("GUID:"):
                    for assembly_name, (definition, _) in self.assembly_names.items():
                        meta = definition.with_suffix(".asmdef.meta")
                        if meta.is_file() and re.search(
                                rf"^guid: {re.escape(name[5:])}$", meta.read_text(), re.M):
                            return assembly_name
                if name in self.assembly_names:
                    return name
                raise ValueError(f"Cannot resolve assembly reference {path}")
        return None

    def lookup(self, name, *, namespace=None):
        namespace = namespace or self.namespace
        matches = (self.qualified.get(name, []) if "." in name else
                   self.qualified.get(f"{namespace}.{name}", []) or self.index.get(name, []))
        if len(matches) > 1:
            paths = sorted({str(self.paths[decl][0]) for item in matches for decl in item.declarations})
            raise ValueError(f"Ambiguous type {name}: {', '.join(paths)}")
        return matches[0] if matches else None

    def use(self, item, *, public=False):
        for decl in item.declarations:
            if (decl.containing_types or decl.generic_parameters
                    or decl.access not in (None, "public", "internal") or decl.is_static):
                raise ValueError(f"Unsupported or inaccessible type {item.qualified}")
            if public and decl.access != "public":
                raise ValueError(f"Public API cannot expose {item.qualified}")
            assembly = self.assembly_at(self.paths[decl][0].parent)
            if assembly != self.target_assembly:
                if decl.access != "public":
                    raise ValueError(f"Inaccessible cross-assembly type {item.qualified}")
                if assembly is None:
                    raise ValueError(f"{item.qualified} lives in a predefined Unity assembly")
                if self.target_assembly is None and not self.assembly_names[assembly][1].get(
                        "autoReferenced", True):
                    raise ValueError(f"Predefined Unity assemblies cannot reference {assembly}")
                self.dependencies.add(assembly)
        return item.reference

    def resolve(self, name):
        raw = name.removesuffix("[]")
        bare = raw.removeprefix("global::")
        suffix = name[len(raw):]
        if bare in PRIMITIVE_TYPES - {"var"}:
            if bare == "void" and suffix:
                raise ValueError("void[] is invalid")
            return bare + suffix
        item = self.types.get(bare) or self.lookup(bare)
        if not item:
            raise ValueError(f"Unresolved type {bare}")
        return self.use(item, public=True) + suffix

    def member(self, item, raw):
        if annotation := re.fullmatch(ANNOTATION, raw):
            if annotation["annotation"].lower() not in KINDS:
                raise ValueError(f"Unsupported annotation {raw}")
            return
        if item.kind == "enum" and valid_name(raw):
            key, declaration = (raw, None), raw
        elif item.kind != "enum" and (method := METHOD.fullmatch(raw)):
            name = method["mermaid"] or method["cs"]
            result = self.resolve(method["result"] or method["cs_result"] or "void")
            args = []
            names = set()
            for arg in (method["args"] or method["cs_args"] or "").split(","):
                if not arg.strip() and not (method["args"] or method["cs_args"] or "").strip():
                    continue
                pieces = arg.split()
                if len(pieces) != 2 or not valid_name(pieces[1]) or pieces[1] in names:
                    raise ValueError(f"Expected a typed parameter with a unique name: {arg}")
                param_type = self.resolve(pieces[0])
                if param_type == "void":
                    raise ValueError("Parameters cannot have type void")
                names.add(pieces[1])
                args.append((param_type, pieces[1]))
            if not valid_name(name) or name == item.name:
                raise ValueError(f"Invalid method name {name}")
            key = (name, tuple(arg[0] for arg in args))
            declaration = f"{result} {name}({', '.join(' '.join(arg) for arg in args)})"
        elif item.kind in ("class", "struct") and (match := FIELD.fullmatch(raw)):
            name = match["name"]
            kind = self.resolve(match["type"])
            if not valid_name(name) or name == item.name or kind == "void":
                raise ValueError(f"Invalid field {raw}")
            key, declaration = (name, None), f"public {kind} {name};"
        else:
            raise ValueError(f"Unsupported member {raw}")
        if key in item.members and item.members[key] != declaration:
            raise ValueError(f"Conflicting member {raw}")
        if any(old[0] == key[0] and (old[1] is None or key[1] is None) and old != key
               for old in item.members):
            raise ValueError(f"Conflicting member {raw}")
        item.members[key] = declaration

    def existing_members(self, item):
        return [member for decl in item.declarations for member in decl.members]

    def existing_headers(self, item):
        return {re.sub(r"\s+", "", member.header)
                for member in self.existing_members(item)}

    def location(self, item):
        return ", ".join(f"{path}:{line}" for path, line in
                         (self.paths[decl] for decl in item.declarations))

    def check_existing(self, item, raw, line):
        if re.fullmatch(ANNOTATION, raw):
            return
        candidate = Type(item.name, item.qualified, item.kind)
        saved = self.dependencies.copy()
        try:
            self.member(candidate, raw)
        except ValueError:
            normalized = re.sub(r"\s+", "", raw)
            if normalized in self.existing_headers(item):
                return
        finally:
            self.dependencies = saved
        for (name, parameters), declaration in candidate.members.items():
            if parameters is None:
                match = FIELD.fullmatch(raw)
                if any(member.name == name and
                       (item.kind == "enum" or (match and member.kind == "field"
                        and match["type"] in member.declared_types and member.access == "public"))
                       for member in self.existing_members(item)):
                    return
            elif any(self.method_signature(member.header, item) ==
                     self.rendered_signature(declaration)
                     for member in self.existing_members(item)
                     if member.access == "public" or item.kind == "interface"):
                return
        self.gaps.append(f"line {line}: Check member {item.name}.{raw} at {self.location(item)}")

    @staticmethod
    def rendered_signature(declaration):
        header, params = declaration[:-1].split("(", 1)
        result, name = header.split()
        return name, result, tuple(part.split()[0] for part in params.split(",") if part.strip())

    def method_signature(self, header, owner):
        header = re.sub(r"^(?:(?:public|protected|internal|abstract|override|virtual|new)\s+)+",
                        "", header.strip())
        match = METHOD.fullmatch(header)
        if not match:
            return None
        namespace = owner.qualified.rpartition(".")[0]

        def qualify(raw):
            name = raw.removesuffix("[]")
            bare = name.removeprefix("global::")
            item = self.types.get(bare) if namespace == self.namespace else None
            item = item or self.lookup(bare, namespace=namespace)
            return (item.reference + raw[len(name):]) if item else raw

        args = (match["cs_args"] or match["args"] or "").strip()
        return (match["cs"] or match["mermaid"],
                qualify(match["cs_result"] or match["result"] or "void"),
                tuple(qualify(arg.split()[0]) for arg in args.split(",")) if args else ())

    def existing_bases(self, item):
        namespace = item.qualified.rpartition(".")[0]
        for decl in item.declarations:
            for _, raw in decl.bases:
                yield raw, self.lookup(raw.removeprefix("global::"), namespace=namespace)

    def edge(self, edge):
        left, right = (self.types[edge[side]] for side in ("left", "right"))
        kind, direction = edge["kind"], edge["direction"]
        structural = kind in ("composition", "aggregation")
        target_side = "right" if (direction == "left") == structural else "left"
        owner, target = (left, right) if target_side == "right" else (right, left)
        description = f"{kind} {owner.name} -> {target.name}"
        line = edge["startLine"]
        if kind == "dependency":
            self.gaps.append(f"line {line}: Manual dependency {owner.name} -> {target.name}")
            return
        base = kind in ("inheritance", "realization")
        if base:
            valid = ((kind == "realization" and owner.kind in ("class", "struct")
                      and target.kind == "interface") or
                     (kind == "inheritance" and owner.kind == target.kind
                      and owner.kind in ("class", "interface")))
            if not valid:
                raise ValueError(f"Incompatible type kinds for {description}")
        else:
            if owner.kind not in ("class", "struct"):
                raise ValueError(f"{owner.kind} cannot hold a relationship field")
            multiplicity = edge[f"{target_side}Multiplicity"]
            if multiplicity not in ("", "1", "0..1", "*", "0..*", "1..*"):
                raise ValueError(f"Unsupported target multiplicity {multiplicity}")
            many = multiplicity in ("*", "0..*", "1..*")
            label = edge["label"]
            name = label if valid_name(label) else "_" + target.name[0].lower() + target.name[1:]
            if name == owner.name:
                raise ValueError(f"Relationship field conflicts with type {name}")
        if owner.declarations:
            if base:
                present = any(match is target for _, match in self.existing_bases(owner))
            else:
                expected = {target.name, target.qualified, target.reference}
                def matches(raw):
                    if many:
                        match = re.fullmatch(
                            r"(?:global::)?(?:System\.Collections\.Generic\.)?List<(.+)>",
                            raw.replace(" ", ""))
                        return bool(match and match[1] in expected)
                    return raw in expected

                present = any(member.kind == "field" and member.name == name
                              and any(matches(raw) for raw in member.declared_types)
                              for member in self.existing_members(owner))
            if not present:
                self.gaps.append(f"line {line}: Missing {description} at {self.location(owner)}")
            return
        reference = self.use(target, public=base)
        if base:
            if any(decl.is_sealed for decl in target.declarations):
                raise ValueError(f"Cannot inherit sealed type {target.name}")
            if all(base is not target for base in owner.bases):
                owner.bases.append(target)
            self.status.append(description)
            return
        field_type = f"global::System.Collections.Generic.List<{reference}>" if many else reference
        key = (name, None)
        public = owner.members.get(key)
        if public == f"public {field_type} {name};":
            if many:
                owner.members[key] = (f"public {field_type} {name} = new {field_type}();"
                                      if owner.kind == "class" else public)
        else:
            initializer = f" = new {field_type}()" if many and owner.kind == "class" else ""
            declaration = f"private {field_type} {name}{initializer};"
            if any(old[0] == name for old in owner.members) and public != declaration:
                raise ValueError(f"Conflicting relationship field {owner.name}.{name}")
            owner.members[key] = declaration
        self.status.append(f"{description} via {owner.name}.{name}")

    def contracts(self, item, active=()):
        if item.qualified in active:
            raise ValueError(f"Inheritance cycle involving {item.qualified}")
        required = {}
        available = set()
        if item.declarations:
            bases = []
            for raw, base in self.existing_bases(item):
                if base is None:
                    raise ValueError(f"Cannot validate inherited contract {item.qualified}: {raw}")
                bases.append(base)
            for member in self.existing_members(item):
                if member.kind == "ctor" or member.is_static:
                    continue
                if item.kind == "interface" or member.is_abstract:
                    signature = self.method_signature(member.header, item)
                    header = member.header.strip()
                    if signature is None or (item.kind != "interface" and
                                             not re.match(r"(public|protected)\s+", header)):
                        raise ValueError(f"Unsupported abstract member {item.qualified}.{member.name}")
                    required[signature] = ("public" if item.kind == "interface" else
                                           header.split()[0] + " override")
                elif member.kind == "method" and (member.access == "public" or member.is_override):
                    available.add(self.method_signature(member.header, item))
        else:
            bases = item.bases
            if item.kind == "interface":
                required.update((self.rendered_signature(value), "public")
                                for (_, params), value in item.members.items() if params is not None)
        for base in bases:
            inherited, concrete = self.contracts(base, (*active, item.qualified))
            for signature, modifier in inherited.items():
                if signature not in required or "override" in modifier:
                    required[signature] = modifier
            available.update(concrete)
        if active and not item.declarations and item.kind == "class":
            available.update(self.rendered_signature(value)
                             for (_, params), value in item.members.items() if params is not None)
        return {key: value for key, value in required.items() if key not in available}, available

    def render(self, item):
        classes = [base for base in item.bases if base.kind == "class"]
        if len(classes) > 1:
            raise ValueError(f"{item.name} has multiple base classes")
        for base in classes:
            constructors = [m for m in self.existing_members(base) if m.kind == "ctor"]
            if constructors and not any(
                    m.access in ("public", "protected", "protected internal") and
                    re.search(r"\(\s*\)$", m.header) for m in constructors):
                raise ValueError(f"No supported accessible parameterless constructor on {base.name}")
        required, _ = self.contracts(item)
        methods = {self.rendered_signature(value) for (_, params), value in item.members.items()
                   if params is not None}
        if item.kind != "interface":
            missing = sorted(required.keys() - methods)
            if missing:
                names = ", ".join(name for name, _, _ in missing)
                raise ValueError(f"{item.name} needs diagram methods for inherited contracts: {names}")
        references = [base.reference for base in classes + [b for b in item.bases if b.kind != "class"]]
        suffix = " : " + ", ".join(references) if references else ""
        lines = [f"namespace {self.namespace}", "{", f"    public {item.kind} {item.name}{suffix}", "    {"]
        for (_, params), value in item.members.items():
            if item.kind == "enum":
                lines.append(f"        {value},")
            elif params is None:
                lines.append(f"        {value}")
            elif item.kind == "interface":
                lines.append(f"        {value};")
            else:
                modifier = required.get(self.rendered_signature(value), "public")
                lines.extend((f"        {modifier} {value}", "        {",
                              "            throw new global::System.NotImplementedException();",
                              "        }"))
        return "\n".join([*lines, "    }", "}", ""])

    def plan(self, graph):
        if graph["diagnostics"]:
            raise ValueError("\n".join(f"line {d['line']}: {d['message']}" for d in graph["diagnostics"]))
        existing_assembly = self.assembly_names.get(self.assembly)
        assembly_path = self.destination / f"{self.assembly}.asmdef"
        if self.assembly:
            if existing_assembly and existing_assembly[0] != assembly_path:
                raise ValueError(f"Assembly name already used: {self.assembly}")
            if not existing_assembly and (self.destination in self.assemblies or
                                          any(self.destination.rglob("*.cs"))):
                raise ValueError("A new assembly would change the existing output directory's assembly boundary")
        self.target_assembly = self.assembly or self.assembly_at(self.destination)
        for record in graph["classes"]:
            name, kind = record["name"], record["kind"]
            if not valid_name(name):
                raise ValueError(f"Invalid C# type name {name}")
            item = self.lookup(name)
            if item:
                if kind != "class" and kind != item.kind:
                    raise ValueError(f"Kind mismatch for {name} at {self.location(item)}")
                self.status.append(f"Existing {name} at {self.location(item)}")
            else:
                if not self.namespace:
                    raise ValueError("--namespace is required to generate new types")
                item = Type(name, f"{self.namespace}.{name}", kind)
                self.status.append(f"New {kind} {name}")
            self.types[name] = item
        for record in graph["classes"]:
            item = self.types[record["name"]]
            for member in record["members"]:
                line, raw = member["startLine"], member["text"]
                try:
                    if item.declarations:
                        self.check_existing(item, raw, line)
                    else:
                        self.member(item, raw)
                except ValueError as error:
                    raise ValueError(f"line {line}: {error}") from error
        for edge in graph["relationships"]:
            try:
                self.edge(edge)
            except ValueError as error:
                raise ValueError(f"line {edge['startLine']}: {error}") from error
        files = {self.destination / f"{item.name}.cs": self.render(item)
                 for item in self.types.values() if not item.declarations}
        if self.assembly and not existing_assembly:
            files[assembly_path] = json.dumps({"name": self.assembly, "rootNamespace": self.namespace,
                                               "references": sorted(self.dependencies)}, indent=4) + "\n"
            self.check_assembly_cycles()
        elif self.target_assembly:
            path, data = self.assembly_names[self.target_assembly]
            missing = self.dependencies - self.named_references(data)
            if missing:
                raise ValueError(f"Add assembly references to {path}: {', '.join(sorted(missing))}")
        names = {entry.name.casefold() for entry in self.destination.iterdir()} if self.destination.exists() else set()
        for path in files:
            if path.name.casefold() in names:
                raise ValueError(f"Output filename collision: {path}")
            names.add(path.name.casefold())
        return files

    def named_references(self, data):
        references = set(data.get("references", []))
        for name, (path, _) in self.assembly_names.items():
            meta = path.with_suffix(".asmdef.meta")
            if meta.is_file():
                guid = re.search(r"^guid: (\S+)$", meta.read_text(), re.M)
                if guid and f"GUID:{guid[1]}" in references:
                    references.add(name)
        return references

    def check_assembly_cycles(self):
        pending, seen = list(self.dependencies), set()
        while pending:
            name = pending.pop()
            if name == self.assembly:
                raise ValueError(f"Assembly dependency cycle involving {name}")
            if name in self.assembly_names and name not in seen:
                seen.add(name)
                pending.extend(self.named_references(self.assembly_names[name][1]))


def apply(files):
    created = []
    directories = []
    try:
        for path, content in files.items():
            missing = []
            folder = path.parent
            while not folder.exists():
                missing.append(folder)
                folder = folder.parent
            for folder in reversed(missing):
                folder.mkdir()
                directories.append(folder)
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                created.append(path)
                handle.write(content)
    except OSError:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for folder in reversed(directories):
            if not any(folder.iterdir()):
                folder.rmdir()
        raise


def main(argv):
    parser = argparse.ArgumentParser(prog="mermaid-graph.sh scaffold", description=__doc__)
    parser.add_argument("diagram", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--namespace", default="")
    parser.add_argument("--asmdef")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    for label, name in (("namespace", args.namespace), ("assembly name", args.asmdef)):
        if name is not None and (name or label == "assembly name") and not all(
                valid_name(part) for part in name.split(".")):
            parser.error(f"Invalid {label}: {name}")
    try:
        root, destination = context(args.project_root, args.output)
        graph = parse(args.diagram.read_text(encoding="utf-8-sig"))
        scaffold = Scaffold(root, destination, args.namespace, args.asmdef)
        files = scaffold.plan(graph)
        if args.apply:
            apply(files)
        for line in scaffold.status + scaffold.gaps:
            print(line)
        for path in files:
            print(f"{'Created' if args.apply else 'Would create'} {path}")
        if not files:
            print("No files to generate.")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")
