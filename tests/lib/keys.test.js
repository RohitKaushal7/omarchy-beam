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
  assert.equal(Keys.route(press(KEY.Backspace), { text: "", chip: false, confirming: false }).op, "none")
})

test("Ctrl+C copies the selected text when the line has a selection, else the row", () => {
  assert.equal(Keys.route(press(KEY.C, MOD.Control), { text: "abc", selection: true }).op, "copyText")
  assert.equal(Keys.route(press(KEY.C, MOD.Control), { text: "abc", selection: false }).op, "copy")
  assert.equal(Keys.route(press(KEY.Insert, MOD.Control), { text: "abc", selection: true }).op, "copyText")
})

test("caret keys: arrows, words, Home/End, Shift to select", () => {
  const edit = (key, mods) => Keys.route(press(key, mods), typed)
  assert.deepEqual(edit(KEY.Left), { op: "edit", edit: "left", extend: false })
  assert.deepEqual(edit(KEY.Right, MOD.Shift), { op: "edit", edit: "right", extend: true })
  assert.deepEqual(edit(KEY.Left, MOD.Control), { op: "edit", edit: "wordLeft", extend: false })
  assert.deepEqual(edit(KEY.Right, MOD.Control | MOD.Shift), { op: "edit", edit: "wordRight", extend: true })
  assert.deepEqual(edit(KEY.Home), { op: "edit", edit: "home", extend: false })
  assert.deepEqual(edit(KEY.End, MOD.Shift), { op: "edit", edit: "end", extend: true })
})

test("deleting keys, Ctrl+U and Ctrl+A", () => {
  const edit = (key, mods) => Keys.route(press(key, mods), typed)
  assert.deepEqual(edit(KEY.Backspace), { op: "edit", edit: "backspace", word: false })
  assert.deepEqual(edit(KEY.Backspace, MOD.Shift), { op: "edit", edit: "backspace", word: false })
  assert.deepEqual(edit(KEY.Backspace, MOD.Control), { op: "edit", edit: "backspace", word: true })
  assert.deepEqual(edit(KEY.Delete), { op: "edit", edit: "delete", word: false })
  assert.deepEqual(edit(KEY.Delete, MOD.Control), { op: "edit", edit: "delete", word: true })
  assert.deepEqual(edit(KEY.Delete, MOD.Shift), { op: "edit", edit: "delete", word: false }, "not the input's cut")
  assert.deepEqual(edit(KEY.U, MOD.Control), { op: "edit", edit: "deleteToStart" })
  assert.deepEqual(edit(KEY.A, MOD.Control), { op: "edit", edit: "selectAll" })
  assert.equal(edit(KEY.U, MOD.Control | MOD.Shift).op, "none")
})

test("editing keys on an empty line do nothing", () => {
  const empty = { text: "", chip: false, confirming: false }
  for (const key of [KEY.Left, KEY.Right, KEY.Home, KEY.End, KEY.Delete, KEY.Backspace]) {
    assert.equal(Keys.route(press(key), empty).op, "none")
  }
  assert.equal(Keys.route(press(KEY.A, MOD.Control), empty).op, "none")
})

test("the text input's own shortcuts never see a key", () => {
  for (const [key, mods] of [[0x5a, MOD.Control], [0x58, MOD.Control], [0x4b, MOD.Control], [0x59, MOD.Control],
                             [KEY.Left, MOD.Alt], [KEY.Backspace, MOD.Alt], [0x41, MOD.Meta],
                             [KEY.Insert, 0], [KEY.Cut, 0], [KEY.F20, 0]]) {
    assert.equal(Keys.route(press(key, mods), typed).op, "none", key.toString(16))
  }
  assert.equal(Keys.route(press(KEY.Paste), typed).op, "paste")
  assert.equal(Keys.route(press(KEY.F18), typed).op, "paste")
  assert.equal(Keys.route(press(KEY.Copy), typed).op, "copy")
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
