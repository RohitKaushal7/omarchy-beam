"""Unit conversion: `5 ft in cm`, `72f to c`, `3.2 GB in MiB`, `5'11\" in cm`."""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from . import fmt
from .types import Answer, Context

D = Decimal
PI = D("3.14159265358979323846264338327950288")

# symbol: (dimension, factor to the dimension's base unit, aliases)
UNITS: Dict[str, Tuple[str, Decimal, Tuple[str, ...]]] = {
    # length (metre)
    "nm": ("length", D("1e-9"), ("nanometer", "nanometers", "nanometre", "nanometres")),
    "µm": ("length", D("1e-6"), ("um", "micron", "microns", "micrometer", "micrometers")),
    "mm": ("length", D("0.001"), ("millimeter", "millimeters", "millimetre", "millimetres")),
    "cm": ("length", D("0.01"), ("centimeter", "centimeters", "centimetre", "centimetres")),
    "m": ("length", D("1"), ("meter", "meters", "metre", "metres")),
    "km": ("length", D("1000"), ("kilometer", "kilometers", "kilometre", "kilometres", "kms")),
    "in": ("length", D("0.0254"), ("inch", "inches", '"')),
    "ft": ("length", D("0.3048"), ("foot", "feet", "'")),
    "yd": ("length", D("0.9144"), ("yard", "yards", "yds")),
    "mi": ("length", D("1609.344"), ("mile", "miles")),
    "nmi": ("length", D("1852"), ("nautical mile", "nautical miles")),
    # mass (kilogram)
    "mg": ("mass", D("0.000001"), ("milligram", "milligrams")),
    "g": ("mass", D("0.001"), ("gram", "grams", "gm", "gms")),
    "kg": ("mass", D("1"), ("kilogram", "kilograms", "kilo", "kilos", "kgs")),
    "t": ("mass", D("1000"), ("tonne", "tonnes", "metric ton", "metric tons")),
    "lb": ("mass", D("0.45359237"), ("lbs", "pound", "pounds")),
    "oz": ("mass", D("0.028349523125"), ("ounce", "ounces")),
    "st": ("mass", D("6.35029318"), ("stone", "stones")),
    # volume (litre)
    "ml": ("volume", D("0.001"), ("milliliter", "milliliters", "millilitre", "millilitres", "cc", "cm3")),
    "l": ("volume", D("1"), ("liter", "liters", "litre", "litres", "ltr")),
    "m³": ("volume", D("1000"), ("m3", "cubic meter", "cubic meters", "cubic metre", "cubic metres")),
    "tsp": ("volume", D("0.00492892159375"), ("teaspoon", "teaspoons")),
    "tbsp": ("volume", D("0.01478676478125"), ("tablespoon", "tablespoons")),
    "fl oz": ("volume", D("0.0295735295625"), ("floz", "fluid ounce", "fluid ounces")),
    "cup": ("volume", D("0.2365882365"), ("cups",)),
    "pt": ("volume", D("0.473176473"), ("pint", "pints")),
    "qt": ("volume", D("0.946352946"), ("quart", "quarts")),
    "gal": ("volume", D("3.785411784"), ("gallon", "gallons")),
    # area (square metre)
    "cm²": ("area", D("0.0001"), ("cm2", "sq cm", "square centimeter", "square centimeters")),
    "m²": ("area", D("1"), ("m2", "sqm", "sq m", "square meter", "square meters", "square metre", "square metres")),
    "km²": ("area", D("1000000"), ("km2", "sq km", "square kilometer", "square kilometers")),
    "ha": ("area", D("10000"), ("hectare", "hectares")),
    "acre": ("area", D("4046.8564224"), ("acres", "ac")),
    "ft²": ("area", D("0.09290304"), ("ft2", "sqft", "sq ft", "square foot", "square feet")),
    "in²": ("area", D("0.00064516"), ("in2", "sq in", "square inch", "square inches")),
    "mi²": ("area", D("2589988.110336"), ("mi2", "sq mi", "square mile", "square miles")),
    # speed (metre per second)
    "m/s": ("speed", D("1"), ("mps", "meters per second", "metres per second")),
    "km/h": ("speed", D("1") / D("3.6"), ("kmh", "kph", "kmph", "km/hr", "kilometers per hour")),
    "mph": ("speed", D("0.44704"), ("mi/h", "miles per hour")),
    "kn": ("speed", D("1852") / D("3600"), ("knot", "knots", "kt")),
    "ft/s": ("speed", D("0.3048"), ("fps", "feet per second")),
    # duration (second)
    "ms": ("duration", D("0.001"), ("millisecond", "milliseconds", "msec")),
    "s": ("duration", D("1"), ("sec", "secs", "second", "seconds")),
    "min": ("duration", D("60"), ("mins", "minute", "minutes")),
    "h": ("duration", D("3600"), ("hr", "hrs", "hour", "hours")),
    "day": ("duration", D("86400"), ("days", "d")),
    "week": ("duration", D("604800"), ("weeks", "wk", "wks")),
    "month": ("duration", D("2629746"), ("months", "mo")),
    "year": ("duration", D("31556952"), ("years", "yr", "yrs")),
    # data (byte)
    "bit": ("data", D("0.125"), ("bits",)),
    "B": ("data", D("1"), ("byte", "bytes")),
    "KB": ("data", D("1e3"), ("kilobyte", "kilobytes")),
    "MB": ("data", D("1e6"), ("megabyte", "megabytes")),
    "GB": ("data", D("1e9"), ("gigabyte", "gigabytes")),
    "TB": ("data", D("1e12"), ("terabyte", "terabytes")),
    "PB": ("data", D("1e15"), ("petabyte", "petabytes")),
    "KiB": ("data", D(1024), ("kibibyte", "kibibytes")),
    "MiB": ("data", D(1024) ** 2, ("mebibyte", "mebibytes")),
    "GiB": ("data", D(1024) ** 3, ("gibibyte", "gibibytes")),
    "TiB": ("data", D(1024) ** 4, ("tebibyte", "tebibytes")),
    # energy (joule)
    "J": ("energy", D("1"), ("joule", "joules")),
    "kJ": ("energy", D("1000"), ("kilojoule", "kilojoules")),
    "cal": ("energy", D("4.184"), ("calorie", "calories")),
    "kcal": ("energy", D("4184"), ("kilocalorie", "kilocalories", "kcals")),
    "Wh": ("energy", D("3600"), ("watt hour", "watt hours")),
    "kWh": ("energy", D("3600000"), ("kilowatt hour", "kilowatt hours", "units")),
    # pressure (pascal)
    "Pa": ("pressure", D("1"), ("pascal", "pascals")),
    "kPa": ("pressure", D("1000"), ("kilopascal", "kilopascals")),
    "bar": ("pressure", D("100000"), ("bars",)),
    "atm": ("pressure", D("101325"), ("atmosphere", "atmospheres")),
    "psi": ("pressure", D("6894.757293168"), ()),
    "mmHg": ("pressure", D("133.322387415"), ("torr",)),
    # angle (radian)
    "rad": ("angle", D("1"), ("radian", "radians")),
    "°": ("angle", PI / 180, ("deg", "degree", "degrees")),
    "grad": ("angle", PI / 200, ("gon", "gradian", "gradians")),
    "turn": ("angle", 2 * PI, ("turns", "rev", "revolution", "revolutions")),
    # temperature (handled specially; factor unused)
    "°C": ("temperature", D(1), ("c", "celsius", "centigrade", "degc", "deg c")),
    "°F": ("temperature", D(1), ("f", "fahrenheit", "degf", "deg f")),
    "K": ("temperature", D(1), ("k", "kelvin", "kelvins")),
}

