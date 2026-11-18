const test = require("node:test")
const assert = require("node:assert/strict")
const Precheck = require("../../lib/precheck.js")

test("likelyAnswer: sums, conversions, currency, colours and dates", () => {
  for (const q of ["357/2", "2(3+4)", "-5 + 3", "(1+2)*3", ".5 * 4", "5 ft in cm", "100 usd in inr", "$50",
                   "₹2400 to eur", "#ff8800", "0xff", "sqrt 2", "pi * 2", "ans * 2", "what % of 2400 is 432",
                   "days until dec 25", "now in tokyo", "today + 90 days", "in 3 weeks", "3pm ist in pst",
                   "what day is 15 aug 2027"]) {
    assert.ok(Precheck.likelyAnswer(q), q)
  }
})

test("likelyAnswer: names and words that only contain digits or answer words", () => {
  for (const q of ["", "   ", "firefox 2", "chrome", "minecraft", "pihole", "timer", "what's new",
                   "screen time", "nightlight", "x".repeat(300) + "1"]) {
    assert.ok(!Precheck.likelyAnswer(q), q)
  }
})
