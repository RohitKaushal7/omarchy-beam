import io
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

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


if __name__ == "__main__":
    unittest.main()