# Single letters that are only a temperature when the other side is one too.
_AMBIGUOUS = {"c", "f", "k"}

DEFAULT_TARGETS = {
    "nm": ["µm"], "µm": ["mm"], "mm": ["in"], "cm": ["in"], "m": ["ft"], "km": ["mi"],
    "in": ["cm"], "ft": ["m", "cm"], "yd": ["m"], "mi": ["km"], "nmi": ["km"],
    "mg": ["g"], "g": ["oz"], "kg": ["lb"], "t": ["lb"], "lb": ["kg"], "oz": ["g"], "st": ["kg"],
    "ml": ["fl oz"], "l": ["gal"], "m³": ["l"], "tsp": ["ml"], "tbsp": ["ml"], "fl oz": ["ml"],
    "cup": ["ml"], "pt": ["l"], "qt": ["l"], "gal": ["l"],
    "cm²": ["in²"], "m²": ["ft²"], "km²": ["mi²"], "ha": ["acre"], "acre": ["ha"],
    "ft²": ["m²"], "in²": ["cm²"], "mi²": ["km²"],
    "m/s": ["km/h"], "km/h": ["mph"], "mph": ["km/h"], "kn": ["km/h"], "ft/s": ["m/s"],
    "ms": ["s"], "s": ["min"], "min": ["h"], "h": ["min"], "day": ["h"], "week": ["day"],
    "month": ["day"], "year": ["day"],
    "bit": ["B"], "B": ["KiB"], "KB": ["KiB"], "MB": ["MiB"], "GB": ["GiB"], "TB": ["TiB"],
    "PB": ["TiB"], "KiB": ["KB"], "MiB": ["MB"], "GiB": ["GB"], "TiB": ["TB"],
    "J": ["cal"], "kJ": ["kcal"], "cal": ["J"], "kcal": ["kJ"], "Wh": ["kJ"], "kWh": ["kJ"],
    "Pa": ["psi"], "kPa": ["psi"], "bar": ["psi"], "atm": ["kPa"], "psi": ["kPa"], "mmHg": ["kPa"],
    "rad": ["°"], "°": ["rad"], "grad": ["°"], "turn": ["°"],
    "°C": ["°F"], "°F": ["°C"], "K": ["°C"],
}

