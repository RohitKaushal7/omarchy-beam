"""Owner-only, size-bounded files for the helper's state and cache.

Writes go through a randomly named temp file (never a fixed `.tmp` that a
planted symlink could redirect) and are published with os.replace. Reads
accept only regular files and refuse anything over a byte limit, so a
swapped-in device or an oversized file cannot exhaust the helper.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from typing import Iterator, Optional, TextIO

MAX_FILE = 4 * 1024 * 1024


def log(message: str) -> None:
    """One diagnostic line on stderr (the shell log). Never include typed text;
    a closed stderr is ignored rather than raised from an error handler."""
    try:
        sys.stderr.write(f"beam: {message}\n")
        sys.stderr.flush()
    except (OSError, ValueError):
        pass


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name}")


def loads(text):
    """json.loads that refuses NaN and ±Infinity."""
    return json.loads(text, parse_constant=_reject_constant)


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path) or "."
    if not os.path.isdir(directory):
        os.makedirs(directory, mode=0o700, exist_ok=True)


def write_text(path: str, text: str) -> None:
    _ensure_dir(path)
    directory, name = os.path.split(path)
    fd, tmp = tempfile.mkstemp(dir=directory or ".", prefix=f".{name}.")  # 0600, O_EXCL
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json(path: str, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, allow_nan=False))


def read_text(path: str, limit: int = MAX_FILE) -> str:
    """The file's text, if it is a regular file of at most `limit` bytes."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"{path} is not a regular file")
        data = f.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path} is larger than {limit} bytes")
    return data.decode("utf-8")


def read_json(path: str, limit: int = MAX_FILE):
    return loads(read_text(path, limit))


def append_line(path: str, line: str, max_bytes: int) -> None:
    """Append one line; once the file passes max_bytes keep only its newest half."""
    _ensure_dir(path)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)  # also for a log an older version created with the umask
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")
        size = f.tell()
    if size <= max_bytes:
        return
    with open(path, "rb") as f:
        f.seek(max(0, size - max_bytes // 2))
        tail = f.read()
    cut = tail.find(b"\n") + 1 if size > max_bytes // 2 else 0
    write_text(path, tail[cut:].decode("utf-8", "replace"))


def bounded_lines(stream: TextIO, limit: int) -> Iterator[Optional[str]]:
    """Lines of at most `limit` characters; a longer line is consumed in
    pieces and reported once as None, never held in memory whole."""
    while True:
        line = stream.readline(limit + 1)
        if not line:
            return
        if line.endswith("\n") or len(line) <= limit:
            yield line
            continue
        while line and not line.endswith("\n"):
            line = stream.readline(limit + 1)
        yield None
