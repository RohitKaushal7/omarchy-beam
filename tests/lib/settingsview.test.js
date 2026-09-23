const test = require("node:test")
const assert = require("node:assert/strict")
const Settings = require("../../lib/settings.js")

const SECTIONS = [
  { title: "A", icon: "a", items: [{ path: "sources.apps", type: "bool", label: "Apps" },
                                   { path: "jev.debounceMs", type: "int", label: "Pause", from: 100, to: 2000, step: 50 }] },
  { title: "B", icon: "b", items: [{ path: "calc.grouping", type: "choice", label: "Grouping", options: ["auto", "indian", "international"] }] }
]

test("flattenSections puts a header before each section's fields", () => {
  const rows = Settings.flattenSections(SECTIONS)
  assert.deepEqual(rows.map(r => r.type), ["header", "bool", "int", "header", "choice"])
  assert.equal(rows[0].title, "A")
  assert.equal(rows[4].path, "calc.grouping")
})

test("nextField skips headers and wraps; page moves clamp", () => {
  const rows = Settings.flattenSections(SECTIONS)
  assert.equal(Settings.nextField(rows, -1, 1), 1)   // from nothing → first field
  assert.equal(Settings.nextField(rows, 1, 1), 2)
  assert.equal(Settings.nextField(rows, 2, 1), 4)    // over the header
  assert.equal(Settings.nextField(rows, 4, 1), 1)    // wraps
  assert.equal(Settings.nextField(rows, 1, -1), 4)   // wraps backwards
  assert.equal(Settings.nextField(rows, 1, 6), 4)    // page down clamps to last
  assert.equal(Settings.nextField(rows, 4, -6), 1)   // page up clamps to first
  assert.equal(Settings.nextField([{ type: "header" }], -1, 1), -1)
})

test("stepValue moves ints by step within bounds and cycles choices", () => {
  const int = SECTIONS[0].items[1]
  assert.equal(Settings.stepValue(int, 350, 1), 400)
  assert.equal(Settings.stepValue(int, 350, -1), 300)
  assert.equal(Settings.stepValue(int, 1990, 1), 2000)
  assert.equal(Settings.stepValue(int, 100, -1), 100)
  assert.equal(Settings.stepValue(int, 350, 10), 850)   // shift = 10 steps
  const choice = SECTIONS[1].items[0]
  assert.equal(Settings.stepValue(choice, "auto", 1), "indian")
  assert.equal(Settings.stepValue(choice, "international", 1), "auto")
  assert.equal(Settings.stepValue(choice, "auto", -1), "international")
  assert.equal(Settings.stepValue(choice, "weird", 1), "auto")
  assert.equal(Settings.stepValue(SECTIONS[0].items[0], true, 1), false)  // bool flips either way
})
