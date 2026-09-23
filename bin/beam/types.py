"""Shared value types for the engine."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional

# Answer families, in dispatch order. Names match the QML `sources.*` settings.
KINDS = ("developer", "time", "currency", "units", "calculator")


@dataclass(frozen=True)
class Answer:
    value: str  # large display text, e.g. "178.5" or "₹8,352.40"
    copy: str  # what Enter copies, e.g. "178.5"
    detail: str  # dim interpretation line, e.g. "357 ÷ 2"
    kind: str  # one of KINDS
    pending: bool = False  # currency row waiting for rates

    def to_json(self) -> dict:
        return asdict(self)


def _bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _str(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


@dataclass
class Settings:
    enabled: frozenset = frozenset(KINDS)
    home_currency: str = "auto"
    grouping: str = "auto"
    significant_digits: int = 10
    rates_refresh_hours: int = 24
    jev_enabled: bool = True
    jev_key_file: str = "~/.config/typesafe/api_key"
    jev_cache_size: int = 500
    idle_exit_minutes: int = 10

    @classmethod
    def from_config(cls, cfg: Optional[dict]) -> "Settings":
        """Build from Beam's shell.json entry (nested groups); bad values fall back."""
        cfg = cfg if isinstance(cfg, dict) else {}
        sources = cfg.get("sources") if isinstance(cfg.get("sources"), dict) else {}
        calc = cfg.get("calc") if isinstance(cfg.get("calc"), dict) else {}
        jev = cfg.get("jev") if isinstance(cfg.get("jev"), dict) else {}
        engine = cfg.get("engine") if isinstance(cfg.get("engine"), dict) else {}
        enabled = frozenset(k for k in KINDS if _bool(sources.get(k), True))
        grouping = calc.get("grouping")
        home = _str(calc.get("homeCurrency"), "auto")
        return cls(
            enabled=enabled,
            home_currency="auto" if home.lower() == "auto" else home.upper(),
            grouping=grouping if grouping in ("auto", "indian", "international") else "auto",
            significant_digits=_int(calc.get("significantDigits"), 10, 3, 20),
            rates_refresh_hours=_int(calc.get("ratesRefreshHours"), 24, 1, 24 * 30),
            jev_enabled=_bool(jev.get("enabled"), True),
            jev_key_file=_str(jev.get("keyFile"), "~/.config/typesafe/api_key"),
            jev_cache_size=_int(jev.get("cacheSize"), 500, 0, 10000),
            idle_exit_minutes=_int(engine.get("idleExitMinutes"), 10, 1, 24 * 60),
        )


def _default_locale() -> str:
    for name in ("LC_ALL", "LC_MONETARY", "LC_NUMERIC", "LANG"):
        value = os.environ.get(name, "")
        if value and value not in ("C", "POSIX"):
            return value
    return ""


def _now() -> datetime:
    return datetime.now().astimezone()


@dataclass
class Context:
    settings: Settings = field(default_factory=Settings)
    now: Callable[[], datetime] = _now
    locale: str = field(default_factory=_default_locale)
    ans: Optional[Decimal] = None
    rates: Any = None  # currency.RateStore, or None when currency is unavailable
