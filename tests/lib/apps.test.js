const test = require("node:test")
const assert = require("node:assert/strict")
const Apps = require("../../lib/apps.js")

test("desktop ids drop the .desktop suffix and whitespace", () => {
  assert.equal(Apps.normalizeDesktopId("  chromium.desktop "), "chromium")
  assert.equal(Apps.normalizeDesktopId("org.telegram.desktop"), "org.telegram")
  assert.equal(Apps.normalizeDesktopId(""), "")
})

test("hidden-id lists parse one id per line into a set", () => {
  assert.deepEqual(Apps.parseIdList("a.desktop\n\n  b \nc.desktop\n"), { a: true, b: true, c: true })
  assert.deepEqual(Apps.parseIdList(""), {})
})

test("visibleEntries skips noDisplay, hidden and nameless entries, sorted by name", () => {
  const values = [
    { id: "zed", name: "Zed" },
    { id: "btop", name: "btop", noDisplay: true },
    { id: "hidden-one", name: "Hidden" },
    { id: "chromium", name: "Chromium" },
    { id: "blank", name: "" },
    null
  ]
  const rows = Apps.visibleEntries(values, { "hidden-one": true })
  assert.deepEqual(rows.map(r => r.entry.id), ["chromium", "zed"])
})
