const test = require("node:test")
const assert = require("node:assert/strict")
const Edit = require("../../lib/edit.js")

const at = (text, cursor, anchor) => Edit.make(text, cursor, anchor)

test("make: caret at the end by default, clamped into the text", () => {
  assert.deepEqual(Edit.make("abc"), { text: "abc", cursor: 3, anchor: 3 })
  assert.deepEqual(Edit.make("abc", 9, -4), { text: "abc", cursor: 3, anchor: 0 })
  assert.deepEqual(Edit.make(""), { text: "", cursor: 0, anchor: 0 })
})

test("left and right move one character, never splitting an emoji", () => {
  assert.equal(Edit.move(at("abc", 3), "left").cursor, 2)
  assert.equal(Edit.move(at("abc", 0), "left").cursor, 0)
  assert.equal(Edit.move(at("abc", 3), "right").cursor, 3)
  const s = "a😀b"
  assert.equal(Edit.move(at(s, 3), "left").cursor, 1)
  assert.equal(Edit.move(at(s, 1), "right").cursor, 3)
})

test("without Shift a selection collapses to its near edge", () => {
  const sel = at("hello world", 9, 3)
  assert.deepEqual(Edit.move(sel, "left"), { text: "hello world", cursor: 3, anchor: 3 })
  assert.deepEqual(Edit.move(sel, "right"), { text: "hello world", cursor: 9, anchor: 9 })
  assert.deepEqual(Edit.move(sel, "home"), { text: "hello world", cursor: 0, anchor: 0 })
})

test("Shift keeps the anchor and grows or shrinks the selection", () => {
  let s = at("hello", 5)
  s = Edit.move(s, "left", true)
  s = Edit.move(s, "left", true)
  assert.deepEqual(s, { text: "hello", cursor: 3, anchor: 5 })
  assert.equal(Edit.selected(s), "lo")
  s = Edit.move(s, "right", true)
  assert.equal(Edit.selected(s), "o")
  s = Edit.move(s, "home", true)
  assert.equal(Edit.selected(s), "hello")
})

test("word moves skip spaces, then a run of non-spaces", () => {
  const t = "100 usd  in inr"
  assert.equal(Edit.wordBefore(t, t.length), 12)
  assert.equal(Edit.wordBefore(t, 12), 9)
  assert.equal(Edit.wordBefore(t, 9), 4)
  assert.equal(Edit.wordBefore(t, 2), 0)
  assert.equal(Edit.wordAfter(t, 0), 3)
  assert.equal(Edit.wordAfter(t, 3), 7)
  assert.equal(Edit.wordAfter(t, 7), 11)
  assert.equal(Edit.move(at(t, 7), "wordLeft").cursor, 4)
  assert.equal(Edit.move(at(t, 4), "wordRight").cursor, 7)
})

test("insert goes in at the caret, over a selection", () => {
  assert.deepEqual(Edit.insert(at("1200 usd", 2), "5"), { text: "12500 usd", cursor: 3, anchor: 3 })
  assert.deepEqual(Edit.insert(at("1200 usd", 4, 0), "99"), { text: "99 usd", cursor: 2, anchor: 2 })
  assert.deepEqual(Edit.insert(at("ab"), "cd"), { text: "abcd", cursor: 4, anchor: 4 })
})

test("Backspace and Delete: a character, a word, or the selection", () => {
  assert.deepEqual(Edit.deleteBack(at("12345", 3)), { text: "1245", cursor: 2, anchor: 2 })
  assert.deepEqual(Edit.deleteBack(at("12345", 0)), { text: "12345", cursor: 0, anchor: 0 })
  assert.deepEqual(Edit.deleteBack(at("a😀", 3)), { text: "a", cursor: 1, anchor: 1 })
  assert.deepEqual(Edit.deleteForward(at("12345", 3)), { text: "1235", cursor: 3, anchor: 3 })
  assert.deepEqual(Edit.deleteForward(at("12345", 5)), { text: "12345", cursor: 5, anchor: 5 })
  assert.deepEqual(Edit.deleteBack(at("hello wrold  ", 13), true), { text: "hello ", cursor: 6, anchor: 6 })
  assert.deepEqual(Edit.deleteBack(at("hello wrold", 8), true), { text: "hello old", cursor: 6, anchor: 6 })
  assert.deepEqual(Edit.deleteForward(at("go  far away", 2), true), { text: "go away", cursor: 2, anchor: 2 })
  assert.deepEqual(Edit.deleteBack(at("hello world", 5, 11)), { text: "hello", cursor: 5, anchor: 5 })
  assert.deepEqual(Edit.deleteForward(at("hello world", 0, 6)), { text: "world", cursor: 0, anchor: 0 })
})

test("Ctrl+Backspace at the end matches the old end-of-line edit", () => {
  for (const t of ["firefox", "open the  ", "357/2", "a b c", "  "]) {
    const old = t.replace(/\s+$/, "").replace(/\S+$/, "")
    assert.equal(Edit.deleteBack(at(t), true).text, old, JSON.stringify(t))
  }
})

test("Ctrl+U deletes before the caret, which clears the line at the end", () => {
  assert.equal(Edit.deleteToStart(at("reboot")).text, "")
  assert.deepEqual(Edit.deleteToStart(at("100 usd", 4)), { text: "usd", cursor: 0, anchor: 0 })
  assert.deepEqual(Edit.deleteToStart(at("abcdef", 1, 3)), { text: "def", cursor: 0, anchor: 0 })
})

test("select all, then typing or Backspace replaces everything", () => {
  const all = Edit.selectAll(at("firefox", 2))
  assert.deepEqual(all, { text: "firefox", cursor: 7, anchor: 0 })
  assert.equal(Edit.selected(all), "firefox")
  assert.deepEqual(Edit.deleteBack(all), { text: "", cursor: 0, anchor: 0 })
  assert.deepEqual(Edit.deleteForward(all), { text: "", cursor: 0, anchor: 0 })
  assert.deepEqual(Edit.insert(all, "z"), { text: "z", cursor: 1, anchor: 1 })
  assert.equal(Edit.selected(at("abc", 1)), "")
})

test("flatten: newline runs become one space; the caret keeps its place", () => {
  const s = at("ax\n  yb", 6)
  assert.deepEqual(Edit.flatten(s), { text: "ax yb", cursor: 4, anchor: 4 })
  assert.deepEqual(Edit.flatten(at("a\r\nb")), { text: "a b", cursor: 3, anchor: 3 })
  const same = at("plain", 2)
  assert.equal(Edit.flatten(same), same)
})

test("apply runs the edits lib/keys.js routes", () => {
  const s = at("abc", 1)
  assert.equal(Edit.apply(s, { edit: "left" }).cursor, 0)
  assert.deepEqual(Edit.apply(s, { edit: "end", extend: true }), { text: "abc", cursor: 3, anchor: 1 })
  assert.equal(Edit.apply(s, { edit: "backspace" }).text, "bc")
  assert.equal(Edit.apply(s, { edit: "delete" }).text, "ac")
  assert.equal(Edit.apply(s, { edit: "deleteToStart" }).text, "bc")
  assert.equal(Edit.apply(s, { edit: "selectAll" }).anchor, 0)
  assert.equal(Edit.apply(s, { edit: "insert", text: "Z" }).text, "aZbc")
  assert.equal(Edit.apply(s, { edit: "nonsense" }), s)
})
