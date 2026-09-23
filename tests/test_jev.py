import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from helpers import read
from beam import jev


def items(n):
    return [{"key": f"k{i}", "label": f"Item {i}", "path": "Setup"} for i in range(n)]


def fake_post(picks, calls=None, tokens=100):
    """picks: text -> probability for any slice that contains it; rest goes to NONE."""
    def post(key, payload):
        if calls is not None:
            calls.append(payload)
        crit = payload["questions"]["target"]["criteria"]
        probs = {t: p for t, p in picks.items() if t in crit}
        probs[jev.NONE] = max(0.0, 1 - sum(probs.values()))
        return {"answers": {"target": {"choice": max(probs, key=probs.get), "probabilities": probs}},
                "usage": {"input_tokens": tokens}}
    return post


def client(post, tmp=None, **kw):
    tmp = tmp or tempfile.mkdtemp()
    return jev.JevClient(lambda: ("k", "file"), post=post, cache_path=os.path.join(tmp, "cache.json"),
                         usage_path=os.path.join(tmp, "usage.jsonl"), **kw)


class Catalogs(unittest.TestCase):
    def test_dedupe_and_hash(self):
        cat = jev.Catalog([{"key": "a", "label": "Nightlight", "path": "Trigger › Toggle"},
                           {"key": "b", "label": "Nightlight", "path": "Trigger › Toggle"},
                           {"key": "c", "label": ""}, "junk"])
        self.assertEqual(cat.texts, ["Nightlight — Trigger › Toggle"])
        self.assertEqual(cat.text_to_key["Nightlight — Trigger › Toggle"], "a")
        self.assertNotEqual(cat.hash, jev.Catalog(items(1)).hash)


class Picks(unittest.TestCase):
    def test_single_slice(self):
        calls = []
        c = client(fake_post({"Item 3 — Setup": 0.9}, calls))
        pick, cached = c.pick("Screen Warmer", jev.Catalog(items(10)))
        self.assertEqual((pick.key, cached), ("k3", False))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["state"], {"request": "screen warmer"})
        self.assertIn(jev.NONE, calls[0]["questions"]["target"]["criteria"])

    def test_below_threshold_is_none(self):
        c = client(fake_post({"Item 3 — Setup": 0.2}))
        self.assertEqual(c.pick("x y z", jev.Catalog(items(10))), (None, False))

    def test_slices_in_parallel_and_single_winner(self):
        calls = []
        c = client(fake_post({"Item 400 — Setup": 0.8}, calls))
        pick, _ = c.pick("thing", jev.Catalog(items(600)))
        self.assertEqual(pick.key, "k400")
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(len(p["questions"]["target"]["criteria"]) <= 255 for p in calls))

    def test_second_round_when_slices_disagree(self):
        calls = []
        c = client(fake_post({"Item 1 — Setup": 0.6, "Item 300 — Setup": 0.5}, calls))
        pick, _ = c.pick("thing", jev.Catalog(items(400)))
        self.assertEqual(len(calls), 3)
        final = calls[-1]["questions"]["target"]["criteria"]
        self.assertEqual(set(final), {"Item 1 — Setup", "Item 300 — Setup", jev.NONE})
        self.assertEqual(pick.key, "k1")

    def test_cache_hit_and_persistence(self):
        tmp = tempfile.mkdtemp()
        calls = []
        c = client(fake_post({"Item 3 — Setup": 0.9}, calls), tmp)
        cat = jev.Catalog(items(10))
        c.pick("warmer screen", cat)
        self.assertEqual(c.pick("  Warmer   Screen ", cat), (jev.Pick("k3", 0.9), True))
        self.assertEqual(len(calls), 1)
        again = client(fake_post({}, calls), tmp)
        self.assertEqual(again.pick("warmer screen", cat)[1], True)
        self.assertEqual(len(calls), 1)

    def test_misses_are_cached_too(self):
        calls = []
        c = client(fake_post({}, calls))
        cat = jev.Catalog(items(10))
        c.pick("nothing", cat)
        c.pick("nothing", cat)
        self.assertEqual(len(calls), 1)

    def test_catalog_change_invalidates(self):
        calls = []
        c = client(fake_post({"Item 3 — Setup": 0.9}, calls))
        c.pick("q", jev.Catalog(items(10)))
        c.pick("q", jev.Catalog(items(11)))
        self.assertEqual(len(calls), 2)

    def test_cache_size_bound(self):
        c = client(fake_post({}), cache_size=3)
        cat = jev.Catalog(items(5))
        for q in "abcde":
            c.pick(q, cat)
        self.assertEqual(len(c._cache), 3)

    def test_cache_size_can_change_at_runtime(self):
        c = client(fake_post({}), cache_size=10)
        cat = jev.Catalog(items(5))
        for q in "abcde":
            c.pick(q, cat)
        c.set_cache_size(2)
        self.assertEqual(len(c._cache), 2)
        c.set_cache_size(0)
        self.assertEqual(len(c._cache), 0)
        c.pick("f", cat)
        self.assertEqual(len(c._cache), 0)

    def test_zero_size_loads_nothing(self):
        tmp = tempfile.mkdtemp()
        full = client(fake_post({}), tmp, cache_size=10)
        for q in "abc":
            full.pick(q, jev.Catalog(items(5)))
        self.assertEqual(len(client(fake_post({}), tmp, cache_size=0)._cache), 0)

    def test_no_key(self):
        c = jev.JevClient(lambda: (None, "no-key"), post=fake_post({}))
        self.assertEqual(c.pick("q", jev.Catalog(items(3))), (None, False))
        self.assertEqual(c.status(), "no-key")

    def test_errors_return_none_and_log(self):
        def boom(key, payload):
            raise jev.JevError("HTTP 529")
        tmp = tempfile.mkdtemp()
        c = client(boom, tmp)
        self.assertEqual(c.pick("q", jev.Catalog(items(3))), (None, False))
        log = read(os.path.join(tmp, "usage.jsonl"))
        self.assertIn("HTTP 529", log)

    def test_auth_error_disables(self):
        def denied(key, payload):
            raise jev.AuthError("HTTP 401")
        c = client(denied)
        with self.assertRaises(jev.AuthError):
            c.pick("q", jev.Catalog(items(3)))
        self.assertEqual(c.status(), "auth-failed")
        self.assertEqual(c.pick("other", jev.Catalog(items(3))), (None, False))

    def test_usage_log_has_no_query_text(self):
        tmp = tempfile.mkdtemp()
        c = client(fake_post({"Item 3 — Setup": 0.9}), tmp)
        c.pick("my secret query", jev.Catalog(items(10)))
        log = read(os.path.join(tmp, "usage.jsonl"))
        self.assertNotIn("secret", log)
        self.assertIn('"tokens": 100', log)
        self.assertIn("1 API calls", jev.format_stats(os.path.join(tmp, "usage.jsonl")))


