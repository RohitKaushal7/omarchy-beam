"""JSON-lines server the Beam plugin talks to over stdin/stdout."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional, TextIO

from . import timeparse
from .answer import answer
from .jev import AuthError, Catalog, JevClient, read_key
from .types import Context, Settings

MAX_LINE = 1 << 20  # 1 MiB
MAX_RECENT = 20
RECENT_FIELDS = ("key", "kind", "icon", "iconFont", "appIcon", "appId", "label", "detail", "action", "target", "url")


class Server:
    def __init__(self, out: TextIO, ctx: Context, state_dir: str, cache_dir: str,
                 jev_client: Optional[JevClient] = None, clock: Callable[[], float] = time.monotonic,
                 exit_fn: Callable[[int], None] = os._exit):
        self.out = out
        self.ctx = ctx
        self._write_lock = threading.Lock()
        self._clock = clock
        self._exit = exit_fn
        self.last_activity = clock()
        self.recent_path = os.path.join(state_dir, "recent.json")
        self.catalog = Catalog([])
        self.latest_answer: Optional[tuple] = None  # (id, query) of the newest answer request
        self.jev = jev_client or JevClient(
            lambda: read_key(self.ctx.settings.jev_key_file),
            cache_path=os.path.join(cache_dir, "jev-cache.json"),
            usage_path=os.path.join(state_dir, "usage.jsonl"),
            cache_size=ctx.settings.jev_cache_size)
        self._jev_slot: Optional[tuple] = None
        self._jev_latest = -1
        self._jev_event = threading.Event()
        threading.Thread(target=self._jev_worker, daemon=True).start()
        if ctx.rates is not None:
            ctx.rates.listeners.append(self._rates_refreshed)

    # ── output ───────────────────────────────────────────────────────────
    def send(self, obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        with self._write_lock:
            try:
                self.out.write(line)
                self.out.flush()
            except (BrokenPipeError, ValueError):
                self._exit(0)

    # ── input ────────────────────────────────────────────────────────────
    def handle(self, line: str) -> None:
        self.last_activity = self._clock()
        if len(line) > MAX_LINE:
            self.send({"op": "error", "error": "line too long"})
            return
        try:
            msg = json.loads(line)
            op = msg["op"]
        except (ValueError, KeyError, TypeError):
            self.send({"op": "error", "error": "bad message"})
            return
        handler = getattr(self, f"op_{op}", None)
        if handler is None:
            self.send({"op": "error", "error": f"unknown op {op!r}"})
            return
        handler(msg)

    def op_ping(self, msg: dict) -> None:
        self.send({"op": "pong"})

    def op_config(self, msg: dict) -> None:
        self.ctx.settings = Settings.from_config(msg.get("settings"))
        if self.ctx.rates is not None:
            self.ctx.rates.refresh_hours = self.ctx.settings.rates_refresh_hours
        self.send({"op": "config", "jev": self.jev_status()})

    def op_status(self, msg: dict) -> None:
        age = self.ctx.rates.age_seconds() if self.ctx.rates is not None else None
        self.send({"op": "status", "jev": self.jev_status(), "ratesAgeSeconds": age,
                   "catalog": len(self.catalog)})

    def op_answer(self, msg: dict) -> None:
        rid, q = msg.get("id"), str(msg.get("q") or "")
        self.latest_answer = (rid, q)
        results = answer(q, self.ctx)
        self.send({"op": "answer", "id": rid, "answers": [a.to_json() for a in results]})

    def op_used(self, msg: dict) -> None:
        try:
            self.ctx.ans = Decimal(str(msg.get("copy", "")).replace(",", ""))
        except InvalidOperation:
            pass

    def op_recent(self, msg: dict) -> None:
        """Remember an activated row; the plugin reads recent.json directly."""
        entry = msg.get("entry") if isinstance(msg.get("entry"), dict) else {}
        if not entry.get("key"):
            return
        entry = {k: str(entry.get(k) or "") for k in RECENT_FIELDS}
        try:
            with open(self.recent_path, encoding="utf-8") as f:
                recent = [r for r in json.load(f) if isinstance(r, dict)]
        except (OSError, ValueError, TypeError):
            recent = []
        recent = [entry] + [r for r in recent if r.get("key") != entry["key"]]
        try:
            os.makedirs(os.path.dirname(self.recent_path), exist_ok=True)
            tmp = self.recent_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(recent[:MAX_RECENT], f, ensure_ascii=False)
            os.replace(tmp, self.recent_path)
        except OSError:
            pass

    def op_catalog(self, msg: dict) -> None:
        items = msg.get("items") if isinstance(msg.get("items"), list) else []
        self.catalog = Catalog(items)
        self.send({"op": "catalog", "count": len(self.catalog), "hash": self.catalog.hash})

    def op_jev(self, msg: dict) -> None:
        rid, q = msg.get("id"), str(msg.get("q") or "")
        self._jev_latest = rid
        if not self.ctx.settings.jev_enabled:
            self.send({"op": "jev", "id": rid, "pick": None, "status": "off"})
            return
        hit, pick = self.jev.cached(q, self.catalog)
        if hit:
            self.send({"op": "jev", "id": rid, "pick": self._pick_json(pick), "cached": True})
            return
        self._jev_slot = (rid, q, self.catalog)  # newest request wins the slot
        self._jev_event.set()

    # ── background work ──────────────────────────────────────────────────
    def jev_status(self) -> str:
        return "off" if not self.ctx.settings.jev_enabled else self.jev.status()

    @staticmethod
    def _pick_json(pick) -> Optional[dict]:
        return {"key": pick.key, "p": pick.p} if pick else None

    def _jev_worker(self) -> None:
        while True:
            self._jev_event.wait()
            self._jev_event.clear()
            slot, self._jev_slot = self._jev_slot, None
            if slot is None:
                continue
            rid, q, catalog = slot
            try:
                pick, cached = self.jev.pick(q, catalog)
            except AuthError:
                self.send({"op": "jev", "id": rid, "pick": None, "status": "auth-failed"})
                continue
            except Exception as e:  # never let one bad reply stop the worker
                print(f"beam: jev lookup failed: {e!r}", file=sys.stderr)
                pick, cached = None, False
            if rid == self._jev_latest:  # a newer query makes this reply stale
                self.send({"op": "jev", "id": rid, "pick": self._pick_json(pick), "cached": cached})

    def _rates_refreshed(self, ok: bool) -> None:
        latest = self.latest_answer
        if not ok or latest is None:
            return
        rid, q = latest
        results = answer(q, self.ctx)
        if any(a.kind == "currency" for a in results):
            self.send({"op": "answer", "id": rid, "answers": [a.to_json() for a in results], "update": True})

    def check_idle(self) -> bool:
        idle = self._clock() - self.last_activity
        if idle >= self.ctx.settings.idle_exit_minutes * 60:
            self._exit(0)
            return True
        return False


def serve(stdin: TextIO, stdout: TextIO, ctx: Context, state_dir: str, cache_dir: str) -> int:
    server = Server(stdout, ctx, state_dir, cache_dir)
    threading.Thread(target=timeparse.warm_up, daemon=True).start()

    def watchdog():
        while not server.check_idle():
            time.sleep(15)

    threading.Thread(target=watchdog, daemon=True).start()
    server.send({"op": "ready", "version": __import__("beam").VERSION})
    for line in stdin:
        if line.strip():
            server.handle(line)
    return 0
