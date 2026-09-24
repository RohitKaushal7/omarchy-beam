"""Currency conversion with a daily-cached rate table (ExchangeRate-API open access)."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, Optional

from . import fmt, net
from .types import Answer, Context

RATES_URL = "https://open.er-api.com/v6/latest/USD"
RETRY_AFTER = 300  # seconds before another fetch after a failed one
ATTRIBUTION = "Rates By Exchange Rate API"

ISO = set("""AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN
BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL
GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KRW KWD
KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO
NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS
SRD SSP STN SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VES VND VUV WST XAF XCD
XOF XPF YER ZAR ZMW ZWL""".split())
SYMBOLS = {"hk$": "HKD", "r$": "BRL", "a$": "AUD", "c$": "CAD", "s$": "SGD", "nz$": "NZD",
           "$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY", "₩": "KRW", "₽": "RUB",
           "₺": "TRY", "₫": "VND", "฿": "THB", "₱": "PHP", "₪": "ILS", "₦": "NGN", "rs": "INR", "rs.": "INR"}
WORDS = {"dollar": "USD", "dollars": "USD", "buck": "USD", "bucks": "USD", "usd": "USD",
         "rupee": "INR", "rupees": "INR", "euro": "EUR", "euros": "EUR", "pound": "GBP",
         "pounds": "GBP", "quid": "GBP", "yen": "JPY", "yuan": "CNY", "rmb": "CNY", "renminbi": "CNY",
         "dirham": "AED", "dirhams": "AED", "won": "KRW", "ruble": "RUB", "rubles": "RUB",
         "rouble": "RUB", "roubles": "RUB", "franc": "CHF", "francs": "CHF", "ringgit": "MYR",
         "baht": "THB", "taka": "BDT", "peso": "MXN", "pesos": "MXN", "lira": "TRY", "rand": "ZAR",
         "riyal": "SAR", "riyals": "SAR", "dinar": "KWD", "shekel": "ILS", "shekels": "ILS"}
DISPLAY_SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥", "KRW": "₩", "RUB": "₽",
                  "TRY": "₺", "VND": "₫", "THB": "฿", "PHP": "₱", "ILS": "₪", "NGN": "₦"}
ZERO_DECIMALS = {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "IDR", "PYG", "UGX", "XAF", "XOF"}
MULTIPLIERS = {"k": Decimal(1000), "m": Decimal(10) ** 6, "lakh": Decimal(10) ** 5, "lakhs": Decimal(10) ** 5,
               "lac": Decimal(10) ** 5, "crore": Decimal(10) ** 7, "crores": Decimal(10) ** 7,
               "cr": Decimal(10) ** 7}
TERRITORY_CURRENCY = {"IN": "INR", "US": "USD", "GB": "GBP", "JP": "JPY", "CA": "CAD", "AU": "AUD",
                      "NZ": "NZD", "SG": "SGD", "AE": "AED", "CH": "CHF", "CN": "CNY", "KR": "KRW",
                      "BR": "BRL", "MX": "MXN", "ZA": "ZAR", "RU": "RUB", "TR": "TRY", "SE": "SEK",
                      "NO": "NOK", "DK": "DKK", "PL": "PLN", "PK": "PKR", "BD": "BDT", "NP": "NPR",
                      "LK": "LKR", "ID": "IDR", "MY": "MYR", "TH": "THB", "PH": "PHP", "VN": "VND",
                      "IL": "ILS", "NG": "NGN", "SA": "SAR", "HK": "HKD", "TW": "TWD"}
EURO_TERRITORIES = {"AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE", "IT", "LT", "LU",
                    "LV", "MT", "NL", "PT", "SI", "SK"}

_SYM_ALT = "|".join(re.escape(s) for s in sorted(SYMBOLS, key=len, reverse=True))
_AMOUNT = re.compile(rf"^(?P<pre>{_SYM_ALT})?\s*(?P<num>\d[\d,]*(?:\.\d+)?|\.\d+)\s*"
                     rf"(?P<mult>k|m|lakhs?|lac|crores?|cr)?\b\s*(?P<post>.*?)\s*$", re.I)
_SEPARATORS = (" in ", " to ", " as ", " into ", " -> ", " → ", " = ")


def http_fetch(url: str = RATES_URL, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "beam-omarchy/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return net.read_json(resp)


class RateStore:
    """USD-based rate table cached on disk; refreshed in the background."""

    def __init__(self, cache_path: str, refresh_hours: int = 24,
                 fetch: Callable[[], dict] = http_fetch, clock: Callable[[], float] = time.time):
        self.cache_path = cache_path
        self.refresh_hours = refresh_hours
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._fetching = False
        self._data: Optional[dict] = None
        self.last_failure: Optional[float] = None
        self.listeners: List[Callable[[bool], None]] = []  # told after every background refresh
        self._load()

    def _load(self) -> None:
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("rates"), dict) and isinstance(data.get("fetched_at"), (int, float)):
                self._data = data
        except (OSError, ValueError, AttributeError):
            self._data = None

    def rates(self) -> Optional[Dict[str, float]]:
        return self._data["rates"] if self._data else None

    def age_seconds(self) -> Optional[float]:
        return self._clock() - self._data["fetched_at"] if self._data else None

    def stale(self) -> bool:
        age = self.age_seconds()
        return age is None or age > self.refresh_hours * 3600

    def recently_failed(self) -> bool:
        return self.last_failure is not None and self._clock() - self.last_failure < RETRY_AFTER

    def refresh_now(self) -> bool:
        ok = self._refresh()
        self.last_failure = None if ok else self._clock()
        return ok

    def _refresh(self) -> bool:
        try:
            payload = self._fetch()
            rates = payload.get("rates") if isinstance(payload, dict) else None
            if payload.get("result") != "success" or not isinstance(rates, dict) or rates.get("USD") != 1:
                return False
            data = {"rates": {k: float(v) for k, v in rates.items() if isinstance(v, (int, float)) and v > 0},
                    "fetched_at": self._clock(),
                    "updated_at": payload.get("time_last_update_unix")}
        except Exception:
            return False
        self._data = data
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self.cache_path)
        except OSError:
            pass
        return True

    def refresh_async(self, on_done: Optional[Callable[[bool], None]] = None) -> None:
        with self._lock:
            if self._fetching:
                return
            self._fetching = True

        def run():
            ok = self.refresh_now()
            with self._lock:
                self._fetching = False
            for listener in list(self.listeners) + ([on_done] if on_done else []):
                listener(ok)

        threading.Thread(target=run, daemon=True).start()


def code_for(word: str) -> Optional[str]:
    w = word.strip().lower()
    if not w:
        return None
    if w in SYMBOLS:
        return SYMBOLS[w]
    if w in WORDS:
        return WORDS[w]
    if len(w) == 3 and w.upper() in ISO:
        return w.upper()
    return None


def home_currency(ctx: Context) -> str:
    if ctx.settings.home_currency != "auto" and ctx.settings.home_currency in ISO:
        return ctx.settings.home_currency
    lang = (ctx.locale or "").split(".")[0]
    territory = lang.split("_")[1].upper() if "_" in lang else ""
    if territory in EURO_TERRITORIES:
        return "EUR"
    return TERRITORY_CURRENCY.get(territory, "USD")


def _age_text(store: RateStore) -> str:
    age = store.age_seconds() or 0
    if age < 3600:
        return "rates <1 h old"
    if age < 86400:
        return f"rates {int(age // 3600)} h old"
    fetched = time.localtime(store._data["fetched_at"])
    return "rates from " + time.strftime("%-d %b", fetched)


def _split(s: str):
    low = s.lower()
    for sep in _SEPARATORS:
        idx = low.rfind(sep)
        if idx > 0:
            return s[:idx].strip(), s[idx + len(sep):].strip()
    return s, None


def format_money(value: Decimal, code: str, ctx: Context) -> str:
    decimals = 0 if code in ZERO_DECIMALS else 2
    grouping = fmt.resolve_grouping(ctx.settings.grouping, ctx.locale, code)
    number = fmt.display(value, grouping=grouping, decimals=decimals)
    symbol = DISPLAY_SYMBOL.get(code)
    return f"{symbol}{number}" if symbol else f"{code} {number}"


def parse(q: str, ctx: Context) -> Optional[List[Answer]]:
    s = q.strip()
    if not s or len(s) > 60 or not any(ch.isdigit() for ch in s) or ctx.rates is None:
        return None
    head, dst_word = _split(s)
    dst = code_for(dst_word) if dst_word else None
    if dst_word and dst is None:
        return None
    m = _AMOUNT.match(head)
    if not m:
        return None
    pre = code_for(m.group("pre")) if m.group("pre") else None
    post = code_for(m.group("post")) if m.group("post") else None
    if m.group("post") and post is None:
        return None
    if pre and post and pre != post:
        return None
    src = pre or post
    if src is None:
        return None
    try:
        amount = Decimal(m.group("num").replace(",", ""))
    except InvalidOperation:
        return None
    if m.group("mult"):
        amount *= MULTIPLIERS[m.group("mult").lower()]
    home = home_currency(ctx)
    target = dst or (home if src != home else ("USD" if home != "USD" else "EUR"))
    if target == src:
        return None
    label = f"{fmt.display(amount, grouping=fmt.resolve_grouping(ctx.settings.grouping, ctx.locale, src))} {src} → {target}"
    store: RateStore = ctx.rates
    rates = store.rates()
    if rates is None:
        if store.recently_failed():
            return [Answer(value="Rates unavailable", copy="", detail=f"{label} · offline, will retry",
                           kind="currency")]
        store.refresh_async()
        return [Answer(value="Fetching rates…", copy="", detail=label, kind="currency", pending=True)]
    if store.stale() and not store.recently_failed():
        store.refresh_async()
    if src not in rates or target not in rates:
        return None
    result = amount / Decimal(str(rates[src])) * Decimal(str(rates[target]))
    decimals = 0 if target in ZERO_DECIMALS else 2
    return [Answer(value=format_money(result, target, ctx), copy=fmt.fixed(result, decimals),
                   detail=f"{label} · {_age_text(store)} · {ATTRIBUTION}", kind="currency")]
