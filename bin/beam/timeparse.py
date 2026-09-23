"""Time zones and dates: `3pm ist in pst`, `now in tokyo`, `days until dec 25`."""

from __future__ import annotations

import calendar
import re
import threading
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from .types import Answer, Context

ABBREVIATIONS = {
    "ist": "Asia/Kolkata", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "pt": "America/Los_Angeles", "est": "America/New_York", "edt": "America/New_York",
    "et": "America/New_York", "cst": "America/Chicago", "cdt": "America/Chicago",
    "ct": "America/Chicago", "mst": "America/Denver", "mdt": "America/Denver", "mt": "America/Denver",
    "utc": "UTC", "gmt": "UTC", "z": "UTC", "bst": "Europe/London", "cet": "Europe/Paris",
    "cest": "Europe/Paris", "eet": "Europe/Athens", "jst": "Asia/Tokyo", "kst": "Asia/Seoul",
    "sgt": "Asia/Singapore", "hkt": "Asia/Hong_Kong", "aest": "Australia/Sydney",
    "aedt": "Australia/Sydney", "nzst": "Pacific/Auckland", "nzdt": "Pacific/Auckland",
    "pkt": "Asia/Karachi", "gst": "Asia/Dubai", "wib": "Asia/Jakarta", "brt": "America/Sao_Paulo",
    "npt": "Asia/Kathmandu", "sast": "Africa/Johannesburg", "msk": "Europe/Moscow",
}
PLACES = {
    "india": "Asia/Kolkata", "delhi": "Asia/Kolkata", "new delhi": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "bengaluru": "Asia/Kolkata",
    "chennai": "Asia/Kolkata", "hyderabad": "Asia/Kolkata", "pune": "Asia/Kolkata",
    "sf": "America/Los_Angeles", "san francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles",
    "california": "America/Los_Angeles", "nyc": "America/New_York", "new york": "America/New_York",
    "boston": "America/New_York", "washington": "America/New_York", "texas": "America/Chicago",
    "austin": "America/Chicago", "uk": "Europe/London", "england": "Europe/London",
    "germany": "Europe/Berlin", "france": "Europe/Paris", "japan": "Asia/Tokyo",
    "china": "Asia/Shanghai", "beijing": "Asia/Shanghai", "korea": "Asia/Seoul",
    "australia": "Australia/Sydney", "uae": "Asia/Dubai", "nepal": "Asia/Kathmandu",
    "pakistan": "Asia/Karachi", "singapore": "Asia/Singapore", "hong kong": "Asia/Hong_Kong",
}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTHS["sept"] = 9

_cities: Dict[str, str] = {}
_cities_lock = threading.Lock()


def warm_up() -> None:
    """Index zoneinfo city names once (~25 ms); call from a background thread."""
    with _cities_lock:
        if _cities:
            return
        index = {}
        for name in available_timezones():
            if "/" in name and not name.startswith(("Etc/", "SystemV/", "posix/", "right/")):
                index.setdefault(name.rsplit("/", 1)[1].replace("_", " ").lower(), name)
        _cities.update(index)


def zone(name: str) -> Optional[ZoneInfo]:
    key = " ".join(name.strip().lower().split())
    if not key:
        return None
    target = ABBREVIATIONS.get(key) or PLACES.get(key)
    if target is None:
        warm_up()
        target = _cities.get(key)
    if target is None:
        return None
    try:
        return ZoneInfo(target)
    except ZoneInfoNotFoundError:
        return None


def _place_label(name: str, tz: ZoneInfo) -> str:
    key = name.strip().lower()
    if key in ABBREVIATIONS or len(key) <= 3:
        return key.upper()
    return " ".join(w.capitalize() for w in key.split())


