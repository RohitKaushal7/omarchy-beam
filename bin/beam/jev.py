"""Jev (TypeSafe System One) picks: which app or action does the query mean?"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

API_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/") + "/v1/systemone"
MODEL = "jev-latest"
NONE = "(none of these)"
SLICE = 254  # a Choice allows 255 options; one is kept for NONE
ACCEPT = 0.35
MAX_QUERY = 200
USD_PER_M_INPUT_TOKENS = 0.042
INSTRUCTIONS = ("A person typed `request` into their desktop launcher. Which of these apps or system "
                "actions do they want to open or run? Pick the one that does what they asked for.")


class JevError(Exception):
    pass


class AuthError(JevError):
    pass


@dataclass(frozen=True)
class Pick:
    key: str
    p: float


class Catalog:
    """Launcher items as Choice options; the hash keys the cache."""

    def __init__(self, items: List[dict]):
        self.text_to_key: Dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict) or not item.get("key") or not item.get("label"):
                continue
            text = option_text(str(item["label"]), str(item.get("path") or ""))
            self.text_to_key.setdefault(text, str(item["key"]))
        self.texts = list(self.text_to_key)
        self.hash = hashlib.sha1("\n".join(f"{t}\t{k}" for t, k in self.text_to_key.items())
                                 .encode()).hexdigest()[:16]

    def __len__(self) -> int:
        return len(self.texts)


def option_text(label: str, path: str) -> str:
    text = f"{label} — {path}" if path else label
    return " ".join(text.split())[:120]


def read_key(key_file: str) -> Tuple[Optional[str], str]:
    """(key, source) where source is env, file or no-key. The key is never logged."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key, "env"
    try:
        with open(os.path.expanduser(key_file), encoding="utf-8") as f:
            key = f.read().strip()
    except OSError:
        key = ""
    return (key, "file") if key else (None, "no-key")


def http_post(key: str, payload: dict, timeout: float = 6.0) -> dict:
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json",
                                          "User-Agent": "beam-omarchy/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        e.close()
        if e.code in (401, 403):
            raise AuthError(f"HTTP {e.code}") from None
        raise JevError(f"HTTP {e.code}") from None
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as e:
        raise JevError(str(e)) from None


