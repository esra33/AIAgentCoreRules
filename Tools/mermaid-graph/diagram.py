"""Parse the editable subset without normalizing the surrounding Mermaid source."""

import re


ID = r"[A-Za-z_][A-Za-z0-9_]*"
ARROWS = {
    "<|--": ("inheritance", "left"), "--|>": ("inheritance", "right"),
    "<|..": ("realization", "left"), "..|>": ("realization", "right"),
    "*--": ("composition", "left"), "--*": ("composition", "right"),
    "o--": ("aggregation", "left"), "--o": ("aggregation", "right"),
    "<--": ("association", "left"), "-->": ("association", "right"),
    "<..": ("dependency", "left"), "..>": ("dependency", "right"),
}
DECLARATION = re.compile(rf"class\s+(?P<name>{ID})(?:\s*(?P<braces>\{{\s*\}}|\{{))?")
MEMBER = re.compile(rf"(?P<name>{ID})\s*:\s*(?P<member>.+)")
ANNOTATION = r"<<\s*(?P<annotation>[A-Za-z]+)\s*>>"
ANNOTATED_CLASS = re.compile(rf"{ANNOTATION}\s+(?P<name>{ID})")
KINDS = {"interface": "interface", "struct": "struct", "enum": "enum", "enumeration": "enum"}
RELATION = re.compile(
    rf'(?P<left>{ID})\s*(?:"(?P<leftMultiplicity>[^"\r\n]*)"\s*)?'
    rf'(?P<arrow>{"|".join(map(re.escape, ARROWS))})\s*'
    rf'(?:"(?P<rightMultiplicity>[^"\r\n]*)"\s*)?(?P<right>{ID})'
    r'(?:\s*:\s*(?P<label>.*))?'
)
LINES = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$")


def parse(source):
    lines = LINES.findall(source)
    classes, relationships, diagnostics = {}, [], []
    header = False
    block = None

    def class_record(name):
        return classes.setdefault(name, {"name": name, "kind": "class", "declarations": [],
                                         "members": [], "references": []})

    def annotate(record, text, number):
        match = re.fullmatch(ANNOTATION, text)
        kind = KINDS.get(match["annotation"].lower()) if match else None
        if kind:
            if record["kind"] not in ("class", kind):
                diagnostics.append({"line": number, "message": "Conflicting type annotations."})
            record["kind"] = kind

    def reference(record, match, group, offset, number):
        start, end = match.span(group)
        record["references"].append({"line": number, "start": offset + start, "end": offset + end})

    for number, line in enumerate(lines, 1):
        statement = line.strip()
        offset = len(line) - len(line.lstrip())
        if not statement or (statement.startswith("%%") and not statement.startswith("%%{")):
            continue
        if "%%" in statement:
            diagnostics.append({"line": number, "message": "Unsupported Mermaid directive or inline comment."})
            continue
        if ";" in statement or re.match(r"acc(?:Title|Descr)\b", statement):
            diagnostics.append({"line": number, "message": "Unsupported statement. Edit it in the source pane."})
            continue
        if not header:
            if statement == "classDiagram":
                header = True
            else:
                diagnostics.append({"line": number, "message": "Expected a classDiagram header."})
            continue
        if block:
            record, declaration = block
            if statement == "}":
                declaration["endLine"] = number
                block = None
            elif any(char in statement for char in "{}"):
                diagnostics.append({"line": number, "message": "Unsupported syntax inside a class block."})
            else:
                record["members"].append({"text": statement, "startLine": number, "endLine": number})
                annotate(record, statement, number)
            continue
        if match := DECLARATION.fullmatch(statement):
            record = class_record(match["name"])
            declaration = {"startLine": number, "endLine": number}
            record["declarations"].append(declaration)
            reference(record, match, "name", offset, number)
            if match["braces"] == "{":
                block = record, declaration
        elif match := ANNOTATED_CLASS.fullmatch(statement):
            record = class_record(match["name"])
            record["declarations"].append({"startLine": number, "endLine": number})
            reference(record, match, "name", offset, number)
            annotate(record, statement[:match.start("name")].strip(), number)
        elif match := RELATION.fullmatch(statement):
            edge = {key: value or "" for key, value in match.groupdict().items()}
            edge["kind"], edge["direction"] = ARROWS[edge["arrow"]]
            edge.update(startLine=number, endLine=number)
            relationships.append(edge)
            for endpoint in ("left", "right"):
                reference(class_record(edge[endpoint]), match, endpoint, offset, number)
        elif match := MEMBER.fullmatch(statement):
            record = class_record(match["name"])
            record["members"].append({"text": match["member"], "startLine": number, "endLine": number})
            reference(record, match, "name", offset, number)
            annotate(record, match["member"], number)
        else:
            diagnostics.append({"line": number, "message": "Unsupported statement. Edit it in the source pane."})
    if block:
        diagnostics.append({"line": block[1]["startLine"], "message": "Unclosed class block."})
    if not header and not diagnostics:
        diagnostics.append({"line": 1, "message": "Missing classDiagram header."})
    return {"classes": list(classes.values()), "relationships": relationships, "diagnostics": diagnostics}