ALIASES: Dict[str, str] = {}
for _sym, (_dim, _factor, _aliases) in UNITS.items():
    for _name in (_sym, *_aliases):
        ALIASES.setdefault(_name.lower(), _sym)

_NUMBER = r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?(?:e[-+]?\d+)?"
_HEAD = re.compile(rf"^\s*(?P<num>{_NUMBER})\s*(?P<rest>.+?)\s*$", re.I)
_FEET_INCHES = re.compile(
    r"^\s*(?P<ft>\d+(?:\.\d+)?)\s*(?:'|ft|feet|foot)\s*(?P<in>\d+(?:\.\d+)?)\s*(?:\"|in|inch|inches)?"
    r"(?:\s+(?:in|to|as|into)\s+(?P<to>.+?))?\s*$", re.I)
_SEPARATORS = (" in ", " to ", " as ", " into ", " -> ", " → ", " = ", "->", "→", "=")


def lookup(name: str) -> Optional[str]:
    name = name.strip().lower().replace("degrees ", "deg ").replace("degree ", "deg ")
    if name.startswith("°") and len(name) > 1:
        name = name[1:].strip()
        return {"c": "°C", "f": "°F", "k": "K"}.get(name, ALIASES.get(name))
    return ALIASES.get(name)


def _to_base(value: Decimal, sym: str) -> Decimal:
    dim, factor, _ = UNITS[sym]
    if dim != "temperature":
        return value * factor
    if sym == "°C":
        return value + D("273.15")
    if sym == "°F":
        return (value - 32) * 5 / 9 + D("273.15")
    return value


def _from_base(value: Decimal, sym: str) -> Decimal:
    dim, factor, _ = UNITS[sym]
    if dim != "temperature":
        return value / factor
    if sym == "°C":
        return value - D("273.15")
    if sym == "°F":
        return (value - D("273.15")) * 9 / 5 + 32
    return value


def convert(value: Decimal, src: str, dst: str) -> Decimal:
    if UNITS[src][0] != UNITS[dst][0]:
        raise ValueError("incompatible units")
    return _from_base(_to_base(value, src), dst)


def _split_target(rest: str) -> Tuple[str, Optional[str]]:
    low = rest.lower()
    for sep in _SEPARATORS:
        idx = low.rfind(sep)
        if idx > 0:
            return rest[:idx].strip(), rest[idx + len(sep):].strip()
    return rest.strip(), None


def _resolve(src_name: str, dst_name: Optional[str]) -> Optional[Tuple[str, Optional[str]]]:
    src = lookup(src_name)
    dst = lookup(dst_name) if dst_name else None
    if src is None or (dst_name and dst is None):
        return None
    src_low, dst_low = src_name.strip().lower(), (dst_name or "").strip().lower()
    src_ambiguous, dst_ambiguous = src_low in _AMBIGUOUS, dst_low in _AMBIGUOUS
    if src_ambiguous or dst_ambiguous:
        # "72f to c": both sides must be temperatures; "5 k" alone is not a unit.
        if dst is None or UNITS[src][0] != "temperature" or UNITS[dst][0] != "temperature":
            return None
    if dst is not None and UNITS[src][0] != UNITS[dst][0]:
        return None
    return src, dst


def _answers(value: Decimal, src: str, targets: List[str], label: str, ctx: Context) -> List[Answer]:
    digits = ctx.settings.significant_digits
    grouping = fmt.resolve_grouping(ctx.settings.grouping, ctx.locale)
    out = []
    for dst in targets:
        result = convert(value, src, dst)
        sep = "" if dst in ("°", "°C", "°F", "'", '"') else " "
        out.append(Answer(value=f"{fmt.display(result, digits, grouping)}{sep}{dst}",
                          copy=fmt.plain(result, digits), detail=f"{label} → {dst}", kind="units"))
    return out


def parse(q: str, ctx: Context) -> Optional[List[Answer]]:
    s = q.strip()
    if not s or len(s) > 80 or not any(ch.isdigit() for ch in s):
        return None
    m = _FEET_INCHES.match(s)
    if m:
        inches = D(m.group("ft")) * 12 + D(m.group("in"))
        dst = lookup(m.group("to")) if m.group("to") else "cm"
        if dst is None or UNITS[dst][0] != "length":
            return None
        label = f"{m.group('ft')}′{m.group('in')}″"
        return _answers(inches, "in", [dst], label, ctx)
    m = _HEAD.match(s)
    if not m or not m.group("num") or not any(ch.isdigit() for ch in m.group("num")):
        return None
    try:
        value = D(m.group("num").replace(",", ""))
    except Exception:
        return None
    src_name, dst_name = _split_target(m.group("rest"))
    resolved = _resolve(src_name, dst_name)
    if resolved is None:
        return None
    src, dst = resolved
    targets = [dst] if dst else DEFAULT_TARGETS.get(src, [])
    if not targets:
        return None
    return _answers(value, src, targets, f"{fmt.plain(value)} {src}", ctx)
