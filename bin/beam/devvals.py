"""Developer values: number bases, colours, unix timestamps and byte sizes."""

from __future__ import annotations

import colorsys
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from . import fmt
from .types import Answer, Context

_LITERAL = re.compile(r"^\s*(?P<lit>0x[0-9a-f]+|0b[01]+|0o[0-7]+|\d+)\s*"
                      r"(?:(?:in|to|as)\s+(?P<to>hex|hexadecimal|bin|binary|oct|octal|dec|decimal))?\s*$", re.I)
_HEX_COLOR = re.compile(r"^\s*#(?P<hex>[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})\s*$", re.I)
_RGB = re.compile(r"^\s*rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([\d.]+)\s*)?\)\s*$", re.I)
_HSL = re.compile(r"^\s*hsl\(\s*(\d{1,3}(?:\.\d+)?)\s*,\s*(\d{1,3}(?:\.\d+)?)%\s*,\s*(\d{1,3}(?:\.\d+)?)%\s*\)\s*$", re.I)
_UNIX = re.compile(r"^\s*(\d{10}|\d{13})\s*$")
_UNIX_NOW = re.compile(r"^\s*(?:now\s+(?:in\s+)?(?:unix|epoch)|(?:unix|epoch)(?:\s+now)?|timestamp|unix\s*time)\s*$", re.I)
_BYTES = re.compile(r"^\s*(?P<n>\d[\d,]*)\s*(?:bytes?|b)\s*$", re.I)

UNIX_MIN, UNIX_MAX = 946684800, 4102444800  # 2000-01-01 .. 2100-01-01


def _base_forms(n: int) -> dict:
    sign = "-" if n < 0 else ""
    a = abs(n)
    return {"dec": str(n), "hex": f"{sign}0x{a:x}", "bin": f"{sign}0b{a:b}", "oct": f"{sign}0o{a:o}"}


def _bases(q: str) -> Optional[List[Answer]]:
    m = _LITERAL.match(q)
    if not m:
        return None
    lit, to = m.group("lit").lower(), (m.group("to") or "").lower()[:3]
    if lit.isdigit() and not to:
        return None  # a bare decimal number is not a developer value
    n = int(lit, 0) if not lit.isdigit() else int(lit)
    forms = _base_forms(n)
    src = "dec" if lit.isdigit() else {"0x": "hex", "0b": "bin", "0o": "oct"}[lit[:2]]
    order = [to] if to else ["dec"]
    order += [k for k in ("dec", "hex", "bin", "oct") if k not in order and k != src]
    names = {"dec": "decimal", "hex": "hex", "bin": "binary", "oct": "octal"}
    return [Answer(value=forms[k], copy=forms[k], detail=f"{lit} → {names[k]}", kind="developer")
            for k in order[:3]]


def _hsl_text(r: int, g: int, b: int) -> str:
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return f"hsl({round(h * 360) % 360}, {round(s * 100)}%, {round(l * 100)}%)"


def _color_answers(r: int, g: int, b: int, a: Optional[float], label: str, skip: str) -> List[Answer]:
    forms = []
    hex_text = f"#{r:02x}{g:02x}{b:02x}" + (f"{round(a * 255):02x}" if a is not None else "")
    rgb_text = f"rgba({r}, {g}, {b}, {a:g})" if a is not None else f"rgb({r}, {g}, {b})"
    for key, text in (("hex", hex_text), ("rgb", rgb_text), ("hsl", _hsl_text(r, g, b))):
        if key != skip:
            forms.append(Answer(value=text, copy=text, detail=f"{label} → {key}", kind="developer"))
    return forms


def _colors(q: str) -> Optional[List[Answer]]:
    m = _HEX_COLOR.match(q)
    if m:
        h = m.group("hex").lower()
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = round(int(h[6:8], 16) / 255, 2) if len(h) == 8 else None
        return _color_answers(r, g, b, a, "#" + m.group("hex").lower(), "hex")
    m = _RGB.match(q)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        if max(r, g, b) > 255:
            return None
        a = float(m.group(4)) if m.group(4) else None
        if a is not None and not 0 <= a <= 1:
            return None
        return _color_answers(r, g, b, a, "rgb", "rgb")
    m = _HSL.match(q)
    if m:
        h, s, l = (float(m.group(i)) for i in (1, 2, 3))
        if h > 360 or s > 100 or l > 100:
            return None
        rf, gf, bf = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
        return _color_answers(round(rf * 255), round(gf * 255), round(bf * 255), None, "hsl", "hsl")
    return None


def _format_dt(dt: datetime) -> str:
    return dt.strftime("%a, %-d %b %Y · %H:%M:%S %Z").strip()


def _unix(q: str, ctx: Context) -> Optional[List[Answer]]:
    if _UNIX_NOW.match(q):
        now = int(ctx.now().timestamp())
        return [Answer(value=str(now), copy=str(now), detail="now → unix time", kind="developer")]
    m = _UNIX.match(q)
    if not m:
        return None
    raw = int(m.group(1))
    seconds = raw / 1000 if len(m.group(1)) == 13 else raw
    if not UNIX_MIN <= seconds <= UNIX_MAX:
        return None
    tz = ctx.now().tzinfo
    local = datetime.fromtimestamp(seconds, tz)
    utc = datetime.fromtimestamp(seconds, timezone.utc)
    unit = "ms" if len(m.group(1)) == 13 else "s"
    return [
        Answer(value=_format_dt(local), copy=local.isoformat(timespec="seconds"),
               detail=f"unix {unit} → local time", kind="developer"),
        Answer(value=utc.strftime("%Y-%m-%dT%H:%M:%SZ"), copy=utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
               detail=f"unix {unit} → UTC", kind="developer"),
    ]


def _human_bytes(n: int, base: int, units: List[str]) -> str:
    value = Decimal(n)
    unit = units[0]
    for next_unit in units[1:]:
        if abs(value) < base:
            break
        value /= base
        unit = next_unit
    return f"{fmt.plain(value, 3)} {unit}"


def _bytes(q: str) -> Optional[List[Answer]]:
    m = _BYTES.match(q)
    if not m:
        return None
    try:
        n = int(m.group("n").replace(",", ""))
    except ValueError:
        return None
    if n < 1024:
        return None
    iec = _human_bytes(n, 1024, ["B", "KiB", "MiB", "GiB", "TiB", "PiB"])
    si = _human_bytes(n, 1000, ["B", "KB", "MB", "GB", "TB", "PB"])
    label = f"{n:,} bytes"
    return [Answer(value=iec, copy=iec, detail=f"{label} → binary", kind="developer"),
            Answer(value=si, copy=si, detail=f"{label} → decimal", kind="developer")]


def parse(q: str, ctx: Context) -> Optional[List[Answer]]:
    s = q.strip()
    if not s or len(s) > 80:
        return None
    for fn in (_colors, _bases, _bytes):
        result = fn(s)
        if result:
            return result
    return _unix(s, ctx)
