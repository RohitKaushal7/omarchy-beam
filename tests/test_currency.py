import json
import os
import tempfile
import time
import unittest

from helpers import make_ctx
from beam import currency

FIXTURE = {"result": "success", "time_last_update_unix": 1790000000,
           "rates": {"USD": 1, "INR": 83.524, "EUR": 0.92, "GBP": 0.79, "JPY": 150.2, "CHF": 0.88}}


def store_with(fetch=lambda: FIXTURE, clock=lambda: 1_790_000_000.0):
    path = os.path.join(tempfile.mkdtemp(), "rates.json")
    return currency.RateStore(path, 24, fetch=fetch, clock=clock)


def ctx_with(store, locale="en_IN.UTF-8", **settings):
    ctx = make_ctx(locale=locale, **settings)
    ctx.rates = store
    return ctx


class Parsing(unittest.TestCase):
    def setUp(self):
        self.store = store_with()
        self.assertTrue(self.store.refresh_now())
        self.ctx = ctx_with(self.store)

    def first(self, q):
        got = currency.parse(q, self.ctx)
        return None if got is None else got[0]

    def test_conversions(self):
        cases = [
            ("100 usd in inr", "₹8,352.40", "8352.40"),
            ("100 USD to INR", "₹8,352.40", "8352.40"),
            ("$100 in inr", "₹8,352.40", "8352.40"),
            ("$100", "₹8,352.40", "8352.40"),
            ("100 dollars", "₹8,352.40", "8352.40"),
            ("50 bucks in rupees", "₹4,176.20", "4176.20"),
            ("₹2400 to eur", "€26.44", "26.44"),
            ("rs 2400 in usd", "$28.73", "28.73"),
            ("₹2400", "$28.73", "28.73"),
            ("10k inr in usd", "$119.73", "119.73"),
            ("1 lakh inr in usd", "$1,197.26", "1197.26"),
            ("100 eur in jpy", "¥16,326", "16326"),
            ("100 usd in chf", "CHF 88.00", "88.00"),
            ("1,00,000 inr in usd", "$1,197.26", "1197.26"),
        ]
        for q, value, copy in cases:
            with self.subTest(q=q):
                a = self.first(q)
                self.assertIsNotNone(a, q)
                self.assertEqual((a.value, a.copy), (value, copy))

    def test_detail_has_age_and_attribution(self):
        self.assertEqual(self.first("100 usd in inr").detail,
                         "100 USD → INR · rates <1 h old · Rates By Exchange Rate API")

    def test_home_currency_setting(self):
        ctx = ctx_with(self.store, home_currency="EUR")
        self.assertEqual(currency.parse("$100", ctx)[0].value, "€92.00")

    def test_home_from_locale(self):
        self.assertEqual(currency.home_currency(ctx_with(self.store, locale="de_DE.UTF-8")), "EUR")
        self.assertEqual(currency.home_currency(ctx_with(self.store, locale="")), "USD")

    def test_not_claimed(self):
        for q in ("100", "chrome", "5 m in km", "100 apples in inr", "100 usd in apples", "100 usd in usd",
                  "5 ft in cm", "357/2", "$", "usd"):
            with self.subTest(q=q):
                self.assertIsNone(currency.parse(q, self.ctx))

    def test_no_store(self):
        ctx = make_ctx()
        self.assertIsNone(currency.parse("100 usd in inr", ctx))


class Store(unittest.TestCase):
    def test_pending_then_fetch(self):
        calls = []

        def fetch():
            calls.append(1)
            return FIXTURE

        store = store_with(fetch=fetch)
        ctx = ctx_with(store)
        a = currency.parse("100 usd in inr", ctx)[0]
        self.assertTrue(a.pending)
        self.assertEqual(a.value, "Fetching rates…")
        for _ in range(100):
            if store.rates():
                break
            time.sleep(0.01)
        self.assertEqual(currency.parse("100 usd in inr", ctx)[0].value, "₹8,352.40")
        self.assertEqual(len(calls), 1)

    def test_cache_persists(self):
        store = store_with()
        store.refresh_now()
        again = currency.RateStore(store.cache_path, 24, fetch=lambda: {}, clock=lambda: 1_790_000_000.0 + 7200)
        self.assertEqual(again.rates()["INR"], 83.524)
        self.assertFalse(again.stale())
        ctx = ctx_with(again)
        self.assertIn("rates 2 h old", currency.parse("1 usd in inr", ctx)[0].detail)

    def test_stale_uses_old_rates_with_date(self):
        store = store_with()
        store.refresh_now()
        old = currency.RateStore(store.cache_path, 24, fetch=lambda: {}, clock=lambda: 1_790_000_000.0 + 3 * 86400)
        self.assertTrue(old.stale())
        detail = currency.parse("1 usd in inr", ctx_with(old))[0].detail
        self.assertIn("rates from ", detail)

    def test_bad_payload_rejected(self):
        store = store_with(fetch=lambda: {"result": "error"})
        self.assertFalse(store.refresh_now())
        self.assertIsNone(store.rates())

    def test_fetch_exception(self):
        def boom():
            raise OSError("offline")
        store = store_with(fetch=boom)
        self.assertFalse(store.refresh_now())


if __name__ == "__main__":
    unittest.main()
