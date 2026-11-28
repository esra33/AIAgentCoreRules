#!/usr/bin/env python3
"""Compatibility path for the Unity typecheck engine; use unity.py typecheck."""
import sys
from _typecheck_engine import *  # noqa: F401,F403
from _typecheck_engine import main

if __name__ == "__main__":
    sys.exit(main())
