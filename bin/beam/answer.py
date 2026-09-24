"""Answer dispatcher: cheapest gate first, first parser that claims the query wins."""

from __future__ import annotations

from typing import List

from . import calc, currency, devvals, timeparse, units
from .store import log
from .types import Answer, Context

MAX_QUERY = 200
MAX_ANSWERS = 3

PARSERS = (
    ("developer", devvals.parse),
    ("time", timeparse.parse),
    ("currency", currency.parse),
    ("units", units.parse),
    ("calculator", calc.parse),
)


def answer(q: str, ctx: Context) -> List[Answer]:
    s = " ".join(str(q or "").split())
    if not s or len(s) > MAX_QUERY:
        return []
    for kind, parse in PARSERS:
        if kind not in ctx.settings.enabled:
            continue
        try:
            result = parse(s, ctx)
        except Exception as e:  # a parser bug must never take the engine down
            log(f"{kind} parser failed: {type(e).__name__}")  # never the query text
            result = None
        if result:
            return list(result[:MAX_ANSWERS])
    return []
