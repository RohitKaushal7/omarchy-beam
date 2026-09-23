import unittest
from decimal import Decimal

import helpers  # noqa: F401
from beam import fmt


class Plain(unittest.TestCase):
    def test_cases(self):
        cases = [
            (Decimal("178.5"), 10, "178.5"),
            (Decimal("100"), 10, "100"),
            (Decimal("0.1") + Decimal("0.2"), 10, "0.3"),
            (Decimal("2") / Decimal("3"), 10, "0.6666666667"),
            (Decimal("-0"), 10, "0"),
            (Decimal("123456789012345678"), 10, "1.23456789e+17"),
            (Decimal("0.0000001234"), 10, "1.234e-7"),
            (Decimal("999999999999999"), 10, "1e+15"),
            (1.5, 10, "1.5"),
        ]
        for value, digits, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(fmt.plain(value, digits), expected)


class Grouping(unittest.TestCase):
    def test_international(self):
        self.assertEqual(fmt.group("1234567.25", "international"), "1,234,567.25")
        self.assertEqual(fmt.group("-1234", "international"), "-1,234")
        self.assertEqual(fmt.group("999", "international"), "999")

    def test_indian(self):
        self.assertEqual(fmt.group("123456789.5", "indian"), "12,34,56,789.5")
        self.assertEqual(fmt.group("100000", "indian"), "1,00,000")
        self.assertEqual(fmt.group("1000", "indian"), "1,000")

    def test_sci_untouched(self):
        self.assertEqual(fmt.group("1.5e+20", "indian"), "1.5e+20")

    def test_display_decimals(self):
        self.assertEqual(fmt.display(Decimal("8352.4"), decimals=2, grouping="indian"), "8,352.40")

    def test_resolve(self):
        self.assertEqual(fmt.resolve_grouping("auto", "en_IN.UTF-8"), "indian")
        self.assertEqual(fmt.resolve_grouping("auto", "en_US.UTF-8"), "international")
        self.assertEqual(fmt.resolve_grouping("auto", "en_US.UTF-8", "INR"), "indian")
        self.assertEqual(fmt.resolve_grouping("auto", "en_IN.UTF-8", "EUR"), "international")
        self.assertEqual(fmt.resolve_grouping("international", "en_IN.UTF-8", "INR"), "international")

    def test_not_finite(self):
        with self.assertRaises(ValueError):
            fmt.plain(float("inf"))


class SettingsFromConfig(unittest.TestCase):
    def test_bad_types_fall_back(self):
        from beam.types import KINDS, Settings
        s = Settings.from_config({"sources": {"units": False, "currency": "yes"},
                                  "calc": {"significantDigits": "abc", "grouping": "weird", "homeCurrency": "eur"},
                                  "engine": {"idleExitMinutes": -5}})
        self.assertEqual(s.enabled, frozenset(k for k in KINDS if k != "units"))
        self.assertEqual(s.significant_digits, 10)
        self.assertEqual(s.grouping, "auto")
        self.assertEqual(s.home_currency, "EUR")
        self.assertEqual(s.idle_exit_minutes, 1)

    def test_none(self):
        from beam.types import Settings
        self.assertEqual(Settings.from_config(None), Settings())


if __name__ == "__main__":
    unittest.main()
