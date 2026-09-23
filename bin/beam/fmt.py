"""Number formatting: significant digits, grouping and scientific notation."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SCI_HIGH = Decimal("1e15")
SCI_LOW = Decimal("1e-6")


def to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(f"not a number: {value!r}") from None
    if not d.is_finite():
        raise ValueError("not finite")
    return d


def round_sig(d: Decimal, digits: int) -> Decimal:
    if d == 0:
        return Decimal(0)
    quantum = Decimal(1).scaleb(d.adjusted() - digits + 1)
    return d.quantize(quantum, rounding=ROUND_HALF_UP)


def _sci(d: Decimal, digits: int) -> str:
    mantissa, exponent = format(d, f".{digits - 1}e").split("e")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{int(exponent):+d}"


def plain(value, digits: int = 10) -> str:
    """Ungrouped string for copying: 1234.5, 0.1, 1.5e+20."""
    d = round_sig(to_decimal(value), digits)
    if d == 0:
        return "0"
    if abs(d) >= SCI_HIGH or abs(d) < SCI_LOW:
        return _sci(d, digits)
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def fixed(value, decimals: int) -> str:
    d = to_decimal(value).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    s = format(d, "f")
    return "0" + s[2:] if s.startswith("-0") and d == 0 else s


def group(s: str, style: str) -> str:
    """Insert thousands separators into a plain decimal string."""
    if "e" in s:
        return s
    sign = "-" if s.startswith("-") else ""
    body = s[1:] if sign else s
    whole, dot, frac = body.partition(".")
    if style == "indian" and len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    elif len(whole) > 3:
        whole = f"{int(whole):,}"
    return sign + whole + (dot + frac if dot else "")


def display(value, digits: int = 10, grouping: str = "international", decimals=None) -> str:
    s = fixed(value, decimals) if decimals is not None else plain(value, digits)
    return group(s, grouping)


def resolve_grouping(setting: str, locale: str, currency: str = "") -> str:
    if setting in ("indian", "international"):
        return setting
    if currency == "INR":
        return "indian"
    if currency:
        return "international"
    lang = (locale or "").split(".")[0]
    return "indian" if lang in ("en_IN", "hi_IN") else "international"
