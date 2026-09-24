"""Bounded HTTP for the helper: one total deadline, no redirects, capped bodies.

Each request gets a watchdog that shuts the socket down when its deadline
passes, so a peer that trickles bytes cannot hold a lookup or the rate
refresh open past it; per-read socket timeouts alone would not stop that.
Redirects are errors: both endpoints are fixed, and following one would
carry the Authorization header to another host.
"""

from __future__ import annotations

import http.client
import socket
import ssl
import threading
import urllib.parse
from typing import Dict, Optional

from .store import loads

# The rate table is ~4 KB and a Jev answer for 255 options ~40 KB.
MAX_BODY = 256 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}  # plain http only for local test servers


class ResponseTooLarge(ValueError):
    pass


class DeadlineExceeded(TimeoutError):
    pass


class HTTPStatusError(OSError):
    def __init__(self, code: int):
        super().__init__(f"HTTP {code}")
        self.code = code


class _Watchdog:
    """Shuts the connection's socket down once `seconds` have passed."""

    def __init__(self, seconds: float):
        self.expired = False
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._timer = threading.Timer(seconds, self._expire)
        self._timer.daemon = True
        self._timer.start()

    def watch(self, create):
        # A duplicate of the raw socket still reaches the connection after
        # TLS wraps (and detaches) the original.
        def create_connection(*args, **kwargs):
            sock = create(*args, **kwargs)
            with self._lock:
                self._sock = sock.dup()
                if self.expired:
                    self._shutdown()
            return sock
        return create_connection

    def _expire(self):
        with self._lock:
            self.expired = True
            self._shutdown()

    def _shutdown(self):
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def close(self):
        self._timer.cancel()
        with self._lock:
            if self._sock is not None:
                self._sock.close()
                self._sock = None


def read_json(resp, limit: int = MAX_BODY):
    """Parse a response body of at most `limit` bytes; larger bodies are rejected unparsed."""
    length = resp.headers.get("Content-Length")
    if length is not None and length.strip().isdigit() and int(length) > limit:
        raise ResponseTooLarge(f"response is {int(length)} bytes, limit {limit}")
    body = resp.read(limit + 1)
    if len(body) > limit:
        raise ResponseTooLarge(f"response exceeds {limit} bytes")
    return loads(body)


def _connection(url: str, timeout: float):
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme == "https" and host:
        return http.client.HTTPSConnection(host, parts.port, timeout=timeout,
                                           context=ssl.create_default_context())
    if parts.scheme == "http" and host in LOOPBACK:
        return http.client.HTTPConnection(host, parts.port, timeout=timeout)
    raise ValueError(f"refusing to fetch {parts.scheme}://{host}")


def request_json(url: str, *, method: str = "GET", headers: Optional[Dict[str, str]] = None,
                 body: Optional[bytes] = None, timeout: float, limit: int = MAX_BODY):
    """One request that finishes, fails or is cut off within `timeout` seconds in total.

    Name resolution happens before the watchdog has a socket to close; it is
    bounded by the system resolver's own timeouts."""
    conn = _connection(url, timeout)
    parts = urllib.parse.urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    watchdog = _Watchdog(timeout)
    conn._create_connection = watchdog.watch(conn._create_connection)
    resp = None
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        if not 200 <= resp.status < 300:
            raise HTTPStatusError(resp.status)
        result = read_json(resp, limit)
    except (OSError, http.client.HTTPException, ValueError):
        if watchdog.expired:
            raise DeadlineExceeded(f"no complete response within {timeout:g} s") from None
        raise
    finally:
        watchdog.close()
        if resp is not None:
            resp.close()
        conn.close()
    if watchdog.expired:
        raise DeadlineExceeded(f"no complete response within {timeout:g} s")
    return result
