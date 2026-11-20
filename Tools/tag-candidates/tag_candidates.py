#!/usr/bin/env python3
"""Find repeated/near-duplicate passages across a project's rule markdown files
and stage [TAG] extraction candidates for human review.

Never edits the files it scans. See README.md for CLI usage.
"""

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

IMPORT_LINE_RE = re.compile(r"^@(\S.*)$")
TAG_TABLE_ROW_RE = re.compile(r"^\|\s*\*\*\[([A-Z0-9_]+)\]\*\*\s*\|\s*(.*?)\s*\|\s*$")
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "be", "with", "this", "that", "it", "as", "by", "its", "not", "no", "every",
    "all", "any", "one", "per", "if", "when", "than", "then", "at", "from",
}


@dataclass
class Chunk:
    text: str
    file: str
    line: int


@dataclass
class Candidate:
    text: str
    occurrences: List[Chunk]
    classification: str  # "new-candidate" or "already-tagged"
    suggested_tag: Optional[str] = None
    matched_tag: Optional[str] = None
    signal: str = ""  # "exact-ngram" or "near-duplicate"


def parse_claude_md_imports(claude_md_path: Path) -> List[Path]:
    """Resolve the flat `@path` import lines in a root CLAUDE.md into file paths.

    Only the documented pattern here is handled: a flat list of @imports in the
    root file, not imports nested inside the imported files themselves.
    """
    if not claude_md_path.is_file():
        return []
    base_dir = claude_md_path.parent
    resolved: List[Path] = []
    for raw_line in claude_md_path.read_text(encoding="utf-8").splitlines():
        match = IMPORT_LINE_RE.match(raw_line.strip())
        if not match:
            continue
        candidate = (base_dir / match.group(1).strip()).resolve()
        if candidate.is_file():
            resolved.append(candidate)
    return resolved


