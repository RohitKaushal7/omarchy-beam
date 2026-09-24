"""Bounded reads of remote JSON: a response can never grow the helper's memory past MAX_BODY."""

from __future__ import annotations

import json

# The rate table is ~4 KB and a Jev answer for 255 options ~40 KB.
MAX_BODY = 256 * 1024


class ResponseTooLarge(ValueError):
    pass


def read_json(resp, limit: int = MAX_BODY):
    """Parse a response body of at most `limit` bytes; larger bodies are rejected unparsed."""
    length = resp.headers.get("Content-Length")
    if length is not None and length.strip().isdigit() and int(length) > limit:
        raise ResponseTooLarge(f"response is {int(length)} bytes, limit {limit}")
    body = resp.read(limit + 1)
    if len(body) > limit:
        raise ResponseTooLarge(f"response exceeds {limit} bytes")
    return json.loads(body)
