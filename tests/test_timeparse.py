import unittest

from helpers import make_ctx
from beam import timeparse

CTX = make_ctx()  # 2026-09-23 14:30 in Asia/Kolkata (a Wednesday)


def first(q):
    got = timeparse.parse(q, CTX)
    return None if got is None else got[0]


class Times(unittest.TestCase):
    def test_now_in(self):
        a = first("now in tokyo")
        self.assertEqual(a.value, "18:00 · Wed 23 Sep")
        self.assertEqual(a.copy, "18:00")
        self.assertEqual(a.detail, "now in Tokyo (UTC+9)")
        self.assertEqual(first("time in london").value, "10:00 · Wed 23 Sep")
        self.assertEqual(first("new york time").value, "05:00 · Wed 23 Sep")
        self.assertEqual(first("time in nyc").detail, "now in NYC (UTC-4)")

    def test_convert(self):
        self.assertEqual(first("3pm ist in pst").value, "02:30")
        self.assertEqual(first("3pm ist in pst").detail, "15:00 IST → PST (UTC-7)")
        self.assertEqual(first("9am pst to ist").value, "21:30")
        self.assertEqual(first("11pm ist in jst").value, "02:30 (next day)")
        self.assertEqual(first("10:30 utc in ist").value, "16:00")
        self.assertEqual(first("noon in london").value, "07:30")
        self.assertEqual(first("5pm in berlin").detail, "17:00 local → Berlin (UTC+2)")

    def test_time_rejects(self):
        for q in ("5 to 7", "13pm ist in pst", "3pm ist in narnia", "25:00 utc in ist", "now in"):
            with self.subTest(q=q):
                self.assertIsNone(timeparse.parse(q, CTX))


class Dates(unittest.TestCase):
    def test_until(self):
        a = first("days until dec 25")
        self.assertEqual(a.value, "93 days")
        self.assertEqual(a.copy, "93")
        self.assertEqual(a.detail, "until Fri, 25 Dec 2026 (13 weeks 2 days)")
        self.assertEqual(first("days until 1 jan").value, "100 days")
        self.assertEqual(first("days until jan 1").detail, "until Fri, 1 Jan 2027 (14 weeks 2 days)")
        self.assertEqual(first("days since 2026-01-01").value, "265 days")

    def test_shift(self):
        self.assertEqual(first("today + 90 days").value, "Tue, 22 Dec 2026")
        self.assertEqual(first("today + 90 days").copy, "2026-12-22")
        self.assertEqual(first("tomorrow + 2 weeks").value, "Thu, 8 Oct 2026")
        self.assertEqual(first("in 3 weeks").value, "Wed, 14 Oct 2026")
        self.assertEqual(first("2026-01-31 + 1 month").value, "Sat, 28 Feb 2026")
        self.assertEqual(first("today - 1 year").value, "Tue, 23 Sep 2025")

    def test_diff_and_weekday(self):
        self.assertEqual(first("2026-01-15 - 2025-06-01").value, "228 days")
        self.assertEqual(first("what day is 15 aug 2027").value, "Sunday")
        self.assertEqual(first("what day was jan 26 1950").value, "Thursday")

    def test_date_rejects(self):
        for q in ("days until never", "today + 5 apples", "30 feb - 1 jan", "chrome", "5 - 3", "2024",
                  "in 5 minutes"):
            with self.subTest(q=q):
                self.assertIsNone(timeparse.parse(q, CTX))


if __name__ == "__main__":
    unittest.main()
