#!/usr/bin/env python3
"""Compatibility path for Tools/link-diagram-tasks/link_diagram_tasks.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "link-diagram-tasks"))
from link_diagram_tasks import *  # noqa: F401,F403
from link_diagram_tasks import main

if __name__ == "__main__":
    main()
