import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from helpers import BIN, make_ctx
from beam import currency, jev
from beam.protocol import Server


class Out(io.StringIO):
    def messages(self):
        return [json.loads(line) for line in self.getvalue().splitlines() if line]


class FakeJev:
    def __init__(self, pick=None, delay=0.0):
        self.pick_value, self.delay, self.calls = pick, delay, []

    def status(self):
        return "file"

    def cached(self, q, catalog):
        return False, None

    def pick(self, q, catalog):
        self.calls.append(q)
        time.sleep(self.delay)
        return self.pick_value, False


def server(jev_client=None, ctx=None, **kw):
    out = Out()
    tmp = tempfile.mkdtemp()
    s = Server(out, ctx or make_ctx(locale="en_US.UTF-8"), tmp, tmp, jev_client=jev_client or FakeJev(), **kw)
    return s, out


def wait_for(fn, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.01)
    return False


class Ops(unittest.TestCase):
    def test_answer(self):
        s, out = server()
        s.handle(json.dumps({"op": "answer", "id": 7, "q": "357/2"}))
        msg = out.messages()[-1]
        self.assertEqual((msg["op"], msg["id"], msg["answers"][0]["value"]), ("answer", 7, "178.5"))

    def test_answer_empty(self):
        s, out = server()
        s.handle(json.dumps({"op": "answer", "id": 1, "q": "chrome"}))
        self.assertEqual(out.messages()[-1]["answers"], [])

    def test_bad_messages(self):
        s, out = server()
        for line in ("not json", "{}", json.dumps({"op": "nope"}), "[1,2]"):
            s.handle(line)
        self.assertTrue(all(m["op"] == "error" for m in out.messages()))

    def test_config_applies_settings(self):
        s, out = server()
        s.handle(json.dumps({"op": "config", "settings": {"sources": {"calculator": False}}}))
        self.assertEqual(out.messages()[-1]["op"], "config")
        s.handle(json.dumps({"op": "answer", "id": 2, "q": "357/2"}))
        self.assertEqual(out.messages()[-1]["answers"], [])

    def test_used_sets_ans(self):
        s, out = server()
        s.handle(json.dumps({"op": "used", "copy": "178.5"}))
        s.handle(json.dumps({"op": "answer", "id": 3, "q": "ans*2"}))
        self.assertEqual(out.messages()[-1]["answers"][0]["value"], "357")

    def test_catalog(self):
        s, out = server()
        s.handle(json.dumps({"op": "catalog", "items": [{"key": "a", "label": "Nightlight", "path": ""}]}))
        self.assertEqual(out.messages()[-1]["count"], 1)


class Recent(unittest.TestCase):
    def test_recent_file(self):
        s, _ = server()
        for key in ("app:a", "action:b", "app:a"):
            s.handle(json.dumps({"op": "recent", "entry": {"key": key, "kind": key.split(":")[0], "label": key,
                                                            "junk": "x"}}))
        recent = json.load(open(s.recent_path))
        self.assertEqual([r["key"] for r in recent], ["app:a", "action:b"])
        self.assertNotIn("junk", recent[0])
        self.assertEqual(recent[0]["url"], "")

    def test_recent_capped(self):
        s, _ = server()
        for i in range(30):
            s.handle(json.dumps({"op": "recent", "entry": {"key": f"k{i}"}}))
        self.assertEqual(len(json.load(open(s.recent_path))), 20)


class JevOps(unittest.TestCase):
    def test_pick_reply(self):
        s, out = server(FakeJev(jev.Pick("trigger.toggle.nightlight", 0.9)))
        s.handle(json.dumps({"op": "jev", "id": 5, "q": "screen warmer"}))
        self.assertTrue(wait_for(lambda: any(m["op"] == "jev" for m in out.messages())))
        msg = [m for m in out.messages() if m["op"] == "jev"][0]
        self.assertEqual(msg["pick"], {"key": "trigger.toggle.nightlight", "p": 0.9})

    def test_stale_reply_dropped(self):
        fake = FakeJev(jev.Pick("a", 0.9), delay=0.1)
        s, out = server(fake)
        s.handle(json.dumps({"op": "jev", "id": 1, "q": "first"}))
        time.sleep(0.02)
        s.handle(json.dumps({"op": "jev", "id": 2, "q": "second"}))
        self.assertTrue(wait_for(lambda: any(m.get("id") == 2 for m in out.messages() if m["op"] == "jev")))
        time.sleep(0.15)
        ids = [m["id"] for m in out.messages() if m["op"] == "jev"]
        self.assertEqual(ids, [2])

    def test_disabled(self):
        s, out = server()
        s.handle(json.dumps({"op": "config", "settings": {"jev": {"enabled": False}}}))
        s.handle(json.dumps({"op": "jev", "id": 9, "q": "x"}))
        self.assertEqual(out.messages()[-1], {"op": "jev", "id": 9, "pick": None, "status": "off"})


class Rates(unittest.TestCase):
    def test_pending_answer_is_updated(self):
        gate = threading.Event()

        def fetch():
            gate.wait(2)
            return {"result": "success", "rates": {"USD": 1, "INR": 80}}

        ctx = make_ctx(locale="en_IN.UTF-8")
        ctx.rates = currency.RateStore(os.path.join(tempfile.mkdtemp(), "r.json"), fetch=fetch)
        s, out = server(ctx=ctx)
        s.handle(json.dumps({"op": "answer", "id": 4, "q": "100 usd in inr"}))
        self.assertTrue(out.messages()[-1]["answers"][0]["pending"])
        gate.set()
        self.assertTrue(wait_for(lambda: any(m.get("update") for m in out.messages())))
        update = [m for m in out.messages() if m.get("update")][0]
        self.assertEqual((update["id"], update["answers"][0]["value"]), (4, "₹8,000.00"))


class Idle(unittest.TestCase):
    def test_exits_after_idle(self):
        now = [0.0]
        exits = []
        s, _ = server(clock=lambda: now[0], exit_fn=exits.append)
        self.assertFalse(s.check_idle())
        now[0] = 10 * 60 + 1
        self.assertTrue(s.check_idle())
        self.assertEqual(exits, [0])


class EndToEnd(unittest.TestCase):
    def test_serve_latency_and_ordering(self):
        env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.mkdtemp(), "LANG": "en_US.UTF-8"}
        proc = subprocess.Popen([sys.executable, "-I", f"{BIN}/beam.py", "serve"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True, env=env, bufsize=1)
        try:
            self.assertEqual(json.loads(proc.stdout.readline())["op"], "ready")
            queries = ["357/2", "chrome", "5 ft in cm", "0xff", "firefox", "2^10"] * 34
            timings = []
            for i, q in enumerate(queries):
                start = time.perf_counter()
                proc.stdin.write(json.dumps({"op": "answer", "id": i, "q": q}) + "\n")
                proc.stdin.flush()
                msg = json.loads(proc.stdout.readline())
                timings.append((time.perf_counter() - start) * 1000)
                self.assertEqual(msg["id"], i)
            timings.sort()
            p95 = timings[int(len(timings) * 0.95)]
            self.assertLess(p95, 5.0, f"answer round trip p95 {p95:.2f} ms")
        finally:
            proc.stdin.close()
            proc.wait(5)


if __name__ == "__main__":
    unittest.main()
