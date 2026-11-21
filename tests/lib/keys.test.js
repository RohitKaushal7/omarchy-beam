const test = require("node:test")
const assert = require("node:assert/strict")
const Keys = require("../../lib/keys.js")

const { KEY, MOD } = Keys
const press = (key, modifiers, isAutoRepeat) => ({ key, modifiers: modifiers || 0, isAutoRepeat: !!isAutoRepeat })
const typed = { text: "reboot", chip: false, confirming: false }

test("Enter runs the selection; Shift+Enter pastes", () => {
  assert.deepEqual(Keys.route(press(KEY.Return), typed), { op: "enter", paste: false })
  assert.deepEqual(Keys.route(press(KEY.Enter), typed), { op: "enter", paste: false })
  assert.deepEqual(Keys.route(press(KEY.Return, MOD.Shift), typed), { op: "enter", paste: true })
})

test("a held Enter repeats nothing: it cannot confirm a risky action", () => {
  const confirming = { text: "reboot", chip: false, confirming: true }
  for (const key of [KEY.Return, KEY.Enter]) {
    for (const mods of [0, MOD.Shift]) {
      assert.deepEqual(Keys.route(press(key, mods, true), confirming), { op: "none" })
      assert.deepEqual(Keys.route(press(key, mods, true), typed), { op: "none" })
    }
  }
})

test("Esc clears a confirmation, then the text or chip, then closes", () => {
  assert.equal(Keys.route(press(KEY.Escape), { text: "x", chip: true, confirming: true }).op, "unconfirm")
  assert.equal(Keys.route(press(KEY.Escape), { text: "x", chip: false, confirming: false }).op, "clear")
  assert.equal(Keys.route(press(KEY.Escape), { text: "", chip: true, confirming: false }).op, "clear")
  assert.equal(Keys.route(press(KEY.Escape), { text: "", chip: false, confirming: false }).op, "dismiss")
})

test("shortcuts: settings, copy, bounded paste, Tab", () => {
  assert.equal(Keys.route(press(KEY.Comma, MOD.Control), typed).op, "settings")
  assert.equal(Keys.route(press(KEY.C, MOD.Control), typed).op, "copy")
  assert.equal(Keys.route(press(KEY.V, MOD.Control), typed).op, "paste")
  assert.equal(Keys.route(press(KEY.Insert, MOD.Shift), typed).op, "paste")
  assert.equal(Keys.route(press(KEY.Tab), typed).op, "tab")
  assert.equal(Keys.route(press(KEY.Backtab, MOD.Shift), typed).op, "none")
})

test("Backspace on an empty line drops the chip", () => {
  assert.equal(Keys.route(press(KEY.Backspace), { text: "", chip: true, confirming: false }).op, "unchip")
  assert.equal(Keys.route(press(KEY.Backspace), { text: "g", chip: true, confirming: false }).op, "edit")
})

test("arrows and pages move the selection", () => {
  assert.deepEqual(Keys.route(press(KEY.Up), typed), { op: "move", delta: -1 })
  assert.deepEqual(Keys.route(press(KEY.Down), typed), { op: "move", delta: 1 })
  assert.deepEqual(Keys.route(press(KEY.PageUp), typed), { op: "move", delta: -6 })
  assert.deepEqual(Keys.route(press(KEY.PageDown), typed), { op: "move", delta: 6 })
})

test("plain keys are left to the text input", () => {
  assert.equal(Keys.route(press(0x41), typed), null)
  assert.equal(Keys.route(press(0x20), typed), null)
})
