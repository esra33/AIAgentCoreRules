#!/usr/bin/env python3
"""Compatibility path for the Unity index engine; use unity.py index."""
import sys
from _index_engine import *  # noqa: F401,F403
from _index_engine import main

if __name__ == "__main__":
    sys.exit(main())
