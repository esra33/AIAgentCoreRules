#!/usr/bin/env python3
"""Cache a description of an image or PDF so an agent doesn't re-interpret it every time.

The agent (not this tool) does the actual reading and describing — Claude has native
multimodal access to images and PDFs via its Read tool. This tool only manages the cache:
hash the source file's bytes, and store/retrieve the agent-written Markdown description
keyed by that hash, so a second encounter with the same bytes is a cache hit instead of
another vision pass.

For storyboards and flow diagrams, the tool auto-extracts any ```mermaid code fence from
the description into a sibling <hash>.mmd file for rendering via the doc-review preview server.

Usage:
    python3 deimagify.py check <path>                   # hash the file, report hit/miss
    python3 deimagify.py store <path> --from <md-file>   # cache a description for this file's hash
    python3 deimagify.py store <path> --from -           # read the description from stdin
    python3 deimagify.py forget <path>                   # drop the cached entry for this file's hash
    python3 deimagify.py list                            # show every cached entry

Cache location: ~/.claude/deimagify-cache/ — one <hash>.md per description, plus a sibling
<hash>.mmd (auto-extracted from ```mermaid fences), plus an index.json with path/size/cached-at
per hash (for `list` and debugging). Keyed by content hash, not path, so a moved or copied file
still hits cache; a changed file (different bytes) is a fresh miss. Lives outside every git
repo, so there's nothing to commit.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CACHE_DIR = Path.home() / ".claude" / "deimagify-cache"
INDEX_PATH = CACHE_DIR / "index.json"
MERMAID_FENCE_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text())
    return {}


def save_index(index: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2, sort_keys=True))


def description_path_for(digest: str) -> Path:
    return CACHE_DIR / f"{digest}.md"


def diagram_path_for(digest: str) -> Path:
    return CACHE_DIR / f"{digest}.mmd"


def extract_mermaid(text: str) -> Optional[str]:
    match = MERMAID_FENCE_RE.search(text)
    return match.group(1).strip() + "\n" if match else None


def cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        print(f"error: no such file {path}", file=sys.stderr)
        return 2
    digest = file_hash(path)
    description_path = description_path_for(digest)
    if description_path.is_file():
        print(f"HIT {digest} {description_path}")
        print(description_path.read_text())
        diagram_path = diagram_path_for(digest)
        if diagram_path.is_file():
            print(f"DIAGRAM {diagram_path}")
        return 0
    print(f"MISS {digest} {description_path}")
    return 1


def cmd_store(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        print(f"error: no such file {path}", file=sys.stderr)
        return 2
    digest = file_hash(path)
    description_path = description_path_for(digest)
    if description_path.exists() and not args.force:
        print(f"error: already cached at {description_path} (pass --force to overwrite)", file=sys.stderr)
        return 1
    text = sys.stdin.read() if args.source == "-" else Path(args.source).expanduser().read_text()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    description_path.write_text(text)
    diagram_path = diagram_path_for(digest)
    diagram_path.unlink(missing_ok=True)
    mermaid_code = extract_mermaid(text)
    if mermaid_code:
        diagram_path.write_text(mermaid_code)
    index = load_index()
    index[digest] = {
        "source_path": str(path),
        "size_bytes": path.stat().st_size,
        "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_index(index)
    print(f"STORED {digest} {description_path}")
    if mermaid_code:
        print(f"DIAGRAM {diagram_path}")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        print(f"error: no such file {path}", file=sys.stderr)
        return 2
    digest = file_hash(path)
    description_path = description_path_for(digest)
    diagram_path = diagram_path_for(digest)
    removed = False
    if description_path.exists():
        description_path.unlink()
        removed = True
    if diagram_path.exists():
        diagram_path.unlink()
        removed = True
    index = load_index()
    if digest in index:
        del index[digest]
        save_index(index)
        removed = True
    print(f"{'FORGOT' if removed else 'NOT-CACHED'} {digest}")
    return 0 if removed else 1


def cmd_list(args: argparse.Namespace) -> int:
    index = load_index()
    if not index:
        print("(empty cache)")
        return 0
    for digest, meta in sorted(index.items(), key=lambda kv: kv[1].get("cached_at", "")):
        diagram_marker = " [diagram]" if diagram_path_for(digest).is_file() else ""
        print(f"{digest}  {meta.get('cached_at', '?')}  {meta.get('source_path', '?')}{diagram_marker}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Hash the file and report cache hit/miss")
    check.add_argument("path")
    check.set_defaults(func=cmd_check)

    store = sub.add_parser("store", help="Cache a description for this file's current hash")
    store.add_argument("path")
    store.add_argument("--from", dest="source", required=True, help="Markdown file to cache, or - for stdin")
    store.add_argument("--force", action="store_true", help="Overwrite an existing cached entry")
    store.set_defaults(func=cmd_store)

    forget = sub.add_parser("forget", help="Drop the cached entry for this file's current hash")
    forget.add_argument("path")
    forget.set_defaults(func=cmd_forget)

    list_cmd = sub.add_parser("list", help="Show every cached entry")
    list_cmd.set_defaults(func=cmd_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
