"""Test helpers: put bin/ on sys.path and build deterministic contexts."""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

from beam.types import Context, Settings  # noqa: E402

FIXED_NOW = datetime(2026, 9, 23, 14, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def make_ctx(locale="en_IN.UTF-8", now=FIXED_NOW, **settings):
    return Context(settings=Settings(**settings), now=lambda: now, locale=locale)