def attached(edge, name):
    return name in (edge["left"], edge["right"])


def edit(source, change):
    graph = parse(source)
    if graph["diagnostics"]:
        raise ValueError("Visual edits are disabled while the diagram has unsupported syntax.")
    classes = {record["name"]: record for record in graph["classes"]}
    edges = {edge["startLine"]: edge for edge in graph["relationships"]}
    lines = LINES.findall(source)
    newline = next(iter(re.findall(r"\r\n|\r|\n", source)), "\n")

    def append(statement):
        separator = "" if source.endswith(("\n", "\r")) else newline
        return source + separator + statement + (newline if not separator else "")

    def identifier(field):
        value = change.get(field)
        if not isinstance(value, str) or not re.fullmatch(ID, value):
            raise ValueError("Use a class ID containing letters, digits, and underscores, starting with a letter or underscore.")
        return value

    action = change.get("action")
    if action in ("addClass", "renameClass"):
        new_name = identifier("newName")
        if new_name in classes:
            raise ValueError("That class already exists.")
        if action == "addClass":
            kind = change.get("kind", "class")
            if kind not in ("class", "interface", "struct", "enum"):
                raise ValueError("Select a supported node type.")
            if kind == "class":
                return append(f"class {new_name}")
            annotation = "enumeration" if kind == "enum" else kind
            return append(newline.join((f"class {new_name} {{", f"    <<{annotation}>>", "}")))
    if action in ("renameClass", "deleteClass"):
        name = identifier("name")
        if name not in classes:
            raise ValueError("Select an existing class.")
        record = classes[name]
        if action == "renameClass":
            for ref in sorted(record["references"], key=lambda ref: (ref["line"], ref["start"]), reverse=True):
                index = ref["line"] - 1
                lines[index] = lines[index][:ref["start"]] + new_name + lines[index][ref["end"]:]
        else:
            removed = {edge["startLine"] for edge in edges.values() if attached(edge, name)}
            removed.update(member["startLine"] for member in record["members"])
            for declaration in record["declarations"]:
                for number in range(declaration["startLine"], declaration["endLine"] + 1):
                    statement = lines[number - 1].strip()
                    if statement and not statement.startswith("%%"):
                        removed.add(number)
            lines = [line for number, line in enumerate(lines, 1) if number not in removed]
    elif action in ("addRelationship", "editRelationship", "deleteRelationship"):
        if action != "addRelationship":
            number = change.get("line")
            if type(number) is not int or number not in edges:
                raise ValueError("Select an existing relationship.")
        if action == "deleteRelationship":
            del lines[number - 1]
        else:
            left, right = identifier("left"), identifier("right")
            if left not in classes or right not in classes:
                raise ValueError("Both endpoints must be existing classes.")
            arrow = change.get("arrow")
            if not isinstance(arrow, str) or arrow not in ARROWS:
                raise ValueError("Select a supported relationship type.")
            fields = {}
            for field in ("leftMultiplicity", "rightMultiplicity", "label"):
                value = change.get(field, "")
                if (not isinstance(value, str) or any(char in value for char in "\r\n;") or
                        "%%" in value or (field != "label" and '"' in value)):
                    raise ValueError("Use plain single-line values and omit quotes around multiplicities.")
                fields[field] = value.strip()
            left_mult = f' "{fields["leftMultiplicity"]}"' if fields["leftMultiplicity"] else ""
            right_mult = f' "{fields["rightMultiplicity"]}"' if fields["rightMultiplicity"] else ""
            label = f' : {fields["label"]}' if fields["label"] else ""
            statement = f"{left}{left_mult} {arrow}{right_mult} {right}{label}"
            if action == "addRelationship":
                return append(statement)
            old = lines[number - 1]
            if all(change.get(key, "") == edges[number][key] for key in ("left", "right", "arrow", *fields)):
                return source
            indent = old[:len(old) - len(old.lstrip())]
            ending = old[len(old.rstrip("\r\n")):]
            lines[number - 1] = indent + statement + ending
    else:
        raise ValueError("Unknown visual edit.")
    return "".join(lines)
