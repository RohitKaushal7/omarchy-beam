import subprocess
import sys
import time
import unittest

from helpers import BIN, make_ctx
from beam import answer as answer_mod
from beam.answer import answer
from beam.types import KINDS

CTX = make_ctx(locale="en_US.UTF-8")

ROUTING = [
    ("357/2", "calculator", "178.5"),
    ("5 ft in cm", "units", "152.4 cm"),
    ("0xff", "developer", "255"),
    ("#ff8800", "developer", "rgb(255, 136, 0)"),
    ("3pm ist in pst", "time", "02:30"),
    ("days until dec 25", "time", "93 days"),
    ("1536000 bytes", "developer", "1.46 MiB"),
    ("1700000000", "developer", "Wed, 15 Nov 2023 · 03:43:20 IST"),
]

NEVER = ["chrome", "firefox dev", "gg ai", "yt lofi beats", "screen warmer", "nightlight",
         "install docker", "github.com/omacom", "localhost:3000", "settings", "ask claude",
         "reboot", "beam settings", "", "   ", "e", "x"]

GARBAGE = ["🙂🙂", "½ + ¼", "٣ + ٤", "∞", "‮123", "1e999999", "9" * 400, "((((((((((1))))))))))",
           "2^99999", "10!!!!", "sqrt(" * 50, "---1", "%%%", "#" * 5, "0x" + "f" * 100, "۱۲۳"]


class Dispatch(unittest.TestCase):
    def test_routing(self):
        for q, kind, value in ROUTING:
            with self.subTest(q=q):
                got = answer(q, CTX)
                self.assertTrue(got, q)
                self.assertEqual((got[0].kind, got[0].value), (kind, value))

    def test_plain_text_never_claimed(self):
        for q in NEVER:
            with self.subTest(q=q):
                self.assertEqual(answer(q, CTX), [])

    def test_garbage_is_safe(self):
        for q in GARBAGE:
            with self.subTest(q=q[:20]):
                self.assertIsInstance(answer(q, CTX), list)

    def test_parser_failure_log_has_no_query_text(self):
        import contextlib
        import io
        import unittest.mock
        err = io.StringIO()
        with unittest.mock.patch.object(answer_mod, "PARSERS", [("calculator", lambda s, c: 1 / 0)]), \
                contextlib.redirect_stderr(err):
            self.assertEqual(answer_mod.answer("my secret 2+2", make_ctx()), [])
        self.assertIn("calculator", err.getvalue())
        self.assertNotIn("secret", err.getvalue())

    def test_long_input_rejected_fast(self):
        start = time.perf_counter()
        self.assertEqual(answer("1+" * 5000 + "1", CTX), [])
        self.assertLess(time.perf_counter() - start, 0.01)

    def test_disabled_sources(self):
        ctx = make_ctx(locale="en_US.UTF-8", enabled=frozenset(k for k in KINDS if k != "calculator"))
        self.assertEqual(answer("357/2", ctx), [])
        self.assertTrue(answer("5 ft in cm", ctx))

    def test_speed(self):
        queries = [q for q, _, _ in ROUTING] + NEVER
        start = time.perf_counter()
        rounds = 50
        for _ in range(rounds):
            for q in queries:
                answer(q, CTX)
        per_query_ms = (time.perf_counter() - start) / (rounds * len(queries)) * 1000
        self.assertLess(per_query_ms, 1.0)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", f"{BIN}/beam.py", *args],
                              capture_output=True, text=True, timeout=10)

    def test_selftest(self):
        r = self.run_cli("selftest")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_eval(self):
        r = self.run_cli("eval", "2+2")
        self.assertEqual(r.returncode, 0)
        self.assertIn('"value": "4"', r.stdout)
        self.assertEqual(self.run_cli("eval", "chrome").returncode, 1)

    def test_usage(self):
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli("version").stdout.strip(), "0.1.0")


if __name__ == "__main__":
    unittest.main()