def _clock(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _offset(dt: datetime) -> str:
    off = dt.utcoffset() or timedelta(0)
    minutes = int(off.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    h, m = divmod(abs(minutes), 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")


def _day(dt) -> str:
    return dt.strftime("%a, %-d %b %Y")


# ── times ────────────────────────────────────────────────────────────────────

_TIME = r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ampm>am|pm|a\.m\.|p\.m\.)?|(?P<word>noon|midnight)"
_NOW_IN = re.compile(r"^(?:(?:current\s+)?time|now|what time is it)\s+(?:in|at)\s+(?P<place>[a-z .]+?)\??$", re.I)
_PLACE_TIME = re.compile(r"^(?P<place>[a-z .]+?)\s+time$", re.I)
_CONVERT = re.compile(rf"^(?:{_TIME})\s*(?P<src>[a-z .]+?)?\s+(?:in|to)\s+(?P<dst>[a-z .]+?)$", re.I)


def _time_answers(q: str, ctx: Context) -> Optional[List[Answer]]:
    m = _NOW_IN.match(q) or _PLACE_TIME.match(q)
    if m:
        tz = zone(m.group("place"))
        if tz is None:
            return None
        there = ctx.now().astimezone(tz)
        label = _place_label(m.group("place"), tz)
        return [Answer(value=f"{_clock(there)} · {there.strftime('%a %-d %b')}", copy=_clock(there),
                       detail=f"now in {label} ({_offset(there)})", kind="time")]
    m = _CONVERT.match(q)
    if not m:
        return None
    dst = zone(m.group("dst"))
    src = zone(m.group("src")) if m.group("src") else ctx.now().tzinfo
    if dst is None or src is None:
        return None
    if m.group("word"):
        hour, minute = (12, 0) if m.group("word").lower() == "noon" else (0, 0)
    else:
        hour, minute = int(m.group("h")), int(m.group("m") or 0)
        ampm = (m.group("ampm") or "").replace(".", "").lower()
        if not ampm and not m.group("m") and not m.group("src"):
            return None  # "5 to 7" is not a time
        if ampm:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if ampm == "pm" else 0)
        if hour > 23 or minute > 59:
            return None
    today = ctx.now().astimezone(src).date()
    start = datetime(today.year, today.month, today.day, hour, minute, tzinfo=src)
    there = start.astimezone(dst)
    shift = (there.date() - start.date()).days
    suffix = {1: " (next day)", -1: " (previous day)"}.get(shift, "")
    src_label = _place_label(m.group("src"), src) if m.group("src") else "local"
    dst_label = _place_label(m.group("dst"), dst)
    return [Answer(value=f"{_clock(there)}{suffix}", copy=_clock(there),
                   detail=f"{_clock(start)} {src_label} → {dst_label} ({_offset(there)})", kind="time")]


# ── dates ────────────────────────────────────────────────────────────────────

_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DAY_MONTH = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?,?(?:\s+(\d{4}))?$", re.I)
_MONTH_DAY = re.compile(r"^([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?(?:\s+(\d{4}))?$", re.I)
_UNIT_DAYS = {"day": 1, "days": 1, "d": 1, "week": 7, "weeks": 7, "w": 7}
_UNIT_MONTHS = {"month": 1, "months": 1, "year": 12, "years": 12, "y": 12}


def parse_date(text: str, ctx: Context, future: bool = False) -> Optional[date]:
    s = " ".join(text.strip().lower().split())
    today = ctx.now().date()
    if s in ("today", "now"):
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s == "yesterday":
        return today - timedelta(days=1)
    m = _ISO.match(s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = _DAY_MONTH.match(s)
        if m:
            d, mo_name, y = int(m.group(1)), m.group(2), m.group(3)
        else:
            m = _MONTH_DAY.match(s)
            if not m:
                return None
            mo_name, d, y = m.group(1), int(m.group(2)), m.group(3)
        mo = MONTHS.get(mo_name.lower())
        if mo is None:
            return None
        if y is None:
            y = today.year
            try:
                if future and date(y, mo, d) < today:
                    y += 1
            except ValueError:
                return None
        y = int(y)
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


_UNTIL = re.compile(r"^(?:how many\s+)?days?\s+(?P<dir>until|till|til|to|since|from)\s+(?P<date>.+)$", re.I)
_SHIFT = re.compile(r"^(?P<base>.+?)\s*(?P<op>[+-])\s*(?P<n>\d+)\s*(?P<unit>[a-z]+)$", re.I)
_IN = re.compile(r"^in\s+(?P<n>\d+)\s*(?P<unit>[a-z]+)$", re.I)
_DIFF = re.compile(r"^(?P<a>.+?)\s+-\s+(?P<b>.+)$")
_WEEKDAY = re.compile(r"^(?:what\s+day\s+(?:is|was|will\s+be)\s+)(?P<date>.+?)\??$", re.I)


def _shift(base: date, sign: int, n: int, unit: str) -> Optional[date]:
    unit = unit.lower()
    if unit in _UNIT_DAYS:
        return base + timedelta(days=sign * n * _UNIT_DAYS[unit])
    if unit in _UNIT_MONTHS:
        return add_months(base, sign * n * _UNIT_MONTHS[unit])
    return None


def _span(days: int) -> str:
    weeks, rest = divmod(abs(days), 7)
    if weeks and rest:
        return f" ({weeks} weeks {rest} days)"
    if weeks:
        return f" ({weeks} weeks)"
    return ""


def _date_answers(q: str, ctx: Context) -> Optional[List[Answer]]:
    today = ctx.now().date()
    m = _UNTIL.match(q)
    if m:
        future = m.group("dir").lower() in ("until", "till", "til", "to")
        target = parse_date(m.group("date"), ctx, future=future)
        if target is None:
            return None
        days = (target - today).days if future else (today - target).days
        word = "until" if future else "since"
        return [Answer(value=f"{days:,} days", copy=str(days),
                       detail=f"{word} {_day(target)}{_span(days)}", kind="time")]
    m = _IN.match(q)
    if m:
        result = _shift(today, 1, int(m.group("n")), m.group("unit"))
        if result is None:
            return None
        return [Answer(value=_day(result), copy=result.isoformat(),
                       detail=f"today + {m.group('n')} {m.group('unit').lower()}", kind="time")]
    m = _SHIFT.match(q)
    if m:
        base = parse_date(m.group("base"), ctx)
        if base is None:
            return None
        sign = 1 if m.group("op") == "+" else -1
        result = _shift(base, sign, int(m.group("n")), m.group("unit"))
        if result is None:
            return None
        return [Answer(value=_day(result), copy=result.isoformat(),
                       detail=f"{_day(base)} {m.group('op')} {m.group('n')} {m.group('unit').lower()}",
                       kind="time")]
    m = _WEEKDAY.match(q)
    if m:
        target = parse_date(m.group("date"), ctx)
        if target is None:
            return None
        return [Answer(value=target.strftime("%A"), copy=target.strftime("%A"),
                       detail=_day(target), kind="time")]
    m = _DIFF.match(q)
    if m:
        a, b = parse_date(m.group("a"), ctx), parse_date(m.group("b"), ctx)
        if a is None or b is None:
            return None
        days = (a - b).days
        return [Answer(value=f"{days:,} days", copy=str(days),
                       detail=f"{_day(a)} − {_day(b)}{_span(days)}", kind="time")]
    return None


def parse(q: str, ctx: Context) -> Optional[List[Answer]]:
    s = " ".join(q.strip().split())
    if not s or len(s) > 80:
        return None
    return _time_answers(s, ctx) or _date_answers(s, ctx)