class MalformedResponses(unittest.TestCase):
    def test_pick_outside_the_options_is_no_pick(self):
        def post(key, payload):
            return {"answers": {"target": {"choice": "Not an option", "probabilities": {"Not an option": 0.9}}}}
        self.assertEqual(client(post).pick("q", jev.Catalog(items(3))), (None, False))

    def test_probabilities_not_a_dict_is_no_pick(self):
        def post(key, payload):
            return {"answers": {"target": {"choice": "Item 1 — Setup", "probabilities": ["x"]}}}
        self.assertEqual(client(post).pick("q", jev.Catalog(items(3))), (None, False))

    def test_http_protocol_errors_become_jev_errors(self):
        import http.client
        import unittest.mock
        with unittest.mock.patch("urllib.request.urlopen", side_effect=http.client.IncompleteRead(b"")):
            with self.assertRaises(jev.JevError):
                jev.http_post("k", {})


class ReadKey(unittest.TestCase):
    def test_env_then_file(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "key")
        old = os.environ.pop("TYPESAFE_API_KEY", None)
        try:
            self.assertEqual(jev.read_key(path), (None, "no-key"))
            with open(path, "w") as f:
                f.write("abc\n")
            self.assertEqual(jev.read_key(path), ("abc", "file"))
            os.environ["TYPESAFE_API_KEY"] = "envkey"
            self.assertEqual(jev.read_key(path), ("envkey", "env"))
        finally:
            os.environ.pop("TYPESAFE_API_KEY", None)
            if old is not None:
                os.environ["TYPESAFE_API_KEY"] = old


class Handler(BaseHTTPRequestHandler):
    status = 200

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Handler.seen = (self.headers["Authorization"], body)
        self.send_response(Handler.status)
        self.end_headers()
        if Handler.status == 200:
            self.wfile.write(json.dumps({"answers": {"target": {"choice": "A", "probabilities": {"A": 0.9}}},
                                         "usage": {"input_tokens": 7}}).encode())

    def log_message(self, *args):
        pass


class HttpPost(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.old_url = jev.API_URL
        jev.API_URL = f"http://127.0.0.1:{self.server.server_port}/v1/systemone"

    def tearDown(self):
        jev.API_URL = self.old_url
        self.server.shutdown()
        self.server.server_close()

    def test_success_and_auth_header(self):
        Handler.status = 200
        result = jev.http_post("secret", {"x": 1})
        self.assertEqual(result["usage"]["input_tokens"], 7)
        self.assertEqual(Handler.seen[0], "Bearer secret")

    def test_status_mapping(self):
        Handler.status = 401
        with self.assertRaises(jev.AuthError):
            jev.http_post("bad", {})
        Handler.status = 529
        with self.assertRaises(jev.JevError):
            jev.http_post("k", {})


if __name__ == "__main__":
    unittest.main()
