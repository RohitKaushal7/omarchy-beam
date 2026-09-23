#!/usr/bin/env python3
"""Beam engine entry point. Run as: python3 -I bin/beam.py <command>."""

import os
import sys

# -I leaves the script directory off sys.path; add it so `beam` imports.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from beam.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
