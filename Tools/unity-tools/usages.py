#!/usr/bin/env python3
"""Compatibility path for the Unity usages engine; use unity.py usages."""
import sys
from _usages_engine import *  # noqa: F401,F403
from _usages_engine import main

if __name__ == "__main__":
    sys.exit(main())