class JevClient:
    def __init__(self, key_provider: Callable[[], Tuple[Optional[str], str]],
                 post: Callable[[str, dict], dict] = http_post, cache_path: Optional[str] = None,
                 usage_path: Optional[str] = None, cache_size: int = 500,
                 clock: Callable[[], float] = time.time):
        self._key_provider = key_provider
        self._post = post
        self._cache_path = cache_path
        self._usage_path = usage_path
        self._cache_size = cache_size
        self._clock = clock
        self._cache: "OrderedDict[str, Optional[Pick]]" = OrderedDict()
        self._lock = threading.Lock()
        self.auth_failed = False
        self._load_cache()

    # ── cache ────────────────────────────────────────────────────────────
    def _load_cache(self) -> None:
        if not self._cache_path:
            return
        try:
            with open(self._cache_path, encoding="utf-8") as f:
                entries = json.load(f).get("entries", [])
            for ck, key, p in entries[-self._cache_size:]:
                self._cache[ck] = Pick(key, float(p)) if key else None
        except (OSError, ValueError, TypeError, AttributeError):
            self._cache.clear()

    def _save_cache(self) -> None:
        if not self._cache_path:
            return
        entries = [[ck, pick.key if pick else None, pick.p if pick else 0] for ck, pick in self._cache.items()]
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            tmp = self._cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"entries": entries}, f)
            os.replace(tmp, self._cache_path)
        except OSError:
            pass

    @staticmethod
    def normalise(query: str) -> str:
        return " ".join(str(query).lower().split())[:MAX_QUERY]

    def cached(self, query: str, catalog: Catalog):
        """(True, pick) on a hit, (False, None) on a miss."""
        ck = f"{catalog.hash}|{self.normalise(query)}"
        with self._lock:
            if ck in self._cache:
                self._cache.move_to_end(ck)
                return True, self._cache[ck]
        return False, None

    def _remember(self, query: str, catalog: Catalog, pick: Optional[Pick]) -> None:
        if self._cache_size <= 0:
            return
        ck = f"{catalog.hash}|{self.normalise(query)}"
        with self._lock:
            self._cache[ck] = pick
            self._cache.move_to_end(ck)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
            self._save_cache()

    # ── status ───────────────────────────────────────────────────────────
    def status(self) -> str:
        if self.auth_failed:
            return "auth-failed"
        return self._key_provider()[1]

    # ── calls ────────────────────────────────────────────────────────────
    def _ask(self, key: str, query: str, texts: List[str]) -> Tuple[Dict[str, float], int]:
        criteria = {t: None for t in texts}
        criteria[NONE] = "None of these matches what the person wants."
        payload = {"model": MODEL, "state": {"request": query},
                   "questions": {"target": {"type": "choice", "instructions": INSTRUCTIONS,
                                            "criteria": criteria}}}
        result = self._post(key, payload)
        try:
            answer = result["answers"]["target"]
            probs = answer.get("probabilities") or {answer["choice"]: 1.0}
            tokens = int((result.get("usage") or {}).get("input_tokens") or 0)
            # Only the options we offered count; anything else is not a pick.
            return {str(k): float(v) for k, v in probs.items() if str(k) in criteria}, tokens
        except (KeyError, TypeError, ValueError, AttributeError):
            raise JevError("unexpected response") from None

    @staticmethod
    def _best(probs: Dict[str, float]) -> Optional[Tuple[str, float]]:
        ranked = sorted(((p, t) for t, p in probs.items() if t != NONE), reverse=True)
        return (ranked[0][1], ranked[0][0]) if ranked else None

    def pick(self, query: str, catalog: Catalog) -> Tuple[Optional[Pick], bool]:
        """(pick or None, cached). Raises AuthError on a rejected key."""
        query = self.normalise(query)
        hit, pick = self.cached(query, catalog)
        if hit:
            self._log(cached=True, picked=pick is not None)
            return pick, True
        key, _source = self._key_provider()
        if not key or self.auth_failed or not len(catalog):
            return None, False
        started = self._clock()
        slices = [catalog.texts[i:i + SLICE] for i in range(0, len(catalog), SLICE)]
        tokens, rounds = 0, 1
        try:
            with ThreadPoolExecutor(max_workers=len(slices)) as pool:
                results = list(pool.map(lambda texts: self._ask(key, query, texts), slices))
            best = []
            for probs, t in results:
                tokens += t
                b = self._best(probs)
                if b and b[1] >= ACCEPT:
                    best.append(b)
            texts = list(dict.fromkeys(t for t, _ in sorted(best, key=lambda b: -b[1])))
            chosen: Optional[Tuple[str, float]] = None
            if len(texts) == 1:
                chosen = max(best, key=lambda b: b[1])
            elif len(texts) > 1:
                rounds = 2
                probs, t = self._ask(key, query, texts)
                tokens += t
                b = self._best(probs)
                chosen = b if b and b[1] >= ACCEPT else None
        except AuthError:
            self.auth_failed = True
            self._log(error="auth")
            raise
        except JevError as e:
            self._log(error=str(e)[:80], ms=round((self._clock() - started) * 1000))
            return None, False
        pick = Pick(catalog.text_to_key[chosen[0]], round(chosen[1], 4)) if chosen else None
        self._remember(query, catalog, pick)
        self._log(slices=len(slices), rounds=rounds, tokens=tokens, picked=pick is not None,
                  ms=round((self._clock() - started) * 1000))
        return pick, False

    # ── usage log (no query text is ever written) ────────────────────────
    def _log(self, **fields) -> None:
        if not self._usage_path:
            return
        record = {"ts": round(self._clock(), 3), "cached": False, **fields}
        try:
            os.makedirs(os.path.dirname(self._usage_path), exist_ok=True)
            with open(self._usage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass


def format_stats(usage_path: str) -> str:
    try:
        with open(usage_path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        rows = []
    if not rows:
        return f"No Jev usage recorded yet ({usage_path})."
    calls = [r for r in rows if not r.get("cached") and not r.get("error")]
    hits = [r for r in rows if r.get("cached")]
    errors = [r for r in rows if r.get("error")]
    tokens = sum(int(r.get("tokens") or 0) for r in calls)
    latencies = sorted(int(r["ms"]) for r in calls if "ms" in r)
    picked = sum(1 for r in rows if r.get("picked"))
    lines = [
        f"Jev usage ({usage_path})",
        f"  lookups     {len(rows)}  ({len(calls)} API calls, {len(hits)} cache hits"
        f" = {len(hits) / len(rows):.0%})",
        f"  picked      {picked}  (a ✦ row was offered)",
        f"  errors      {len(errors)}",
        f"  tokens      {tokens:,} in  (≈ ${tokens * USD_PER_M_INPUT_TOKENS / 1e6:.4f})",
    ]
    if latencies:
        lines.append(f"  latency     p50 {latencies[len(latencies) // 2]} ms, max {latencies[-1]} ms")
    return "\n".join(lines)
