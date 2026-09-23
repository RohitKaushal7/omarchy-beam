import unittest
from decimal import Decimal

from helpers import make_ctx
from beam import calc

CTX = make_ctx(locale="en_US.UTF-8")

# (query, expected display value)
CLAIMED = [
    ("357/2", "178.5"),
    ("357 / 2", "178.5"),
    ("2+2", "4"),
    ("0.1+0.2", "0.3"),
    ("2*3+4", "10"),
    ("2+3*4", "14"),
    ("(2+3)*4", "20"),
    ("2^10", "1,024"),
    ("2**10", "1,024"),
    ("-2^2", "-4"),
    ("2^3^2", "512"),
    ("10 x 3", "30"),
    ("10x3", "30"),
    ("10×3", "30"),
    ("10÷4", "2.5"),
    ("10 − 3", "7"),
    ("2(3+4)", "14"),
    ("(1+2)(3+4)", "21"),
    ("3pi", "9.424777961"),
    ("pi", "3.141592654"),
    ("sqrt(16)", "4"),
    ("sqrt 2", "1.414213562"),
    ("sin(0)", "0"),
    ("cos(0)", "1"),
    ("log(1000)", "3"),
    ("ln(e)", "1"),
    ("abs(-5)", "5"),
    ("round(2.567, 2)", "2.57"),
    ("floor(2.7)", "2"),
    ("ceil(2.1)", "3"),
    ("max(1, 200, 3)", "200"),
    ("min(4,2)", "2"),
    ("5!", "120"),
    ("1,20,000 * 2", "240,000"),
    ("120,000 / 4", "30,000"),
    ("1,234.5 + 1", "1,235.5"),
    ("50%", "0.5"),
    ("2400 + 18%", "2,832"),
    ("2400 - 10%", "2,160"),
    ("18% of 2400", "432"),
    ("18 % of 2,400", "432"),
    ("what % of 2400 is 432", "18%"),
    ("432 is what % of 2400", "18%"),
    ("10 mod 3", "1"),
    ("1e3 + 1", "1,001"),
    ("2/3", "0.6666666667"),
    ("sqrt(2", "1.414213562"),
    ("1/3*3", "1"),
    ("10^20", "1e+20"),
]

NOT_CLAIMED = [
    "", "   ", "chrome", "firefox dev", "gg ai", "e", "42", "2024", "-5", "hello 2",
    "1/0", "sqrt(-1)", "2 3", "1,2", "10 % 3", "ln(0)", "abc(2)", "x", "5x", "(", ")",
    "0^-1", "(-8)^0.5", "1001!", "ans + 1", "a" * 300, "2" + "+2" * 150,
]


class Claimed(unittest.TestCase):
    def test_values(self):
        for query, expected in CLAIMED:
            with self.subTest(query=query):
                got = calc.parse(query, CTX)
                self.assertIsNotNone(got, query)
                self.assertEqual(got[0].value, expected)
                self.assertEqual(got[0].kind, "calculator")

    def test_copy_is_ungrouped(self):
        self.assertEqual(calc.parse("1000*1000", CTX)[0].copy, "1000000")

    def test_detail(self):
        self.assertEqual(calc.parse("357/2", CTX)[0].detail, "357÷2")
        self.assertEqual(calc.parse("3 * 4", CTX)[0].detail, "3 × 4")
        self.assertEqual(calc.parse("18% of 2400", CTX)[0].detail, "18% of 2400")

    def test_indian_grouping(self):
        ctx = make_ctx(locale="en_IN.UTF-8")
        self.assertEqual(calc.parse("100000*10", ctx)[0].value, "10,00,000")

    def test_ans(self):
        ctx = make_ctx()
        ctx.ans = Decimal("178.5")
        self.assertEqual(calc.parse("ans * 2", ctx)[0].value, "357")


class NotClaimed(unittest.TestCase):
    def test_rejects(self):
        for query in NOT_CLAIMED:
            with self.subTest(query=query[:30]):
                self.assertIsNone(calc.parse(query, CTX))


if __name__ == "__main__":
    unittest.main()
