// Caret and selection editing for the search line, on plain states:
//   { text, cursor, anchor }
// cursor is where the caret is; anchor is the other end of the selection
// (equal to cursor when nothing is selected). Every function returns a new
// state and leaves its argument alone.
//
// Words are runs of non-space characters, as Ctrl+Backspace has always
// treated them in Omarchy's search lines.

function make(text, cursor, anchor) {
  var t = String(text || "")
  var c = clamp(cursor === undefined ? t.length : cursor, t)
  var a = clamp(anchor === undefined ? c : anchor, t)
  return { text: t, cursor: c, anchor: a }
}

function clamp(pos, text) {
  var n = Number(pos)
  if (!isFinite(n)) return text.length
  return Math.max(0, Math.min(text.length, Math.round(n)))
}

function hasSelection(s) { return s.cursor !== s.anchor }
function selectionStart(s) { return Math.min(s.cursor, s.anchor) }
function selectionEnd(s) { return Math.max(s.cursor, s.anchor) }
function selected(s) { return s.text.slice(selectionStart(s), selectionEnd(s)) }

function isHigh(code) { return code >= 0xd800 && code <= 0xdbff }
function isLow(code) { return code >= 0xdc00 && code <= 0xdfff }

// One character back or forward, never splitting a surrogate pair (emoji).
function charBefore(text, pos) {
  if (pos <= 0) return 0
  if (pos >= 2 && isLow(text.charCodeAt(pos - 1)) && isHigh(text.charCodeAt(pos - 2))) return pos - 2
  return pos - 1
}

function charAfter(text, pos) {
  if (pos >= text.length) return text.length
  if (pos + 1 < text.length && isHigh(text.charCodeAt(pos)) && isLow(text.charCodeAt(pos + 1))) return pos + 2
  return pos + 1
}

function isSpace(ch) { return /\s/.test(ch) }

// Start of the word before pos (skipping spaces first), and end of the word after it.
function wordBefore(text, pos) {
  var i = pos
  while (i > 0 && isSpace(text.charAt(i - 1))) i--
  while (i > 0 && !isSpace(text.charAt(i - 1))) i--
  return i
}

function wordAfter(text, pos) {
  var i = pos
  while (i < text.length && isSpace(text.charAt(i))) i++
  while (i < text.length && !isSpace(text.charAt(i))) i++
  return i
}

// how: left, right, wordLeft, wordRight, home, end. extend keeps the anchor,
// growing or shrinking the selection; without it a selection collapses,
// and plain Left/Right land on its near edge.
function move(s, how, extend) {
  var t = s.text
  var pos = s.cursor
  if (!extend && hasSelection(s) && (how === "left" || how === "right")) {
    pos = how === "left" ? selectionStart(s) : selectionEnd(s)
  } else if (how === "left") pos = charBefore(t, s.cursor)
  else if (how === "right") pos = charAfter(t, s.cursor)
  else if (how === "wordLeft") pos = wordBefore(t, s.cursor)
  else if (how === "wordRight") pos = wordAfter(t, s.cursor)
  else if (how === "home") pos = 0
  else if (how === "end") pos = t.length
  return { text: t, cursor: pos, anchor: extend ? s.anchor : pos }
}

function replaceRange(s, from, to, str) {
  var text = s.text.slice(0, from) + str + s.text.slice(to)
  var at = from + str.length
  return { text: text, cursor: at, anchor: at }
}

// Typed or pasted text goes in at the caret, over any selection.
function insert(s, str) {
  return replaceRange(s, selectionStart(s), selectionEnd(s), String(str || ""))
}

// Backspace (word: Ctrl+Backspace). A selection is deleted as a whole.
function deleteBack(s, word) {
  if (hasSelection(s)) return insert(s, "")
  var from = word ? wordBefore(s.text, s.cursor) : charBefore(s.text, s.cursor)
  return replaceRange(s, from, s.cursor, "")
}

// Delete (word: Ctrl+Delete).
function deleteForward(s, word) {
  if (hasSelection(s)) return insert(s, "")
  var to = word ? wordAfter(s.text, s.cursor) : charAfter(s.text, s.cursor)
  return replaceRange(s, s.cursor, to, "")
}

// Ctrl+U: everything before the caret (and the selection). At the end, as
// the caret is unless moved, that clears the line.
function deleteToStart(s) {
  return replaceRange(s, 0, selectionEnd(s), "")
}

// The caret goes to the end, as in a text field, with everything selected.
function selectAll(s) {
  return { text: s.text, cursor: s.text.length, anchor: 0 }
}

var NEWLINES = /\s*[\r\n]+\s*/g

// The line holds one line: newline runs (from an input-method commit) become
// one space, and the caret keeps its place in the text around them.
function flatten(s) {
  var text = s.text.replace(NEWLINES, " ")
  if (text === s.text) return s
  var map = function(pos) { return Math.min(text.length, s.text.slice(0, pos).replace(NEWLINES, " ").length) }
  return { text: text, cursor: map(s.cursor), anchor: map(s.anchor) }
}

// An edit as lib/keys.js routes it: { edit, extend, word, text }.
function apply(s, op) {
  switch (op.edit) {
  case "left": case "right": case "wordLeft": case "wordRight": case "home": case "end":
    return move(s, op.edit, !!op.extend)
  case "backspace": return deleteBack(s, !!op.word)
  case "delete": return deleteForward(s, !!op.word)
  case "deleteToStart": return deleteToStart(s)
  case "selectAll": return selectAll(s)
  case "insert": return insert(s, op.text)
  }
  return s
}

if (typeof module !== "undefined") {
  module.exports = {
    make: make, hasSelection: hasSelection, selectionStart: selectionStart, selectionEnd: selectionEnd,
    selected: selected, move: move, insert: insert, deleteBack: deleteBack, deleteForward: deleteForward,
    deleteToStart: deleteToStart, selectAll: selectAll, flatten: flatten, apply: apply,
    wordBefore: wordBefore, wordAfter: wordAfter
  }
}
