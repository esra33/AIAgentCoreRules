#!/usr/bin/env python3
"""Unified entry point for the independent Unity index, typecheck, and usages engines."""
import argparse
import subprocess
import sys
from pathlib import Path


ENGINES = {"index": "_index_engine.py", "typecheck": "_typecheck_engine.py", "usages": "_usages_engine.py"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=ENGINES)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    return subprocess.call([sys.executable, "-B", str(Path(__file__).with_name(ENGINES[args.command])), *args.arguments])


if __name__ == "__main__":
    sys.exit(main())
