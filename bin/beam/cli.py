"""Command line: `serve`, `eval`, `stats`, `selftest`, `version`."""

from __future__ import annotations

import json
import os
import sys
from typing import List

from . import VERSION
from .answer import answer
from .types import Context

USAGE = """usage: beam.py <command>

  serve            JSON-lines engine for the Beam plugin (stdin/stdout)
  eval <query>     print the answers for a query
  stats            summarise Jev usage
  selftest         evaluate a few known queries
  version          print the version
"""


def cache_dir() -> str:
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "beam")


def state_dir() -> str:
    return os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "beam")


def make_context() -> Context:
    from .currency import RateStore

    ctx = Context()
    ctx.rates = RateStore(os.path.join(cache_dir(), "rates.json"), ctx.settings.rates_refresh_hours)
    return ctx


SELFTEST = [("357/2", "178.5"), ("5 ft in cm", "152.4 cm"), ("0xff", "255"), ("72f to c", "22.22222222°C")]


def main(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0 if argv else 2
    cmd, args = argv[0], argv[1:]
    if cmd == "version":
        print(VERSION)
        return 0
    if cmd == "eval":
        if not args:
            sys.stderr.write("usage: beam.py eval <query>\n")
            return 2
        ctx = make_context()
        results = answer(" ".join(args), ctx)
        print(json.dumps([a.to_json() for a in results], ensure_ascii=False, indent=2))
        return 0 if results else 1
    if cmd == "selftest":
        ctx = Context()
        failed = 0
        for q, expected in SELFTEST:
            got = answer(q, ctx)
            ok = bool(got) and got[0].value == expected
            failed += not ok
            print(f"{'ok ' if ok else 'BAD'} {q!r} -> {got[0].value if got else None!r}")
        return 1 if failed else 0
    if cmd == "serve":
        from .protocol import serve

        return serve(sys.stdin, sys.stdout, make_context(), state_dir(), cache_dir())
    if cmd == "stats":
        from .jev import format_stats

        print(format_stats(os.path.join(state_dir(), "usage.jsonl")))
        return 0
    sys.stderr.write(USAGE)
    return 2
