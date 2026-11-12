"""
Declaration-level C# parser.

Extracts type and member declarations from a source file. Pure — it knows nothing
about SQLite, so it can be exercised on a string in a test without a database.

Scope, deliberately: declarations only. It does not resolve names, follow `using`
directives, or look inside method bodies. C# declaration syntax is regular enough that
a scanner gets this right; call-site analysis is not, which is why it is out of scope.

Approach:
  1. Blank out comments and string/char literals, preserving length and line breaks, so
     brace counting cannot be thrown off by a `{` inside a string or an interpolation.
  2. Precompute brace depth at the start of every line.
  3. Walk lines, maintaining a namespace stack and a type stack keyed by depth. A member
     is a declaration sitting at exactly (enclosing type depth + 1).

Conditional compilation: `#if` branches are all indexed and the condition is not
recorded. The index therefore answers "what exists in source", not "what exists in an
RC build".
"""

import re

KEYWORDS = {
    "class", "struct", "interface", "enum", "record", "where", "new", "unmanaged",
    "notnull", "default", "void", "return", "if", "else", "for", "foreach", "while",
    "switch", "case", "do", "try", "catch", "finally", "using", "lock", "base", "this",
}

TYPE_KINDS = ("class", "interface", "struct", "enum", "record")

TYPE_MODS = (
    "public", "private", "protected", "internal", "static", "sealed", "abstract",
    "partial", "readonly", "ref", "unsafe", "new",
)

MEMBER_MODS = (
    "public", "private", "protected", "internal", "static", "readonly", "const",
    "virtual", "override", "abstract", "sealed", "async", "extern", "unsafe", "new",
    "partial", "event", "volatile", "required", "implicit", "explicit", "operator",
)

_TYPE_RE = re.compile(
    r"\b(?P<kind>class|interface|struct|enum|record)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"\s*(?P<generic><.*?>)?"
)

_NS_RE = re.compile(r"^\s*namespace\s+(?P<name>[A-Za-z_][\w.]*)\s*(?P<brace>[{;])?")

_MOD_RE = re.compile(r"^\s*(?:(?:%s)\s+)*" % "|".join(MEMBER_MODS))

_ATTR_LINE_RE = re.compile(r"^\s*\[.*\]\s*$")


class TypeDecl:
    __slots__ = ("name", "arity", "namespace", "container", "kind", "line", "end_line",
                 "signature", "access", "is_abstract", "is_sealed", "is_static", "is_partial",
                 "bases", "members", "attributes")

    def __init__(self, **kw):
        for slot in self.__slots__:
            setattr(self, slot, kw.get(slot))
        self.bases = self.bases or []
        self.members = self.members or []
        self.attributes = self.attributes or []

    def __repr__(self):
        return "<TypeDecl %s.%s %s line=%d bases=%d members=%d>" % (
            self.namespace, self.name, self.kind, self.line, len(self.bases), len(self.members))


class MemberDecl:
    __slots__ = ("name", "kind", "signature", "line", "end_line", "access", "is_static",
                 "is_abstract", "is_virtual", "is_override", "is_async", "attributes")

    def __init__(self, **kw):
        for slot in self.__slots__:
            setattr(self, slot, kw.get(slot))
        self.attributes = self.attributes or []


def blank_literals(text):
    """Replace comment and literal *content* with spaces, keeping length and newlines.

    Brace counting depends on this: `$"{x}"` and `"{"` would otherwise corrupt depth,
    and `//` comments routinely contain unbalanced braces.
    """
    out = list(text)
    i, n = 0, len(text)

    def blank(start, end):
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = text[i]

        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue

        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue

        # Verbatim string: @"..." or $@"..." / @$"...". Only "" escapes a quote.
        if c in "@$" and i + 1 < n:
            k = i
            prefix = ""
            while k < n and text[k] in "@$" and len(prefix) < 2:
                prefix += text[k]
                k += 1
            if k < n and text[k] == '"' and "@" in prefix:
                j = k + 1
                while j < n:
                    if text[j] == '"':
                        if j + 1 < n and text[j + 1] == '"':
                            j += 2
                            continue
                        j += 1
                        break
                    j += 1
                blank(k + 1, j - 1)
                i = j
                continue

        if c == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                if text[j] == "\n":
                    break
                j += 1
            blank(i + 1, j - 1)
            i = j
            continue

        if c == "'":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "'":
                    j += 1
                    break
                if text[j] == "\n":
                    break
                j += 1
            blank(i + 1, j - 1)
            i = j
            continue

        i += 1

    return "".join(out)


