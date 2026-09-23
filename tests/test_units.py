import unittest

from helpers import make_ctx
from beam import units

CTX = make_ctx(locale="en_US.UTF-8")

CLAIMED = [
    ("5 ft in cm", "152.4 cm"),
    ("5ft to cm", "152.4 cm"),
    ("5 feet in meters", "1.524 m"),
    ("10 km in miles", "6.213711922 mi"),
    ("1 mi to km", "1.609344 km"),
    ("5 in in cm", "12.7 cm"),
    ("12 cm in in", "4.724409449 in"),
    ("72f to c", "22.22222222°C"),
    ("72 °F in °C", "22.22222222°C"),
    ("100 c to f", "212°F"),
    ("0 celsius in kelvin", "273.15 K"),
    ("300 kelvin in c", "26.85°C"),
    ("3.2 GB in MiB", "3,051.757813 MiB"),
    ("1 GiB in MB", "1,073.741824 MB"),
    ("8 bits in bytes", "1 B"),
    ("100 km/h in mph", "62.13711922 mph"),
    ("60 mph to kmh", "96.56064 km/h"),
    ("2 kg in lb", "4.409245244 lb"),
    ("16 oz in g", "453.59237 g"),
    ("1 gallon in liters", "3.785411784 l"),
    ("1 acre in sqft", "43,560 ft²"),
    ("90 min in hours", "1.5 h"),
    ("1 day in minutes", "1,440 min"),
    ("180 deg in rad", "3.141592654 rad"),
    ("1 atm in psi", "14.69594878 psi"),
    ("1 kWh in kJ", "3,600 kJ"),
    ("1,500 m in km", "1.5 km"),
    ("5'11\" in cm", "180.34 cm"),
    ("5'11", "180.34 cm"),
    ("6 ft 2 in to m", "1.8796 m"),
]

DEFAULTS = [
    ("5 kg", ["11.02311311 lb"]),
    ("30 c", None),  # ambiguous single letter without a target
    ("20 °C", ["68°F"]),
    ("1536000 bytes", ["1,500 KiB"]),
    ("5 ft", ["1.524 m", "152.4 cm"]),
]

NOT_CLAIMED = [
    "", "chrome", "5", "5 apples", "5 kg in cm", "5 k", "72f", "10 x 3", "357/2",
    "100 usd in inr", "3pm ist in pst", "in 3 weeks", "5 m in", "abc ft in cm", "k" * 100,
]


class Units(unittest.TestCase):
    def test_claimed(self):
        for query, expected in CLAIMED:
            with self.subTest(query=query):
                got = units.parse(query, CTX)
                self.assertIsNotNone(got, query)
                self.assertEqual(got[0].value, expected)
                self.assertEqual(got[0].kind, "units")

    def test_defaults(self):
        for query, expected in DEFAULTS:
            with self.subTest(query=query):
                got = units.parse(query, CTX)
                if expected is None:
                    self.assertIsNone(got)
                else:
                    self.assertEqual([a.value for a in got], expected)

    def test_copy_and_detail(self):
        a = units.parse("5 ft in cm", CTX)[0]
        self.assertEqual(a.copy, "152.4")
        self.assertEqual(a.detail, "5 ft → cm")

    def test_not_claimed(self):
        for query in NOT_CLAIMED:
            with self.subTest(query=query[:20]):
                self.assertIsNone(units.parse(query, CTX))


if __name__ == "__main__":
    unittest.main()