def normalize(text: str) -> str:
    text = re.sub(r"[`*_#>\[\]]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _is_bullet_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("- ") or stripped.startswith("* ")


def _is_table_row_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def gather_chunks(file_path: Path, min_words: int = 6) -> List[Chunk]:
    """Split a markdown file into comparable chunks: bullet lines and pipe-table
    rows on their own (a table has no blank lines between rows, so without this
    every row would merge into one block reported at the table's first line),
    everything else grouped into blank-line-separated paragraph blocks."""
    lines = file_path.read_text(encoding="utf-8").splitlines()
    chunks: List[Chunk] = []
    block_lines: List[str] = []
    block_start = 0

    def flush_block() -> None:
        if not block_lines:
            return
        text = " ".join(line.strip() for line in block_lines if line.strip())
        if len(text.split()) >= min_words:
            chunks.append(Chunk(text=text, file=str(file_path), line=block_start))
        block_lines.clear()

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        if not line.strip():
            flush_block()
            continue
        if _is_bullet_line(line) or _is_table_row_line(line):
            flush_block()
            line_text = line.strip()
            if len(line_text.split()) >= min_words:
                chunks.append(Chunk(text=line_text, file=str(file_path), line=idx))
            continue
        if not block_lines:
            block_start = idx
        block_lines.append(line)
    flush_block()
    return chunks


def parse_core_tags(core_tags_path: Path) -> Dict[str, str]:
    if not core_tags_path.is_file():
        return {}
    tags: Dict[str, str] = {}
    for raw_line in core_tags_path.read_text(encoding="utf-8").splitlines():
        match = TAG_TABLE_ROW_RE.match(raw_line.strip())
        if match:
            tags[match.group(1)] = match.group(2)
    return tags


def find_exact_ngram_repeats(chunks: List[Chunk], ngram: int) -> Dict[str, List[Chunk]]:
    """Find exact n-grams repeated across ≥2 files, then merge overlapping windows
    that come from the same pair of chunks into one maximal-span candidate — a
    sliding 8-word window over one real repeated sentence otherwise reports as
    several near-identical candidates instead of one."""
    chunk_words: Dict[int, List[str]] = {}
    chunk_by_id: Dict[int, Chunk] = {}
    gram_occurrences: Dict[str, List[tuple]] = {}  # gram -> [(chunk, start_idx), ...]

    for chunk in chunks:
        words = normalize(chunk.text).split()
        chunk_words[id(chunk)] = words
        chunk_by_id[id(chunk)] = chunk
        if len(words) < ngram:
            continue
        for i in range(len(words) - ngram + 1):
            gram = " ".join(words[i : i + ngram])
            gram_occurrences.setdefault(gram, []).append((chunk, i))

    cross_file_grams = {
        gram: occ
        for gram, occ in gram_occurrences.items()
        if len({c.file for c, _ in occ}) >= 2
    }

    # Merge grams that share the exact same set of chunks (= overlapping windows
    # of one underlying repeat) into a single maximal-span candidate per chunk set.
    groups: Dict[frozenset, Dict[int, List[int]]] = {}
    for occ in cross_file_grams.values():
        key = frozenset(id(c) for c, _ in occ)
        spans = groups.setdefault(key, {})
        for chunk, start in occ:
            spans.setdefault(id(chunk), []).append(start)

    merged: Dict[str, List[Chunk]] = {}
    for key, spans_by_chunk in groups.items():
        occurrences: List[Chunk] = []
        texts: List[str] = []
        for chunk_id, starts in spans_by_chunk.items():
            chunk = chunk_by_id[chunk_id]
            start = min(starts)
            end = max(s + ngram for s in starts)
            occurrences.append(chunk)
            texts.append(" ".join(chunk_words[chunk_id][start:end]))
        # All occurrences of one exact-ngram repeat share identical merged text.
        merged[max(texts, key=len)] = occurrences
    return merged


def find_near_duplicates(chunks: List[Chunk], threshold: float) -> List[List[Chunk]]:
    groups: List[List[Chunk]] = []
    used = [False] * len(chunks)
    normalized = [normalize(c.text) for c in chunks]
    for i in range(len(chunks)):
        if used[i]:
            continue
        group = [chunks[i]]
        for j in range(i + 1, len(chunks)):
            if used[j] or chunks[j].file == chunks[i].file:
                continue
            ratio = difflib.SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if ratio >= threshold:
                group.append(chunks[j])
                used[j] = True
        if len(group) >= 2:
            used[i] = True
            groups.append(group)
    return groups


def suggest_tag_name(text: str) -> str:
    words = [w for w in re.findall(r"[a-zA-Z]+", text.lower()) if w not in STOPWORDS]
    picked = words[:2] if words else ["TAG"]
    name = "".join(w.upper() for w in picked)
    return name[:16] if name else "TAG"


def classify_against_core_tags(
    text: str, core_tags: Dict[str, str], threshold: float = 0.5
) -> Optional[str]:
    normalized_text = normalize(text)
    best_tag, best_ratio = None, 0.0
    for tag, rule in core_tags.items():
        ratio = difflib.SequenceMatcher(None, normalized_text, normalize(rule)).ratio()
        if ratio > best_ratio:
            best_tag, best_ratio = tag, ratio
    return best_tag if best_ratio >= threshold else None


def build_candidates(
    files: List[Path],
    core_tags: Dict[str, str],
    ngram: int,
    near_dup_threshold: float,
    min_words: int,
    tag_match_threshold: float,
) -> List[Candidate]:
    all_chunks: List[Chunk] = []
    for f in files:
        all_chunks.extend(gather_chunks(f, min_words=min_words))

    candidates: List[Candidate] = []
    seen_texts = set()

    for gram, occurrences in find_exact_ngram_repeats(all_chunks, ngram).items():
        if gram in seen_texts:
            continue
        seen_texts.add(gram)
        matched_tag = classify_against_core_tags(gram, core_tags, tag_match_threshold)
        candidates.append(
            Candidate(
                text=gram,
                occurrences=occurrences,
                classification="already-tagged" if matched_tag else "new-candidate",
                suggested_tag=None if matched_tag else suggest_tag_name(gram),
                matched_tag=matched_tag,
                signal="exact-ngram",
            )
        )

    for group in find_near_duplicates(all_chunks, near_dup_threshold):
        representative = group[0].text
        key = normalize(representative)
        if key in seen_texts:
            continue
        seen_texts.add(key)
        matched_tag = classify_against_core_tags(representative, core_tags, tag_match_threshold)
        candidates.append(
            Candidate(
                text=representative,
                occurrences=group,
                classification="already-tagged" if matched_tag else "new-candidate",
                suggested_tag=None if matched_tag else suggest_tag_name(representative),
                matched_tag=matched_tag,
                signal="near-duplicate",
            )
        )

    return candidates


def candidates_to_dict(candidates: List[Candidate]) -> dict:
    return {
        "candidates": [
            {
                "text": c.text,
                "signal": c.signal,
                "classification": c.classification,
                "suggested_tag": c.suggested_tag,
                "matched_tag": c.matched_tag,
                "occurrences": [
                    {"file": occ.file, "line": occ.line} for occ in c.occurrences
                ],
            }
            for c in candidates
        ]
    }


def render_markdown(candidates: List[Candidate]) -> str:
    lines = ["# Tag candidates report", ""]
    if not candidates:
        lines.append("No repeated or near-duplicate passages found above threshold.")
        return "\n".join(lines)

    new_candidates = [c for c in candidates if c.classification == "new-candidate"]
    already_tagged = [c for c in candidates if c.classification == "already-tagged"]

    lines.append(f"{len(new_candidates)} new-candidate, {len(already_tagged)} already-tagged.")
    lines.append("")
    lines.append(
        "This is a staged proposal only — nothing here has been written to any source file. "
        "Review each candidate for semantic identity (not just syntactic similarity) before "
        "extracting a tag or adding a reference."
    )

    for heading, group in (
        ("New tag candidates", new_candidates),
        ("Already covered by an existing tag — add a reference instead", already_tagged),
    ):
        lines.append("")
        lines.append(f"## {heading}")
        if not group:
            lines.append("None.")
            continue
        for c in group:
            lines.append("")
            lines.append(f"### `{c.suggested_tag or c.matched_tag}` ({c.signal})")
            lines.append(f"> {c.text}")
            lines.append("")
            lines.append("Occurrences:")
            for occ in c.occurrences:
                lines.append(f"- `{occ.file}:{occ.line}`")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="Explicit markdown files to scan. "
                         "Default: resolve the host project's always-loaded CLAUDE.md import chain.")
    parser.add_argument("--root", default=".", help="Project root (default: cwd).")
    parser.add_argument("--claude-md", default=None,
                         help="Path to the root CLAUDE.md to resolve @imports from "
                              "(default: <root>/CLAUDE.md).")
    parser.add_argument("--core-tags", default=None,
                         help="Path to CoreTags.md (default: resolved relative to this tool).")
    parser.add_argument("--ngram", type=int, default=8, help="Exact-repeat n-gram size (words).")
    parser.add_argument("--threshold", type=float, default=0.72,
                         help="difflib similarity ratio for near-duplicate chunks.")
    parser.add_argument("--min-words", type=int, default=6,
                         help="Minimum words for a chunk to be considered.")
    parser.add_argument("--tag-match-threshold", type=float, default=0.5,
                         help="Similarity ratio to classify a candidate as already-tagged.")
    parser.add_argument("--out-json", default=None, help="Optional path to write the JSON report.")
    parser.add_argument("--out-md", default=None, help="Optional path to write the Markdown report.")
    return parser


def resolve_files(args: argparse.Namespace) -> List[Path]:
    if args.files:
        return [Path(f).resolve() for f in args.files]
    root = Path(args.root).resolve()
    claude_md = Path(args.claude_md).resolve() if args.claude_md else root / "CLAUDE.md"
    return parse_claude_md_imports(claude_md)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    files = resolve_files(args)
    if not files:
        print("No files resolved to scan (check --root/--claude-md or pass files explicitly).",
              file=sys.stderr)
        return 1

    core_tags_path = (
        Path(args.core_tags).resolve()
        if args.core_tags
        else (Path(__file__).resolve().parent.parent.parent / "Rules" / "CoreTags.md")
    )
    core_tags = parse_core_tags(core_tags_path)

    candidates = build_candidates(
        files=files,
        core_tags=core_tags,
        ngram=args.ngram,
        near_dup_threshold=args.threshold,
        min_words=args.min_words,
        tag_match_threshold=args.tag_match_threshold,
    )

    report_dict = candidates_to_dict(candidates)
    markdown = render_markdown(candidates)

    if args.out_json:
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    if args.out_md:
        Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_md).write_text(markdown, encoding="utf-8")

    print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