def _split_top_level(text, sep=","):
    """Split on `sep` ignoring anything nested in <>, (), [] — for base lists."""
    parts, buf, angle, paren, square = [], [], 0, 0, 0
    for ch in text:
        if ch == "<":
            angle += 1
        elif ch == ">":
            angle = max(0, angle - 1)
        elif ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            square += 1
        elif ch == "]":
            square = max(0, square - 1)
        if ch == sep and not (angle or paren or square):
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _simple_name(raw):
    """`IMessageListener<OnUpdateMessage>` -> `IMessageListener`; drops qualifiers."""
    name = raw.split("<", 1)[0].strip()
    if "." in name:
        name = name.rsplit(".", 1)[1]
    return name.strip()


def _arity(generic):
    if not generic:
        return 0
    inner = generic.strip()[1:-1]
    return len(_split_top_level(inner)) if inner.strip() else 0


def _gather(clean_lines, start, col, stops):
    """Join lines from (start, col) until a stop character. Returns (text, end_line)."""
    chunk, i = [], start
    first = clean_lines[start][col:]
    while i < len(clean_lines):
        segment = first if i == start else clean_lines[i]
        cut = None
        angle = 0
        for pos, ch in enumerate(segment):
            if ch == "<":
                angle += 1
            elif ch == ">":
                angle = max(0, angle - 1)
            elif ch in stops and not angle:
                cut = pos
                break
        if cut is not None:
            chunk.append(segment[:cut])
            return " ".join(chunk), i
        chunk.append(segment)
        i += 1
        if i - start > 40:  # runaway guard
            break
    return " ".join(chunk), min(i, len(clean_lines) - 1)


def _access_of(text):
    for token in ("protected internal", "private protected", "public", "internal",
                  "protected", "private"):
        if re.search(r"\b%s\b" % token.replace(" ", r"\s+"), text):
            return token
    return None


def _leading_attributes(clean_line, raw_line):
    """Attribute sections at the start of a line: `[A, B(x)] [C] public int X;`.

    Returns (end column, [(simple name, raw text)], is_global). Columns line up between the
    clean and raw lines because blank_literals preserves length, so names come from the clean
    line (a `]` inside a string cannot end a section) and the raw text, arguments included,
    from the raw line. is_global marks `[assembly: …]` / `[module: …]`, which belong to no
    declaration.
    """
    attrs, pos, n, is_global = [], 0, len(clean_line), False
    while True:
        while pos < n and clean_line[pos] in " \t":
            pos += 1
        if pos >= n or clean_line[pos] != "[":
            break
        depth, end, cuts = 0, None, []
        for k in range(pos, n):
            ch = clean_line[k]
            if ch in "[(<{":
                depth += 1
            elif ch in "])>}":
                depth -= 1
                if depth == 0:
                    end = k
                    break
            elif ch == "," and depth == 1:
                cuts.append(k)
        if end is None:
            break
        bounds = [pos] + cuts + [end]
        for a, b in zip(bounds, bounds[1:]):
            clean_part = clean_line[a + 1:b].strip()
            target = re.match(r"(\w+)\s*:(?!:)\s*", clean_part)
            if target:
                is_global = is_global or target.group(1) in ("assembly", "module")
                clean_part = clean_part[target.end():]
            name = _simple_name(clean_part.split("(", 1)[0])
            if re.fullmatch(r"[A-Za-z_]\w*", name or ""):
                raw_part = raw_line[a + 1:b].strip()
                if target:
                    raw_part = raw_part[target.end():] if raw_part.startswith(target.group(0)) else raw_part
                attrs.append((name, raw_part))
        pos = end + 1
    return (pos if attrs else 0), attrs, is_global


def _block_end(depths_after, here, header_end):
    """Last line of a declaration whose header ends on header_end. A header that opened a
    body (depth after it is deeper than the declaration's own) runs to the line where the
    depth returns; otherwise the declaration ends on its header's last line."""
    k = header_end
    while k < len(depths_after) and depths_after[k] > here:
        k += 1
    return min(k, len(depths_after) - 1)


