import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from helpers import make_ctx
from beam import devvals

CTX = make_ctx()


def values(q):
    got = devvals.parse(q, CTX)
    return None if got is None else [a.value for a in got]


class Bases(unittest.TestCase):
    def test_literals(self):
        self.assertEqual(values("0xff"), ["255", "0b11111111", "0o377"])
        self.assertEqual(values("0b1010"), ["10", "0xa", "0o12"])
        self.assertEqual(values("0o17"), ["15", "0xf", "0b1111"])

    def test_targets(self):
        self.assertEqual(values("255 in hex")[0], "0xff")
        self.assertEqual(values("255 to bin")[0], "0b11111111")
        self.assertEqual(values("255 as octal")[0], "0o377")
        self.assertEqual(values("0xff in bin")[0], "0b11111111")
        self.assertEqual(values("0b1010 in dec")[0], "10")

    def test_detail(self):
        self.assertEqual(devvals.parse("0xff", CTX)[0].detail, "0xff → decimal")


class Colors(unittest.TestCase):
    def test_hex(self):
        self.assertEqual(values("#ff8800"), ["rgb(255, 136, 0)", "hsl(32, 100%, 50%)"])
        self.assertEqual(values("#f80"), ["rgb(255, 136, 0)", "hsl(32, 100%, 50%)"])
        self.assertEqual(values("#ff880080")[0], "rgba(255, 136, 0, 0.5)")

    def test_rgb_hsl(self):
        self.assertEqual(values("rgb(255, 136, 0)"), ["#ff8800", "hsl(32, 100%, 50%)"])
        self.assertEqual(values("hsl(32, 100%, 50%)")[0], "#ff8800")

    def test_invalid(self):
        self.assertIsNone(values("rgb(300, 0, 0)"))
        self.assertIsNone(values("ff8800"))
        self.assertIsNone(values("#ggg"))


class Unix(unittest.TestCase):
    def test_seconds(self):
        got = devvals.parse("1700000000", CTX)
        self.assertEqual(got[0].value, "Wed, 15 Nov 2023 · 03:43:20 IST")
        self.assertEqual(got[0].copy, "2023-11-15T03:43:20+05:30")
        self.assertEqual(got[1].value, "2023-11-14T22:13:20Z")

    def test_millis(self):
        self.assertEqual(devvals.parse("1700000000000", CTX)[1].value, "2023-11-14T22:13:20Z")

    def test_now(self):
        expected = str(int(datetime(2026, 9, 23, 14, 30, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()))
        for q in ("now in unix", "unix now", "epoch", "timestamp", "unix"):
            with self.subTest(q=q):
                self.assertEqual(values(q), [expected])

    def test_phone_numbers_rejected(self):
        self.assertIsNone(values("9876543210"))
        self.assertIsNone(values("0123456789"))


class Bytes(unittest.TestCase):
    def test_human(self):
        self.assertEqual(values("1536000 bytes"), ["1.46 MiB", "1.54 MB"])
        self.assertEqual(values("1,048,576 b"), ["1 MiB", "1.05 MB"])

    def test_small_rejected(self):
        self.assertIsNone(values("512 bytes"))


class NotClaimed(unittest.TestCase):
    def test_plain_words_and_numbers(self):
        for q in ("", "chrome", "42", "2024", "357/2", "5 ft in cm", "0x", "hex", "#", "0xzz", "x" * 90):
            with self.subTest(q=q[:20]):
                self.assertIsNone(devvals.parse(q, CTX))


if __name__ == "__main__":
    unittest.main()
