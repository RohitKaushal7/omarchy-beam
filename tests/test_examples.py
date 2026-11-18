"""The settings view's examples (lib/examples.js) say what Beam answers; check
each engine line against the real helper so they stay true."""

import json
import os
import re
import unittest
from decimal import Decimal

from helpers import make_ctx
from beam.answer import answer
from beam.types import Settings
from test_currency import store_with

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_examples():
    with open(os.path.join(ROOT, "lib", "examples.js"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^var EXAMPLES = (\{.*?^\})$", text, re.S | re.M)
    if not m:
        raise AssertionError("lib/examples.js has no `var EXAMPLES = {…}` block")
    return json.loads(m.group(1))  # strict JSON, so this test and QML read the same data


EXAMPLES = load_examples()
ENGINE_SECTIONS = {path: s for path, s in EXAMPLES.items() if s.get("engine")}


def context(line):
    """Beam's defaults, an en_US locale (the helper's), and the line's own settings."""
    config = {"calc": {}}
    for group, values in (line.get("settings") or {}).items():
        config.setdefault(group, {}).update(values)
    ctx = make_ctx(locale=line.get("locale", "en_US.UTF-8"))
    ctx.settings = Settings.from_config(config)
    store = store_with()
    store.refresh_now()
    ctx.rates = store  # fixture rates: currency lines are `varies`, so only their shape is checked
    if "ans" in line:
        ctx.ans = Decimal(line["ans"])
    return ctx


def shown(line, answers):
    """What the line claims Beam shows: the copied value, or the answer rows joined."""
    if "copy" in line:
        return answers[0].copy
    rows = line.get("rows")
    picked = [answers[i] for i in rows] if rows else answers
    return " · ".join(a.value for a in picked)


class Examples(unittest.TestCase):
    def test_every_engine_line_is_what_beam_answers(self):
        count = 0
        for path, section in ENGINE_SECTIONS.items():
            for line in section["lines"]:
                count += 1
                with self.subTest(path=path, q=line["q"], note=line.get("note", "")):
                    got = answer(line["q"], context(line))
                    if line.get("none"):
                        self.assertEqual(got, [], "expected no answer row")
                        continue
                    self.assertTrue(got, "no answer")
                    self.assertEqual(got[0].kind, line.get("kind", section["engine"]))
                    value = shown(line, got)
                    if "copy" in line:
                        self.assertIn(line["copy"], line["a"], "`a` must show the copied value")
                        claimed = line["copy"]
                    else:
                        claimed = line["a"]
                    if line.get("varies"):
                        pattern = line.get("pattern")
                        self.assertTrue(pattern, "a `varies` line needs a `pattern`")
                        self.assertRegex(value, pattern)
                        self.assertRegex(claimed, pattern, "the representative result has the wrong shape")
                    else:
                        self.assertEqual(value, claimed)
        self.assertGreater(count, 50)

    def test_deterministic_lines_have_no_pattern(self):
        for path, section in EXAMPLES.items():
            for line in section["lines"]:
                with self.subTest(path=path, q=line["q"]):
                    if "pattern" in line and section.get("engine"):
                        self.assertIn("varies", line, "a fixed result needs no pattern; mark it `varies`")

    def test_lines_are_short_and_plain(self):
        for path, section in EXAMPLES.items():
            for line in section["lines"]:
                with self.subTest(path=path, q=line["q"]):
                    self.assertIsInstance(line["q"], str)
                    self.assertTrue(line["a"])
                    self.assertLessEqual(len(line["q"]) + len(line["a"]), 72)
                    self.assertNotIn("<", line["a"])  # shown as plain text, but keep it markup-free


if __name__ == "__main__":
    unittest.main()
