import io
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

import helpers  # noqa: F401  (puts bin/ on sys.path)
from beam import currency, jev, net


class FakeResponse(io.BytesIO):
    """A response body that records how many bytes were asked for."""

    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}
        self.requested = 0

    def read(self, size=-1):
        self.requested += size if size and size > 0 else len(self.getvalue())
        return super().read(size)


class ReadJson(unittest.TestCase):
    def test_small_body_parses(self):
        self.assertEqual(net.read_json(FakeResponse(b'{"a": 1}'), limit=64), {"a": 1})

    def test_body_at_the_limit_parses(self):
        body = b'{"a": "' + b"x" * 55 + b'"}'
        self.assertEqual(len(body), 64)
        self.assertEqual(net.read_json(FakeResponse(body), limit=64)["a"], "x" * 55)

    def test_oversized_body_rejected_after_bounded_read(self):
        resp = FakeResponse(b"[" + b"1," * 10_000 + b"1]")
        with self.assertRaises(net.ResponseTooLarge):
            net.read_json(resp, limit=64)
        self.assertLessEqual(resp.requested, 65)

    def test_oversized_content_length_rejected_before_reading(self):
        resp = FakeResponse(b"{}", headers={"Content-Length": "999999"})
        with self.assertRaises(net.ResponseTooLarge):
            net.read_json(resp, limit=64)
        self.assertEqual(resp.requested, 0)

    def test_non_finite_numbers_rejected(self):
        with self.assertRaises(ValueError):
            net.read_json(FakeResponse(b'{"rates": {"USD": 1, "X": Infinity}}'))

    def test_too_large_is_a_value_error(self):
        self.assertTrue(issubclass(net.ResponseTooLarge, ValueError))


class BigHandler(BaseHTTPRequestHandler):
    """Streams a body larger than the cap, without a Content-Length."""

    def _reply(self):
        if self.command == "POST":
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(b"[")
            for _ in range(net.MAX_BODY // 1024 + 8):
                self.wfile.write(b"1," * 512)
            self.wfile.write(b"1]")
        except OSError:
            pass  # the client stopped reading, as it should

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


class OversizedResponses(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), BigHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_rates_fetch_rejects_oversized_body(self):
        with self.assertRaises(net.ResponseTooLarge):
            currency.http_fetch(self.url + "/v6/latest/USD", timeout=5)

    def test_jev_post_rejects_oversized_body(self):
        old = jev.API_URL
        jev.API_URL = self.url + "/v1/systemone"
        try:
            with self.assertRaises(jev.JevError):
                jev.http_post("k", {}, timeout=5)
        finally:
            jev.API_URL = old


class DripHandler(BaseHTTPRequestHandler):
    """Keeps the connection alive with one byte at a time, never finishing.

    `stage` picks where it stalls: in the status line and headers, or in the body."""
    stage = "body"

    def _reply(self):
        if self.command == "POST":
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            if DripHandler.stage == "headers":
                self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
            else:
                self.send_response(200)
                self.send_header("Content-Length", "1000")
                self.end_headers()
                self.wfile.write(b"[")
            for _ in range(600):  # 60 s of drip, far past any deadline under test
                self.wfile.write(b"1")
                self.wfile.flush()
                time.sleep(0.1)
        except OSError:
            pass  # the client hung up, as it should

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


class Redirector(BaseHTTPRequestHandler):
    target = ""

    def _reply(self):
        if self.command == "POST":
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(302)
        self.send_header("Location", Redirector.target)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


class Recorder(BaseHTTPRequestHandler):
    seen = []

    def _reply(self):
        Recorder.seen.append(self.headers.get("Authorization"))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def within(seconds, fn):
    """Run fn in a thread; return (finished, elapsed, exception)."""
    box = {}

    def run():
        try:
            fn()
        except BaseException as e:  # noqa: BLE001 - the test inspects it
            box["error"] = e

    start = time.monotonic()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    return not t.is_alive(), time.monotonic() - start, box.get("error")


class TotalDeadline(unittest.TestCase):
    def setUp(self):
        self.server, self.url = serve(DripHandler)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def check(self, stage, call):
        DripHandler.stage = stage
        finished, elapsed, error = within(6, call)
        self.assertTrue(finished, f"still reading after 6 s ({stage} drip)")
        self.assertLess(elapsed, 2.5)
        self.assertIsNotNone(error)
        return error

    def test_slow_body_stops_at_the_deadline(self):
        error = self.check("body", lambda: net.request_json(self.url + "/x", timeout=1))
        self.assertIsInstance(error, net.DeadlineExceeded)

    def test_slow_headers_stop_at_the_deadline(self):
        error = self.check("headers", lambda: net.request_json(self.url + "/x", timeout=1))
        self.assertIsInstance(error, net.DeadlineExceeded)

    def test_rates_fetch_has_a_total_deadline(self):
        self.check("body", lambda: currency.http_fetch(self.url + "/v6/latest/USD", timeout=1))

    def test_jev_post_has_a_total_deadline(self):
        old = jev.API_URL
        jev.API_URL = self.url + "/v1/systemone"
        try:
            error = self.check("body", lambda: jev.http_post("k", {}, timeout=1))
            self.assertIsInstance(error, jev.JevError)
        finally:
            jev.API_URL = old


class Redirects(unittest.TestCase):
    def setUp(self):
        self.recorder, recorder_url = serve(Recorder)
        self.redirector, self.url = serve(Redirector)
        Redirector.target = recorder_url + "/elsewhere"
        Recorder.seen = []

    def tearDown(self):
        for server in (self.recorder, self.redirector):
            server.shutdown()
            server.server_close()

    def test_redirect_is_an_error_not_followed(self):
        with self.assertRaises(net.HTTPStatusError) as caught:
            net.request_json(self.url + "/x", headers={"Authorization": "Bearer secret"}, timeout=2)
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(Recorder.seen, [])

    def test_jev_key_never_follows_a_redirect(self):
        old = jev.API_URL
        jev.API_URL = self.url + "/v1/systemone"
        try:
            with self.assertRaises(jev.JevError):
                jev.http_post("secret", {}, timeout=2)
        finally:
            jev.API_URL = old
        self.assertEqual(Recorder.seen, [])


class Schemes(unittest.TestCase):
    def test_only_https_or_loopback_http(self):
        for url in ("http://example.com/x", "ftp://127.0.0.1/x", "file:///etc/passwd"):
            with self.assertRaises(ValueError, msg=url):
                net.request_json(url, timeout=1)

    def test_jev_endpoint_is_fixed(self):
        self.assertEqual(jev.API_URL, "https://api.typesafe.ai/v1/systemone")


if __name__ == "__main__":
    unittest.main()