class SourceParser:
    def parse(self, path, text):
        clean = blank_literals(text)
        clean_lines = clean.split("\n")
        raw_lines = text.split("\n")

        depths, depths_after = [], []
        depth = 0
        for line in clean_lines:
            depths.append(depth)
            depth += line.count("{") - line.count("}")
            depths_after.append(depth)

        types = []
        ns_stack = []          # (name, depth) ; file-scoped uses depth -1
        type_stack = []        # (TypeDecl, depth)
        consumed_until = -1
        pending_attrs = []     # attribute sections on lines of their own, waiting for a declaration

        for i, line in enumerate(clean_lines):
            if i <= consumed_until:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Attributes: a line of its own is held for the next declaration; a leading
            # section on a declaration line is taken and blanked (columns kept), so the
            # declaration is matched as if it were not there.
            attr_end, attrs, is_global = _leading_attributes(line, raw_lines[i])
            if attrs:
                if not line[attr_end:].strip():
                    if not is_global:
                        pending_attrs.extend(attrs)
                    continue
                line = " " * attr_end + line[attr_end:]
                clean_lines[i] = line
                attrs = pending_attrs + ([] if is_global else attrs)
            elif _ATTR_LINE_RE.match(line):
                continue
            else:
                attrs = pending_attrs
            pending_attrs = []

            here = depths[i]

            while ns_stack and ns_stack[-1][1] >= 0 and here <= ns_stack[-1][1]:
                ns_stack.pop()
            while type_stack and here <= type_stack[-1][1]:
                type_stack.pop()

            ns_match = _NS_RE.match(line)
            if ns_match:
                ns_stack.append((ns_match.group("name"),
                                 here if ns_match.group("brace") == "{" else -1))
                # Do not skip the rest of the line: `namespace X { class Y { } }` is
                # legal and would otherwise vanish entirely. Blank the namespace prefix
                # so column positions still line up, then fall through to type
                # detection on the remainder. Depths were precomputed, so mutating the
                # working copy here cannot corrupt brace accounting.
                remainder = line[ns_match.end():]
                if not remainder.strip():
                    continue
                line = " " * ns_match.end() + remainder
                clean_lines[i] = line

            decl = self._try_type(clean_lines, raw_lines, i, here, ns_stack, type_stack)
            if decl is not None:
                type_decl, end_line = decl
                type_decl.end_line = _block_end(depths_after, here, end_line) + 1
                type_decl.attributes = attrs
                types.append(type_decl)
                type_stack.append((type_decl, here))
                consumed_until = end_line
                continue

            if type_stack and here == type_stack[-1][1] + 1:
                member = self._try_member(clean_lines, raw_lines, i, type_stack[-1][0])
                if member is not None:
                    member_decl, end_line = member
                    member_decl.end_line = (i + 1 if member_decl.kind == "enum_member"
                                            else _block_end(depths_after, here, end_line) + 1)
                    member_decl.attributes = attrs
                    type_stack[-1][0].members.append(member_decl)
                    consumed_until = end_line

        return types

    # -- declaration handling -------------------------------------------

    def _try_type(self, clean_lines, raw_lines, i, here, ns_stack, type_stack):
        line = clean_lines[i]
        match = _TYPE_RE.search(line)
        if not match:
            return None

        before = line[: match.start()]
        # `where T : class` and `List<Foo> x = new()` are not declarations.
        if "where" in before or "=" in before or "(" in before:
            return None
        if match.group("name") in KEYWORDS:
            return None
        # Everything before the keyword must be modifiers, or it is not a declaration.
        residue = before
        for mod in TYPE_MODS:
            residue = re.sub(r"\b%s\b" % mod, "", residue)
        if residue.strip():
            return None

        kind = match.group("kind")
        name = match.group("name")
        generic = match.group("generic")

        # `record class Foo` / `record struct Foo`
        if kind == "record" and name in ("class", "struct"):
            remainder = line[match.end("name"):]
            follow = _TYPE_RE.search("record " + remainder)
            if follow:
                name = follow.group("name")
                generic = follow.group("generic")

        tail_start = match.end()
        body, end_line = _gather(clean_lines, i, tail_start, "{;")

        bases = []
        if ":" in body:
            base_text = body.split(":", 1)[1]
            base_text = re.split(r"\bwhere\b", base_text)[0]
            for raw in _split_top_level(base_text):
                simple = _simple_name(raw)
                if simple and simple not in KEYWORDS:
                    bases.append((simple, raw.strip()))

        namespace = ".".join(n for n, _ in ns_stack if n)
        container = ".".join(t.name for t, _ in type_stack)

        return TypeDecl(
            name=name,
            arity=_arity(generic),
            namespace=namespace,
            container=container,
            kind=kind,
            line=i + 1,
            signature=" ".join((line[:tail_start] + " " + body).split())[:600],
            access=_access_of(line[: match.start()]),
            is_abstract=int(bool(re.search(r"\babstract\b", line[: match.start()]))),
            is_sealed=int(bool(re.search(r"\bsealed\b", line[: match.start()]))),
            is_static=int(bool(re.search(r"\bstatic\b", line[: match.start()]))),
            is_partial=int(bool(re.search(r"\bpartial\b", line[: match.start()]))),
            bases=bases,
            members=[],
        ), end_line

    def _try_member(self, clean_lines, raw_lines, i, owner):
        line = clean_lines[i]
        stripped = line.strip()
        if not stripped or stripped[0] in "{}":
            return None

        if owner.kind == "enum":
            name = re.match(r"^\s*([A-Za-z_]\w*)", line)
            if not name:
                return None
            return MemberDecl(
                name=name.group(1), kind="enum_member",
                signature=stripped.rstrip(",").strip(), line=i + 1,
                access=None, is_static=0, is_abstract=0, is_virtual=0,
                is_override=0, is_async=0,
            ), i

        # Two boundaries: classify on the text before any initialiser, but consume all
        # the way to the terminator, or a multi-line field initialiser leaves its
        # continuation lines to be misread as further declarations.
        body, _ = _gather(clean_lines, i, 0, ";{=")
        _, end_line = _gather(clean_lines, i, 0, ";{")
        full = " ".join(x.strip() for x in body.split()).strip()
        if not full:
            return None

        mods = _MOD_RE.match(full)
        rest = full[mods.end():] if mods else full
        mod_text = full[: mods.end()] if mods else ""

        if not rest or rest[0] in "{}=":
            return None

        is_event = bool(re.search(r"\bevent\b", mod_text))
        is_delegate = bool(re.match(r"\s*delegate\b", rest))
        if is_delegate:
            rest = re.sub(r"^\s*delegate\b", "", rest)

        paren = rest.find("(")
        name, kind = None, None

        if paren > 0:
            head = rest[:paren].strip()
            tokens = head.replace("\t", " ").split()
            if tokens:
                candidate = tokens[-1]
                candidate = candidate.split("<", 1)[0]
                if re.fullmatch(r"[A-Za-z_]\w*", candidate) and candidate not in KEYWORDS:
                    name = candidate
                    if is_delegate:
                        kind = "delegate"
                    elif len(tokens) == 1 and candidate == owner.name:
                        kind = "ctor"
                    else:
                        kind = "method"
        if name is None:
            tokens = rest.split()
            if len(tokens) >= 2:
                candidate = tokens[-1].rstrip("{;,").split("<", 1)[0]
                if re.fullmatch(r"[A-Za-z_]\w*", candidate) and candidate not in KEYWORDS:
                    name = candidate
                    kind = "event" if is_event else ("property" if "{" in clean_lines[i][len(line.rstrip()):] or
                                                     i < len(clean_lines) else "field")
        if name is None:
            return None

        if kind in (None, "property", "field"):
            trailing = clean_lines[i][len(clean_lines[i].rstrip()):]
            lookahead = clean_lines[i + 1].strip() if i + 1 < len(clean_lines) else ""
            has_accessor = ("{" in clean_lines[i][clean_lines[i].find(name):] or
                            lookahead.startswith("{") or "=>" in clean_lines[i])
            kind = "event" if is_event else ("property" if has_accessor else "field")

        signature = " ".join(raw_lines[i].split())
        if end_line > i:
            extra = " ".join(" ".join(raw_lines[k].split()) for k in range(i + 1, end_line + 1))
            signature = (signature + " " + extra).strip()
        signature = signature.rstrip("{").strip()

        return MemberDecl(
            name=name,
            kind=kind,
            signature=signature[:600],
            line=i + 1,
            access=_access_of(mod_text),
            is_static=int(bool(re.search(r"\bstatic\b", mod_text))),
            is_abstract=int(bool(re.search(r"\babstract\b", mod_text))),
            is_virtual=int(bool(re.search(r"\bvirtual\b", mod_text))),
            is_override=int(bool(re.search(r"\boverride\b", mod_text))),
            is_async=int(bool(re.search(r"\basync\b", mod_text))),
        ), end_line
